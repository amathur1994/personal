"""
LLM layer for finews_bot.

Passes retrieved context + user query to a locally running Mistral 7B
model via Ollama and returns a grounded financial summary response.
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"

SYSTEM_PROMPT = """You are a financial assistant with access to live market data.
Answer the user's question using only the context provided below.
Be concise, factual, and avoid speculation beyond what the data supports.
If the context doesn't contain enough information to answer, say so clearly."""


def build_prompt(context, query):
    return f"""{SYSTEM_PROMPT}

## Market Context
{context}

## User Question
{query}

## Answer
"""

def generate(query, context, stream: bool = False):
    prompt = build_prompt(context, query)

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
