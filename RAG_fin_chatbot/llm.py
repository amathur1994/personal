"""
LLM layer for finews_bot.

Passes retrieved context + user query to a locally running Mistral 7B
model via Ollama and returns a grounded financial summary response.
Supports conversation history for multi-turn memory.
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"

SYSTEM_PROMPT = """You are FinBot, a financial assistant specialising in Indian markets and the global factors that impact them.
Answer the user's question using only the context provided below.
Be concise, factual, and avoid speculation beyond what the data supports.
If the context doesn't contain enough information to answer, say so clearly."""


def build_prompt(context, query, history = None):
    history_block = ""
    if history:
        lines = []
        for turn in history:
            lines.append(f"User: {turn['user']}")
            lines.append(f"Assistant: {turn['assistant']}")
        history_block = "\n## Conversation History\n" + "\n".join(lines) + "\n"

    return f"""{SYSTEM_PROMPT}
{history_block}
## Live Market Context
{context}

## Current Question
{query}

## Answer
"""


def generate(query, context, history = None, stream = False):
    prompt = build_prompt(context, query, history)

    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": stream,
    })

    response.raise_for_status()
    return response.json()["response"]


if __name__ == "__main__":
    from retriever import retrieve, format_context

    query = input("Enter your query: ")
    chunks = retrieve(query)
    context = format_context(chunks)

    print(f"Query: {query}\n")
    print("Answer:\n")
    print(generate(query, context))
