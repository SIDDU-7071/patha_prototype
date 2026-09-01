"""
pif_writer.py

Builds and writes the .pif file content for the prototype.

The PIF format for this prototype is intentionally minimal:

    METHOD: JATA
    UNIT: CHARACTER
    SOURCE_TYPE: TXT


    <encoded line 1>
    <encoded line 2>
    ...

No integrity/checksum/hash sections are added at this stage - those
belong to a later stage of the project, outside this scope.

The '.pif' output is always a single plain-text file, never a folder.
"""

METHOD = "JATA"
UNIT = "CHARACTER"
SOURCE_TYPE = "TXT"


def build_pif_content(encoded_lines):
    """
    Build the full text content of a .pif file from a list of already
    Jāṭā-encoded lines (one line per overlapping pair).

    Args:
        encoded_lines: list[str], each already formatted like
            "A B | B A | A B".

    Returns:
        str: the complete PIF file content, header + blank line + body.
    """
    header = f"METHOD: {METHOD}\nUNIT: {UNIT}\nSOURCE_TYPE: {SOURCE_TYPE}\n\n"
    body = "\n".join(encoded_lines)
    return f"{header}\n{body}\n"


def write_pif_file(output_path, content):
    """
    Write the given PIF content to a single file (never a folder).

    Args:
        output_path: path-like object or string for the .pif file.
        content: full text content to write.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
