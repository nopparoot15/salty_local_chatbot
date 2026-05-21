"""Web search + real-time data for Fahsai.

Sources:
- Gold / FX / crypto price  → Yahoo Finance (no API key)
- Thai lottery results       → DuckDuckGo news (ddgs) with date-specific query
- General queries           → DuckDuckGo news (ddgs)
"""
from __future__ import annotations
import json
import re
import datetime
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


def _latest_draw_date() -> datetime.date:
    today = datetime.date.today()
    if today.day >= 16:
        draw = today.replace(day=16)
    else:
        draw = today.replace(day=1)
    if draw >= today:
        if draw.day == 16:
            draw = draw.replace(day=1)
        else:
            prev = draw - datetime.timedelta(days=1)
            draw = prev.replace(day=16)
    return draw


def _get_lottery() -> str:
    """Scrape Thai lottery results from news.sanook.com/lotto/."""
    try:
        url = "https://news.sanook.com/lotto/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", "replace")

        # Results live in a JSON-LD block — literal \r\n sequences in source
        idx = html.find("รางวัลที่ 1")
        if idx == -1:
            return ""
        block = html[idx:idx + 600]
        # Unescape JSON-LD literal sequences → real newlines/spaces
        block = block.replace("\\r\\n", "\n").replace("\\n", "\n")
        block = block.replace("&nbsp;", " ")

        def grab(pattern):
            m = re.search(pattern, block, re.DOTALL)
            if not m:
                return None
            return re.sub(r"\s+", " ", m.group(1)).strip()

        # Prize numbers follow on the NEXT LINE after the label
        first   = grab(r"รางวัลที่ 1[^\n]*\n(\d{6})")
        three_f = grab(r"เลขหน้า 3 ตัว[^\n]*\n([\d\s]+)")
        three_b = grab(r"เลขท้าย 3 ตัว[^\n]*\n([\d\s]+)")
        two     = grab(r"เลขท้าย 2 ตัว[^\n]*\n(\d{2})")

        # Find draw date from page title / og:title
        date_m = re.search(
            r"(\d{1,2})[/\s](มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|"
            r"กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)[/\s](\d{4})", html)
        draw_label = date_m.group(0) if date_m else "งวดล่าสุด"

        lines = [f"[ผลสลากกินแบ่งรัฐบาล งวด {draw_label} (sanook)]"]
        if first:
            lines.append(f"รางวัลที่ 1       : {first}")
        if three_f:
            nums = " ".join(re.findall(r"\d{3}", three_f))
            if nums: lines.append(f"เลขหน้า 3 ตัว    : {nums}")
        if three_b:
            nums = " ".join(re.findall(r"\d{3}", three_b))
            if nums: lines.append(f"เลขท้าย 3 ตัว    : {nums}")
        if two:
            lines.append(f"เลขท้าย 2 ตัว    : {two}")
        return "\n".join(lines) if len(lines) > 1 else ""
    except Exception:
        return ""


def _get_oil_price() -> str:
    """Scrape Thai pump prices from gasprice.kapook.com."""
    try:
        url = "https://gasprice.kapook.com/gasprice.php"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", "replace")
        # Each brand block: <article class="gasprice ptt"> ... <li><span>FUEL</span><em>PRICE</em></li>
        # Use PTT as reference (first brand)
        brand_m = re.search(
            r'<article class="gasprice ptt">.*?</article>', html, re.DOTALL)
        if not brand_m:
            return ""
        block = brand_m.group(0)
        pairs = re.findall(r'<span>([^<]+)</span><em>([\d.]+)</em>', block)
        if not pairs:
            return ""
        lines = ["[ราคาน้ำมันหน้าปั๊ม ปตท. (gasprice.kapook.com)]"]
        for fuel, price in pairs:
            lines.append(f"{fuel.strip():<22}: {price} บาท/ลิตร")
        return "\n".join(lines)
    except Exception:
        return ""


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

_LOTTERY_KW = ["หวย", "สลาก", "ลอตเตอรี", "lottery", "lotto", "ตรวจหวย"]
_OIL_KW   = ["น้ำมัน", "oil", "ปิโตรเลียม", "crude", "wti", "brent", "ราคาน้ำมัน"]
_GOLD_KW  = ["ทอง", "gold", "ราคาทอง"]
_BTC_KW   = ["bitcoin", "btc", "บิตคอยน์", "บิตคอย"]
_ETH_KW   = ["ethereum", "eth", "อีเธอเรียม"]
_USDTHB_KW = ["usd", "ดอลลาร์", "dollar", "เหรียญ", "usdthb", "แลกเงิน", "อัตราแลก"]


def _special_fetch(text: str) -> str:
    tl = text.lower()
    if any(k in tl for k in _LOTTERY_KW):
        return _get_lottery()
    if any(k in tl for k in _OIL_KW):
        return _get_oil_price()
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
    # lottery
    "หวย", "สลาก", "ลอตเตอรี", "ตรวจหวย",
    # oil
    "น้ำมัน", "ปิโตรเลียม", "oil", "crude",
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
