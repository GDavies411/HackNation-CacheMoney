"""
Inspect SupportMind Excel workbook: sheet names, columns, row counts.

Run from repo root:
  python scripts/inspect_workbook.py [path/to/workbook.xlsx]
"""

import sys
from pathlib import Path

# Avoid UnicodeEncodeError on Windows when printing column names
if sys.stdout.encoding and sys.stdout.encoding.lower() in ("cp1252", "cp437"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_XLSX = REPO_ROOT / "src" / "data" / "SupportMind__Final_Data.xlsx"


def main() -> None:
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    if not xlsx.exists():
        print(f"Not found: {xlsx}")
        sys.exit(1)

    xl = pd.ExcelFile(xlsx, engine="openpyxl")
    print("Sheets:", xl.sheet_names)

    for name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=name)
        cols = list(df.columns)
        print(f"\n{name}: {len(df)} rows")
        preview = cols[:14]
        if len(cols) > 14:
            preview = preview + ["..."]
        print("  Columns:", preview)


if __name__ == "__main__":
    main()
