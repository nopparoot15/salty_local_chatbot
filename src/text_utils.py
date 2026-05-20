import re
import sys as _sys
import ctypes as _ctypes

_tk_clipboard_set = None
_tk_clipboard_get = None


def _setup_clipboard_ctypes():
    if _sys.platform != "win32":
        return None, None
    _u32 = _ctypes.windll.user32
    _k32 = _ctypes.windll.kernel32
    _k32.GlobalLock.restype  = _ctypes.c_void_p
    _k32.GlobalLock.argtypes = [_ctypes.c_void_p]
    _k32.GlobalUnlock.argtypes = [_ctypes.c_void_p]
    _k32.GlobalAlloc.restype = _ctypes.c_void_p
    _k32.GlobalAlloc.argtypes = [_ctypes.c_uint, _ctypes.c_size_t]
    _u32.GetClipboardData.restype = _ctypes.c_void_p
    _u32.SetClipboardData.argtypes = [_ctypes.c_uint, _ctypes.c_void_p]
    return _u32, _k32

_u32, _k32 = _setup_clipboard_ctypes()


def win_get_clipboard() -> str:
    if _sys.platform != "win32":
        if _tk_clipboard_get:
            try:
                return _tk_clipboard_get()
            except Exception:
                pass
        return ""
    if not _u32.OpenClipboard(0):
        return ""
    try:
        h = _u32.GetClipboardData(13)  # CF_UNICODETEXT
        if not h:
            return ""
        ptr = _k32.GlobalLock(h)
        if not ptr:
            return ""
        try:
            return _ctypes.wstring_at(ptr)
        finally:
            _k32.GlobalUnlock(h)
    except Exception:
        return ""
    finally:
        _u32.CloseClipboard()


def win_set_clipboard(text: str) -> None:
    if _sys.platform != "win32":
        if _tk_clipboard_set:
            try:
                _tk_clipboard_set(text)
            except Exception:
                pass
        return
    try:
        data = (text + "\0").encode("utf-16-le")
        h = _k32.GlobalAlloc(0x42, len(data))
        if not h:
            return
        ptr = _k32.GlobalLock(h)
        if not ptr:
            return
        _ctypes.memmove(ptr, data, len(data))
        _k32.GlobalUnlock(h)
        if _u32.OpenClipboard(0):
            _u32.EmptyClipboard()
            _u32.SetClipboardData(13, h)
            _u32.CloseClipboard()
    except Exception:
        pass


# ── Compiled regexes ──────────────────────────────────────────────────────────

EMOJI_RE = re.compile(
    r'[\U00010000-\U0010ffff\U00002600-\U000027BF\U0000FE00-\U0000FE0F]+',
    flags=re.UNICODE,
)

_RE_THINK        = re.compile(r"<think>.*?</think>", re.DOTALL)
_RE_THINK_OPEN   = re.compile(r"<think>.*",          re.DOTALL)
_RE_BOLD         = re.compile(r"\*+([^*]+)\*+")
_RE_HEADING      = re.compile(r"#+\s*")
_RE_SP_KHA       = re.compile(r"\s+ค่ะ")
_RE_SP_KA        = re.compile(r"\s+คะ")
_RE_NA_KA        = re.compile(r"นะ\s+คะ")
_RE_SPACES       = re.compile(r"[^\S\n]{2,}")  # collapse spaces/tabs, preserve newlines
_RE_KHRAP        = re.compile(r'ครับ|(?<!ห)ว่?ะ')
# bare "ว" particle after common sentence-final words (ไหมว, หรอว, นะว ...)
_RE_WA_PTCL      = re.compile(
    r'(ไหม|มั้ย|หรอ|เหรอ|นะ|ล่ะ|ไหน|เลย|ด้วย|อยู่)ว(?=[^฀-๿]|$)',
    re.MULTILINE,
)
_RE_CODE_FENCE   = re.compile(r'(```.*?```)', re.DOTALL)  # capturing — used to split around code blocks
_RE_CODE_BLOCK   = re.compile(r"```.*?```", re.DOTALL)
_RE_CODE_INLINE  = re.compile(r"`([^`]+)`")
_RE_BULLET       = re.compile(r"^[-*]\s+", re.MULTILINE)
_RE_HEADING_LN   = re.compile(r"^#{1,6}\s+", re.MULTILINE)

_RE_PROMPT_BLEED = re.compile(
    r'^(กฎการพูด|ตัวอย่างการพูด|บุคลิก|เวลาตอนนี้|ฟ้าใส สาวไทย|instruction|system prompt)'
    r'.*$',
    re.MULTILINE | re.IGNORECASE,
)


def _strip_md(text):
    """Strip markdown + emoji for LLM history storage."""
    text = _RE_THINK.sub("", text)
    text = EMOJI_RE.sub("", text)
    text = _RE_BOLD.sub(r"\1", text)
    text = _RE_HEADING.sub("", text)
    text = _RE_SP_KHA.sub("ค่ะ", text)
    text = _RE_SP_KA.sub("คะ", text)
    text = _RE_NA_KA.sub("นะคะ", text)
    return _RE_SPACES.sub(" ", text).strip()


def strip_think(text):
    """Remove <think> blocks — keep markdown and everything else intact."""
    text = _RE_THINK.sub("", text)
    text = _RE_THINK_OPEN.sub("", text)
    return text.strip()


def fix_gender(text: str) -> str:
    """Remove wrong-gender particles and prompt-bleed lines, skipping code blocks."""
    parts = _RE_CODE_FENCE.split(text)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:  # inside a ```...``` block — leave untouched
            out.append(part)
        else:
            part = _RE_KHRAP.sub("", part)
            part = _RE_WA_PTCL.sub(r'\1', part)
            part = _RE_PROMPT_BLEED.sub("", part)
            out.append(part)
    return re.sub(r'\n{3,}', '\n\n', ''.join(out)).strip()


def strip_md_for_copy(text):
    """Strip markdown for clipboard — removes formatting symbols, keeps emojis and content."""
    text = _RE_THINK.sub("", text)
    text = _RE_CODE_BLOCK.sub("", text)
    text = _RE_BOLD.sub(r"\1", text)
    text = _RE_CODE_INLINE.sub(r"\1", text)
    text = _RE_HEADING_LN.sub("", text)
    text = _RE_BULLET.sub("• ", text)
    return _RE_SPACES.sub(" ", text).strip()
