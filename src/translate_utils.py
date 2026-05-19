import re

_TH_RE = re.compile(r'[ก-๙]')


def is_thai(text: str) -> bool:
    return bool(_TH_RE.search(text))


def th_to_en(text: str) -> str:
    if not text.strip():
        return text
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source='th', target='en').translate(text)
        return result or text
    except Exception:
        return text


def en_to_th(text: str) -> str:
    if not text.strip():
        return text
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source='en', target='th').translate(text)
        return result or text
    except Exception:
        return text
