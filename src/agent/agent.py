"""
Comparator Agent: Finds the best matching ticket and returns its KB article and script.

Flow:
1. Accept user support question
2. Query embeddings for 5 closest matching tickets (by description)
3. Pull ticket metadata from DB (status, tier, module, category, resolution, KB_Article_ID, Script_ID)
4. Use OpenAI to select the best match
5. Return winning KB_Article_ID and Script_ID with rationale

Requires OPENAI_API_KEY in .env.
"""

import json
import os
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import create_engine, text


# Load .env from repo root
def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        root = Path(__file__).resolve().parent.parent.parent
        load_dotenv(root / ".env")
    except ImportError:
        pass

_load_dotenv()


class AgentError(Exception):
    """Raised when the agent cannot run (missing key, API failure, DB error)."""
    pass


# Optional hooks for orchestration with guardrails agent
incoming_hook: Callable[[str, dict], str] | None = None
outgoing_hook: Callable[[dict, dict], dict] | None = None


def compare(
    question: str,
    chroma_path: str | Path,
    db_path: str | Path,
    *,
    top_k: int = 5,
    model: str = "gpt-4o-mini",
) -> dict[str, Any]:
    """
    Find the best matching ticket for a support question.

    Args:
        question: User's support question/complaint.
        chroma_path: Path to Chroma vector store.
        db_path: Path to SQLite DB with tickets.
        top_k: Number of similar tickets to retrieve (default 5).
        model: OpenAI model to use for comparison.

    Returns:
        dict with:
          - ranked_results: list of all candidates ranked from best to worst, each with:
              - rank: position (1-5)
              - ticket_number, kb_article_id, script_id, script_text
              - rationale: why this rank
              - module, category, status, tier
          - question: original question
          - no_match: bool, true if no relevant matches found

    Raises:
        AgentError: if OPENAI_API_KEY missing, API fails, or DB error.
    """
    from openai import OpenAI
    import chromadb
    from chromadb.utils import embedding_functions

    chroma_path = Path(chroma_path)
    db_path = Path(db_path)

    # Incoming hook: guardrails agent can preprocess
    context = {"question": question}
    if incoming_hook is not None:
        question = incoming_hook(question, context)

    # Step 1: Query embeddings for top 5 matching tickets
    if not chroma_path.exists():
        raise AgentError(f"Chroma index not found: {chroma_path}")

    try:
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        client = chromadb.PersistentClient(
            path=str(chroma_path),
            settings=chromadb.Settings(anonymized_telemetry=False)
        )
        collection = client.get_collection(name="supportmind", embedding_function=ef)
        
        # Query for tickets only (filter by source_type metadata)
        results = collection.query(
            query_texts=[question],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
            where={"source_type": "ticket"}
        )
    except Exception as e:
        raise AgentError(f"Embedding query failed: {e}") from e

    # Extract ticket numbers from results
    ticket_numbers = []
    if results["metadatas"] and results["metadatas"][0]:
        for meta in results["metadatas"][0]:
            ticket_num = meta.get("source_id")
            if ticket_num and ticket_num not in ticket_numbers:
                ticket_numbers.append(ticket_num)

    if not ticket_numbers:
        return {
            "winner": None,
            "candidates": [],
            "question": question,
            "no_match": True,
        }

    # Step 2: Query DB for ticket metadata including script text
    if not db_path.exists():
        raise AgentError(f"DB not found: {db_path}")

    engine = create_engine(f"sqlite:///{db_path}")
    candidates = []

    try:
        with engine.connect() as conn:
            for ticket_num in ticket_numbers:
                # Get ticket data
                ticket_query = text("""
                    SELECT 
                        Ticket_Number,
                        Status,
                        Tier,
                        Module,
                        Category,
                        Resolution,
                        KB_Article_ID,
                        Script_ID,
                        Description
                    FROM Tickets 
                    WHERE Ticket_Number = :ticket_num
                """)
                
                result = conn.execute(ticket_query, {"ticket_num": ticket_num})
                row = result.fetchone()
                
                if row:
                    # Get script text if script_id exists
                    script_text = ""
                    if row.Script_ID:
                        script_query = text("""
                            SELECT Script_Text_Sanitized 
                            FROM Scripts_Master 
                            WHERE Script_ID = :script_id
                        """)
                        script_result = conn.execute(script_query, {"script_id": row.Script_ID})
                        script_row = script_result.fetchone()
                        if script_row and script_row.Script_Text_Sanitized:
                            script_text = script_row.Script_Text_Sanitized
                    
                    candidates.append({
                        "ticket_number": row.Ticket_Number,
                        "status": row.Status,
                        "tier": row.Tier,
                        "module": row.Module,
                        "category": row.Category,
                        "resolution": row.Resolution or "",
                        "kb_article_id": row.KB_Article_ID or "",
                        "script_id": row.Script_ID or "",
                        "script_text": script_text,
                        "description": row.Description or "",
                    })
    except Exception as e:
        raise AgentError(f"Database query failed: {e}") from e
    finally:
        engine.dispose()

    if not candidates:
        return {
            "ranked_results": [],
            "question": question,
            "no_match": True,
        }

    # Step 3: Use OpenAI to rank all candidates
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        raise AgentError("OPENAI_API_KEY not set in .env")

    try:
        openai_client = OpenAI(api_key=api_key.strip())
    except Exception as e:
        raise AgentError(f"OpenAI client init failed: {e}") from e

    # Prepare candidates for OpenAI (truncate long fields)
    candidates_for_llm = []
    for i, c in enumerate(candidates):
        candidates_for_llm.append({
            "index": i,
            "ticket_number": c["ticket_number"],
            "status": c["status"],
            "tier": c["tier"],
            "module": c["module"],
            "category": c["category"],
            "description": c["description"][:300],
            "resolution": c["resolution"][:300],
            "has_kb_article": bool(c["kb_article_id"]),
            "has_script": bool(c["script_id"]),
        })

    system_prompt = """You are a support ticket ranker. Given a user's support question and a list of similar resolved tickets, rank ALL of them from best to worst match.

Return a JSON object with:
{
    "rankings": [
        {
            "index": <candidate index>,
            "rank": 1,
            "rationale": "<one sentence why this is ranked #1>"
        },
        {
            "index": <candidate index>,
            "rank": 2,
            "rationale": "<one sentence why this is ranked #2>"
        },
        ... (rank all candidates)
    ]
}

Rank based on:
- Similarity to the user's issue
- Quality of resolution
- Availability of KB article and script
- Module/category match

Return only valid JSON, no markdown."""

    user_content = f"""User question: {question}

Candidate tickets:
{json.dumps(candidates_for_llm, indent=2)}"""

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
        )
    except Exception as e:
        raise AgentError(f"OpenAI API call failed: {e}") from e

    # Parse OpenAI response
    response_text = (response.choices[0].message.content or "").strip()
    
    # Strip markdown if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines)

    try:
        decision = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise AgentError(f"OpenAI returned invalid JSON: {e}") from e

    rankings = decision.get("rankings", [])
    
    if not rankings:
        return {
            "ranked_results": [],
            "question": question,
            "no_match": True,
        }

    # Step 4: Build ranked results with full data
    ranked_results = []
    for ranking in rankings:
        idx = ranking.get("index", -1)
        if idx < 0 or idx >= len(candidates):
            continue
        
        candidate = candidates[idx]
        ranked_results.append({
            "rank": ranking.get("rank", 0),
            "ticket_number": candidate["ticket_number"],
            "kb_article_id": candidate["kb_article_id"],
            "script_id": candidate["script_id"],
            "script_text": candidate["script_text"],
            "rationale": ranking.get("rationale", ""),
            "module": candidate["module"],
            "category": candidate["category"],
            "status": candidate["status"],
            "tier": candidate["tier"],
        })
    
    # Sort by rank to ensure proper order
    ranked_results.sort(key=lambda x: x["rank"])

    result = {
        "ranked_results": ranked_results,
        "question": question,
        "no_match": False,
    }

    # Outgoing hook: guardrails agent can validate
    if outgoing_hook is not None:
        result = outgoing_hook(result, context)

    return result
