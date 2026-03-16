"""
Chunking and embedding module for finews_bot.

Converts raw fetched data into text chunks, embeds them using a local
HuggingFace sentence-transformer, and stores them in a persistent ChromaDB.
"""
import chromadb
from chromadb.utils import embedding_functions
from data_fetcher import fetch_all

TICKERS = ["AAPL", "MSFT", "GOOGL", "^NSEI"]
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "finews"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# convert stock data into natural language text 
def stocks_to_texts(stocks):
    results = []
    for s in stocks:
        text = (
            f"{s['name']} ({s['ticker']}) is currently priced at {s['price']}. "
            f"It changed {s['change_pct']}% over the past 5 days with a volume of {s['volume']}. "
            f"{s['summary'][:500]}"
        ).strip()
        results.append((f"stock_{s['ticker']}", text))
    return results

# convert the news info into plain text
def news_to_texts(articles, prefix = "news"):
    results = []
    for i, a in enumerate(articles):
        text = f"{a['title']}. {a.get('description', '')} {a.get('summary', '')}".strip()
        if text:
            results.append((f"{prefix}_{i}", text))
    return results

# convert macro econ data into US 
def macro_to_texts(macro):
    lines = []
    for name, val in macro.items():
        lines.append(f"{name.replace('_', ' ').title()}: {val['value']} (as of {val['date']})")
    text = "Current US macro indicators — " + ". ".join(lines)
    return [("macro_indicators", text)]


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    return client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)


def upsert_chunks(collection, chunks):
    if not chunks:
        return
    ids = [c[0] for c in chunks]
    docs = [c[1] for c in chunks]
    collection.upsert(ids=ids, documents=docs)
    print(f"  Upserted {len(chunks)} chunks.")

# run the data fetch + embedding pipeline 
def build_vector_db():
    print("Fetching fresh data ...")
    data = fetch_all(tickers=TICKERS)

    print("Building chunks ...")
    chunks = (
        stocks_to_texts(data["stocks"])
        + news_to_texts(data["news"], prefix="news")
        + news_to_texts(data["rss"], prefix="rss")
        + macro_to_texts(data["macro"])
    )
    print(f"  Total chunks: {len(chunks)}")
    print("look at your chunked data:")
    print(chunks)

    print("Embedding and storing in ChromaDB ...")
    collection = get_collection()
    upsert_chunks(collection, chunks)

    print(f"Done. Vector DB persisted at: {CHROMA_PATH}")
    return collection

if __name__ == "__main__":
    build_vector_db()
