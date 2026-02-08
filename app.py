"""
Streamlit app for testing the comparator agent interactively.

Run from repo root:
    python -m streamlit run app.py
"""

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from src.agent import AgentError, compare

DEFAULT_DB = REPO_ROOT / "data" / "supportmind.db"
DEFAULT_CHROMA = REPO_ROOT / "data" / "chroma"


def format_response(result: dict) -> str:
    """Format comparator result into readable text."""
    if result.get("no_match"):
        return "❌ No relevant matches found. The issue may require escalation or a new solution."
    
    ranked_results = result.get("ranked_results", [])
    if not ranked_results:
        return "❌ Could not rank the candidates."
    
    lines = []
    lines.append("## 📊 Ranked Results")
    lines.append("")
    
    for item in ranked_results:
        rank = item["rank"]
        emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
        
        lines.append(f"### {emoji} Rank {rank}: {item['ticket_number']}")
        lines.append(f"**Module:** {item['module']} | **Category:** {item['category']}")
        lines.append(f"**Rationale:** {item['rationale']}")
        lines.append("")
        
        if item.get('kb_article_id'):
            lines.append(f"📄 **KB Article:** `{item['kb_article_id']}`")
        else:
            lines.append("📄 **KB Article:** None")
        
        if item.get('script_id'):
            lines.append(f"📜 **Script:** `{item['script_id']}`")
            if item.get('script_text'):
                # Show truncated preview in main display
                script_preview = item['script_text'][:200]
                lines.append(f"**Script Preview:**")
                lines.append(f"```\n{script_preview}{'...' if len(item['script_text']) > 200 else ''}\n```")
                lines.append(f"*Full script available in details below*")
        else:
            lines.append("📜 **Script:** None")
        
        lines.append("")
        lines.append("---")
        lines.append("")
    
    return "\n".join(lines)


def main():
    st.set_page_config(page_title="SupportMind Comparator", page_icon="🔍", layout="wide")
    
    st.title("🔍 SupportMind Comparator Agent")
    st.markdown("Find the best matching KB article and script for support questions")
    
    # Check prerequisites
    if not DEFAULT_CHROMA.exists():
        st.error("❌ Chroma index not found. Run: `python scripts/run_build_index.py`")
        st.stop()
    
    if not DEFAULT_DB.exists():
        st.error("❌ DB not found. Run: `python scripts/run_etl.py`")
        st.stop()
    
    import os
    if not os.getenv("OPENAI_API_KEY"):
        st.error("❌ OPENAI_API_KEY not set. Add it to `.env` in the repo root.")
        st.stop()
    
    st.success("I'm here to help you with any of your RealPage support questions!")
    
    # Sidebar settings
    with st.sidebar:
        st.header("Settings")
        top_k = st.slider("Number of candidates to compare", min_value=3, max_value=10, value=5)
        model = st.selectbox("OpenAI Model", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], index=0)
        
        st.markdown("---")
        st.markdown("### How it works")
        st.markdown("""
        1. Query embeddings for similar ticket descriptions
        2. Pull ticket metadata and scripts from database
        3. Use OpenAI to rank all candidates
        4. Return ranked results with KB articles and scripts
        """)
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and "metadata" in message:
                with st.expander("View details"):
                    st.json(message["metadata"])
    
    # Chat input
    if prompt := st.chat_input("Describe your support issue..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Searching for best match..."):
                try:
                    result = compare(
                        prompt,
                        DEFAULT_CHROMA,
                        DEFAULT_DB,
                        top_k=top_k,
                        model=model
                    )
                    
                    # Format and display response
                    formatted_response = format_response(result)
                    st.markdown(formatted_response)
                    
                    # Show metadata in expander
                    metadata = {
                        "num_ranked": len(result.get("ranked_results", [])),
                        "no_match": result["no_match"],
                        "top_3": result.get("ranked_results", [])[:3]  # Show top 3 in summary
                    }
                    
                    with st.expander("📋 View full details & complete scripts"):
                        st.markdown("### Full Ranked Results")
                        for item in result.get("ranked_results", []):
                            st.markdown(f"**Rank {item['rank']}: {item['ticket_number']}**")
                            st.markdown(f"Module: {item['module']} | Category: {item['category']}")
                            st.markdown(f"Rationale: {item['rationale']}")
                            
                            if item.get('kb_article_id'):
                                st.markdown(f"📄 KB Article: `{item['kb_article_id']}`")
                            
                            if item.get('script_id'):
                                st.markdown(f"📜 Script: `{item['script_id']}`")
                                if item.get('script_text'):
                                    st.markdown(f"**Full Script Text** ({len(item['script_text'])} characters):")
                                    st.code(item['script_text'], language="text")
                            
                            st.markdown("---")
                        
                        st.markdown("### Raw JSON Data")
                        st.json(result)
                    
                    # Add assistant response to chat history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": formatted_response,
                        "metadata": metadata
                    })
                    
                except AgentError as e:
                    error_msg = f"❌ Agent error: {e}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
                except Exception as e:
                    error_msg = f"❌ Unexpected error: {e}"
                    st.error(error_msg)
                    import traceback
                    st.code(traceback.format_exc())
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
    
    # Clear chat button
    if st.sidebar.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()


if __name__ == "__main__":
    main()
