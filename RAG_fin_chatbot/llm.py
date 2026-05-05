"""
LLM layer for KanuBot.

Passes retrieved context + user query to Claude Haiku via the Anthropic API
and returns a grounded financial summary response.
Supports conversation history for multi-turn memory.
"""

import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are KanuBot, a financial assistant specialising in Indian markets and the global factors that impact them.
Answer the user's question using only the context provided below.
Be concise, factual, and avoid speculation beyond what the data supports.
If the context doesn't contain enough information to answer, say so clearly."""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def generate(query, context, history=None, **kwargs):
    messages = []

    if history:
        for turn in history:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["assistant"]})

    user_message = f"""## Live Market Context
{context}

## Current Question
{query}"""

    messages.append({"role": "user", "content": user_message})

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return response.content[0].text


if __name__ == "__main__":
    from retriever import retrieve, format_context

    query = input("Enter your query: ")
    chunks = retrieve(query)
    context = format_context(chunks)

    print(f"Query: {query}\n")
    print("Answer:\n")
    print(generate(query, context))
