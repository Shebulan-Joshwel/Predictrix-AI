"""
Embeds every chunk using OpenRouter's free embedding model, stores in
ChromaDB (free, local, no server to run).
"""
from dotenv import load_dotenv
load_dotenv()

import argparse
import os

from openai import OpenAI
import chromadb

from src.ingest.parse_corpus import ingest_corpus
from src.chunk.chunker import chunk_all


EMBEDDING_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
BATCH_SIZE = 100
CHROMA_DB_PATH = "data/processed/chroma_db"
COLLECTION_NAME = "ashen_era_corpus"


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY not set. In PowerShell: "
            '$env:OPENROUTER_API_KEY="your-key-here"'
        )
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)


def embed_and_store(limit: int | None = None):
    client = get_client()

    print("Ingesting corpus...")
    docs, report = ingest_corpus()
    print(f"  {report['parsed_files']} files -> {len(docs)} documents "
          f"({len(report['failed'])} failed, skipped -- not embedded)")

    print("Chunking...")
    chunks = chunk_all(docs)
    if limit:
        chunks = chunks[:limit]
        print(f"  LIMITED to first {limit} chunks for testing")
    print(f"  {len(chunks)} chunks ready to embed")

    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = chroma_client.create_collection(COLLECTION_NAME)

    total_calls = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        texts = [c.text for c in batch]

        response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts, encoding_format="float")
        embeddings = [item.embedding for item in response.data]
        total_calls += 1

        collection.add(
            ids=[c.chunk_id for c in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=[{
                "doc_id": c.doc_id,
                "title": c.title,
                "source_type": c.source_type,
                "reliability_prior": c.reliability_prior,
                "file_path": c.file_path,
                "needs_review": c.needs_review,
            } for c in batch],
        )
        print(f"  embedded {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)} chunks "
              f"({total_calls} API calls so far)")

    print(f"\nDone. {len(chunks)} chunks stored in ChromaDB at {CHROMA_DB_PATH}")
    print(f"Total API calls used: {total_calls} (free tier: ~50/day without credits)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    embed_and_store(limit=args.limit)