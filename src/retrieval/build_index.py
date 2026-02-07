"""
Build Chroma vector index from SQLite: chunk tickets, scripts, KB; embed; persist.

Re-index of a single new KB article is supported via add_kb_article_to_index() for
the self-learning loop (after publish).
"""

from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

from .chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    Chunk,
    load_chunks_from_db,
)

# Collection name in Chroma
COLLECTION_NAME = "supportmind"

# Default paths (repo-relative)
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "supportmind.db"
DEFAULT_CHROMA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "chroma"


def get_embedding_function():
    """Local embedding: use Chroma default (ONNX all-MiniLM-L6-v2) so no sentence-transformers install required.
    For slightly better quality, install sentence-transformers and we will use it when available."""
    try:
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    except (ValueError, ImportError):
        return embedding_functions.DefaultEmbeddingFunction()


def build_index(
    db_path: str | Path,
    chroma_path: str | Path,
    *,
    collection_name: str = COLLECTION_NAME,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    embedding_model: Optional[str] = None,
) -> int:
    """
    Load chunks from DB, embed, and write to Chroma. Replaces existing collection.
    Returns total number of chunks indexed.
    """
    db_path = Path(db_path)
    chroma_path = Path(chroma_path)
    chroma_path.mkdir(parents=True, exist_ok=True)

    if embedding_model:
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=embedding_model)
    else:
        ef = get_embedding_function()

    client = chromadb.PersistentClient(path=str(chroma_path))
    # Replace existing collection so we have a clean index
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        name=collection_name,
        embedding_function=ef,
    )

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for chunk in load_chunks_from_db(
        db_path,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    ):
        # Chroma metadata values must be str, int, float, or bool
        chunk_id = f"{chunk.source_type}_{chunk.source_id}_{chunk.chunk_index}"
        ids.append(chunk_id)
        documents.append(chunk.text)
        metadatas.append({
            "source_type": chunk.source_type,
            "source_id": str(chunk.source_id),
            "chunk_index": chunk.chunk_index,
        })

    if not ids:
        return 0

    # Add in batches to avoid memory and API issues
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
        )

    return len(ids)


def add_kb_article_to_index(
    kb_article_id: str,
    title: str,
    body: str,
    chroma_path: str | Path,
    *,
    collection_name: str = COLLECTION_NAME,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> int:
    """
    Add one KB article's chunks to the existing Chroma collection (for re-index after publish).
    Returns number of chunks added.
    """
    from .chunking import _safe_str, _sliding_chunks

    chroma_path = Path(chroma_path)
    title = _safe_str(title)
    body = _safe_str(body)
    combined = f"Title: {title}\n\n{body}".strip() if title else body
    if not combined:
        return 0

    chunks = _sliding_chunks(combined, chunk_size, chunk_overlap)
    chunk_list = [
        Chunk(text=c, source_type="kb", source_id=kb_article_id, chunk_index=i)
        for i, c in enumerate(chunks)
    ]
    if not chunk_list:
        return 0

    ef = get_embedding_function()
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_collection(name=collection_name, embedding_function=ef)

    ids = []
    documents = []
    metadatas = []
    for chunk in chunk_list:
        chunk_id = f"kb_{chunk.source_id}_{chunk.chunk_index}"
        ids.append(chunk_id)
        documents.append(chunk.text)
        metadatas.append({
            "source_type": "kb",
            "source_id": str(chunk.source_id),
            "chunk_index": chunk.chunk_index,
        })

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def main() -> None:
    """CLI: build index with default paths."""
    import sys
    repo_root = Path(__file__).resolve().parent.parent.parent
    db = repo_root / "data" / "supportmind.db"
    chroma_dir = repo_root / "data" / "chroma"
    if len(sys.argv) >= 2:
        db = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        chroma_dir = Path(sys.argv[2])
    if not db.exists():
        print("DB not found:", db)
        return
    n = build_index(db, chroma_dir)
    print("Chroma index built:", chroma_dir)
    print("  Chunks indexed:", n)


if __name__ == "__main__":
    main()
