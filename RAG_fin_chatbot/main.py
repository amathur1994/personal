"""
Execution script to launch KanuBot 1.0 — markets summary chatbot.
"""

import gradio as gr
from retriever import retrieve, format_context
from llm import generate

# no. of past conversation turns passed to the LLM memory
MEMORY_WINDOW = 5

HEADER = """
<div style="text-align:center; padding: 8px 0 4px;">
  <h1 style="font-size:2rem; margin-bottom:4px;">📈 KanuBot</h1>
  <p style="color:#555; font-size:1rem; margin:0;">Your personal Indian Markets Guru — powered by live data & Mistral 7B</p>
</div>
"""

EXAMPLE_QUERIES = [
    "Give me a summary of Indian markets today.",
    "How is the rupee performing against the dollar?",
    "What are the latest crude oil prices and how do they affect India?",
    "How are Indian IT stocks doing this week?",
    "What is the current Fed funds rate and how does it impact India?",
    "How is Nifty 50 trending this week?",
    "What's the outlook for Indian pharma stocks?",
]


def refresh_data():
    """Rebuild the vector DB with fresh market data."""
    try:
        from embedder import build_vector_db
        build_vector_db()
        return "✅ Market data refreshed successfully!"
    except Exception as e:
        return f"❌ Refresh failed: {e}"


def chat(message, history):
    """
    Core chat handler called by Gradio on each user message.
    Supports both Gradio 5.x (flat dict list) and older ([user, assistant] pairs) history formats.
    """
    if history and isinstance(history[0], dict):
        pairs = [
            {"user": history[i]["content"], "assistant": history[i + 1]["content"]}
            for i in range(0, len(history) - 1, 2)
            if history[i].get("role") == "user" and history[i + 1].get("role") == "assistant"
        ]
        memory = pairs[-MEMORY_WINDOW:]
    else:
        memory = [
            {"user": h[0], "assistant": h[1]}
            for h in history[-MEMORY_WINDOW:]
        ]

    chunks = retrieve(message)
    if not chunks:
        return (
            "⚠️ No relevant market data found for your query. "
            "Try clicking **Refresh Market Data** to load the latest data first."
        )

    context = format_context(chunks)
    return generate(message, context, history=memory)


# ── Gradio UI ──────────────────────────────────────────────────────────────────

with gr.Blocks(
    title="KanuBot — Indian Markets Chatbot",
    theme=gr.themes.Soft(primary_hue="emerald", secondary_hue="slate"),
    css="""
        #refresh-row { align-items: center; }
        #status-box textarea { font-size: 0.9rem; }
        footer { display: none !important; }
    """,
) as app:

    gr.HTML(HEADER)

    gr.Markdown(
        "> 💡 **Tip:** Click **Refresh Market Data** before your first question to pull in live prices.",
        elem_id="tip-bar",
    )

    with gr.Row(elem_id="refresh-row"):
        refresh_btn = gr.Button("🔄 Refresh Market Data", variant="primary", scale=1, min_width=200)
        refresh_status = gr.Textbox(
            interactive=False,
            scale=4,
            show_label=False,
            placeholder="Status will appear here after refresh...",
            elem_id="status-box",
        )

    gr.ChatInterface(
        fn=chat,
        chatbot=gr.Chatbot(
            height=480,
            label="KanuBot",
            avatar_images=(None, "https://api.dicebear.com/7.x/bottts/svg?seed=kanubot"),
            placeholder="<b>Ask me anything about Indian markets!</b><br>Nifty, Sensex, USD/INR, FIIs, commodities, earnings, macro data...",
            buttons=["copy", "copy_all"],
        ),
        textbox=gr.Textbox(
            placeholder="e.g. How is Nifty trending today?",
            scale=7,
        ),
        examples=EXAMPLE_QUERIES,
        cache_examples=False,
        submit_btn="Send ➤",
    )

    refresh_btn.click(fn=refresh_data, outputs=refresh_status)


if __name__ == "__main__":
    app.launch(share=True)
