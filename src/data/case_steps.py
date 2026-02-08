"""
Write resolution documentation to Case_Steps table (for QA and self-learning loop input).
"""

from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text


def add_case_steps(
    db_path: str | Path,
    ticket_number: str,
    *,
    steps_text: Optional[str] = None,
    resolution_summary: Optional[str] = None,
) -> int:
    """
    Append a row to Case_Steps for documented resolution. Returns the new row id.
    """
    from datetime import datetime
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")
    now = datetime.utcnow().isoformat() + "Z"
    engine = create_engine("sqlite:///" + str(db_path))
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO Case_Steps (ticket_number, steps_text, resolution_summary, created_at, updated_at)
                VALUES (:ticket_number, :steps_text, :resolution_summary, :now, :now)
            """),
            {
                "ticket_number": ticket_number,
                "steps_text": steps_text or "",
                "resolution_summary": resolution_summary or "",
                "now": now,
            },
        )
        conn.commit()
        r = conn.execute(text("SELECT last_insert_rowid()"))
        row_id = r.scalar()
    engine.dispose()
    return row_id or 0
