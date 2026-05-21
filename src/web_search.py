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


def _get_lottery() -> str:
    """Get latest Thai government lottery results via DuckDuckGo news."""
    if not _DDGS_OK:
        return ""
    today = datetime.date.today()
    # Thai lotto draws on 1st and 16th of each month
    if today.day >= 16:
        draw = today.replace(day=16)
    else:
        # Last draw was on the 1st of this month or 16th of last month
        if today.day >= 1:
            draw = today.replace(day=1)
        else:
            prev = today.replace(day=1) - datetime.timedelta(days=1)
            draw = prev.replace(day=16)
    # If draw date is today or future, go back one period
    if draw >= today:
        if draw.day == 16:
            draw = draw.replace(day=1)
        else:
            prev = draw - datetime.timedelta(days=1)
            draw = prev.replace(day=16)

    _TH_MONTH = ["","มกราคม","กุมภาพันธ์","มีนาคม","เมษายน","พฤษภาคม","มิถุนายน",
                 "กรกฎาคม","สิงหาคม","กันยายน","ตุลาคม","พฤศจิกายน","ธันวาคม"]
    bud_year = draw.year + 543
    short_date = f"{draw.day}/{draw.month}/{str(bud_year)[-2:]}"
    long_date = f"{draw.day} {_TH_MONTH[draw.month]} {bud_year}"
    query = f"ผลหวยรัฐบาล {short_date} รางวัลที่1"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=5))
        if not results:
            return ""
        # Try to extract the first prize 6-digit number from snippets
        first_prize = None
        lines = [f"[ผลสลากกินแบ่งรัฐบาล งวด {long_date}]"]
        for r in results:
            body = (r.get("body") or "").strip()
            title = (r.get("title") or "").strip()
            combined = title + " " + body
            if not first_prize:
                # Look for 6-digit after prize keywords
                m = re.search(r'รางวัลที่\s*1[^\d]*(\d{6})', combined)
                if m:
                    first_prize = m.group(1)
                else:
                    # Standalone 6-digit that looks like a prize (not a date)
                    candidates = re.findall(r'\b(\d{6})\b', combined)
                    for c in candidates:
                        if not re.match(r'(0[1-9]|[12]\d|3[01])(0[1-9]|1[0-2])\d{2}', c):
                            first_prize = c
                            break
            if body and len(body) > 30:
                lines.append(body[:250])
                if len(lines) >= 4:
                    break
        if first_prize:
            lines.insert(1, f"รางวัลที่ 1: {first_prize}")
        return "\n\n".join(lines)
    except Exception:
        return ""


def _get_oil_price() -> str:
    usdthb = _yf("USDTHB=X")
    wti    = _yf("CL=F")
    brent  = _yf("BZ=F")
    if wti is None and brent is None:
        return ""
    lines = ["[ราคาน้ำมันดิบปัจจุบัน (Yahoo Finance)]"]
    if wti:
        thb = f" ≈ {wti * usdthb:,.0f} THB/bbl" if usdthb else ""
        lines.append(f"WTI Crude   : {wti:,.2f} USD/bbl{thb}")
    if brent:
        thb = f" ≈ {brent * usdthb:,.0f} THB/bbl" if usdthb else ""
        lines.append(f"Brent Crude : {brent:,.2f} USD/bbl{thb}")
    if usdthb:
        lines.append(f"อัตราแลกเปลี่ยน: 1 USD = {usdthb:.2f} THB")
    return "\n".join(lines)


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
