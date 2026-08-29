"""
FORMAT-LEVEL readers. Each function here knows about ONE file extension and
NOTHING about topic (wiki/codex/chronicle/ephemera). That separation is the
whole point: the README says chronicles can be PDF or DOCX, codex can be
PDF or DOCX, and ephemera is "mixed formats, including scanned pages" -- so
"what folder is this file in" and "how do I read this file" are two
different questions with two different answers, and conflating them (like
the first draft of this code did) breaks the moment a codex entry happens
to be a PDF instead of a DOCX.

Every reader returns the same shape: (raw_text, tables, image_refs)
  raw_text    : str            -- full extracted text, markdown-ish where possible
  tables      : list[dict]     -- any field/value tables found, e.g. infoboxes,
                                   codex registers
  image_refs  : list[str]      -- paths/refs to embedded or linked images (kept
                                   for 1A-style needs later; harmless for 1C)

read_any() is the single entry point everything else should call --
it looks at the file extension and dispatches to the right reader.
"""

import re
import subprocess
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None


IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def read_markdown(path: Path) -> tuple[str, list[dict], list[str]]:
    """.md files: plain read, no conversion needed. Wikilinks/infobox parsing
    happen one layer up (entity_extraction.py) since that's markdown-specific
    syntax, not something every format has."""
    text = path.read_text(encoding="utf-8")
    image_refs = [m.group(2) for m in IMAGE_PATTERN.finditer(text)]
    return text, [], image_refs


def read_docx(path: Path) -> tuple[str, list[dict], list[str]]:
    """
    .docx files: read directly with python-docx, walking paragraphs and
    tables IN DOCUMENT ORDER (python-docx doesn't do this by default --
    .paragraphs and .tables are separate lists with position info lost,
    so we walk the underlying XML body ourselves).

    Originally this shelled out to `pandoc`, but pandoc is an extra system
    install most people (especially on Windows) don't have on PATH. Doing
    it natively in python-docx means one less thing anyone on the team
    needs to install.

    Headings (Word styles "Heading 1/2/3") are converted to markdown
    '#'/'##'/'###' so the rest of the pipeline (split.py) doesn't need to
    know or care that this text originally came from a .docx.

    2-column tables (the "Field | Value" register pattern seen in every
    codex sample) are converted to markdown pipe-table lines, inserted
    into the text AT THE POSITION they appeared -- this keeps a table tied
    to the correct entry after splitting, the same way it naturally would
    be for a markdown source file.
    """
    from docx import Document as DocxDocument
    from docx.table import Table as DocxTable
    from docx.text.paragraph import Paragraph as DocxParagraph
    from docx.oxml.ns import qn

    def iter_block_items(doc):
        """Yield paragraphs and tables in the order they appear in the body.
        Standard python-docx recipe -- .paragraphs/.tables alone lose order."""
        for child in doc.element.body.iterchildren():
            if child.tag == qn("w:p"):
                yield DocxParagraph(child, doc)
            elif child.tag == qn("w:tbl"):
                yield DocxTable(child, doc)

    doc = DocxDocument(str(path))
    lines = []

    for block in iter_block_items(doc):
        if isinstance(block, DocxParagraph):
            text = block.text
            style_name = block.style.name if block.style else ""
            heading_match = re.match(r"Heading (\d)", style_name)
            if heading_match and text.strip():
                level = min(int(heading_match.group(1)), 3)
                lines.append("#" * level + " " + text.strip())
            else:
                lines.append(text)
        elif isinstance(block, DocxTable):
            for i, row in enumerate(block.rows):
                if i == 0:
                    continue  # first row is a label row (e.g. "Classification | Record"), not data
                cells = [c.text.strip() for c in row.cells]
                if len(cells) == 2 and cells[0]:
                    lines.append(f"| {cells[0]} | {cells[1]} |")

    text = "\n".join(lines)
    # Image extraction from .docx is out of scope for 1C (no image embedding
    # needed in answers) -- worth revisiting if the team ever tackles 1A.
    return text, [], []


def read_pdf(path: Path) -> tuple[str, list[dict], list[str]]:
    """
    .pdf files: try normal text extraction first (pdfplumber). If a page
    yields almost no text, it's very likely a "simulated scan" -- an image
    of a page rather than real embedded text -- so we fall back to OCR via
    pdftoppm (render page -> image) + pytesseract (image -> text).

    This dual-path handles BOTH real text PDFs (ephemera prose, or a codex/
    chronicle that happens to be PDF) AND scanned-page ephemera without
    needing to know in advance which kind a given file is.
    """
    if pdfplumber is None:
        raise RuntimeError("pdfplumber not installed")

    text_parts = []
    tables = []
    needs_ocr_pages = []

    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            if len(page_text.strip()) < 20:
                # Almost no extractable text -> likely a scanned/image page.
                needs_ocr_pages.append(i)
            else:
                text_parts.append(page_text)

            for table in page.extract_tables():
                # Turn a raw pdfplumber table (list of rows) into a field/value
                # dict IF it looks like a 2-column register (matches the codex
                # "Field | Value" pattern seen in the real samples).
                if table and all(len(row) == 2 for row in table if row):
                    tables.append({row[0]: row[1] for row in table if row and row[0]})

    if needs_ocr_pages:
        text_parts.append(_ocr_pdf_pages(path, needs_ocr_pages))

    return "\n\n".join(text_parts), tables, []


def _ocr_pdf_pages(path: Path, page_indices: list[int]) -> str:
    """
    Render specific PDF pages to images with pdftoppm, then OCR them with
    pytesseract. This is our fallback for 'simulated scan' pages, which is
    exactly the kind of file the README warns exists in ephemera/.

    NOTE: we haven't seen a real scanned-page sample yet (all 4 uploaded
    samples had real extractable text), so this path is written defensively
    from the spec but UNVERIFIED against real data. Flag this to the team --
    re-test this function the moment a real scanned example is available.
    """
    if pytesseract is None:
        return "[OCR SKIPPED: pytesseract not available]"

    import tempfile
    ocr_text = []
    with tempfile.TemporaryDirectory() as tmpdir:
        prefix = f"{tmpdir}/page"
        subprocess.run(
            ["pdftoppm", "-jpeg", "-r", "200", str(path), prefix],
            capture_output=True, check=True,
        )
        for img_path in sorted(Path(tmpdir).glob("*.jpg")):
            ocr_text.append(pytesseract.image_to_string(Image.open(img_path)))
    return "\n\n".join(ocr_text)


def read_txt(path: Path) -> tuple[str, list[dict], list[str]]:
    return path.read_text(encoding="utf-8"), [], []


def read_image(path: Path) -> tuple[str, list[dict], list[str]]:
    """Standalone image files (images/ folder, or figure plates). OCR any
    text baked into the image (captions, labels on a figure plate)."""
    if pytesseract is None:
        return "[OCR SKIPPED: pytesseract not available]", [], [str(path)]
    text = pytesseract.image_to_string(Image.open(path))
    return text, [], [str(path)]


READERS = {
    ".md": read_markdown,
    ".markdown": read_markdown,
    ".docx": read_docx,
    ".pdf": read_pdf,
    ".txt": read_txt,
    ".png": read_image,
    ".jpg": read_image,
    ".jpeg": read_image,
}


def read_any(file_path: str) -> tuple[str, list[dict], list[str]]:
    """Single entry point: look at the extension, dispatch, done.
    Callers should NEVER need to know or care about the file's topic folder
    to read it correctly -- that's the whole fix."""
    path = Path(file_path)
    ext = path.suffix.lower()
    reader = READERS.get(ext)
    if reader is None:
        raise ValueError(
            f"No reader registered for extension '{ext}' ({file_path}). "
            f"Known extensions: {list(READERS.keys())}"
        )
    return reader(path)
