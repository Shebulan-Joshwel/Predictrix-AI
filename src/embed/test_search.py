"""
Quick sanity check: embed one query via OpenRouter, search ChromaDB, print
top results. Run after embed_and_store.py.
Usage: python -m src.embed.test_search "your question here"
"""

import sys

from src.embed.embed_and_store import get_client, EMBEDDING_MODEL, CHROMA_DB_PATH, COLLECTION_NAME
import chromadb


def search(query: str, n_results: int = 5):
    client = get_client()

    query_embedding = client.embeddings.create(model=EMBEDDING_MODEL, input=[query], encoding_format="float").data[0].embedding

    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = chroma_client.get_collection(COLLECTION_NAME)

    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)

    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        text_preview = results["documents"][0][i][:200]
        print(f"\n--- Result {i+1} (distance={distance:.3f}) ---")
        print(f"[{meta['source_type']}] {meta['title']} (reliability={meta['reliability_prior']})")
        print(text_preview + "...")


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "What year was Gloamreach founded?"
    search(query)