"""
Two format-agnostic helpers used AFTER a reader in readers.py has already
turned a file into text:

1. extract_wikilinks: pulls [[Entity]] mentions if the text happens to use
   that syntax. This is a MARKDOWN CONVENTION, not a wiki-topic guarantee --
   if an ephemera file or a codex file were ever written in markdown and
   used the same [[...]] convention, this would still catch it. We check
   the TEXT for the pattern, not the folder the file came from.

2. split_into_entries: many raw files contain MULTIPLE logical documents
   (e.g. the codex sample had Ashreach, Blackford, Cindermere Hold... all
   in one .docx). This splits on heading-like breaks so each entity gets
   its own SourceDocument and its own chunk for embedding, instead of one
   giant blob where a question about "Blackford" also drags in irrelevant
   text about "Cindermere Hold".

   Two splitting strategies, tried in order:
   (a) Markdown headings (## or ###) -- reliable, works whenever the source
       came from read_markdown() or read_docx() (pandoc emits real headings).
   (b) Heuristic fallback for plain-text/PDF-extracted text with NO markdown
       headings -- looks for short, standalone title-like lines. This is
       inherently less reliable (PDFs don't preserve heading semantics,
       just visual formatting we've lost by the time pdfplumber gives us
       plain text). Any document split this way is flagged in metadata
       with needs_review=True so a human can sanity-check it -- better to
       flag uncertainty than silently mis-split a document.
"""

import re

WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")

# A markdown heading line: 1-3 '#' characters then a title.
MD_HEADING_PATTERN = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

# Heuristic fallback for headless plain text (e.g. raw PDF extraction):
# a short (<=8 words) standalone line, title-cased, with blank lines around
# it, and NOT ending in sentence punctuation -- a rough proxy for "this
# looks like a heading, not a sentence."
HEURISTIC_HEADING_PATTERN = re.compile(
    r"^\n([A-Z][A-Za-z0-9 ,'\-]{2,50})\n\n(?!\n)", re.MULTILINE
)


def extract_wikilinks(text: str) -> list[str]:
    seen = []
    for match in WIKILINK_PATTERN.finditer(text):
        name = match.group(1).strip()
        if name not in seen:
            seen.append(name)
    return seen


def split_into_entries(text: str, min_heading_level: int = 2, max_heading_level: int = 3):
    """
    Returns a list of (title, body, needs_review) tuples.

    min/max_heading_level lets a caller say "split codex files on ### (level 3,
    per-entity entries)" vs "split chronicles on ## (level 2, per-chapter)" --
    but this is a preference, not a hard requirement, since we can't always
    predict which heading level a given source will use.
    """
    headings = list(MD_HEADING_PATTERN.finditer(text))
    usable_headings = [
        h for h in headings if min_heading_level <= len(h.group(1)) <= max_heading_level
    ]

    if usable_headings:
        entries = []
        for i, h in enumerate(usable_headings):
            title = h.group(2).strip()
            start = h.end()
            end = usable_headings[i + 1].start() if i + 1 < len(usable_headings) else len(text)
            body = text[start:end].strip()
            entries.append((title, body, False))
        return entries

    # Fallback: no markdown headings found at all (likely PDF-extracted plain
    # text). Try the heuristic pattern; if that also finds nothing, treat the
    # WHOLE file as one document rather than guessing wrong.
    heuristic_hits = list(HEURISTIC_HEADING_PATTERN.finditer(text))
    if heuristic_hits:
        entries = []
        for i, h in enumerate(heuristic_hits):
            title = h.group(1).strip()
            start = h.end()
            end = heuristic_hits[i + 1].start() if i + 1 < len(heuristic_hits) else len(text)
            body = text[start:end].strip()
            entries.append((title, body, True))  # needs_review=True: heuristic split
        return entries

    return [("Untitled", text.strip(), True)]  # single blob, flagged for review
