# HackNation-CacheMoney

Self-learning support intelligence layer for the RP HackNation challenge. **Hero feature:** Self-Updating Knowledge Engine — the system learns from resolved cases, proposes KB articles with traceability, and supports triage, recommendation, and QA.

## Project overview

- **Problem:** Knowledge is fragmented across tickets, scripts, and KB articles; fixes stay in case notes; QA is manual.
- **Goal:** Find the best matching KB article and script for new support issues using historical ticket data.
- **Approach:** Comparator agent that uses embeddings (RAG) to find similar tickets, then uses OpenAI to select the best match based on ticket metadata (status, tier, module, category, resolution, KB article, script).

## Repository structure

```
HackNation-CacheMoney/
├── README.md              # This file
├── requirements.txt       # Python deps (pandas, openpyxl, sqlalchemy, chromadb, sentence-transformers)
├── docs/                  # Planning, challenge alignment
├── data/                  # SQLite DB and Chroma index (gitignored; regenerate with scripts)
├── src/
│   ├── data/              # ETL (Excel → SQLite), Case_Steps
│   ├── retrieval/         # Chunking, Chroma build, query (RAG)
│   └── agent/             # Comparator agent: RAG → OpenAI selection → return KB/script IDs
├── scripts/
│   ├── inspect_workbook.py   # List Excel sheets/columns
│   ├── run_etl.py            # Excel → SQLite
│   ├── run_build_index.py    # Build Chroma from DB
│   └── run_case_in.py        # Interactive chat (LLM-only: RAG + OpenAI comparator)
└── .gitignore             # data/chroma/, data/*.db
```

## Current progress

| Phase | Status | What’s in place |
|-------|--------|------------------|
| **1. Data & RAG** | Done | ETL (Excel → SQLite), chunking (tickets, scripts, KB), Chroma index, `query_chroma()` |
| **2. Case-in & agent** | Done | Agent: RAG → OpenAI selection → pull solutions from DB; hooks (incoming/outgoing) for orchestration with other agents (e.g. guardrails) |
| **3. Self-learning loop** | Planned | Gap detection (LLM), extract draft KB, review + versioning, publish, re-index |
| **4. QA & demo** | Planned | QA scorer, demo script (reuse + novel) |

## Getting started

**1. Clone and install**

```bash
git clone https://github.com/GDavies411/HackNation-CacheMoney.git
cd HackNation-CacheMoney
pip install -r requirements.txt
```

**2. Regenerate data (not in repo)**

Place `SupportMind__Final_Data.xlsx` in `src/data/`, then:

```bash
python scripts/run_etl.py
python scripts/run_build_index.py
```

- `run_etl.py` → `data/supportmind.db` (Tickets, Scripts_Master, Knowledge_Articles, Case_Steps, etc.).
- `run_build_index.py` → `data/chroma/` (first run can take 5–15 min).

**3. Run the comparator agent**

Add `OPENAI_API_KEY` to a `.env` file in the repo root, then:

**Web Interface (Recommended)**

```bash
pip install streamlit  # if not already installed
python -m streamlit run app.py
```

Opens a web interface at `http://localhost:8501` where you can:
- Describe support issues
- See the best matching ticket
- View KB article and script IDs
- See the rationale for the match

**Command Line**

```bash
python scripts/run_case_in.py
```

Interactive CLI. Type `quit` or `q` to exit.

**4. Use in code**

```python
from src.agent import compare, AgentError

try:
    result = compare(
        "User cannot upload photo to tenant profile",
        "data/chroma",
        "data/supportmind.db",
        top_k=5
    )
    
    # Result structure:
    # {
    #   "winner": {
    #     "ticket_number": "CS-12345",
    #     "kb_article_id": "KB-001",
    #     "script_id": "S-042",
    #     "rationale": "Exact match for photo upload error",
    #     "module": "Tenant Management",
    #     "category": "Upload Issues"
    #   },
    #   "candidates": [...],  # All tickets considered
    #   "no_match": False,
    #   "question": "..."
    # }
    
    if result["winner"]:
        print(f"KB Article: {result['winner']['kb_article_id']}")
        print(f"Script: {result['winner']['script_id']}")
        print(f"Rationale: {result['winner']['rationale']}")
        
except AgentError as e:
    print("Agent error:", e)
```

## License

Use as needed for the HackNation challenge.
