"""
decoder.py

Person 2's responsibility: the backend decoder for the PIF prototype.

Reconstructs the original ".txt" content from a ".pif" file produced
by the existing, finalized encoder (encoder.py). This module does not
depend on encoder.py - it only depends on utils.py (for the shared
whitespace token constants) and pif_writer.py (for the shared header
constants), so the same single source of truth is used on both sides
without creating an encoder<->decoder coupling.

Pipeline:
    .pif file
      -> read as UTF-8
      -> validate header (METHOD / UNIT / SOURCE_TYPE)
      -> split into Jāṭā groups (one per encoded line)
      -> parse each group into (A, B, is_internally_valid)
      -> reconstruct the original overlapping-pair sequence,
         detecting two distinct kinds of problems along the way:
           - a group whose own "A B | B A | A B" pattern doesn't
             hold ("corrupted group")
           - a group whose claimed "A" doesn't match the previous
             group's "B" ("overlap mismatch")
         Either problem marks the affected reconstructed position
         with the error marker ('*') and reports it - never guesses.
      -> write the reconstructed text to a .txt file

Scope (matches the current prototype exactly):
    - .pif input only, "METHOD: JATA" / "UNIT: CHARACTER" /
      "SOURCE_TYPE: TXT" only.
    - 1 Unicode code point = 1 basic unit (never a byte, bit, or
      grapheme cluster).
    - <SP> / <TAB> / <NL> are reversed back to " " / "\\t" / "\\n".
    - No error *correction*, no prediction, no encryption, no
      compression - a corrupted or disconnected unit is reported and
      marked, never guessed at.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from utils import SPACE_TOKEN, TAB_TOKEN, NEWLINE_TOKEN
from pif_writer import METHOD, UNIT, SOURCE_TYPE

# The error marker used for any reconstructed unit that cannot be
# trusted (a corrupted group, or a group that doesn't connect to the
# previous one). The prototype never guesses a "most likely" original
# character - it reports the problem and marks the position instead.
ERROR_MARKER = "*"

# Must mirror encoder.py's apply_jata_pattern() separators exactly:
#   f"{a} {b} | {b} {a} | {a} {b}"
GROUP_SEPARATOR = " | "
UNIT_SEPARATOR = " "


# --- Data structures ---------------------------------------------------------


@dataclass
class DecodeError:
    """
    One detected problem during decoding.

    Attributes:
        group_number: 1-indexed position of the offending Jāṭā group
            within the PIF's encoded body (matches "Jāṭā group N"
            language from the spec, not a raw file line number, so it
            stays stable regardless of header/blank-line formatting).
        text_position: 1-indexed position of the affected unit in the
            reconstructed output text.
        error_type: "corrupted_group" (the group's own A-B-BA-AB
            pattern doesn't hold) or "overlap_mismatch" (the group's
            claimed A doesn't match the previous group's B).
        expected: the expected value, when determinable. For a
            corrupted group this is the fully correct line implied by
            the group's own claimed A/B. For an overlap mismatch, this
            is the previously trusted unit.
        actual: the actual value found. For a corrupted group this is
            the raw encoded line as read from the PIF. For an overlap
            mismatch, this is the group's claimed A.
        message: a human-readable explanation.
    """

    group_number: int
    text_position: int
    error_type: str
    expected: Optional[str]
    actual: Optional[str]
    message: str


@dataclass
class DecodeResult:
    """
    The outcome of decode_pif_to_txt().

    Attributes:
        text: the fully reconstructed text (already written to
            output_path), with ERROR_MARKER ('*') at any position that
            could not be trusted.
        output_path: where the reconstructed .txt was written.
        errors: every DecodeError detected, in the order encountered.
            An empty list means a clean, fully verified reconstruction.
    """

    text: str
    output_path: str
    errors: List[DecodeError] = field(default_factory=list)

    @property
    def has_errors(self):
        return len(self.errors) > 0


# --- Validation ---------------------------------------------------------------


def validate_pif_extension(input_path):
    """
    Ensure the given path has a '.pif' extension, case-insensitively.

    Raises:
        ValueError: if the file does not have a '.pif' extension.
    """
    path = Path(input_path)
    if path.suffix.lower() != ".pif":
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. Only '.pif' files "
            f"are supported by this decoder."
        )


# --- Reading ---------------------------------------------------------------


def read_pif_file(input_path):
    """
    Read a .pif file as UTF-8 text.

    Args:
        input_path: path to the .pif file.

    Returns:
        str: the file's raw text content.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_header_line(line, expected_key):
    """
    Parse a single "KEY: value" header line and return its value.

    Raises:
        ValueError: if the line isn't in "KEY: value" form, or the key
            doesn't match `expected_key`.
    """
    if ":" not in line:
        raise ValueError(
            f"Invalid PIF header line: expected '{expected_key}: ...' "
            f"but found {line!r}."
        )
    key, _, value = line.partition(":")
    key = key.strip()
    value = value.strip()
    if key != expected_key:
        raise ValueError(
            f"Invalid PIF header: expected a '{expected_key}' field, "
            f"found '{key}'."
        )
    return value


def validate_pif_header(raw_text):
    """
    Validate the PIF header (METHOD / UNIT / SOURCE_TYPE) and return
    the encoded body as a list of non-blank lines, in order.

    Only the exact values this prototype produces are accepted:
        METHOD: JATA
        UNIT: CHARACTER
        SOURCE_TYPE: TXT

    Any number of blank lines between the header and the body (or
    between body lines) are tolerated and skipped - the prototype
    doesn't hard-code an exact blank-line count.

    Args:
        raw_text: the full raw content of the .pif file.

    Returns:
        list[str]: the non-blank encoded Jāṭā group lines, in order.

    Raises:
        ValueError: on a missing/malformed header, or an unsupported
            METHOD/UNIT/SOURCE_TYPE value. This is always a fatal,
            whole-file rejection - never a partial/marked decode.
    """
    lines = raw_text.splitlines()
    if len(lines) < 3:
        raise ValueError("Invalid PIF: missing or incomplete header.")

    method_value = _parse_header_line(lines[0], "METHOD")
    if method_value != METHOD:
        raise ValueError(
            f"Unsupported METHOD '{method_value}'. Only '{METHOD}' is "
            f"supported in this prototype."
        )

    unit_value = _parse_header_line(lines[1], "UNIT")
    if unit_value != UNIT:
        raise ValueError(
            f"Unsupported UNIT '{unit_value}'. Only '{UNIT}' is "
            f"supported in this prototype."
        )

    source_type_value = _parse_header_line(lines[2], "SOURCE_TYPE")
    if source_type_value != SOURCE_TYPE:
        raise ValueError(
            f"Unsupported SOURCE_TYPE '{source_type_value}'. Only "
            f"'{SOURCE_TYPE}' is supported in this prototype."
        )

    body_lines = [line for line in lines[3:] if line != ""]
    if not body_lines:
        raise ValueError(
            "Invalid PIF: no encoded Jāṭā groups found after the header."
        )
    return body_lines


# --- Parsing individual Jāṭā groups --------------------------------------------


def parse_jata_line(line):
    """
    Parse one encoded line into its claimed (A, B) pair and whether
    the full "A B | B A | A B" pattern actually holds.

    Deliberately does NOT use .strip() anywhere on the encoded units
    themselves - only the fixed, literal GROUP_SEPARATOR (' | ') and
    UNIT_SEPARATOR (' ') are split on, so meaningful whitespace tokens
    are never accidentally altered.

    Args:
        line: one non-blank line from the PIF body.

    Returns:
        tuple[str, str, bool, str]: (A, B, is_internally_valid,
        raw_line) - A and B are the claimed units from the first
        section, taken at face value even if the group turns out to
        be corrupted (matching the prototype's rule: a corrupted
        group's *claimed* A is still what a previous group's overlap
        check is compared against; only the group's own internal
        consistency is what's actually in doubt).

    Raises:
        ValueError: if the line is structurally malformed (not
            exactly 3 '|'-separated sections, or a section that isn't
            exactly 2 space-separated units). This is fatal - a
            malformed line is not the same thing as a "corrupted but
            well-formed" group, and cannot be decoded at all.
    """
    sections = line.split(GROUP_SEPARATOR)
    if len(sections) != 3:
        raise ValueError(
            f"Malformed Jāṭā group (expected exactly 3 sections "
            f"separated by ' | '): {line!r}"
        )

    parsed_sections = []
    for section in sections:
        parts = section.split(UNIT_SEPARATOR)
        if len(parts) != 2:
            raise ValueError(
                f"Malformed Jāṭā group section (expected exactly 2 "
                f"units separated by a single space): {section!r}"
            )
        parsed_sections.append(tuple(parts))

    (a1, b1), (b2, a2), (a3, b3) = parsed_sections
    is_valid = (a2 == a1 and b2 == b1 and a3 == a1 and b3 == b1)
    return a1, b1, is_valid, line


# --- Reconstruction -------------------------------------------------------------


def _detokenize(unit):
    """Reverse a single logical unit's whitespace token, if any."""
    if unit == SPACE_TOKEN:
        return " "
    if unit == TAB_TOKEN:
        return "\t"
    if unit == NEWLINE_TOKEN:
        return "\n"
    return unit


def _expected_line_for(a, b):
    """The fully correct encoded line implied by a claimed (a, b) pair."""
    return f"{a} {b} | {b} {a} | {a} {b}"


def reconstruct_text(parsed_groups):
    """
    Reconstruct the original text from a list of parsed Jāṭā groups,
    detecting and marking corrupted groups and overlap mismatches
    along the way rather than guessing.

    Rules (as agreed for this prototype):
        - First group, internally invalid: neither reconstructed unit
          can be trusted - both positions marked '*'.
        - Later group, internally invalid: the already-trusted prefix
          is kept; only the newly-contributed unit is marked '*'.
        - Later group, internally valid but its claimed A doesn't
          match the previous group's B ("overlap mismatch"): the new
          position is marked '*', but the group's own B is trusted as
          the new anchor going forward, so a single break doesn't
          cascade into flagging every following unit too
          ("resynchronization").
        - Otherwise: normal reconstruction, appending the group's B.

    Args:
        parsed_groups: list of (A, B, is_valid, raw_line) tuples, in
            order, as returned by parse_jata_line().

    Returns:
        tuple[str, list[DecodeError]]: the reconstructed text (with
        ERROR_MARKER at any untrustworthy position) and the list of
        detected errors, in order.
    """
    reconstructed_units = []
    errors = []
    trusted_anchor_raw = None  # raw (pre-detokenized) value of the
    # previously trusted "B", used only for overlap comparisons.

    for idx, (a1, b1, is_valid, raw_line) in enumerate(parsed_groups):
        group_number = idx + 1

        if idx == 0:
            if is_valid:
                reconstructed_units.append(_detokenize(a1))
                reconstructed_units.append(_detokenize(b1))
                trusted_anchor_raw = b1
            else:
                reconstructed_units.append(ERROR_MARKER)
                reconstructed_units.append(ERROR_MARKER)
                expected_line = _expected_line_for(a1, b1)
                for pos in (1, 2):
                    errors.append(
                        DecodeError(
                            group_number=group_number,
                            text_position=pos,
                            error_type="corrupted_group",
                            expected=expected_line,
                            actual=raw_line,
                            message=(
                                f"Group {group_number} (the first group) is "
                                f"internally inconsistent with the Jāṭā "
                                f"pattern; neither reconstructed unit can be "
                                f"trusted. Position {pos} marked as "
                                f"'{ERROR_MARKER}'."
                            ),
                        )
                    )
                trusted_anchor_raw = None
            continue

        overlap_mismatch = trusted_anchor_raw is not None and a1 != trusted_anchor_raw

        if overlap_mismatch and is_valid:
            reconstructed_units.append(ERROR_MARKER)
            pos = len(reconstructed_units)
            errors.append(
                DecodeError(
                    group_number=group_number,
                    text_position=pos,
                    error_type="overlap_mismatch",
                    expected=trusted_anchor_raw,
                    actual=a1,
                    message=(
                        f"Group {group_number}: expected this group to "
                        f"start with '{trusted_anchor_raw}' (the previous "
                        f"group's second unit) but found '{a1}'. Position "
                        f"{pos} marked as '{ERROR_MARKER}'; resuming from "
                        f"this group's own data."
                    ),
                )
            )
            trusted_anchor_raw = b1  # resynchronize

        elif overlap_mismatch and not is_valid:
            reconstructed_units.append(ERROR_MARKER)
            pos = len(reconstructed_units)
            expected_line = _expected_line_for(a1, b1)
            errors.append(
                DecodeError(
                    group_number=group_number,
                    text_position=pos,
                    error_type="corrupted_group",
                    expected=expected_line,
                    actual=raw_line,
                    message=(
                        f"Group {group_number} is both internally "
                        f"inconsistent and does not connect to the "
                        f"previous group. Position {pos} marked as "
                        f"'{ERROR_MARKER}'."
                    ),
                )
            )
            trusted_anchor_raw = None  # neither value can be trusted

        elif not is_valid:
            reconstructed_units.append(ERROR_MARKER)
            pos = len(reconstructed_units)
            expected_line = _expected_line_for(a1, b1)
            errors.append(
                DecodeError(
                    group_number=group_number,
                    text_position=pos,
                    error_type="corrupted_group",
                    expected=expected_line,
                    actual=raw_line,
                    message=(
                        f"Group {group_number} is internally inconsistent "
                        f"with the Jāṭā pattern. Position {pos} marked as "
                        f"'{ERROR_MARKER}'."
                    ),
                )
            )
            trusted_anchor_raw = None

        else:
            reconstructed_units.append(_detokenize(b1))
            trusted_anchor_raw = b1

    return "".join(reconstructed_units), errors


# --- Output -----------------------------------------------------------------


def write_txt_file(output_path, text):
    """Write the reconstructed text to a single .txt file, UTF-8 encoded."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)


# --- Main entry point ---------------------------------------------------------


def decode_pif_to_txt(input_path, output_path=None):
    """
    Decode a .pif file back into a .txt file.

    Args:
        input_path: path to the source .pif file.
        output_path: optional explicit output path for the .txt file.
            If not given, defaults to the same name/directory as the
            input, with a .txt extension (e.g. data.pif -> data.txt).

    Returns:
        DecodeResult: text, output_path, and any detected errors.

    Raises:
        ValueError: if the input is not a .pif file, the header is
            missing/invalid/unsupported, or any encoded line is
            structurally malformed. All of these are fatal - no
            output file is written. (A well-formed but *corrupted*
            group is different: it does not raise - it's reported in
            DecodeResult.errors and marked with '*' in the output.)
        FileNotFoundError: if the input file does not exist.
    """
    input_path = Path(input_path)

    validate_pif_extension(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    raw_text = read_pif_file(input_path)
    body_lines = validate_pif_header(raw_text)
    parsed_groups = [parse_jata_line(line) for line in body_lines]
    text, errors = reconstruct_text(parsed_groups)

    if output_path is None:
        output_path = input_path.with_suffix(".txt")
    else:
        output_path = Path(output_path)

    write_txt_file(output_path, text)

    return DecodeResult(text=text, output_path=str(output_path), errors=errors)


# --- Reporting ----------------------------------------------------------------


def format_error_report(result):
    """
    Render a DecodeResult as a human-readable report string, listing
    every detected error plus the final reconstructed output (with
    '*' markers visible in place).

    Args:
        result: a DecodeResult from decode_pif_to_txt().

    Returns:
        str: a multi-line, human-readable report.
    """
    lines = []
    if not result.errors:
        lines.append("No errors detected. Decoding completed successfully.")
    else:
        lines.append(f"{len(result.errors)} error(s) detected during decoding:")
        for err in result.errors:
            lines.append(
                f"- Group {err.group_number}, position {err.text_position} "
                f"[{err.error_type}]: expected={err.expected!r} "
                f"actual={err.actual!r} - {err.message}"
            )
    lines.append("")
    lines.append("Reconstructed output:")
    lines.append(result.text)
    return "\n".join(lines)
