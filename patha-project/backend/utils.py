"""
utils.py

Utility functions for the Pāṭha-Inspired File (PIF) encoder prototype.

Handles:
- Special token definitions (space / tab / newline)
- File extension validation (case-insensitive '.txt')
- Conversion of raw text into a list of "units" (one Unicode code
  point per unit, with space/tab/newline replaced by their prototype
  tokens)
- Reserved-token collision validation
- Minimum length validation
"""

from pathlib import Path

# Prototype tokens for whitespace that is hard to visualize/parse in
# plain text. Each token is a LOGICAL SINGLE UNIT during pair
# generation, even though it is rendered as multiple characters.
SPACE_TOKEN = "<SP>"
TAB_TOKEN = "<TAB>"
NEWLINE_TOKEN = "<NL>"

# The literal pipe character is also reserved: it's the Jāṭā group
# separator in the PIF format ("A B | B A | A B"). If the original
# text contained a literal '|', the encoded line would become
# ambiguous to split back into its three sections, making the PIF
# undecodable. Reserving it here (same mechanism as the whitespace
# tokens) catches this at encode time instead of producing a PIF that
# looks valid but can't be decoded correctly.
PIPE_CHARACTER = "|"

RESERVED_TOKENS = (SPACE_TOKEN, TAB_TOKEN, NEWLINE_TOKEN, PIPE_CHARACTER)

MIN_UNITS_REQUIRED = 2


def validate_txt_extension(input_path):
    """
    Ensure the given path has a '.txt' extension, case-insensitively
    ('.txt', '.TXT', '.Txt', etc. are all accepted as the same type).

    Args:
        input_path: path-like object or string.

    Raises:
        ValueError: if the file does not have a '.txt' extension.
    """
    path = Path(input_path)
    if path.suffix.lower() != ".txt":
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. Only '.txt' files "
            f"are supported in this prototype."
        )


def validate_no_reserved_tokens(text):
    """
    Reject input that already contains one of the prototype's reserved
    sequences ('<SP>', '<TAB>', '<NL>', '|') as literal text.

    The three bracketed tokens represent whitespace units; '|' is the
    Jāṭā group separator. If any of them already appear in the source
    text, the encoded output would be ambiguous to decode (a decoder
    couldn't tell, for example, a literal '<SP>' apart from an encoded
    space, or a literal '|' apart from a group boundary). Escaping
    reserved sequences is explicitly out of scope for this prototype,
    so such input is rejected outright rather than silently mishandled
    or silently producing an undecodable PIF.

    Args:
        text: the raw file content as a string.

    Raises:
        ValueError: if any reserved sequence is found in the text.
    """
    found = [token for token in RESERVED_TOKENS if token in text]
    if found:
        joined = ", ".join(f"'{t}'" for t in found)
        raise ValueError(
            f"Input contains reserved sequence(s) {joined}, which "
            f"conflict with this prototype's internal PIF format "
            f"(whitespace tokens and/or the group separator). "
            f"Escaping reserved sequences is not supported yet."
        )


def text_to_units(text):
    """
    Convert raw text into a list of unit strings, one per Unicode code
    point, except:
        - SPACE   (U+0020) -> SPACE_TOKEN   ('<SP>')
        - TAB     (U+0009) -> TAB_TOKEN     ('<TAB>')
        - NEWLINE ('\\n')   -> NEWLINE_TOKEN ('<NL>')

    Any other whitespace (non-breaking space, vertical tab, form feed,
    Unicode line/paragraph separators, etc.) is preserved as its
    original code point and is NOT converted to a token.

    Iterating a Python 3 `str` already yields one Unicode code point
    per step, so this satisfies "one code point = one basic unit"
    without any extra decoding work.

    Note: the input text is expected to already have platform-specific
    line endings normalized to '\\n' (Python's default text-mode file
    reading does this automatically via universal newline translation).

    Args:
        text: the raw file content as a string.

    Returns:
        list[str]: one entry per logical unit (a single code point, or
            a reserved whitespace token).
    """
    units = []
    for ch in text:
        if ch == " ":
            units.append(SPACE_TOKEN)
        elif ch == "\t":
            units.append(TAB_TOKEN)
        elif ch == "\n":
            units.append(NEWLINE_TOKEN)
        else:
            units.append(ch)
    return units


def validate_minimum_length(units):
    """
    Ensure there are at least MIN_UNITS_REQUIRED units.

    Args:
        units: list of logical units.

    Raises:
        ValueError: if fewer than MIN_UNITS_REQUIRED units are present.
    """
    if len(units) < MIN_UNITS_REQUIRED:
        raise ValueError(f"Minimum {MIN_UNITS_REQUIRED} characters required.")
