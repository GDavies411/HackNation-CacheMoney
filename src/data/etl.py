"""
ETL: Load SupportMind Excel workbook into SQLite (MVP relational DB).

Creates one table per tabular sheet and a Case_Steps table for documented
resolution steps. Join keys: Ticket_Number, Conversation_ID, Script_ID, KB_Article_ID.

Usage:
    from src.data.etl import run_etl
    run_etl("src/data/SupportMind__Final_Data.xlsx", "data/supportmind.db")
"""

from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text

# Tabular sheets to load (exclude README and QA_Evaluation_Prompt — they are long text)
SHEETS_TO_LOAD = [
    "Conversations",
    "Tickets",
    "Questions",
    "Scripts_Master",
    "Placeholder_Dictionary",
    "Knowledge_Articles",
    "KB_Lineage",
    "Existing_Knowledge_Articles",
    "Learning_Events",
]

# Case_Steps: documented resolution steps (empty at seed; filled by pipeline)
CASE_STEPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS Case_Steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number TEXT NOT NULL,
    steps_text TEXT,
    resolution_summary TEXT,
    created_at TEXT,
    updated_at TEXT
);
"""


def _table_name(sheet_name: str) -> str:
    """Sheet name to SQLite table name (safe, no spaces)."""
    return sheet_name.replace(" ", "_").replace("-", "_")


def run_etl(
    xlsx_path: str | Path,
    db_path: str | Path,
    *,
    sheets: Optional[list[str]] = None,
    create_case_steps: bool = True,
) -> dict[str, int]:
    """
    Load Excel workbook into SQLite. Returns dict of table_name -> row count.

    - xlsx_path: path to SupportMind__Final_Data.xlsx
    - db_path: path to SQLite file (e.g. data/supportmind.db)
    - sheets: optional list of sheet names to load (default: SHEETS_TO_LOAD)
    - create_case_steps: if True, ensure Case_Steps table exists
    """
    xlsx_path = Path(xlsx_path)
    db_path = Path(db_path)
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Workbook not found: {xlsx_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine("sqlite:///" + str(db_path))
    to_load = sheets or SHEETS_TO_LOAD
    counts: dict[str, int] = {}

    with pd.ExcelFile(xlsx_path, engine="openpyxl") as xl:
        available = xl.sheet_names
        for sheet_name in to_load:
            if sheet_name not in available:
                continue
            df = pd.read_excel(xl, sheet_name=sheet_name)
            if df.empty:
                table = _table_name(sheet_name)
                df.to_sql(table, engine, if_exists="replace", index=False)
                counts[table] = 0
                continue
            table = _table_name(sheet_name)
            df.to_sql(table, engine, if_exists="replace", index=False)
            counts[table] = len(df)

    if create_case_steps:
        with engine.connect() as conn:
            conn.execute(text(CASE_STEPS_SCHEMA))
            conn.commit()
        if "Case_Steps" not in counts:
            with engine.connect() as conn:
                r = conn.execute(text("SELECT COUNT(*) FROM Case_Steps"))
                counts["Case_Steps"] = r.scalar() or 0

    engine.dispose()
    return counts


def main() -> None:
    """CLI entry: run ETL with default paths."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    xlsx = repo_root / "src" / "data" / "SupportMind__Final_Data.xlsx"
    db = repo_root / "data" / "supportmind.db"
    counts = run_etl(xlsx, db)
    print("ETL complete:", db)
    for table, n in sorted(counts.items()):
        print(f"  {table}: {n} rows")


if __name__ == "__main__":
    main()
