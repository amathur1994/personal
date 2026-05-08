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
import pandas as pd
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

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
}

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

# NSE futures tickers — indices and large-cap stocks
NSE_FUTURES_TICKERS = [
    "NIFTY", "BANKNIFTY", "HDFCBANK", "ICICIBANK", "SBIN",
    "RELIANCE", "TCS", "INFY", "AXISBANK", "BAJFINANCE",
]

def fetch_nse_futures():
    results = []
    session = requests.Session()
    # establish the session cookie NSE requires before any API calls
    session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=TIMEOUT_SECONDS)
    api_headers = {**NSE_HEADERS, "Accept": "application/json",
                   "Referer": "https://www.nseindia.com"}
    for ticker in NSE_FUTURES_TICKERS:
        try:
            url  = f"https://www.nseindia.com/api/quote-derivative?symbol={ticker}"
            resp = session.get(url, headers=api_headers, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            stocks = resp.json().get("stocks", [])
            if not stocks:
                print(f"  [WARN] NSE API returned no futures data for {ticker}")
                continue
            contract   = stocks[0]
            metadata   = contract.get("metadata", {})
            trade_info = contract.get("marketDeptOrderBook", {}).get("tradeInfo", {})
            other_info = contract.get("marketDeptOrderBook", {}).get("otherInfo", {})
            results.append({
                "ticker":                  ticker,
                "expiryDate":              metadata.get("expiryDate"),
                "lastPrice":               metadata.get("lastPrice"),
                "change":                  metadata.get("change"),
                "pChange":                 metadata.get("pChange"),
                "numberOfContractsTraded": metadata.get("numberOfContractsTraded"),
                "totalTurnover":           metadata.get("totalTurnover"),
                "openInterest":            trade_info.get("openInterest"),
                "changeInOpenInterest":    trade_info.get("changeinOpenInterest"),
                "pchangeinOpenInterest":   trade_info.get("pchangeinOpenInterest"),
                "dailyVolatility":         other_info.get("dailyvolatility"),     # lowercase 'v' in NSE JSON
                "annualisedVolatility":    other_info.get("annualisedVolatility"),
            })
        except Exception as e:
            print(f"  [WARN] NSE futures fetch failed for {ticker}: {e}")
    return results

# MCX symbol → global NYMEX/COMEX yfinance proxy (MCX bhavcopy endpoint is broken)
MCX_SYMBOL_MAP = {
    "CRUDEOIL":   "CL=F",   # NYMEX WTI Crude Oil
    "GOLD":       "GC=F",   # COMEX Gold
    "SILVER":     "SI=F",   # COMEX Silver
    "NATURALGAS": "NG=F",   # NYMEX Natural Gas
    "COPPER":     "HG=F",   # COMEX Copper
    "ZINC":       "ZN=F",   # COMEX Zinc
}

def fetch_mcx_bhavcopy():
    # MCX bhavcopy endpoint returns empty responses for all dates; use global futures as proxies
    results = []
    for mcx_symbol, yf_ticker in MCX_SYMBOL_MAP.items():
        try:
            t    = yf.Ticker(yf_ticker)
            hist = t.history(period="1d", timeout=TIMEOUT_SECONDS)
            if hist.empty:
                print(f"  [WARN] MCX proxy: no yfinance data for {mcx_symbol} ({yf_ticker})")
                continue
            row  = hist.iloc[-1]
            info = t.info
            expiry_ts  = info.get("expireDate")
            expiry_str = (datetime.utcfromtimestamp(expiry_ts).strftime("%d-%b-%Y").upper()
                          if expiry_ts else None)
            results.append({
                "Symbol":       mcx_symbol,
                "ExpiryDate":   expiry_str,
                "Open":         round(float(row["Open"]),  2),
                "High":         round(float(row["High"]),  2),
                "Low":          round(float(row["Low"]),   2),
                "Close":        round(float(row["Close"]), 2),
                "Volume":       int(row["Volume"]),
                "OpenInterest": info.get("openInterest"),
            })
        except Exception as e:
            print(f"  [WARN] MCX proxy fetch failed for {mcx_symbol} ({yf_ticker}): {e}")
    return results

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
    # ThreadPoolExecutor is used instead of asyncio because all fetchers rely on
    # the synchronous `requests` library; threads let them overlap I/O without
    # requiring async rewrites of every fetcher.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    tasks = {
        "stocks":      (fetch_stock_data,        (tickers,), "Stock data fetch failed",           []),
        "news":        (fetch_news,               (),         "News fetch failed",                  []),
        "macro":       (fetch_macro_indicators,   (),         "FRED macro fetch failed",            {}),
        "rss":         (fetch_rss_news,           (),         "RSS fetch failed",                   []),
        "forex":       (fetch_forex_data,         (),         "Forex fetch failed",                 []),
        "commodities": (fetch_commodity_data,     (),         "Commodity fetch failed",             []),
        "crypto":      (fetch_crypto_data,        (),         "Crypto fetch failed",                []),
        "worldbank":   (fetch_worldbank_india,    (),         "World Bank fetch failed",            {}),
        "calendar":    (fetch_economic_calendar,  (),         "Economic calendar fetch failed",     []),
        "nse_futures": (fetch_nse_futures,        (),         "NSE futures fetch failed",           []),
        "mcx_futures": (fetch_mcx_bhavcopy,       (),         "MCX bhavcopy fetch failed",          []),
    }

    PRINT_LABELS = {
        "stocks":      "Fetching stock data:",
        "news":        "Fetching news (NewsAPI):",
        "macro":       "Fetching macro indicators (FRED):",
        "rss":         "Fetching RSS news (Yahoo Finance):",
        "forex":       "Fetching forex data:",
        "commodities": "Fetching commodity data:",
        "crypto":      "Fetching crypto data:",
        "worldbank":   "Fetching World Bank India indicators:",
        "calendar":    "Fetching economic calendar (India + US):",
        "nse_futures": "Fetching NSE futures data:",
        "mcx_futures": "Fetching MCX commodity bhavcopy:",
    }

    results = {}
    with ThreadPoolExecutor(max_workers=11) as executor:
        future_to_key = {}
        for key, (fn, args, _, _default) in tasks.items():
            print(PRINT_LABELS[key])
            future_to_key[executor.submit(fn, *args)] = key

        for future in as_completed(future_to_key):
            key = future_to_key[future]
            _fn, _args, warn_msg, default = tasks[key]
            try:
                results[key] = future.result()
            except Exception as e:
                print(f"  [WARN] {warn_msg}: {e}")
                results[key] = default

    return {
        "fetched_at":  (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S IST"),
        "stocks":      results["stocks"],
        "news":        results["news"],
        "macro":       results["macro"],
        "rss":         results["rss"],
        "forex":       results["forex"],
        "commodities": results["commodities"],
        "crypto":      results["crypto"],
        "worldbank":   results["worldbank"],
        "calendar":    results["calendar"],
        "nse_futures": results["nse_futures"],
        "mcx_futures": results["mcx_futures"],
    }

if __name__ == "__main__":
    import json
    data = fetch_all(tickers=STOCK_TICKERS)
    print(json.dumps(data, indent=2, default=str))
