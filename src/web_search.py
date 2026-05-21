"""Web search via DuckDuckGo – no API key needed."""
from __future__ import annotations

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

_TRIGGERS = [
    # Thai
    "ค้นหา", "หาข้อมูล", "ข่าว", "ล่าสุด", "ปัจจุบัน", "ตอนนี้", "วันนี้",
    "ราคา", "สกุลเงิน", "หุ้น", "bitcoin", "btc", "crypto", "forex",
    "อากาศ", "พยากรณ์", "อุณหภูมิ",
    "สถานที่", "ร้านอาหาร", "รีวิว", "คะแนน", "imdb", "รอบฉาย",
    "ผลบอล", "ผลการแข่งขัน", "นักเตะ", "ทีม",
    "สูตร", "วิธีทำ", "ส่วนผสม",
    "ดารา", "นักร้อง", "อัลบั้ม", "เพลง", "ภาพยนตร์", "ซีรีส์",
    "wiki", "วิกิ", "ประวัติ",
    # English
    "latest", "news", "price", "weather", "recipe", "review", "rating",
    "how to", "what is", "who is", "where is", "when is",
]


def should_search(text: str) -> bool:
    tl = text.lower()
    return any(kw in tl for kw in _TRIGGERS)


def search(query: str, max_results: int = 4) -> str:
    """Return a formatted string of search results, or '' on failure."""
    if not _DDGS_OK:
        return ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return ""
        lines = [f"[ข้อมูลจากอินเทอร์เน็ต — ค้นหา: {query}]"]
        for i, r in enumerate(results, 1):
            title = (r.get("title") or "").strip()
            body  = (r.get("body")  or "").strip()[:300]
            url   = (r.get("href")  or "").strip()
            lines.append(f"{i}. {title}\n{body}\n({url})")
        return "\n\n".join(lines)
    except Exception:
        return ""
