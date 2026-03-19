"""
Fetches the up-to-date markets/macroeconomic data from various
online sources. Leverages open API access from various US-based
and global sources. Focus: Indian economy and markets, plus major
global indicators that impact India.

list of sources:
  - yfinance        : Stock price history, forex, commodities, crypto
  - NewsAPI         : Recent financial news headlines and article summaries
  - FRED            : US macro indicators (interest rates, CPI, unemployment)
  - RSS (Yahoo Finance) : Live market news feed without requiring an API key
  - World Bank      : Indian economic indicators (GDP, inflation, FDI, etc.)
  - Trading Economics : Upcoming economic calendar events (India + US)
"""
import os
import feedparser
import yfinance as yf
from datetime import datetime, timedelta
from newsapi import NewsApiClient
from fredapi import Fred
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import wbgapi as wb
_WBGAPI_AVAILABLE = True


load_dotenv()

# load API keys
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
FRED_API_KEY = os.getenv("FRED_API_KEY")

TIMEOUT_SECONDS = 15

# default stock tickers — Indian indices, large-caps, and global benchmarks
STOCK_TICKERS = [
    # Indian indices
    "^NSEI",         # Nifty 50
    "^BSESN",        # BSE Sensex
    "^NSEBANK",      # Nifty Bank
    "^CNXIT",        # Nifty IT
    "^NSMIDCP",      # Nifty Midcap 100

    # Indian large-caps — financials
    "HDFCBANK.NS",   # HDFC Bank
    "ICICIBANK.NS",  # ICICI Bank
    "SBIN.NS",       # State Bank of India
    "KOTAKBANK.NS",  # Kotak Mahindra Bank
    "AXISBANK.NS",   # Axis Bank
    "BAJFINANCE.NS", # Bajaj Finance

    # Indian large-caps — IT
    "TCS.NS",        # Tata Consultancy Services
    "INFY.NS",       # Infosys
    "HCLTECH.NS",    # HCL Technologies
    "WIPRO.NS",      # Wipro
    "TECHM.NS",      # Tech Mahindra

    # Indian large-caps — energy & industrials
    "RELIANCE.NS",   # Reliance Industries
    "ONGC.NS",       # ONGC
    "NTPC.NS",       # NTPC
    "POWERGRID.NS",  # Power Grid Corp
    "ADANIENT.NS",   # Adani Enterprises

    # Indian large-caps — consumer & auto
    "HINDUNILVR.NS", # Hindustan Unilever
    "ITC.NS",        # ITC
    "MARUTI.NS",     # Maruti Suzuki
    "TITAN.NS",      # Titan
    "ASIANPAINT.NS", # Asian Paints
    "NESTLEIND.NS",  # Nestle India
    "BHARTIARTL.NS", # Bharti Airtel

    # Global benchmarks (for India context)
    "AAPL",          # Apple
    "MSFT",          # Microsoft
    "GOOGL",         # Alphabet
]

# fetch equity info from yahoo finance
def fetch_stock_data(tickers: list[str], period: str = "5d"):
    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, timeout=TIMEOUT_SECONDS)
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
        except Exception as e:
            print(f"  [WARN] Failed to fetch stock data for {ticker}: {e}")
    return results

# fetch daily news
def fetch_news(category: str = "business"):
    client = NewsApiClient(api_key=NEWS_API_KEY)

    try:
        response = client.get_top_headlines(
            category=category,
            language="en",
            page_size=20,
        )
    except requests.exceptions.Timeout:
        print("  [WARN] NewsAPI request timed out, skipping.")
        return []
    except Exception as e:
        print(f"  [WARN] NewsAPI fetch failed: {e}")
        return []

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

def fetch_macro_indicators():
    fred = Fred(api_key=FRED_API_KEY)
    indicators = {}
    for name, series_id in FRED_SERIES.items():
        try:
            series = fred.get_series(series_id).dropna()
            indicators[name] = {
                "value": round(series.iloc[-1], 3),
                "date":  series.index[-1].strftime("%Y-%m-%d"),
            }
        except requests.exceptions.Timeout:
            print(f"  [WARN] FRED request timed out for {name} ({series_id}), skipping.")
        except Exception as e:
            print(f"  [WARN] FRED fetch failed for {name} ({series_id}): {e}")
    return indicators

# fetch yahoo finance latest news feed
YAHOO_FINANCE_RSS = "https://finance.yahoo.com/news/rssindex"

def fetch_rss_news(max_items: int = 20):
    try:
        feed = feedparser.parse(YAHOO_FINANCE_RSS, request_headers={"User-Agent": "Mozilla/5.0"})
        if feed.get("bozo") and not feed.entries:
            raise ValueError(feed.get("bozo_exception", "RSS parse error"))
    except Exception as e:
        print(f"  [WARN] RSS feed fetch failed: {e}")
        return []

    articles = []
    for entry in feed.entries[:max_items]:
        articles.append({
            "title":       entry.get("title", ""),
            "published":   entry.get("published", ""),
            "summary":     entry.get("summary", ""),
            "url":         entry.get("link", ""),
        })
    return articles

# fetch forex currency pairs via yfinance
FOREX_PAIRS = ["USDINR=X", "EURINR=X", "GBPINR=X", "JPYINR=X", "EURUSD=X", "GBPUSD=X"]

def fetch_forex_data(pairs: list[str] = FOREX_PAIRS, period: str = "5d"):
    results = []
    for pair in pairs:
        try:
            ticker = yf.Ticker(pair)
            hist = ticker.history(period=period, timeout=TIMEOUT_SECONDS)

            if hist.empty:
                continue

            latest = hist.iloc[-1]
            results.append({
                "pair":       pair,
                "price":      round(latest["Close"], 4),
                "change_pct": round((latest["Close"] - hist.iloc[0]["Open"]) / hist.iloc[0]["Open"] * 100, 2),
                "period":     period,
            })
        except Exception as e:
            print(f"  [WARN] Failed to fetch forex data for {pair}: {e}")
    return results

# fetch commodity prices via yfinance
COMMODITY_TICKERS = ["GC=F", "SI=F", "CL=F", "NG=F"]
COMMODITY_NAMES = {
    "GC=F": "Gold",
    "SI=F": "Silver",
    "CL=F": "Crude Oil (WTI)",
    "NG=F": "Natural Gas",
}

def fetch_commodity_data(tickers: list[str] = COMMODITY_TICKERS, period: str = "5d"):
    results = []
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period=period, timeout=TIMEOUT_SECONDS)

            if hist.empty:
                continue

            latest = hist.iloc[-1]
            results.append({
                "ticker":     ticker,
                "name":       COMMODITY_NAMES.get(ticker, ticker),
                "price":      round(latest["Close"], 2),
                "change_pct": round((latest["Close"] - hist.iloc[0]["Open"]) / hist.iloc[0]["Open"] * 100, 2),
                "period":     period,
            })
        except Exception as e:
            print(f"  [WARN] Failed to fetch commodity data for {ticker}: {e}")
    return results

# fetch cryptocurrency prices via yfinance
CRYPTO_TICKERS = ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD"]
CRYPTO_NAMES = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "BNB-USD": "BNB",
    "SOL-USD": "Solana",
}

def fetch_crypto_data(tickers: list[str] = CRYPTO_TICKERS, period: str = "5d"):
    results = []
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period=period, timeout=TIMEOUT_SECONDS)

            if hist.empty:
                continue

            latest = hist.iloc[-1]
            results.append({
                "ticker":     ticker,
                "name":       CRYPTO_NAMES.get(ticker, ticker),
                "price":      round(latest["Close"], 2),
                "change_pct": round((latest["Close"] - hist.iloc[0]["Open"]) / hist.iloc[0]["Open"] * 100, 2),
                "volume":     int(latest["Volume"]),
                "period":     period,
            })
        except Exception as e:
            print(f"  [WARN] Failed to fetch crypto data for {ticker}: {e}")
    return results

# fetch Indian macro indicators from World Bank
WORLDBANK_INDIA_SERIES = {
    "india_gdp_growth":      "NY.GDP.MKTP.KD.ZG",   # GDP growth (annual %)
    "india_inflation_cpi":   "FP.CPI.TOTL.ZG",      # Inflation, consumer prices (annual %)
    "india_current_account": "BN.CAB.XOKA.CD",      # Current account balance (BoP, current US$)
    "india_fdi_inflows":     "BX.KLT.DINV.CD.WD",   # FDI, net inflows (BoP, current US$)
    "india_trade_pct_gdp":   "NE.TRD.GNFS.ZS",      # Trade (% of GDP)
}

def fetch_worldbank_india():
    if not _WBGAPI_AVAILABLE:
        return {}

    indicators = {}
    for name, series_id in WORLDBANK_INDIA_SERIES.items():
        try:
            # mrv=5 to get recent rows; dropna() to skip missing values
            df = wb.data.DataFrame(series_id, economy="IND", mrv=5)
            col = df["IND"] if "IND" in df.columns else df.iloc[:, 0]
            series = col.dropna()

            if series.empty:
                print(f"  [WARN] No data returned from World Bank for {name}, skipping.")
                continue

            indicators[name] = {
                "value": round(float(series.iloc[-1]), 3),
                "date":  str(series.index[-1]).replace("YR", ""),
            }
        except requests.exceptions.Timeout:
            print(f"  [WARN] World Bank request timed out for {name}, skipping.")
        except Exception as e:
            print(f"  [WARN] World Bank fetch failed for {name}: {e}")
    return indicators

# fetch upcoming economic calendar events (India + US) from Trading Economics
CALENDAR_COUNTRIES = ["india", "united-states"]

def fetch_economic_calendar(countries: list[str] = CALENDAR_COUNTRIES, days_ahead: int = 7):
    events = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    for country in countries:
        url = f"https://tradingeconomics.com/{country}/calendar"
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", {"id": "calendar"})
            if table is None:
                table = soup.find("table")
            if table is None:
                print(f"  [WARN] Could not find calendar table for {country}, skipping.")
                continue

            cutoff = datetime.utcnow() + timedelta(days=days_ahead)
            for row in table.find_all("tr")[1:]:   # skip header
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) < 3:
                    continue

                # typical column order: date, country/category, event, previous, forecast, actual
                event_date_str = cols[0] if cols[0] else ""
                event_name     = cols[2] if len(cols) > 2 else cols[1]
                previous       = cols[3] if len(cols) > 3 else ""
                forecast       = cols[4] if len(cols) > 4 else ""

                events.append({
                    "event_name":      event_name,
                    "country":         country,
                    "date":            event_date_str,
                    "previous_value":  previous,
                    "forecast_value":  forecast,
                })

        except requests.exceptions.Timeout:
            print(f"  [WARN] Economic calendar request timed out for {country}, skipping.")
        except Exception as e:
            print(f"  [WARN] Economic calendar fetch failed for {country}: {e}")

    return events

# combine fetched data
def fetch_all(tickers):
    print("Fetching stock data:")
    try:
        stocks = fetch_stock_data(tickers)
    except Exception as e:
        print(f"  [WARN] Stock data fetch failed: {e}")
        stocks = []

    print("Fetching news (NewsAPI):")
    try:
        news = fetch_news()
    except Exception as e:
        print(f"  [WARN] News fetch failed: {e}")
        news = []

    print("Fetching macro indicators (FRED):")
    try:
        macro = fetch_macro_indicators()
    except Exception as e:
        print(f"  [WARN] FRED macro fetch failed: {e}")
        macro = {}

    print("Fetching RSS news (Yahoo Finance):")
    try:
        rss = fetch_rss_news()
    except Exception as e:
        print(f"  [WARN] RSS fetch failed: {e}")
        rss = []

    print("Fetching forex data:")
    try:
        forex = fetch_forex_data()
    except Exception as e:
        print(f"  [WARN] Forex fetch failed: {e}")
        forex = []

    print("Fetching commodity data:")
    try:
        commodities = fetch_commodity_data()
    except Exception as e:
        print(f"  [WARN] Commodity fetch failed: {e}")
        commodities = []

    print("Fetching crypto data:")
    try:
        crypto = fetch_crypto_data()
    except Exception as e:
        print(f"  [WARN] Crypto fetch failed: {e}")
        crypto = []

    print("Fetching World Bank India indicators:")
    try:
        worldbank = fetch_worldbank_india()
    except Exception as e:
        print(f"  [WARN] World Bank fetch failed: {e}")
        worldbank = {}

    print("Fetching economic calendar (India + US):")
    try:
        calendar = fetch_economic_calendar()
    except Exception as e:
        print(f"  [WARN] Economic calendar fetch failed: {e}")
        calendar = []

    return {
        "fetched_at":  (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S IST"),
        "stocks":      stocks,
        "news":        news,
        "macro":       macro,
        "rss":         rss,
        "forex":       forex,
        "commodities": commodities,
        "crypto":      crypto,
        "worldbank":   worldbank,
        "calendar":    calendar,
    }

if __name__ == "__main__":
    import json
    data = fetch_all(tickers=STOCK_TICKERS)
    print(json.dumps(data, indent=2, default=str))
