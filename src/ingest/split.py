"""
Two format-agnostic helpers used AFTER a reader in readers.py has already
turned a file into text:

1. extract_wikilinks: pulls [[Entity]] mentions if the text happens to use
   that syntax -- a markdown convention, checked on the TEXT, not tied to
   the wiki folder specifically.

2. split_into_entries: splits a file containing multiple logical documents
   into separate entries. Picks the SHALLOWEST heading level actually
   present in range and splits only on that level -- fixes a bug where a
   nested structure (## Creature Name containing ### Appearance, ###
   Threat Assessment sub-sections) caused every creature's "Appearance"
   section to collide into one ID.
"""

import re

WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")

MD_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


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
    headings = list(MD_HEADING_PATTERN.finditer(text))
    usable_headings = [
        h for h in headings if min_heading_level <= len(h.group(1)) <= max_heading_level
    ]

    if usable_headings:
        levels_present = sorted(set(len(h.group(1)) for h in usable_headings))
        split_level = levels_present[0]
        split_headings = [h for h in usable_headings if len(h.group(1)) == split_level]

        entries = []
        for i, h in enumerate(split_headings):
            title = h.group(2).strip()
            start = h.end()
            end = split_headings[i + 1].start() if i + 1 < len(split_headings) else len(text)
            body = text[start:end].strip()
            entries.append((title, body, False))
        return entries

    heuristic_hits = list(HEURISTIC_HEADING_PATTERN.finditer(text))
    if heuristic_hits:
        entries = []
        for i, h in enumerate(heuristic_hits):
            title = h.group(1).strip()
            start = h.end()
            end = heuristic_hits[i + 1].start() if i + 1 < len(heuristic_hits) else len(text)
            body = text[start:end].strip()
            entries.append((title, body, True))
        return entries

    return [("Untitled", text.strip(), True)]