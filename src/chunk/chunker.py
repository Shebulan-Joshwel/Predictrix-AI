"""
Turns SourceDocuments (already split into entity/chapter-level pieces by
the ingestion layer) into smaller CHUNKS sized right for embedding.

WHY WE STILL NEED THIS AFTER ingestion already split things up:
Wiki/codex entries are short (2-8k chars) and stay as ONE chunk. But
chronicle chapters are long narrative prose (tens of thousands of chars) --
too big for a single embedding to represent well, and too big to usefully
cite in an answer. So long documents get split further, on paragraph
boundaries, with a bit of overlap so we don't cut a sentence in half at a
chunk edge and lose the fact it contained.

EVERY CHUNK CARRIES ITS PARENT'S METADATA (source_type, reliability_prior,
title, doc_id) -- this is what lets the agent's conflict-check step later
say "this chunk is from a codex (0.9 reliability), that one's from ephemera
(0.3 reliability)" without re-looking anything up.
"""

from dataclasses import dataclass

from src.models.document import SourceDocument


CHUNK_TARGET_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    source_type: str
    title: str
    reliability_prior: float
    file_path: str
    needs_review: bool = False
    chunk_index: int = 0


def chunk_document(doc: SourceDocument) -> list[Chunk]:
    text = doc.raw_text.strip()

    if len(text) <= CHUNK_TARGET_CHARS * 1.5:
        return [Chunk(
            chunk_id=f"{doc.doc_id}_c0",
            doc_id=doc.doc_id,
            text=text,
            source_type=doc.source_type.value,
            title=doc.title,
            reliability_prior=doc.reliability_prior,
            file_path=doc.file_path,
            needs_review=doc.metadata.get("needs_review", False),
            chunk_index=0,
        )]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > CHUNK_TARGET_CHARS and current:
            chunks.append(current.strip())
            current = current[-CHUNK_OVERLAP_CHARS:] + "\n\n" + para
        else:
            current = current + "\n\n" + para if current else para
    if current.strip():
        chunks.append(current.strip())

    return [
        Chunk(
            chunk_id=f"{doc.doc_id}_c{i}",
            doc_id=doc.doc_id,
            text=chunk_text,
            source_type=doc.source_type.value,
            title=doc.title,
            reliability_prior=doc.reliability_prior,
            file_path=doc.file_path,
            needs_review=doc.metadata.get("needs_review", False),
            chunk_index=i,
        )
        for i, chunk_text in enumerate(chunks)
    ]


def chunk_all(documents: list[SourceDocument]) -> list[Chunk]:
    all_chunks = []
    for doc in documents:
        all_chunks.extend(chunk_document(doc))
    return all_chunks


if __name__ == "__main__":
    from src.ingest.parse_corpus import ingest_corpus
    docs, report = ingest_corpus()
    chunks = chunk_all(docs)
    print(f"{len(docs)} documents -> {len(chunks)} chunks")
    lengths = [len(c.text) for c in chunks]
    print(f"avg chunk length: {sum(lengths)//max(len(lengths),1)} chars, "
          f"max: {max(lengths) if lengths else 0}, min: {min(lengths) if lengths else 0}")