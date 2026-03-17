"""
Entry point for finews_bot.

Orchestrates the full pipeline:
  1. (Optional) Refresh the vector DB with live market data
  2. Accept user queries in an interactive loop
  3. Retrieve relevant context from ChromaDB
  4. Generate a grounded response via the local LLM
"""

import sys
from retriever import retrieve, format_context
from llm import generate


BANNER = """
╔══════════════════════════════════════╗
║         finews_bot  📈               ║
║  Your AI-powered financial assistant ║
╚══════════════════════════════════════╝
Type 'refresh' to reload live market data.
Type 'quit' or 'exit' to quit.
"""


def refresh_data():
    """Rebuild the vector DB with fresh market data."""
    print("\nRefreshing market data — this may take a moment...")
    from embedder import build_vector_db
    build_vector_db()
    print("Vector DB updated.\n")


def answer(query: str) -> str:
    """Retrieve context and generate a response for the given query."""
    chunks = retrieve(query)
    if not chunks:
        return "No relevant market data found for your query. Try refreshing with 'refresh'."
    context = format_context(chunks)
    return generate(query, context)


def run():
    print(BANNER)

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            sys.exit(0)

        if not query:
            continue

        if query.lower() in {"quit", "exit"}:
            print("Goodbye.")
            sys.exit(0)

        if query.lower() == "refresh":
            refresh_data()
            continue

        print("\nAssistant:", answer(query), "\n")


if __name__ == "__main__":
    run()
