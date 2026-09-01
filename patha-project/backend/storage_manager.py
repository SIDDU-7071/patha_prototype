"""
storage_manager.py

File-lifecycle / storage layer for the PIF prototype backend.

This module does NOT contain any Jāṭā/encoding logic of its own. It
only manages where uploaded ".txt" files and generated ".pif" files
live on disk, for how long, and how they're cleaned up. All actual
encoding is delegated to the existing, finalized `encoder.py`
(`encode_txt_to_pif`), which is used exactly as-is and unmodified.

Responsibilities:
    - Accept an upload as either a local file path OR raw bytes +
      an original filename.
    - Save the upload into storage/temporary/ under a collision-safe
      name (so two uploads named "data.txt" never clash).
    - Call the existing encoder to produce a .pif into
      storage/generated/.
    - Hand the generated .pif back to the caller for "download"
      (reading its bytes) without deleting it prematurely.
    - Delete both the temporary .txt and the generated .pif once the
      caller confirms delivery is complete.
    - Clean up automatically if encoding fails partway through.
    - Provide a plain, callable (non-scheduled) sweep for abandoned
      files older than a configurable age.

This module intentionally exposes plain Python functions only - no
web framework, no routes. A future API/UI layer (Person 3's work)
is expected to import and call these directly.

Storage layout (created relative to this file, so behavior does not
depend on the current working directory):

    backend/
        storage/
            temporary/   <- uploaded .txt files, briefly
            generated/   <- generated .pif files, briefly
"""

import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from encoder import encode_txt_to_pif
from utils import validate_txt_extension

# --- Storage locations -----------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parent
STORAGE_ROOT = BACKEND_DIR / "storage"
TEMPORARY_DIR = STORAGE_ROOT / "temporary"
GENERATED_DIR = STORAGE_ROOT / "generated"

# --- Configurable limits ----------------------------------------------------

# 10 MB default upload size limit. A prototype-level safety net, not a
# core functional requirement. Easy to change by editing this constant
# (or by passing max_size_bytes explicitly to save_uploaded_file()).
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024

# Default "abandoned file" age threshold for cleanup_stale_files().
# Files older than this in storage/temporary/ or storage/generated/
# are considered abandoned (e.g. the browser was closed mid-download)
# and are safe to remove.
DEFAULT_STALE_AGE_SECONDS = 60 * 60  # 1 hour


def ensure_storage_dirs():
    """
    Create storage/temporary/ and storage/generated/ if they don't
    already exist. Safe to call repeatedly.
    """
    TEMPORARY_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)


ensure_storage_dirs()


# --- Operation record --------------------------------------------------------


@dataclass
class PifOperation:
    """
    Tracks one upload-encode-download lifecycle end to end.

    Attributes:
        operation_id: unique id for this operation (collision-safe
            filename prefix).
        original_filename: sanitized, path-stripped filename as
            uploaded (e.g. "data.txt").
        temp_path: where the uploaded .txt currently lives in
            storage/temporary/, or None once cleaned up.
        generated_path: where the generated .pif currently lives in
            storage/generated/, or None before generation / after
            cleanup.
        download_filename: the filename to present to the user for
            the generated PIF (e.g. "data.pif") - deliberately does
            NOT include the internal operation_id prefix.
    """

    operation_id: str
    original_filename: str
    temp_path: Optional[Path] = None
    generated_path: Optional[Path] = None
    download_filename: Optional[str] = None


# --- Internal helpers ---------------------------------------------------------


def _sanitize_filename(filename):
    """
    Reduce a filename to a safe basename, stripping any directory
    components regardless of whether they use '/' or '\\' separators.
    This is the path-traversal defense: whatever the caller passes in
    (including something like "../../etc/passwd.txt"), only the final
    path segment is ever used to build a storage path.

    Raises:
        ValueError: if the resulting name is empty or is just "." / "..".
    """
    name = str(filename).replace("\\", "/").split("/")[-1].strip()
    if not name or name in (".", ".."):
        raise ValueError("Invalid or missing filename.")
    return name


def _delete_if_exists(path):
    """
    Delete a file if it exists. Silently does nothing if path is None,
    or the file is already gone - cleanup must be safe to call more
    than once (idempotent) since we can't guarantee it's only ever
    invoked exactly one time.
    """
    if path is None:
        return
    p = Path(path)
    try:
        if p.exists():
            p.unlink()
    except OSError:
        # Already removed by a concurrent cleanup, or a transient
        # filesystem issue - either way, cleanup should not crash the
        # caller's flow over a file that's already going/gone.
        pass


# --- Upload handling ----------------------------------------------------------


def save_uploaded_file(source, original_filename=None, max_size_bytes=None):
    """
    Save an uploaded .txt file into storage/temporary/ under a unique,
    collision-safe name. Does not encode anything yet.

    Args:
        source: either
            - a local file path (str or Path) to an existing .txt
              file, or
            - raw file content as bytes/bytearray.
        original_filename: the filename to associate with this
            upload. Required when `source` is bytes. Optional when
            `source` is a path (defaults to that path's basename).
        max_size_bytes: override the default MAX_UPLOAD_SIZE_BYTES
            limit for this call.

    Returns:
        PifOperation: with operation_id, original_filename, and
        temp_path populated (generated_path/download_filename not
        yet set).

    Raises:
        ValueError: invalid/missing filename, wrong extension, or the
            file exceeds the size limit. No temporary file is written
            in any of these cases.
        FileNotFoundError: `source` is a path that does not exist.
    """
    limit = MAX_UPLOAD_SIZE_BYTES if max_size_bytes is None else max_size_bytes

    if isinstance(source, (bytes, bytearray)):
        if not original_filename:
            raise ValueError(
                "original_filename is required when source is raw bytes."
            )
        content = bytes(source)
        size = len(content)
        raw_filename = original_filename
        source_path = None
    else:
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Input file not found: {source_path}")
        raw_filename = original_filename if original_filename else source_path.name
        size = source_path.stat().st_size
        content = None

    safe_name = _sanitize_filename(raw_filename)

    # Reuse the existing, unmodified extension validator so the rule
    # ("only .txt, case-insensitive") is defined in exactly one place.
    validate_txt_extension(safe_name)

    if size > limit:
        raise ValueError(
            f"Uploaded file exceeds the maximum allowed size of "
            f"{limit // (1024 * 1024)} MB."
        )

    ensure_storage_dirs()
    operation_id = uuid.uuid4().hex
    temp_path = TEMPORARY_DIR / f"{operation_id}_{safe_name}"

    if content is not None:
        temp_path.write_bytes(content)
    else:
        shutil.copyfile(source_path, temp_path)

    return PifOperation(
        operation_id=operation_id,
        original_filename=safe_name,
        temp_path=temp_path,
    )


# --- Encoding (delegates to the existing encoder) ------------------------------


def encode_uploaded_file(operation):
    """
    Run the existing, unmodified encoder against an already-saved
    upload, producing a .pif file in storage/generated/.

    This function does not reimplement any encoding logic - it only
    decides *where* the .pif goes and cleans up on failure. The
    Unicode handling, tokenization, overlapping-pair generation, and
    Jāṭā pattern all remain entirely inside encoder.py, untouched.

    Args:
        operation: a PifOperation from save_uploaded_file(), with
            temp_path already set.

    Returns:
        PifOperation: the same object, with generated_path and
        download_filename now populated.

    Raises:
        Whatever encode_txt_to_pif() raises (ValueError for bad
        extension / reserved tokens / too-short input; FileNotFoundError
        if the temp file is somehow missing). On any such failure, both
        the temporary .txt and any partially-created .pif are removed
        before the exception is re-raised, so failures never leave
        stray files behind.
    """
    stem = Path(operation.original_filename).stem
    download_filename = f"{stem}.pif"
    generated_path = GENERATED_DIR / f"{operation.operation_id}_{download_filename}"

    try:
        encode_txt_to_pif(str(operation.temp_path), str(generated_path))
    except Exception:
        _delete_if_exists(operation.temp_path)
        _delete_if_exists(generated_path)
        raise

    operation.generated_path = generated_path
    operation.download_filename = download_filename
    return operation


def handle_upload(source, original_filename=None, max_size_bytes=None):
    """
    Convenience wrapper for the full upload -> encode flow:

        save_uploaded_file() -> encode_uploaded_file()

    See those two functions for details and error behavior.

    Returns:
        PifOperation: fully populated (temp_path, generated_path,
        download_filename all set) and ready for prepare_download().
    """
    operation = save_uploaded_file(
        source, original_filename=original_filename, max_size_bytes=max_size_bytes
    )
    return encode_uploaded_file(operation)


# --- Download / delivery -------------------------------------------------------


def prepare_download(operation):
    """
    Read the generated PIF's content so it can be handed to the
    caller/frontend. Does NOT delete anything - deletion only happens
    once the caller confirms delivery via finalize_download(), so a
    failed/interrupted download never loses the file it was trying to
    send.

    Args:
        operation: a PifOperation with generated_path set (i.e. one
            that has already been through encode_uploaded_file() /
            handle_upload()).

    Returns:
        tuple[bytes, str]: (pif_file_content, download_filename)

    Raises:
        FileNotFoundError: if the generated PIF is missing (e.g. it
            was already downloaded and cleaned up, or storage was
            swept by cleanup_stale_files()). The message intentionally
            does not include the internal storage path.
    """
    if operation.generated_path is None or not Path(operation.generated_path).exists():
        raise FileNotFoundError(
            "The requested PIF file is not available. It may have "
            "already been downloaded, or the operation has expired."
        )
    content = Path(operation.generated_path).read_bytes()
    return content, operation.download_filename


def finalize_download(operation):
    """
    Confirm that delivery is complete and remove the backend's copies
    of both the temporary .txt and the generated .pif for this
    operation. Safe to call even if one or both files are already
    gone (idempotent).

    After this call, storage/temporary/ and storage/generated/ contain
    no files belonging to this operation - the user's downloaded copy
    of the .pif (already sent) is theirs to keep; nothing is retained
    server-side.
    """
    _delete_if_exists(operation.temp_path)
    _delete_if_exists(operation.generated_path)
    operation.temp_path = None
    operation.generated_path = None


# --- Stale-file safety net -----------------------------------------------------


def cleanup_stale_files(max_age_seconds=DEFAULT_STALE_AGE_SECONDS):
    """
    Remove files from storage/temporary/ and storage/generated/ that
    are older than `max_age_seconds`. This is a plain, callable
    function - not a background thread or scheduler. It's meant to be
    invoked periodically by whatever wraps this backend later (a cron
    job, a manual admin action, a request-triggered check, etc.), as a
    safety net for uploads that were never completed or downloaded
    (closed browser, dropped connection, crashed frontend, etc.).

    Args:
        max_age_seconds: files with a modification time older than
            this many seconds are deleted. Defaults to
            DEFAULT_STALE_AGE_SECONDS (1 hour).

    Returns:
        list[str]: paths of files that were deleted.
    """
    deleted = []
    now = time.time()
    for directory in (TEMPORARY_DIR, GENERATED_DIR):
        if not directory.exists():
            continue
        for entry in directory.iterdir():
            if not entry.is_file():
                continue
            age_seconds = now - entry.stat().st_mtime
            if age_seconds > max_age_seconds:
                try:
                    entry.unlink()
                    deleted.append(str(entry))
                except OSError:
                    pass
    return deleted
