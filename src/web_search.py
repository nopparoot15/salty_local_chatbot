"""Web search + real-time data for Fahsai.

Sources:
- Gold / FX / crypto price  → Yahoo Finance (no API key)
- General queries           → DuckDuckGo news (ddgs)
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error

# ── ddgs ──────────────────────────────────────────────────────────────────────
_DDGS_OK = False
try:
    from ddgs import DDGS
    _DDGS_OK = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _DDGS_OK = True
    except ImportError:
        pass

# ── Helpers ───────────────────────────────────────────────────────────────────

def _yf(symbol: str) -> float | None:
    """Fetch regularMarketPrice from Yahoo Finance. Returns None on error."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?interval=1d&range=1d")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        return data["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except Exception:
        return None


# ── Special-case data fetchers ─────────────────────────────────────────────

def _get_gold_price() -> str:
    gold_usd = _yf("GC=F")
    usdthb   = _yf("USDTHB=X")
    if gold_usd is None or usdthb is None:
        return ""
    per_gram     = gold_usd / 31.1035 * usdthb
    bar_thb      = per_gram * 15.244 * 0.9999   # ทองแท่ง 99.99%
    jewel_thb    = per_gram * 15.244 * 0.965    # ทองรูปพรรณ 96.5%
    return (
        f"[ราคาทองคำปัจจุบัน (Yahoo Finance)]\n"
        f"ทองแท่ง 99.99%  : {bar_thb:,.0f} บาท/บาท(น้ำหนัก)\n"
        f"ทองรูปพรรณ 96.5%: {jewel_thb:,.0f} บาท/บาท(น้ำหนัก)\n"
        f"ราคาตลาดโลก     : {gold_usd:,.2f} USD/troy oz\n"
        f"อัตราแลกเปลี่ยน  : 1 USD = {usdthb:.2f} THB"
    )


def _get_fx(pair_symbol: str, pair_label: str) -> str:
    rate = _yf(pair_symbol)
    if rate is None:
        return ""
    return f"[อัตราแลกเปลี่ยน {pair_label} (Yahoo Finance)]\n{rate:.4f}"


def _get_crypto(symbol: str, label: str) -> str:
    price = _yf(f"{symbol}-USD")
    usdthb = _yf("USDTHB=X")
    if price is None:
        return ""
    thb = f"  ≈ {price * usdthb:,.0f} THB" if usdthb else ""
    return f"[ราคา {label} (Yahoo Finance)]\n{price:,.2f} USD{thb}"


# ── Routing keywords → fetcher ─────────────────────────────────────────────

_GOLD_KW  = ["ทอง", "gold", "ราคาทอง"]
_BTC_KW   = ["bitcoin", "btc", "บิตคอยน์", "บิตคอย"]
_ETH_KW   = ["ethereum", "eth", "อีเธอเรียม"]
_USDTHB_KW = ["usd", "ดอลลาร์", "dollar", "เหรียญ", "usdthb", "แลกเงิน", "อัตราแลก"]


def _special_fetch(text: str) -> str:
    tl = text.lower()
    if any(k in tl for k in _GOLD_KW):
        return _get_gold_price()
    if any(k in tl for k in _BTC_KW):
        return _get_crypto("BTC", "Bitcoin")
    if any(k in tl for k in _ETH_KW):
        return _get_crypto("ETH", "Ethereum")
    if any(k in tl for k in _USDTHB_KW):
        return _get_fx("USDTHB=X", "USD/THB")
    return ""


# ── General DuckDuckGo news search ────────────────────────────────────────────

def _ddg_news(query: str, max_results: int = 4) -> str:
    if not _DDGS_OK:
        return ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        if not results:
            return ""
        lines = [f"[ข่าว/ข้อมูลจากอินเทอร์เน็ต — ค้นหา: {query}]"]
        for i, r in enumerate(results, 1):
            title = (r.get("title") or "").strip()
            body  = (r.get("body")  or r.get("excerpt") or "").strip()[:250]
            lines.append(f"{i}. {title}\n{body}")
        return "\n\n".join(lines)
    except Exception:
        return ""


# ── Trigger detection ─────────────────────────────────────────────────────────

_TRIGGERS = [
    # price / finance
    "ราคา", "หุ้น", "ดัชนี", "ตลาดหุ้น", "fund", "กองทุน",
    "bitcoin", "btc", "crypto", "forex", "ดอลลาร์", "เงินบาท",
    # news / current
    "ข่าว", "ล่าสุด", "ปัจจุบัน", "ตอนนี้", "วันนี้", "อัพเดท",
    # weather
    "อากาศ", "พยากรณ์", "ฝน", "พายุ", "อุณหภูมิ",
    # places / events
    "รอบฉาย", "ตาราง", "ผลบอล", "ผลการแข่ง", "ทีม",
    # info
    "ค้นหา", "หาข้อมูล", "wiki", "วิกิ", "ประวัติ",
    "รีวิว", "แนะนำ", "วิธีทำ", "สูตร",
    # English
    "latest", "news", "price", "weather", "review", "how to",
    "what is", "who is", "where is", "when is",
]


def should_search(text: str) -> bool:
    tl = text.lower()
    return any(kw in tl for kw in _TRIGGERS)


# ── Main entry point ──────────────────────────────────────────────────────────

def search(query: str) -> str:
    """Return context string for the LLM, or '' if nothing useful found."""
    # Try special real-time fetchers first (gold, crypto, FX)
    special = _special_fetch(query)
    if special:
        return special
    # Fall back to DuckDuckGo news
    return _ddg_news(query)
