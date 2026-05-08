"""
Chunking and embedding module.

Converts raw fetched data into text chunks, embeds them using a local
HuggingFace sentence-transformer, and stores them in a persistent ChromaDB.
"""
import chromadb
from chromadb.utils import embedding_functions
from data_fetcher import fetch_all, STOCK_TICKERS
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
def news_to_texts(articles, prefix="news"):
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

# convert forex data into natural language text
def forex_to_texts(forex_data):
    results = []
    for f in forex_data:
        pair_id = f["pair"].replace("=X", "")
        # make a readable label e.g. "USDINR" -> "USD/INR"
        label = f"{pair_id[:3]}/{pair_id[3:]}" if len(pair_id) == 6 else pair_id
        text = (
            f"{label} exchange rate is currently {f['price']}. "
            f"It has changed {f['change_pct']}% over the past 5 days."
        )
        results.append((f"forex_{pair_id}", text))
    return results

# convert commodity data into natural language text
def commodity_to_texts(commodities):
    results = []
    for c in commodities:
        commodity_id = c["name"].lower().replace(" ", "_").replace("(", "").replace(")", "")
        text = (
            f"{c['name']} is currently priced at ${c['price']} per unit. "
            f"It has changed {c['change_pct']}% over the past 5 days."
        )
        results.append((f"commodity_{commodity_id}", text))
    return results

# convert crypto data into natural language text
def crypto_to_texts(crypto_data):
    results = []
    for c in crypto_data:
        symbol = c["ticker"].split("-")[0]
        text = (
            f"{c['name']} ({symbol}) is currently trading at ${c['price']}. "
            f"It changed {c['change_pct']}% over the past 5 days with a 24h volume of {c['volume']}."
        )
        results.append((f"crypto_{symbol}", text))
    return results

# convert World Bank India indicators into individual text chunks
def worldbank_to_texts(wb_data):
    label_map = {
        "india_gdp_growth":      "India's GDP Growth (annual %)",
        "india_inflation_cpi":   "India's Inflation CPI (annual %)",
        "india_current_account": "India's Current Account Balance (USD)",
        "india_fdi_inflows":     "India's FDI Net Inflows (USD)",
        "india_trade_pct_gdp":   "India's Trade as % of GDP",
    }
    results = []
    for name, val in wb_data.items():
        label = label_map.get(name, name.replace("_", " ").title())
        text = f"{label} is {val['value']} as of {val['date']}, according to World Bank data."
        results.append((f"wb_{name}", text))
    return results

# convert economic calendar events into natural language text
def calendar_to_texts(events):
    results = []
    for i, e in enumerate(events):
        country_label = e["country"].replace("-", " ").title()
        previous = e.get("previous_value", "N/A") or "N/A"
        forecast = e.get("forecast_value", "N/A") or "N/A"
        text = (
            f"Upcoming economic event: {e['event_name']} for {country_label} on {e['date']}. "
            f"Previous value: {previous}. Forecast: {forecast}."
        )
        country_slug = e["country"].replace("-", "_")
        results.append((f"cal_{country_slug}_{i}", text))
    return results


def nse_futures_to_texts(futures_data):
    results = []
    for f in futures_data:
        text = (
            f"{f['ticker']} near-month futures expiring {f['expiryDate']} "
            f"last traded at {f['lastPrice']}. "
            f"Change: {f['pChange']}%. Open Interest: {f['openInterest']} contracts, "
            f"changed {f['pchangeinOpenInterest']}% today. "
            f"Daily volatility: {f['dailyVolatility']}%. "
            f"Annualised volatility: {f['annualisedVolatility']}%. "
            f"Contracts traded today: {f['numberOfContractsTraded']}."
        )
        results.append((f"fut_{f['ticker']}", text))
    return results

def mcx_futures_to_texts(mcx_data):
    results = []
    for m in mcx_data:
        expiry = str(m.get("ExpiryDate", "")).replace(" ", "").replace("-", "")
        text = (
            f"{m['Symbol']} MCX futures expiring {m['ExpiryDate']} closed at {m['Close']}. "
            f"High: {m['High']}, Low: {m['Low']}. Volume: {m['Volume']} lots. "
            f"Open Interest: {m['OpenInterest']} contracts."
        )
        results.append((f"mcx_{m['Symbol']}_{expiry}", text))
    return results


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
    data = fetch_all(tickers=STOCK_TICKERS)

    print("Building chunks ...")
    chunks = (
        stocks_to_texts(data["stocks"])
        + news_to_texts(data["news"], prefix="news")
        + news_to_texts(data["rss"], prefix="rss")
        + macro_to_texts(data["macro"])
        + forex_to_texts(data["forex"])
        + commodity_to_texts(data["commodities"])
        + crypto_to_texts(data["crypto"])
        + worldbank_to_texts(data["worldbank"])
        + calendar_to_texts(data["calendar"])
        + nse_futures_to_texts(data["nse_futures"])
        + mcx_futures_to_texts(data["mcx_futures"])
    )
    print(f"  Total chunks: {len(chunks)}")

    print("Embedding and storing in ChromaDB ...")
    collection = get_collection()
    upsert_chunks(collection, chunks)

    print(f"Done. Vector DB persisted at: {CHROMA_PATH}")
    return collection

if __name__ == "__main__":
    build_vector_db()
