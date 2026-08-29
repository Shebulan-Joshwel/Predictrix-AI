"""
Extracts field/value tables from markdown-ish text, regardless of whether
that text came from a .md file (pipe tables: | Field | Value |) or a .docx
via pandoc (grid tables: dash-bordered blocks). This is intentionally
separate from readers.py because table shape depends on the TEXT structure
pandoc/the file produced, and is best applied AFTER a document has been
split into individual entries (see split.py) -- otherwise a codex file with
9 entries would have all 9 entries' tables mashed into one document's table
list, which defeats the purpose of splitting in the first place.
"""

import re


def _extract_pipe_tables(text: str) -> list[dict]:
    """| Field | Value | style, as seen in the wiki infobox sample."""
    tables = []
    for block in re.findall(r"((?:^\|.*\|\s*$\n?)+)", text, re.MULTILINE):
        rows = [line.strip() for line in block.strip().split("\n")]
        parsed = {}
        for row in rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) != 2:
                continue
            key, value = cells
            if key.lower() == "field" or set(key) <= {"-"}:
                continue  # skip header row and '---|---' separator row
            parsed[key] = value
        if parsed:
            tables.append(parsed)
    return tables


def _extract_grid_tables(text: str) -> list[dict]:
    """
    Dash-bordered grid tables, as pandoc emits from .docx tables, e.g.:
        -----------------------------------------------------------------
        Classification                      Record
        ----------------------------------- -----------------------------
        Region                               The Weeping Marshes

        Status                               contested
        -----------------------------------------------------------------
    Structure: full-width dash line, header row, per-column dash separator,
    data rows (2+ spaces between key/value), full-width dash line.
    """
    tables = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if re.match(r"^\s*-{10,}\s*$", lines[i]):
            j = i + 1
            if j < len(lines) and lines[j].strip() and not set(lines[j].strip()) <= {"-", " "}:
                header_line = lines[j]
                j += 1
                if j < len(lines) and re.match(r"^[\s\-]+$", lines[j]) and "-" in lines[j]:
                    j += 1
                    data_start = j
                    while j < len(lines) and not re.match(r"^\s*-{10,}\s*$", lines[j]):
                        j += 1
                    if j < len(lines):  # matching bottom border found
                        header_parts = re.split(r"\s{2,}", header_line.strip())
                        table = {}
                        if len(header_parts) == 2:
                            for data_line in lines[data_start:j]:
                                if not data_line.strip():
                                    continue
                                parts = re.split(r"\s{2,}", data_line.strip())
                                if len(parts) >= 2:
                                    table[parts[0].strip()] = " ".join(parts[1:]).strip()
                        if table:
                            tables.append(table)
                        i = j
                        continue
        i += 1
    return tables


def extract_markdown_tables(text: str) -> list[dict]:
    """Try both known table shapes. A given text block will only match one
    of them in practice, but running both is cheap and avoids needing to
    know in advance whether text came from a .md or a pandoc-converted .docx."""
    tables = _extract_pipe_tables(text)
    if not tables:
        tables = _extract_grid_tables(text)
    return tables
