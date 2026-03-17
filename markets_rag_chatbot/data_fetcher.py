"""
Data fetching module for finews_bot.

Sources:
  - yfinance   : Stock price history and company fundamentals
  - NewsAPI    : Recent financial news headlines and article summaries
  - FRED       : US macro indicators (interest rates, CPI, unemployment)
  - RSS (Yahoo Finance) : Live market news feed without requiring an API key
"""

import os
import feedparser
import yfinance as yf
from datetime import datetime, timedelta
from newsapi import NewsApiClient
from fredapi import Fred
from dotenv import load_dotenv

load_dotenv()

# load API keys 
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
FRED_API_KEY = os.getenv("FRED_API_KEY")

# fetch equity info from yahoo finance
def fetch_stock_data(tickers: list[str], period: str = "5d"):
    results = []
    for ticker in tickers:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        info = stock.info

        if hist.empty:
            continue

        latest = hist.iloc[-1]
        results.append({
            "ticker":    ticker,
            "name":      info.get("longName", ticker),
            "price":     round(latest["Close"], 2),
            "change_pct": round((latest["Close"] - hist.iloc[0]["Open"]) / hist.iloc[0]["Open"] * 100, 2),
            "volume":    int(latest["Volume"]),
            "market_cap": info.get("marketCap"),
            "summary":   info.get("longBusinessSummary", ""),
        })
    return results

# fetch daily news 
def fetch_news(category: str = "business"):
    client = NewsApiClient(api_key=NEWS_API_KEY)

    response = client.get_top_headlines(
        category=category,
        language="en",
        page_size=20,
    )

    articles = []
    for a in response.get("articles", []):
        articles.append({
            "title":       a["title"],
            "source":      a["source"]["name"],
            "published_at": a["publishedAt"],
            "description": a.get("description", ""),
            "url":         a["url"],
        })
    return articles

# fetch macroeconomic data from US Fed Reserve 
FRED_SERIES = {
    "fed_funds_rate":  "FEDFUNDS",    # Federal funds rate
    "cpi":             "CPIAUCSL",    # Consumer price index (inflation)
    "unemployment":    "UNRATE",      # US unemployment rate
    "10yr_treasury":   "GS10",        # 10-year treasury yield
}

def fetch_macro_indicators() -> dict:
    fred = Fred(api_key=FRED_API_KEY)
    indicators = {}
    for name, series_id in FRED_SERIES.items():
        series = fred.get_series(series_id).dropna()
        indicators[name] = {
            "value": round(series.iloc[-1], 3),
            "date":  series.index[-1].strftime("%Y-%m-%d"),
        }
    return indicators

# fetch yahoo finance latest news feed 
YAHOO_FINANCE_RSS = "https://finance.yahoo.com/news/rssindex"

def fetch_rss_news(max_items: int = 20) -> list[dict]:
    feed = feedparser.parse(YAHOO_FINANCE_RSS)
    articles = []
    for entry in feed.entries[:max_items]:
        articles.append({
            "title":       entry.get("title", ""),
            "published":   entry.get("published", ""),
            "summary":     entry.get("summary", ""),
            "url":         entry.get("link", ""),
        })
    return articles

# combine fetched data 
def fetch_all(tickers):
    print("Fetching stock data:")
    stocks = fetch_stock_data(tickers)

    print("Fetching news (NewsAPI):")
    news = fetch_news()

    print("Fetching macro indicators (FRED):")
    macro = fetch_macro_indicators()

    print("Fetching RSS news (Yahoo Finance):")
    rss = fetch_rss_news()

    return {
        "stocks": stocks,
        "news":   news,
        "macro":  macro,
        "rss":    rss,
    }

if __name__ == "__main__":
    import json
    data = fetch_all(tickers=["AAPL", "MSFT", "GOOGL", "^NSEI"])
    print(json.dumps(data, indent=2, default=str))
