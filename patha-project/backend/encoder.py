"""
encoder.py

Person 1's responsibility: the backend encoder for the PIF prototype.

Pipeline:
    .txt file
      -> read text (UTF-8, universal newlines)
      -> validate no reserved tokens present in the raw text
      -> convert to logical units (one code point per unit; space/tab/
         newline become <SP>/<TAB>/<NL> tokens)
      -> generate overlapping pairs (sliding window, size 2, step 1)
      -> apply the Jāṭā-inspired pattern (A B -> A B | B A | A B)
      -> hand off to pif_writer to build + save the .pif file

This module only produces the .pif file. It does NOT decode, verify,
reconstruct, or check anything - that is Person 2's responsibility.

Written as plain, reusable functions (no CLI-only logic) so Person 3's
interface layer can import and call `encode_txt_to_pif` directly.
"""

from pathlib import Path

from utils import (
    validate_txt_extension,
    validate_no_reserved_tokens,
    text_to_units,
    validate_minimum_length,
)
from pif_writer import build_pif_content, write_pif_file


def read_txt_file(input_path):
    """
    Read a .txt file as UTF-8 text.

    Python's default text-mode reading performs universal newline
    translation, so '\\r\\n' and '\\r' are normalized to '\\n' before we
    ever see the string. This keeps newline counting consistent
    regardless of the file's origin platform.

    Args:
        input_path: path to the .txt file.

    Returns:
        str: the file's text content.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        return f.read()


def generate_overlapping_pairs(units):
    """
    Generate overlapping adjacent pairs from a list of units using a
    sliding window of size 2, step 1.

    Example:
        [A, B, C, D, E] -> [(A, B), (B, C), (C, D), (D, E)]

    Args:
        units: list of character units.

    Returns:
        list[tuple]: overlapping (prev, next) pairs.
    """
    return [(units[i], units[i + 1]) for i in range(len(units) - 1)]


def apply_jata_pattern(pair):
    """
    Apply the simplified, prototype Jāṭā-inspired pattern to a single
    pair (A, B):

        A B  ->  A B | B A | A B

    Args:
        pair: a (A, B) tuple of two units.

    Returns:
        str: the formatted pattern line, e.g. "A B | B A | A B".

    Note: this is a simplified computational pattern for the prototype
    only. It is not presented as a reproduction of the complete
    traditional Jāṭā-pāṭha recitation sequence.
    """
    a, b = pair
    return f"{a} {b} | {b} {a} | {a} {b}"


def encode_txt_to_pif(input_path, output_path=None):
    """
    Encode a .txt file into a .pif file.

    Args:
        input_path: path to the source .txt file.
        output_path: optional explicit output path for the .pif file.
            If not given, defaults to the same name/directory as the
            input, with a .pif extension (e.g. data.txt -> data.pif).

    Returns:
        str: path to the generated .pif file.

    Raises:
        ValueError: if the input file is not a .txt file, contains a
            reserved token ('<SP>', '<TAB>', '<NL>') as literal text,
            or contains fewer than 2 logical units.
        FileNotFoundError: if the input file does not exist.
    """
    input_path = Path(input_path)

    validate_txt_extension(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    text = read_txt_file(input_path)
    validate_no_reserved_tokens(text)
    units = text_to_units(text)
    validate_minimum_length(units)

    pairs = generate_overlapping_pairs(units)
    encoded_lines = [apply_jata_pattern(pair) for pair in pairs]

    pif_content = build_pif_content(encoded_lines)

    if output_path is None:
        output_path = input_path.with_suffix(".pif")
    else:
        output_path = Path(output_path)

    write_pif_file(output_path, pif_content)

    return str(output_path)
