"""
One-off diagnostic: prints every paragraph's Word STYLE NAME and whether
it's bold, for the bestiary file specifically. This tells us exactly how
entity names are actually marked in this file (a real Heading style? bold
text with no heading style? something else?) instead of guessing again.

Usage: python -m src.debug_docx_structure "data/raw/codex/codex_vaeloria_ii_armory_of_relics_and_bestiary.docx"
"""

import sys
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.table import Table


def iter_block_items(doc):
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def main(path: str, limit: int = 60):
    doc = Document(path)
    count = 0
    for block in iter_block_items(doc):
        if count >= limit:
            print(f"... (stopped after {limit} blocks, remove --limit or edit script to see more)")
            break
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            style = block.style.name if block.style else "?"
            is_bold = all(run.bold for run in block.runs if run.text.strip()) if block.runs else False
            print(f"[style={style!r:25s} bold={is_bold!s:5s}] {text[:70]}")
            count += 1
        elif isinstance(block, Table):
            print(f"[TABLE with {len(block.rows)} rows]")
            count += 1


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/codex/codex_vaeloria_ii_armory_of_relics_and_bestiary.docx"
    main(path)