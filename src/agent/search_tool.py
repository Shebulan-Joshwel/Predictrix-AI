"""
The agent's search tool -- now HYBRID, not pure semantic.

WHY: a human researcher given "who commands Fenspire?" doesn't just search
by vague meaning -- they search the literal name "Fenspire" too. Pure
vector search can miss an exact-name hit if the surrounding phrasing
differs enough. So every search now does TWO things and merges results:

  1. SEMANTIC: embed the query, vector search (as before) -- good for
     conceptual/paraphrased questions.
  2. KEYWORD: pull out capitalized proper-noun-looking phrases from the
     query (e.g. "Fenspire", "Gauntlet of Sorrowfell") and do an exact
     substring match against chunk text via ChromaDB's $contains filter --
     good for "does this specific named thing appear here" questions,
     which is most of what this corpus's fact-lookup questions are.

Each result is tagged with which method(s) found it -- useful for
debugging and for your report ("our system uses hybrid retrieval, not
just off-the-shelf vector search" is a real, demonstrable design choice).
"""

import re
from dataclasses import dataclass, field

from src.embed.embed_and_store import get_client, EMBEDDING_MODEL, CHROMA_DB_PATH, COLLECTION_NAME
import chromadb


PROPER_NOUN_PATTERN = re.compile(r"\b[A-Z][a-zA-Z']+(?:\s+[A-Z][a-zA-Z']+){0,4}\b")
QUESTION_STOPWORDS = {
    "What", "Which", "Who", "Where", "When", "How", "Why", "In", "On", "At",
    "The", "Is", "Does", "Did", "According", "State",
}


@dataclass
class SearchResult:
    chunk_id: str
    text: str
    title: str
    source_type: str
    reliability_prior: float
    doc_id: str
    found_by: list[str] = field(default_factory=list)  # "semantic" and/or "keyword"


def _extract_entity_candidates(query: str) -> list[str]:
    """Pull likely proper-noun phrases out of a question, dropping common
    question-word false positives that get capitalized by sentence position."""
    candidates = PROPER_NOUN_PATTERN.findall(query)
    return [c for c in candidates if c not in QUESTION_STOPWORDS and len(c) > 2]


def search_corpus(query: str, n_results: int = 5) -> list[SearchResult]:
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = chroma_client.get_collection(COLLECTION_NAME)

    merged: dict[str, SearchResult] = {}  # keyed by chunk_id, for clean dedup

    # 1. Semantic search
    client = get_client()
    query_embedding = client.embeddings.create(
        model=EMBEDDING_MODEL, input=[query], encoding_format="float"
    ).data[0].embedding
    semantic = collection.query(query_embeddings=[query_embedding], n_results=n_results)

    for i in range(len(semantic["ids"][0])):
        chunk_id = semantic["ids"][0][i]
        meta = semantic["metadatas"][0][i]
        merged[chunk_id] = SearchResult(
            chunk_id=chunk_id,
            text=semantic["documents"][0][i],
            title=meta["title"],
            source_type=meta["source_type"],
            reliability_prior=meta["reliability_prior"],
            doc_id=meta["doc_id"],
            found_by=["semantic"],
        )

    # 2. Keyword/entity search -- exact substring match per candidate entity
    for entity in _extract_entity_candidates(query):
        try:
            keyword_hits = collection.get(
                where_document={"$contains": entity}, limit=n_results
            )
        except Exception:
            continue  # ChromaDB version differences -- fail soft, semantic results still stand

        for i, chunk_id in enumerate(keyword_hits["ids"]):
            meta = keyword_hits["metadatas"][i]
            if chunk_id in merged:
                if "keyword" not in merged[chunk_id].found_by:
                    merged[chunk_id].found_by.append("keyword")
            else:
                merged[chunk_id] = SearchResult(
                    chunk_id=chunk_id,
                    text=keyword_hits["documents"][i],
                    title=meta["title"],
                    source_type=meta["source_type"],
                    reliability_prior=meta["reliability_prior"],
                    doc_id=meta["doc_id"],
                    found_by=["keyword"],
                )

    return list(merged.values())