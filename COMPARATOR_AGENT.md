# Comparator Agent - Complete Rewrite

## Overview

The agent has been completely rewritten as a **pure comparator** - focused, clean, and purpose-built for finding the best matching KB article and script for support questions.

## What It Does

1. **Accepts** a user support question
2. **Queries** embeddings for 5 closest matching tickets (by description)
3. **Pulls** ticket metadata from DB:
   - Status, Tier, Module, Category
   - Resolution
   - KB_Article_ID
   - Script_ID
4. **Compares** using OpenAI to select the best match
5. **Returns** winning KB article and script IDs with rationale

## Agent API

### Function: `compare()`

```python
from src.agent import compare, AgentError

result = compare(
    question="User cannot upload photo",
    chroma_path="data/chroma",
    db_path="data/supportmind.db",
    top_k=5,              # Number of candidates (default 5)
    model="gpt-4o-mini"   # OpenAI model
)
```

### Return Structure

```python
{
    "winner": {
        "ticket_number": "CS-64258562",
        "kb_article_id": "KB-12345",
        "script_id": "S-678",
        "rationale": "Exact match for photo upload error with resolution",
        "module": "Tenant Management",
        "category": "Upload Issues"
    },
    "candidates": [
        # All 5 tickets that were considered
        {
            "ticket_number": "CS-64258562",
            "status": "Closed",
            "tier": 2,
            "module": "Tenant Management",
            "category": "Upload Issues",
            "resolution": "...",
            "kb_article_id": "KB-12345",
            "script_id": "S-678",
            "description": "..."
        },
        # ... 4 more
    ],
    "no_match": False,
    "question": "User cannot upload photo"
}
```

If no good match:
```python
{
    "winner": None,
    "candidates": [...],
    "no_match": True,
    "question": "..."
}
```

## Key Design Decisions

### 1. Ticket Embeddings Only
The agent queries embeddings filtered by `source_type: "ticket"` to ensure it's comparing against actual resolved support cases, not scripts or KB articles directly.

### 2. Metadata-Focused Comparison
OpenAI receives:
- Ticket metadata (status, tier, module, category)
- Truncated description (300 chars)
- Truncated resolution (300 chars)
- Boolean flags for KB article and script availability

This ensures the comparison is based on relevant factors, not overwhelming detail.

### 3. Simple Return Values
Returns only the essential IDs (KB article, script) with rationale. The consumer can then fetch full details if needed.

### 4. No String Formatting
Agent returns structured data (dicts). Formatting is handled by consumers (Streamlit app, CLI).

### 5. Hooks for Guardrails
Built-in support for incoming/outgoing hooks:
```python
import src.agent.agent as agent_module

# Preprocess question
agent_module.incoming_hook = lambda q, ctx: your_guardrails.check_input(q, ctx)

# Validate result
agent_module.outgoing_hook = lambda result, ctx: your_guardrails.check_output(result, ctx)
```

## What Was Removed

- ❌ All string formatting logic (100+ lines)
- ❌ Pandas dependency
- ❌ Complex type conversion
- ❌ `builtins.str()` workarounds
- ❌ Variable shadowing issues
- ❌ Multi-source querying (scripts, KB articles)
- ❌ Full resource retrieval

## What Was Added

- ✅ Clean, focused comparator logic
- ✅ Metadata-based comparison
- ✅ Simple JSON return structure
- ✅ Ticket-only embedding queries
- ✅ Clear error handling with warnings (doesn't fail on single ticket fetch error)

## Files Updated

1. **`src/agent/agent.py`** - Complete rewrite (250 lines → 280 lines of cleaner code)
2. **`src/agent/__init__.py`** - Export `compare` instead of `answer`
3. **`app.py`** - Streamlit interface for comparator
4. **`scripts/run_case_in.py`** - CLI interface for comparator
5. **`README.md`** - Updated documentation
6. **`test_comparator.py`** - New test script

## Testing

```bash
# Quick test
python test_comparator.py

# Web interface
python -m streamlit run app.py

# CLI
python scripts/run_case_in.py
```

## Example Interaction

**User:** "Tenant error when uploading photo"

**Agent Returns:**
```json
{
  "winner": {
    "ticket_number": "CS-64258562",
    "kb_article_id": "KB-TEN-001",
    "script_id": "S-UPLOAD-FIX",
    "rationale": "This ticket resolved an identical photo upload error in tenant management with a documented fix",
    "module": "Tenant Management",
    "category": "Upload Issues"
  },
  "no_match": false
}
```

**Streamlit App Shows:**
- ✅ Best Match Found
- Ticket: CS-64258562
- Module: Tenant Management
- Rationale: [...]
- 📄 KB Article ID: `KB-TEN-001`
- 📜 Script ID: `S-UPLOAD-FIX`

## Why This Architecture Works

1. **Single Responsibility** - Agent only compares and selects
2. **Clean Data Flow** - Embeddings → Metadata → OpenAI → Winner
3. **No Type Conversion Issues** - SQLite returns basic types, we just pass them through
4. **Easy to Test** - Simple input/output, JSON-serializable
5. **Extensible** - Hooks for guardrails, easy to add more metadata fields

This is production-ready code that solves the original problem without the complexity that was causing errors.
