"""
Run ETL: Excel → SQLite.

Run from repo root:
  python scripts/run_etl.py [workbook.xlsx] [output.db]

Defaults: src/data/SupportMind__Final_Data.xlsx → data/supportmind.db
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.data.etl import run_etl

DEFAULT_XLSX = REPO_ROOT / "src" / "data" / "SupportMind__Final_Data.xlsx"
DEFAULT_DB = REPO_ROOT / "data" / "supportmind.db"


def main() -> None:
    xlsx = DEFAULT_XLSX
    db = DEFAULT_DB
    if len(sys.argv) >= 2:
        xlsx = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        db = Path(sys.argv[2])
    if not xlsx.exists():
        print(f"Not found: {xlsx}")
        sys.exit(1)
    counts = run_etl(xlsx, db)
    print("ETL complete:", db)
    for table, n in sorted(counts.items()):
        print(f"  {table}: {n} rows")


if __name__ == "__main__":
    main()
