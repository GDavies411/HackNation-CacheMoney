"""
Build Chroma vector index from SQLite (tickets, scripts, KB chunks).

Run from repo root (after ETL):
  python scripts/run_build_index.py [supportmind.db] [chroma_output_dir]

Defaults: data/supportmind.db → data/chroma
First run: may download the embedding model and can take 5–15 minutes to embed all chunks.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.retrieval.build_index import build_index

DEFAULT_DB = REPO_ROOT / "data" / "supportmind.db"
DEFAULT_CHROMA = REPO_ROOT / "data" / "chroma"


def main() -> None:
    db = DEFAULT_DB
    chroma_dir = DEFAULT_CHROMA
    if len(sys.argv) >= 2:
        db = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        chroma_dir = Path(sys.argv[2])
    if not db.exists():
        print("DB not found:", db)
        print("Run ETL first: python scripts/run_etl.py")
        sys.exit(1)
    n = build_index(db, chroma_dir)
    print("Chroma index built:", chroma_dir)
    print("  Chunks indexed:", n)


if __name__ == "__main__":
    main()
