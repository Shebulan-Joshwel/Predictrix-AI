"""
Core data model for the Ashen Era Archive assistant.

WHY THIS FILE EXISTS FIRST:
Every parser (wiki/, codex/, chronicles/, ephemera/, images/) reads a
totally different file format, but the rest of the system (chunking,
embedding, the agent loop) should never have to care whether a fact came
from a .md file or a .pdf. So every parser's ONLY job is: read the weird
format, and return one of these normalized objects. Nothing downstream
touches raw files again.

RELIABILITY TIERING (this is the important design decision):
From reading the real sample files, the corpus explicitly signals trust
level in the text itself, e.g. the codex saying "This is the authoritative
founding record. Popular accounts wrongly claim otherwise." That means
source TYPE alone is a strong prior on reliability, before we even read
the content:
    codex       -> official record, highest trust, may explicitly correct others
    wiki        -> community-compiled, generally reliable but not authoritative
    chronicles  -> in-story narrative, facts stated by characters (can be
                   biased by WHO is speaking)
    ephemera    -> in-world documents. README explicitly warns: "in-world
                   authors are not always reliable." Lowest default trust tier.
    images      -> standalone figure plates / official illustrations, OCR'd
                   text content. Treated similar to wiki until proven otherwise.

This tier is a STARTING PRIOR, not a final answer -- the agent's reasoning
step can and should override it if it finds an explicit correction pointing
the other way.
"""

from dataclasses import dataclass, field
from enum import Enum


class SourceType(str, Enum):
    WIKI = "wiki"
    CODEX = "codex"
    CHRONICLE = "chronicle"
    EPHEMERA = "ephemera"
    IMAGE = "image"


DEFAULT_RELIABILITY = {
    SourceType.CODEX: 0.9,
    SourceType.WIKI: 0.7,
    SourceType.CHRONICLE: 0.5,
    SourceType.EPHEMERA: 0.3,
    SourceType.IMAGE: 0.6,
}


@dataclass
class Entity:
    """A named thing mentioned in a document (person, place, faction, item, event)."""
    name: str


@dataclass
class SourceDocument:
    """
    One normalized document, regardless of what raw format it came from.
    This is the ONLY object every downstream stage should ever import and use.
    """
    doc_id: str
    source_type: SourceType
    title: str
    raw_text: str
    file_path: str
    entities: list[Entity] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    reliability_prior: float = 0.5
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.reliability_prior == 0.5 and self.source_type in DEFAULT_RELIABILITY:
            self.reliability_prior = DEFAULT_RELIABILITY[self.source_type]