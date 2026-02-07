"""
Chunking and ID strategy for RAG: tickets, scripts, KB articles.

Every chunk has metadata: source_type (ticket | script | kb), source_id
(Ticket_Number, Script_ID, or KB_Article_ID) so the agent can fetch full rows from the DB.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pandas as pd
from sqlalchemy import create_engine, text

# Default chunk size (chars) and overlap for splitting long text
DEFAULT_CHUNK_SIZE = 600
DEFAULT_CHUNK_OVERLAP = 100


@dataclass
class Chunk:
    """One chunk of text with metadata for vector store and DB lookup."""

    text: str
    source_type: str  # "ticket" | "script" | "kb"
    source_id: str
    chunk_index: int  # 0-based within the source


def _sliding_chunks(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks (character-based)."""
    if not text or not isinstance(text, str):
        return []
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _safe_str(val: object) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def chunks_from_tickets(
    df: pd.DataFrame,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Iterator[Chunk]:
    """Yield chunks from Tickets: Description + Resolution per row. source_id = Ticket_Number."""
    for _, row in df.iterrows():
        ticket_id = _safe_str(row.get("Ticket_Number", ""))
        if not ticket_id:
            continue
        desc = _safe_str(row.get("Description", ""))
        res = _safe_str(row.get("Resolution", ""))
        combined = f"Description: {desc}\n\nResolution: {res}".strip()
        if not combined:
            continue
        for i, part in enumerate(_sliding_chunks(combined, chunk_size, chunk_overlap)):
            yield Chunk(text=part, source_type="ticket", source_id=ticket_id, chunk_index=i)


def chunks_from_scripts(
    df: pd.DataFrame,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Iterator[Chunk]:
    """Yield chunks from Scripts_Master: Script_Text_Sanitized. source_id = Script_ID."""
    for _, row in df.iterrows():
        script_id = _safe_str(row.get("Script_ID", ""))
        if not script_id:
            continue
        body = _safe_str(row.get("Script_Text_Sanitized", ""))
        if not body:
            continue
        for i, part in enumerate(_sliding_chunks(body, chunk_size, chunk_overlap)):
            yield Chunk(text=part, source_type="script", source_id=str(script_id), chunk_index=i)


def chunks_from_kb(
    df: pd.DataFrame,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Iterator[Chunk]:
    """Yield chunks from Knowledge_Articles: Title + Body. source_id = KB_Article_ID."""
    for _, row in df.iterrows():
        kb_id = _safe_str(row.get("KB_Article_ID", ""))
        if not kb_id:
            continue
        title = _safe_str(row.get("Title", ""))
        body = _safe_str(row.get("Body", ""))
        combined = f"Title: {title}\n\n{body}".strip() if title else body
        if not combined:
            continue
        for i, part in enumerate(_sliding_chunks(combined, chunk_size, chunk_overlap)):
            yield Chunk(text=part, source_type="kb", source_id=str(kb_id), chunk_index=i)


def load_chunks_from_db(
    db_path: str | Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    include_tickets: bool = True,
    include_scripts: bool = True,
    include_kb: bool = True,
) -> Iterator[Chunk]:
    """
    Load Tickets, Scripts_Master, Knowledge_Articles from SQLite and yield chunks
    with source_type and source_id.
    """
    engine = create_engine("sqlite:///" + str(db_path))
    with engine.connect() as conn:
        if include_tickets:
            df_t = pd.read_sql(text("SELECT Ticket_Number, Description, Resolution FROM Tickets"), conn)
            yield from chunks_from_tickets(df_t, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if include_scripts:
            df_s = pd.read_sql(
                text("SELECT Script_ID, Script_Text_Sanitized FROM Scripts_Master"),
                conn,
            )
            yield from chunks_from_scripts(df_s, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if include_kb:
            df_k = pd.read_sql(
                text("SELECT KB_Article_ID, Title, Body FROM Knowledge_Articles"),
                conn,
            )
            yield from chunks_from_kb(df_k, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    engine.dispose()
