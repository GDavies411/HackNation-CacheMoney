"""
Interactive support chat: comparator agent finds best matching KB article and script.

The agent queries embeddings for similar tickets, pulls their metadata from the database,
and uses OpenAI to select the best match. Returns KB article and script IDs with rationale.

Run from repo root:
  python scripts/run_case_in.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.agent import AgentError, compare, incoming_hook, outgoing_hook

DEFAULT_DB = REPO_ROOT / "data" / "supportmind.db"
DEFAULT_CHROMA = REPO_ROOT / "data" / "chroma"
QUIT_COMMANDS = ("quit", "exit", "q", "bye")


def format_response(result: dict) -> str:
    """Format comparator result into readable text."""
    if result.get("no_match"):
        return "No relevant matches found. The issue may require escalation or a new solution."
    
    ranked_results = result.get("ranked_results", [])
    if not ranked_results:
        return "Could not rank the candidates."
    
    lines = []
    lines.append("=== RANKED RESULTS ===")
    lines.append("")
    
    for item in ranked_results:
        rank = item["rank"]
        lines.append(f"RANK {rank}: {item['ticket_number']}")
        lines.append(f"  Module: {item['module']} | Category: {item['category']}")
        lines.append(f"  Rationale: {item['rationale']}")
        
        if item.get('kb_article_id'):
            lines.append(f"  KB Article: {item['kb_article_id']}")
        else:
            lines.append(f"  KB Article: None")
        
        if item.get('script_id'):
            lines.append(f"  Script: {item['script_id']}")
            if item.get('script_text'):
                script_preview = item['script_text'][:150].replace('\n', ' ')
                lines.append(f"  Script Preview: {script_preview}...")
        else:
            lines.append(f"  Script: None")
        
        lines.append("")
    
    return "\n".join(lines)


def main() -> None:
    if not DEFAULT_CHROMA.exists():
        print("Chroma index not found. Run: python scripts/run_build_index.py")
        sys.exit(1)
    if not DEFAULT_DB.exists():
        print("DB not found. Run: python scripts/run_etl.py")
        sys.exit(1)

    # Check API key up front
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set. Add it to .env in the repo root.")
        sys.exit(1)

    print("Comparator agent (embeddings + OpenAI). Describe your support issue.")
    print("Returns ranked results with KB articles and scripts.")
    if outgoing_hook is not None:
        print("Outgoing hook: registered (e.g. guardrails).")
    if incoming_hook is not None:
        print("Incoming hook: registered.")
    print("Type 'quit', 'exit', or 'q' to end.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in QUIT_COMMANDS:
            print("Goodbye.")
            break

        try:
            result = compare(user_input, DEFAULT_CHROMA, DEFAULT_DB, top_k=5)
            response = format_response(result)
            print("Agent:", response)
        except AgentError as e:
            print("Agent error:", e)
        print()


if __name__ == "__main__":
    # --- To orchestrate with guardrails agent: ---
    # import src.agent.agent as agent_module
    # agent_module.outgoing_hook = lambda result, ctx: your_guardrails.check(result, ctx)
    # agent_module.incoming_hook = lambda q, ctx: your_triage.process(q, ctx)
    main()
