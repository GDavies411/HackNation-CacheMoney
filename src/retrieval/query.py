"""
Case-in retrieval: query Chroma for Top-K chunks by case description.

Returns chunks with source_type, source_id so the agent can fetch full rows from the DB.
"""

from pathlib import Path
from typing import Any

import chromadb

from .build_index import COLLECTION_NAME, get_embedding_function


def query_chroma(
    query_text: str,
    chroma_path: str | Path,
    *,
    k: int = 10,
    collection_name: str = COLLECTION_NAME,
    where: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Query the supportmind collection for the top-k most similar chunks.
    Returns list of dicts: text, source_type, source_id, chunk_index, distance (if available).
    """
    chroma_path = Path(chroma_path)
    if not chroma_path.exists():
        return []

    ef = get_embedding_function()
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_collection(name=collection_name, embedding_function=ef)

    results = collection.query(
        query_texts=[query_text],
        n_results=min(k, collection.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    out = []
    if results["documents"] and results["documents"][0]:
        docs = results["documents"][0]
        metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(docs)
        distances = results["distances"][0] if results.get("distances") else [None] * len(docs)
        for i, doc in enumerate(docs):
            meta = metadatas[i] if i < len(metadatas) else {}
            out.append({
                "text": doc,
                "source_type": meta.get("source_type", ""),
                "source_id": meta.get("source_id", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "distance": distances[i] if i < len(distances) else None,
            })
    return out
