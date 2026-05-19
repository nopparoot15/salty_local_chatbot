import re as _re
import os
import sys as _sys_mod
import ctypes as _ct

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

import customtkinter as ctk

# ── Pixel heart renderer ──────────────────────────────────────────────────────

_HEART_PX = [
    [0,1,1,0,0,1,1,0],
    [1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1],
    [0,1,1,1,1,1,1,0],
    [0,0,1,1,1,1,0,0],
    [0,0,0,1,1,0,0,0],
]
_HEART_W, _HEART_H = 8, 7

def _make_heart_strip(n_full, n_half=0, n_total=10, scale=3, display_size=None, raw=False):
    if not _PIL_OK:
        return None
    gap     = scale + 1
    sw      = _HEART_W * scale
    sh      = _HEART_H * scale
    total_w = n_total * sw + (n_total - 1) * gap
    img     = Image.new("RGBA", (total_w, sh), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(img)
    C_FULL  = (220, 50,  50,  255)
    C_EMPTY = (55,  28,  10,  255)
    for i in range(n_total):
        ox      = i * (sw + gap)
        is_full = i < n_full
        is_half = (not is_full) and (i == n_full) and n_half
        for r, row in enumerate(_HEART_PX):
            for c, px in enumerate(row):
                if not px:
                    continue
                x0, y0 = ox + c * scale, r * scale
                if is_full:
                    col = C_FULL
                elif is_half:
                    col = C_FULL if c < _HEART_W // 2 else C_EMPTY
                else:
                    col = C_EMPTY
                draw.rectangle([x0, y0, x0 + scale - 1, y0 + scale - 1], fill=col)
    if raw:
        return img
    size = display_size if display_size else (total_w, sh)
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)


# ── Color emoji renderer ──────────────────────────────────────────────────────

_EMOJI_RE = _re.compile(
    r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF'
    r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002300-\U000023FF'
    r'\U00002700-\U000027BF\U00002B00-\U00002BFF\U0000FE00-\U0000FE0F'
    r'\U0001F000-\U0001F0FF]+',
    flags=_re.UNICODE,
)
_EMOJI_FONT_PATH = r"C:\Windows\Fonts\seguiemj.ttf"
_emoji_fnt_cache: dict = {}

def _get_emoji_font(size: int):
    if not _PIL_OK or not os.path.exists(_EMOJI_FONT_PATH):
        return None
    if size not in _emoji_fnt_cache:
        try:
            _emoji_fnt_cache[size] = ImageFont.truetype(_EMOJI_FONT_PATH, size)
        except Exception:
            _emoji_fnt_cache[size] = None
    return _emoji_fnt_cache[size]


# ── PIL Thai text renderer (FreeType) ─────────────────────────────────────────

def _find_font_file(*names):
    if _sys_mod.platform == "win32":
        for name in names:
            p = os.path.join(r"C:\Windows\Fonts", name)
            if os.path.exists(p):
                return p
        return None
    linux_dirs = [
        "/usr/share/fonts/truetype/noto",
        "/usr/share/fonts/truetype",
        "/usr/share/fonts/opentype/noto",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
        os.path.expanduser("~/.local/share/fonts"),
    ]
    for name in names:
        for d in linux_dirs:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    try:
        import subprocess
        r = subprocess.run(["fc-match", "--format=%{file}", ":lang=th:spacing=proportional"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None

_PIL_REG  = _find_font_file(
    "LeelawUI.ttf", "tahoma.ttf", "arial.ttf",
    "NotoSansThai-Regular.ttf", "NotoSans-Regular.ttf", "DejaVuSans.ttf",
)
_PIL_BOLD = _find_font_file(
    "LeelaUIb.ttf", "LeelawUIb.ttf", "leelawdb.ttf", "tahomabd.ttf", "arialbd.ttf",
    "NotoSansThai-Bold.ttf", "NotoSans-Bold.ttf", "DejaVuSans-Bold.ttf",
)
_PIL_MONO = _find_font_file(
    "consola.ttf", "cour.ttf",
    "NotoMono-Regular.ttf", "DejaVuSansMono.ttf",
)

_pil_fc: dict = {}

def _pf(size: int, bold=False, mono=False):
    k = (size, bold, mono)
    if k not in _pil_fc:
        p = _PIL_MONO if mono else (_PIL_BOLD if (bold and _PIL_BOLD) else _PIL_REG)
        try:
            _pil_fc[k] = ImageFont.truetype(p, size) if p else ImageFont.load_default()
        except Exception:
            _pil_fc[k] = ImageFont.load_default()
    return _pil_fc[k]

_EMOJI_STRIP = _re.compile(
    r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF'
    r'\U0001FA00-\U0001FAFF\U00002300-\U000023FF\U00002700-\U000027BF'
    r'\U00002B00-\U00002BFF\U0000FE00-\U0000FE0F\U0001F000-\U0001F0FF]+',
    _re.UNICODE,
)

# ── GDI init ──────────────────────────────────────────────────────────────────

class _LOGFONTW(_ct.Structure):
    _fields_ = [("lfHeight",_ct.c_long),("lfWidth",_ct.c_long),
                ("lfEscapement",_ct.c_long),("lfOrientation",_ct.c_long),
                ("lfWeight",_ct.c_long),("lfItalic",_ct.c_byte),
                ("lfUnderline",_ct.c_byte),("lfStrikeOut",_ct.c_byte),
                ("lfCharSet",_ct.c_byte),("lfOutPrecision",_ct.c_byte),
                ("lfClipPrecision",_ct.c_byte),("lfQuality",_ct.c_byte),
                ("lfPitchAndFamily",_ct.c_byte),("lfFaceName",_ct.c_wchar*32)]

class _RECT(_ct.Structure):
    _fields_ = [("left",_ct.c_long),("top",_ct.c_long),
                ("right",_ct.c_long),("bottom",_ct.c_long)]

class _SIZE(_ct.Structure):
    _fields_ = [("cx",_ct.c_long),("cy",_ct.c_long)]

class _BMIH(_ct.Structure):
    _fields_ = [("biSize",_ct.c_uint32),("biWidth",_ct.c_int32),
                ("biHeight",_ct.c_int32),("biPlanes",_ct.c_uint16),
                ("biBitCount",_ct.c_uint16),("biCompression",_ct.c_uint32),
                ("biSizeImage",_ct.c_uint32),("biXPelsPerMeter",_ct.c_int32),
                ("biYPelsPerMeter",_ct.c_int32),("biClrUsed",_ct.c_uint32),
                ("biClrImportant",_ct.c_uint32)]

class _BMI(_ct.Structure):
    _fields_ = [("bmiHeader",_BMIH),("bmiColors",_ct.c_uint32*3)]

_GDI_OK = False
_g32    = None
_u32_g  = None

def _init_gdi():
    global _GDI_OK, _g32, _u32_g
    if _sys_mod.platform != "win32":
        return
    try:
        g = _ct.windll.gdi32
        u = _ct.windll.user32
        vp = _ct.c_void_p
        g.CreateCompatibleDC.restype    = vp
        g.CreateCompatibleDC.argtypes   = [vp]
        g.DeleteDC.argtypes             = [vp]
        g.CreateDIBSection.restype      = vp
        g.CreateDIBSection.argtypes     = [vp,vp,_ct.c_uint,_ct.POINTER(vp),vp,_ct.c_uint32]
        g.SelectObject.restype          = vp
        g.SelectObject.argtypes         = [vp,vp]
        g.DeleteObject.argtypes         = [vp]
        g.CreateFontIndirectW.restype   = vp
        g.CreateFontIndirectW.argtypes  = [vp]
        g.CreateSolidBrush.restype      = vp
        g.CreateSolidBrush.argtypes     = [_ct.c_uint32]
        g.SetTextColor.argtypes         = [vp,_ct.c_uint32]
        g.SetBkMode.argtypes            = [vp,_ct.c_int]
        u.DrawTextW.restype             = _ct.c_int
        u.DrawTextW.argtypes            = [vp,_ct.c_wchar_p,_ct.c_int,vp,_ct.c_uint]
        u.FillRect.argtypes             = [vp,vp,vp]
        g.GdiFlush.argtypes             = []
        g.GetTextExtentPoint32W.restype  = _ct.c_int
        g.GetTextExtentPoint32W.argtypes = [vp,_ct.c_wchar_p,_ct.c_int,vp]
        g.GetDeviceCaps.argtypes        = [vp,_ct.c_int]
        g.TextOutW.argtypes             = [vp,_ct.c_int,_ct.c_int,_ct.c_wchar_p,_ct.c_int]
        u.GetDC.restype                 = vp
        u.GetDC.argtypes                = [vp]
        u.ReleaseDC.argtypes            = [vp,vp]
        _g32 = g; _u32_g = u; _GDI_OK = True
    except Exception as _e:
        import traceback as _tb
        try:
            _lp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_error.log")
            with open(_lp, "a", encoding="utf-8") as _lf:
                _lf.write(f"[_init_gdi FAILED] {type(_e).__name__}: {_e}\n{_tb.format_exc()}\n")
        except Exception:
            pass

_init_gdi()

# ── GDI resource caches ───────────────────────────────────────────────────────

_hfont_cache:  dict = {}
_line_h_cache: dict = {}
_screen_dpi_y: int  = 0
_hbr_bot_bg        = None
_meas_hdc          = None
_meas_font_cur     = 0

def _ensure_screen_dpi() -> int:
    global _screen_dpi_y
    if not _screen_dpi_y:
        hdc = _u32_g.GetDC(None)
        _screen_dpi_y = _g32.GetDeviceCaps(hdc, 90) or 96
        _u32_g.ReleaseDC(None, hdc)
    return _screen_dpi_y

def _get_hfont(face: str, height_px: int, bold: bool = False):
    key = (face, height_px, bold)
    if key not in _hfont_cache:
        lf = _LOGFONTW()
        lf.lfHeight = -height_px; lf.lfWeight = 700 if bold else 400
        lf.lfCharSet = 0; lf.lfQuality = 5
        lf.lfFaceName = face[:31]
        _hfont_cache[key] = _g32.CreateFontIndirectW(_ct.byref(lf))
    return _hfont_cache[key]

def _select_meas_font(hfont):
    global _meas_hdc, _meas_font_cur
    if _meas_hdc is None:
        hdc_s = _u32_g.GetDC(None)
        _meas_hdc = _g32.CreateCompatibleDC(hdc_s)
        _u32_g.ReleaseDC(None, hdc_s)
    if hfont != _meas_font_cur:
        _g32.SelectObject(_meas_hdc, hfont)
        _meas_font_cur = hfont
    return _meas_hdc

def _get_line_h(hfont) -> int:
    if hfont not in _line_h_cache:
        hdc = _select_meas_font(hfont)
        rc = _RECT(0, 0, 32000, 32000)
        _u32_g.DrawTextW(hdc, "ก", -1, _ct.byref(rc), 0x00000100 | 0x00000400 | 0x00000800)
        _line_h_cache[hfont] = max(rc.bottom, 1)
    return _line_h_cache[hfont]

def _get_bot_bg_brush():
    global _hbr_bot_bg
    if _hbr_bot_bg is None and _GDI_OK:
        _hbr_bot_bg = _g32.CreateSolidBrush(0xf2 | (0xe0 << 8) | (0xa0 << 16))
    return _hbr_bot_bg

# ── Inline markdown parser ────────────────────────────────────────────────────

_THAI_RE    = _re.compile(r'[฀-๿]')
_MONO_FACE  = "Consolas"
_BOLD_FACE  = "Tahoma"
_INLINE_RE  = _re.compile(r'(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`)', _re.DOTALL)
_SPACESP_RE = _re.compile(r'(\s+)')

def _parse_inline(line: str) -> list:
    runs = []; last = 0
    for m in _INLINE_RE.finditer(line):
        if m.start() > last:
            runs.append((line[last:m.start()], False, False))
        s = m.group(0)
        if   s.startswith('***'): runs.append((m.group(2), True,  False))
        elif s.startswith('**'):  runs.append((m.group(3), True,  False))
        elif s.startswith('`'):   runs.append((m.group(5), False, True))
        else:                     runs.append((m.group(4), False, False))
        last = m.end()
    if last < len(line):
        runs.append((line[last:], False, False))
    return runs or [('', False, False)]

# ── GDI/Uniscribe markdown renderer ──────────────────────────────────────────

def _gdi_render_text(text: str, font_name: str, font_size: int, max_w: int, fg_hex: str):
    if not _GDI_OK or not _PIL_OK or not text:
        return None
    _lmhdc = None
    try:
        dpi_y = _ensure_screen_dpi()
        px_   = lambda pt: int(pt * dpi_y / 72)

        _hdc_s2 = _u32_g.GetDC(None)
        _lmhdc  = _g32.CreateCompatibleDC(_hdc_s2)
        _u32_g.ReleaseDC(None, _hdc_s2)
        _lmf = [None]
        def _smf(hf):
            if hf is not _lmf[0]:
                _g32.SelectObject(_lmhdc, hf)
                _lmf[0] = hf
            return _lmhdc
        def _lh(hf) -> int:
            if hf not in _line_h_cache:
                rc = _RECT(0, 0, 32000, 32000)
                _u32_g.DrawTextW(_smf(hf), "ก", -1, _ct.byref(rc), 0x100 | 0x400 | 0x800)
                _line_h_cache[hf] = max(rc.bottom, 1)
            return _line_h_cache[hf]

        hf_reg  = _get_hfont(font_name,  px_(font_size),     bold=False)
        hf_bold = _get_hfont(_BOLD_FACE, px_(font_size),     bold=True)
        hf_h1   = _get_hfont(_BOLD_FACE, px_(font_size + 10), bold=True)
        hf_h2   = _get_hfont(_BOLD_FACE, px_(font_size + 6),  bold=True)
        hf_h3   = _get_hfont(_BOLD_FACE, px_(font_size + 3),  bold=True)
        hf_mono = _get_hfont(_MONO_FACE, px_(font_size),     bold=False)
        lh_reg  = _lh(hf_reg)
        lh_mono = _lh(hf_mono)

        def meas(s: str, hf) -> int:
            if not s: return 0
            sz = _SIZE()
            _g32.GetTextExtentPoint32W(_smf(hf), s, len(s), _ct.byref(sz))
            return sz.cx

        DT_WRAP = 0x10 | 0x800
        DT_CALC = DT_WRAP | 0x400

        _MD_FENCE = {'markdown', 'md', 'text', 'plaintext', ''}
        paras = []; in_code = False; code_buf = []
        for raw in text.split('\n'):
            if raw.lstrip().startswith('```'):
                lang = raw.lstrip()[3:].strip().lower()
                if in_code:
                    paras.append({'type': 'code', 'lines': code_buf[:]})
                    code_buf.clear(); in_code = False
                elif lang not in _MD_FENCE:
                    in_code = True
                continue
            if in_code:
                code_buf.append(raw); continue
            rs = raw.strip()
            hm = _re.match(r'^(#{1,6})\s*(.*)', rs)
            bm = _re.match(r'^[-*]\s+(.*)',      rs)
            nm = _re.match(r'^(\d+)\.\s+(.*)',   rs)
            if hm:
                lv  = min(len(hm.group(1)), 3)
                hfb = (hf_h1, hf_h2, hf_h3)[lv - 1]
                paras.append({'type': 'para', 'hfont': hfb,
                              'runs': _parse_inline(hm.group(2)), 'indent': 0, 'prefix': ''})
            elif bm:
                paras.append({'type': 'para', 'hfont': hf_reg,
                              'runs': _parse_inline(bm.group(1)), 'indent': 20, 'prefix': '• '})
            elif nm:
                pfx = f"{nm.group(1)}. "
                paras.append({'type': 'para', 'hfont': hf_reg,
                              'runs': _parse_inline(nm.group(2)),
                              'indent': meas(pfx, hf_reg), 'prefix': pfx})
            elif not rs:
                paras.append({'type': 'blank'})
            else:
                paras.append({'type': 'para', 'hfont': hf_reg,
                              'runs': _parse_inline(rs), 'indent': 0, 'prefix': ''})
        if code_buf:
            paras.append({'type': 'code', 'lines': code_buf})

        render_items = []; emoji_pos = []; total_y = 0

        for para in paras:
            if para['type'] == 'blank':
                total_y += lh_reg // 2; continue
            if para['type'] == 'code':
                for cl in para['lines']:
                    lh_m = lh_reg if _THAI_RE.search(cl) else lh_mono
                    parts  = _EMOJI_RE.split(cl)
                    emojis = _EMOJI_RE.findall(cl)
                    flat = []
                    for i, p in enumerate(parts):
                        if p: flat.append((p, False))
                        if i < len(emojis): flat.append((emojis[i], True))
                    seg_x = 0; line_items = []
                    for content, is_emoji in flat:
                        if is_emoji:
                            if seg_x + lh_m > max_w and seg_x > 0:
                                render_items.append(('to', total_y, line_items or [(0, '', hf_mono)]))
                                total_y += lh_m; seg_x = 0; line_items = []
                            emoji_pos.append((seg_x, total_y, content, lh_m))
                            seg_x += lh_m
                        else:
                            cur = ''
                            for ch in content:
                                if meas(cur + ch, hf_mono) <= max_w - seg_x:
                                    cur += ch
                                else:
                                    if cur:
                                        line_items.append((seg_x, cur, hf_mono))
                                    render_items.append(('to', total_y, line_items or [(0, '', hf_mono)]))
                                    total_y += lh_m; seg_x = 0; line_items = []; cur = ch
                            if cur:
                                line_items.append((seg_x, cur, hf_mono))
                                seg_x += meas(cur, hf_mono)
                    render_items.append(('to', total_y, line_items or [(0, '', hf_mono)]))
                    total_y += lh_m
                total_y += lh_reg // 4; continue

            hf_base = para['hfont']
            lh      = _lh(hf_base)
            indent  = para['indent']
            prefix  = para['prefix']
            runs    = para['runs']
            has_emoji = any(_EMOJI_RE.search(r[0]) for r in runs)
            is_plain  = (len(runs) == 1 and not runs[0][1] and not runs[0][2] and not has_emoji)

            if is_plain:
                plain = runs[0][0].strip()
                if not plain:
                    total_y += lh // 2; continue
                if prefix:
                    pfx_w = meas(prefix, hf_base)
                    render_items.append(('to', total_y, [(indent - pfx_w, prefix, hf_base)]))
                rc_m = _RECT(0, 0, max_w - indent, 32000)
                _u32_g.DrawTextW(_smf(hf_base), plain, -1, _ct.byref(rc_m), DT_CALC)
                para_h = max(rc_m.bottom, lh)
                render_items.append(('dt', total_y, plain, hf_base, indent, max_w - indent))
                total_y += para_h
            else:
                cur_items = []; x = indent
                if prefix:
                    pfx_w = meas(prefix, hf_base)
                    cur_items.append((indent - pfx_w, prefix, hf_base))

                def _tok_segments(tok):
                    segs = []
                    parts  = _EMOJI_RE.split(tok)
                    emojis = _EMOJI_RE.findall(tok)
                    for i, p in enumerate(parts):
                        if p: segs.append((p, None))
                        if i < len(emojis): segs.append((None, emojis[i]))
                    return segs

                def _tok_width(segs):
                    return sum((meas(s[0], hf_run) if s[0] else lh) for s in segs)

                for run_txt, run_bold, run_mono in runs:
                    if not run_txt: continue
                    hf_run = hf_mono if run_mono else (hf_bold if run_bold else hf_base)
                    for tok in _SPACESP_RE.split(run_txt):
                        if not tok: continue
                        is_ws = not tok.strip()
                        segs = _tok_segments(tok)
                        tw   = _tok_width(segs)
                        if is_ws:
                            if cur_items: x += tw
                            continue
                        if x + tw > max_w and cur_items:
                            render_items.append(('to', total_y, cur_items[:]))
                            cur_items = []; x = indent; total_y += lh
                            tok  = tok.lstrip()
                            segs = _tok_segments(tok)
                            tw   = _tok_width(segs)
                            if not tok: continue
                        seg_x = x
                        for txt_seg, emj_seg in segs:
                            if txt_seg:
                                sw = meas(txt_seg, hf_run)
                                cur_items.append((seg_x, txt_seg, hf_run))
                                seg_x += sw
                            else:
                                emoji_pos.append((seg_x, total_y, emj_seg, lh))
                                seg_x += lh
                        x += tw
                if cur_items:
                    render_items.append(('to', total_y, cur_items))
                    total_y += lh

        img_h = max(4, total_y + int(font_size * 0.6))
        img_w = max_w

        r_fg = int(fg_hex[1:3], 16); g_fg = int(fg_hex[3:5], 16); b_fg = int(fg_hex[5:7], 16)
        fg_cr = r_fg | (g_fg << 8) | (b_fg << 16)

        bmi = _BMI()
        bmi.bmiHeader.biSize     = _ct.sizeof(_BMIH)
        bmi.bmiHeader.biWidth    = img_w
        bmi.bmiHeader.biHeight   = -img_h
        bmi.bmiHeader.biPlanes   = 1
        bmi.bmiHeader.biBitCount = 32

        pbits = _ct.c_void_p()
        hdc_s = _u32_g.GetDC(None)
        hbmp  = _g32.CreateDIBSection(hdc_s, _ct.byref(bmi), 0, _ct.byref(pbits), None, 0)
        hdc_r = _g32.CreateCompatibleDC(hdc_s)
        _u32_g.ReleaseDC(None, hdc_s)

        old_bm = _g32.SelectObject(hdc_r, hbmp)
        _u32_g.FillRect(hdc_r, _ct.byref(_RECT(0, 0, img_w, img_h)), _get_bot_bg_brush())
        _g32.SetTextColor(hdc_r, fg_cr)
        _g32.SetBkMode(hdc_r, 1)

        cur_hf = None
        def _sel(hf):
            nonlocal cur_hf
            if hf != cur_hf:
                _g32.SelectObject(hdc_r, hf); cur_hf = hf

        for ri in render_items:
            if ri[0] == 'dt':
                _, vy, vtxt, vhf, x0, w = ri
                gdi_txt = _EMOJI_RE.sub('', vtxt)
                if not gdi_txt.strip(): continue
                _sel(vhf)
                _u32_g.DrawTextW(hdc_r, gdi_txt, -1, _ct.byref(_RECT(x0, vy, x0 + w, vy + img_h)), DT_WRAP)
            else:
                _, vy, items = ri
                for vx, vtxt, vhf in items:
                    gdi_txt = _EMOJI_RE.sub('', vtxt)
                    if not gdi_txt: continue
                    _sel(vhf)
                    _g32.TextOutW(hdc_r, vx, vy, gdi_txt, len(gdi_txt))

        _g32.GdiFlush()
        raw_px = _ct.string_at(pbits, img_w * img_h * 4)
        img    = Image.frombuffer("RGBA", (img_w, img_h), raw_px, "raw", "BGRA", 0, 1).convert("RGBA")

        _g32.SelectObject(hdc_r, old_bm)
        _g32.DeleteDC(hdc_r)
        _g32.DeleteObject(hbmp)

        if emoji_pos:
            for ex, ey, echar, lh_ctx in emoji_pos:
                efnt = _get_emoji_font(max(8, int(lh_ctx * 0.80)))
                if not efnt: continue
                try:
                    bbox = efnt.getbbox(echar)
                    if not bbox or bbox[2] <= bbox[0]: continue
                    ew, eh = bbox[2]-bbox[0], bbox[3]-bbox[1]
                    eimg = Image.new("RGBA", (ew+2, eh+2), (0,0,0,0))
                    ImageDraw.Draw(eimg).text((-bbox[0]+1, -bbox[1]+1),
                                              echar, font=efnt, embedded_color=True)
                    ey_adj = ey + max(0, (lh_ctx - eimg.height) // 2)
                    img.paste(eimg, (max(0, min(ex, img_w-eimg.width)),
                                     max(0, min(ey_adj, img_h-eimg.height))), eimg)
                except Exception:
                    pass

        return img.convert("RGB")
    except Exception as _e:
        import traceback as _tb
        try:
            _lp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_error.log")
            with open(_lp, "a", encoding="utf-8") as _lf:
                _lf.write(f"[GDI render error] {type(_e).__name__}: {_e}\n{_tb.format_exc()}\n")
        except Exception:
            pass
        return None
    finally:
        if _lmhdc:
            try: _g32.DeleteDC(_lmhdc)
            except Exception: pass

# ── PIL fallback renderer ─────────────────────────────────────────────────────

def _pil_wrap(text: str, fnt, max_w: int) -> list:
    lines = []
    for para in text.split("\n"):
        if not para:
            lines.append(""); continue
        words = para.split(" "); cur = ""
        for w in words:
            t = (cur + " " + w).strip() if cur else w
            try:
                px = fnt.getbbox(t)[2]
            except Exception:
                px = len(t) * 8
            if px <= max_w:
                cur = t
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
    return lines or [""]

def _pil_render_text(text: str, font_size: int, max_w: int, fg_hex: str):
    if not _PIL_OK or not text or not _PIL_REG:
        return None
    r, g, b = int(fg_hex[1:3], 16), int(fg_hex[3:5], 16), int(fg_hex[5:7], 16)
    tc  = (r, g, b, 255)
    lh  = int(font_size * 1.8)
    segs: list = []; in_code = False

    for raw in text.split("\n"):
        line = _EMOJI_STRIP.sub("", raw).rstrip()
        if line.startswith("```"):
            lang = line[3:].strip().lower()
            if in_code: in_code = False
            elif lang not in ('markdown', 'md', 'text', 'plaintext', ''): in_code = True
            continue
        if in_code:
            fnt = _pf(max(8, font_size - 2), mono=True)
            for l in _pil_wrap(line, fnt, max_w): segs.append((l, fnt))
            continue
        line = line.strip()
        hm = _re.match(r"^(#{1,6})\s*(.+)", line)
        if hm:
            fnt = _pf(font_size + max(0, 4 - min(len(hm.group(1)), 3)), bold=True)
            txt = _re.sub(r"\*+([^*]+)\*+", r"\1", hm.group(2))
            for l in _pil_wrap(txt, fnt, max_w): segs.append((l, fnt))
            continue
        bm = _re.match(r"^[-*]\s+(.+)", line)
        if bm:
            fnt = _pf(font_size)
            txt = "• " + _re.sub(r"\*+([^*]+)\*+", r"\1", bm.group(1))
            txt = _re.sub(r"`([^`]+)`", r"\1", txt)
            for l in _pil_wrap(txt, fnt, max_w): segs.append((l, fnt))
            continue
        txt = _re.sub(r"\*+([^*]+)\*+", r"\1", line)
        txt = _re.sub(r"`([^`]+)`", r"\1", txt)
        fnt = _pf(font_size)
        if not txt.strip():
            segs.append(("", fnt))
        else:
            for l in _pil_wrap(txt, fnt, max_w): segs.append((l, fnt))

    if not segs:
        return None
    img_h = len(segs) * lh + 8
    img   = Image.new("RGBA", (max_w + 4, img_h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(img)
    y = 4
    for txt, fnt in segs:
        if txt:
            try: draw.text((0, y), txt, font=fnt, fill=tc)
            except Exception: pass
        y += lh
    return img
