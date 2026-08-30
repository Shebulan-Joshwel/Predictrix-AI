"""
The single function every other part of the system calls: ingest_file().

THE FIX THIS FILE REPRESENTS:
  Before: "this is in codex/, so read it as a .docx"        <- wrong, breaks
          the moment a codex entry is a .pdf instead.
  Now:    "this is in codex/, so source_type=CODEX (controls reliability
          prior + how we'll route agent questions to it), AND separately,
          this file ends in .pdf, so use read_pdf() (controls HOW we get
          text out of it)." Two independent lookups, combined at the end.

Per-topic heading-split preferences are defaults, not hard assumptions --
they're just *parameters* passed to split_into_entries(), which itself
picks the actual shallowest heading level present (see split.py).
"""

import re
from pathlib import Path

from src.models.document import SourceDocument, SourceType, Entity
from src.ingest.readers import read_any
from src.ingest.split import extract_wikilinks, split_into_entries
from src.ingest.tables import extract_markdown_tables


TOPIC_SPLIT_LEVELS = {
    SourceType.CODEX: (2, 4),       # entity name at ##/###, sub-sections one level deeper   # entity name can be at ## or ###, sub-sections deeper
    SourceType.CHRONICLE: (2, 2),   # "## Chapter 1" style
    SourceType.WIKI: (1, 1),        # one wiki file = one entity, split on H1 only
    SourceType.EPHEMERA: (2, 3),    # multiple entries per file, level varies
}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def ingest_file(file_path: str, source_type: SourceType) -> list[SourceDocument]:
    path = Path(file_path)
    raw_text, structured_tables, image_refs = read_any(file_path)

    min_level, max_level = TOPIC_SPLIT_LEVELS.get(source_type, (2, 3))
    entries = split_into_entries(raw_text, min_level, max_level)

    documents = []
    for title, body, needs_review in entries:
        entities = [Entity(name=n) for n in extract_wikilinks(body)]
        doc_id = f"{source_type.value}_{path.stem}_{path.suffix.lstrip('.')}_{_slugify(title)}"

        entry_tables = extract_markdown_tables(body)
        if structured_tables:
            entry_tables = entry_tables + structured_tables
            if len(entries) > 1:
                needs_review = True

        documents.append(SourceDocument(
            doc_id=doc_id,
            source_type=source_type,
            title=title,
            raw_text=body,
            file_path=str(path),
            entities=entities,
            tables=entry_tables,
            metadata={
                "source_file": path.name,
                "file_extension": path.suffix.lower(),
                "needs_review": needs_review,
                "image_refs": image_refs,
            },
        ))

    return documents