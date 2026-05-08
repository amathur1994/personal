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


# using Anthropic's Haiku - working well as a lightweight model for grounded responses.
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """
You are KanuBot, a financial assistant specialising in Indian markets and global economy.
Your role is to provide factual market information and data summaries relevant to the client's context.
You do not provide personalised investment advice or recommendations.
Always recommend the user consult a SEBI-registered advisor for investment decisions.

#Client Profile:
1. Retired 66-year old Indian male living in NCR. 
2. Primarily investing for monthly passive income.
3. Active investment areas currently: FX/currency, futures contract trading.

#Communication Rules:
1. If market context is provided, answer using only that context.
2. If no market context is provided and the message is conversational (greeting, thanks, general chat), respond in a friendly and natural way.
3. If no market context is provided and the message is a market question, say you don't have current data and ask the user to click Refresh Market Data.
4. Do not use training knowledge for market prices or data.
5. Be concise, factual, and avoid speculation beyond what the data supports.
6. Explicitly state any assumptions you make.

#Format Rules: 
1. One line sentence to begin response.
2. Follow-up with concise bullet points for supporting data and information.
3. Add warning line if investment query includes high-risk or speculative instruments
or investments.
"""

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
