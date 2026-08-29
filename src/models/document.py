"""
Core data model for the Ashen Era Archive assistant.

WHY THIS FILE EXISTS FIRST:
Every parser (wiki/, codex/, chronicles/, ephemera/) reads a totally different
file format, but the rest of the system (chunking, embedding, the agent loop)
should never have to care whether a fact came from a .md file or a .pdf.
So every parser's ONLY job is: read the weird format, and return one of
these normalized objects. Nothing downstream touches raw files again.

RELIABILITY TIERING (this is the important design decision):
From reading the real sample files, we found the corpus explicitly signals
trust level in the text itself, e.g. the codex saying "This is the
authoritative founding record. Popular accounts wrongly claim otherwise."
That means source TYPE alone is a strong prior on reliability, before we
even read the content:
    codex       -> official record, highest trust, may explicitly correct others
    wiki        -> community-compiled, generally reliable but not authoritative
    chronicles  -> in-story narrative, facts stated by characters (can be
                   biased by WHO is speaking, e.g. a liar's private journal)
    ephemera    -> in-world documents (letters, ledgers, auction catalogues).
                   README explicitly warns: "in-world authors are not always
                   reliable." Lowest default trust tier.

This tier is a STARTING PRIOR, not a final answer -- the agent's reasoning
step can and should override it if it finds an explicit correction (like the
Ashreach example) pointing the other way. We're encoding source skepticism
as a signal for the agent to reason over, not a hard filter that deletes data.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    WIKI = "wiki"
    CODEX = "codex"
    CHRONICLE = "chronicle"
    EPHEMERA = "ephemera"


# Default reliability prior per source type, on a 0.0-1.0 scale.
# Used as a *signal* fed to the agent's reasoning step, never a hard filter.
DEFAULT_RELIABILITY = {
    SourceType.CODEX: 0.9,       # official records, may explicitly self-declare authority
    SourceType.WIKI: 0.7,        # community-compiled, generally solid
    SourceType.CHRONICLE: 0.5,   # narrative — true in-world, but character bias possible
    SourceType.EPHEMERA: 0.3,    # in-world docs, README warns these can be unreliable
}


@dataclass
class Entity:
    """A named thing mentioned in a document (person, place, faction, item, event)."""
    name: str
    # We don't classify entity type at parse time (person vs place vs item) --
    # that requires either an NER model or LLM call, which is a later pipeline
    # stage, not the ingestion layer's job. Ingestion just harvests raw mentions.


@dataclass
class SourceDocument:
    """
    One normalized document, regardless of what raw format it came from.
    This is the ONLY object every downstream stage (chunker, embedder, agent)
    should ever import and use.
    """
    doc_id: str                        # stable unique id, e.g. "wiki_aldous_wrenfield"
    source_type: SourceType
    title: str
    raw_text: str                      # full plain-text content, cleaned
    file_path: str                     # original file path, kept for citation/debugging
    entities: list[Entity] = field(default_factory=list)   # e.g. wikilinks, table subjects
    tables: list[dict] = field(default_factory=list)       # structured field/value pairs found
    reliability_prior: float = 0.5     # filled in from DEFAULT_RELIABILITY at parse time
    metadata: dict = field(default_factory=dict)           # anything format-specific worth keeping

    def __post_init__(self):
        if self.reliability_prior == 0.5 and self.source_type in DEFAULT_RELIABILITY:
            self.reliability_prior = DEFAULT_RELIABILITY[self.source_type]
