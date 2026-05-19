import re as _re
import time as _time
import unicodedata as _ucd
import tkinter as tk
import tkinter.font as _tkFont
import customtkinter as ctk

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

from .config import (
    C_BG, C_USER_BG, C_BOT_BG, C_BOT_TEXT, C_PORTRAIT_BG, C_BORDER,
)
from .config import _FONT_UI as _FONT
from .renderer import _gdi_render_text, _pil_render_text, _PIL_REG

# ── Pre-compiled markdown patterns ───────────────────────────────────────────
_RE_BOLD_SPLIT = _re.compile(r'(\*+[^*\n]+\*+)')
_RE_BOLD_MATCH = _re.compile(r'\*+([^*\n]+)\*+')
_RE_HEADING    = _re.compile(r'^(#{1,6})\s*(.*)')
_RE_BULLET     = _re.compile(r'^[-*]\s+(.*)')

# ── Font metrics cache (keyed by font_size) ───────────────────────────────────
_font_metrics_cache: dict = {}

def _get_font_metrics(fs: int) -> dict:
    if fs not in _font_metrics_cache:
        def _lh(fam, sz, wt="normal"):
            return _tkFont.Font(family=fam, size=sz, weight=wt).metrics("linespace")
        _ls = _lh(_FONT, fs)
        _font_metrics_cache[fs] = {
            'ls':   _ls,
            'base': _ls + 4,
            'h1':   _lh("Tahoma",   fs+10, "bold") + 11,
            'h2':   _lh("Tahoma",   fs+6,  "bold") + 8,
            'h3':   _lh("Tahoma",   fs+3,  "bold") + 6,
            'cd':   _lh("Consolas", max(8, fs-2))  + 4,
        }
    return _font_metrics_cache[fs]

# ── Text measurement helper ───────────────────────────────────────────────────

def _measure_px(text: str, font_size: int) -> int:
    try:
        f = _tkFont.Font(family=_FONT, size=font_size)
        lines = text.split("\n") if text else [""]
        return max(f.measure(line) for line in lines)
    except Exception:
        return font_size * max((len(line) for line in text.split("\n")), default=1)


# ── Chat bubble widget ────────────────────────────────────────────────────────

class BubbleFrame(tk.Frame):
    _all_txt: list = []

    def __init__(self, parent, text, role, avatar_img=None, wrap_width=300):
        super().__init__(parent, bg=C_BG)
        self._wrap_px      = wrap_width
        self._font_size    = 15
        self._portrait_lbl = None
        self._text         = text
        self._is_user      = role == "user"

        if self._is_user:
            self._build_user(text)
        else:
            self._build_bot(text, avatar_img)

    def destroy(self):
        if hasattr(self, '_txt') and self._txt in BubbleFrame._all_txt:
            BubbleFrame._all_txt.remove(self._txt)
        super().destroy()

    # ── User bubble ───────────────────────────────────────────────────────────

    def _user_max_wrap(self) -> int:
        return max(80, self._wrap_px - 72 - 28)

    def _user_wrap_for(self, text: str) -> int:
        measured = _measure_px(text, self._font_size)
        return min(measured + 6, self._user_max_wrap())

    def _build_user(self, text):
        self.grid_columnconfigure(0, weight=1)
        self._bubble_usr = ctk.CTkFrame(self, fg_color=C_USER_BG, corner_radius=18)
        self._bubble_usr.grid(row=0, column=0, sticky="e", padx=(60, 12), pady=(3, 3))

        wrap = self._user_wrap_for(text) if text else self._user_max_wrap()
        self._lbl = ctk.CTkLabel(
            self._bubble_usr,
            text=text,
            font=ctk.CTkFont(_FONT, self._font_size + 3),
            text_color="#ffffff",
            fg_color="transparent",
            wraplength=wrap,
            justify="center",
            anchor="center",
        )
        self._lbl.pack(padx=14, pady=10)
        self._lbl.bind("<Button-3>", self._usr_copy_menu)

    # ── Bot bubble ────────────────────────────────────────────────────────────

    def _build_bot(self, text, avatar_img):
        self.grid_columnconfigure(0, weight=1)
        self._portrait_lbl = None

        bubble = ctk.CTkFrame(self, fg_color=C_BOT_BG,
                              border_color=C_BORDER, border_width=2,
                              corner_radius=4)
        bubble.grid(row=0, column=0, sticky="ew", padx=(12, 12), pady=(8, 8))
        self._bubble = bubble

        self._txt = tk.Text(
            bubble,
            font=(_FONT, self._font_size),
            fg=C_BOT_TEXT, bg=C_BOT_BG,
            relief="flat", bd=0, highlightthickness=0,
            wrap=tk.WORD, cursor="xterm",
            insertwidth=0, takefocus=False,
            state=tk.DISABLED, exportselection=False,
            selectbackground=C_BOT_BG, selectforeground=C_BOT_TEXT,
            inactiveselectbackground=C_BOT_BG,
            height=1, width=self._bot_char_width(),
            spacing1=4, spacing2=2,
        )
        self._txt.pack(padx=14, pady=10, fill="x", expand=True)
        self._txt.bindtags((str(self._txt), str(self.winfo_toplevel()), "all"))
        self._txt.tag_configure("mysel", background="#2563eb", foreground="#ffffff")
        self._txt.tag_configure("sel", background=C_BOT_BG, foreground=C_BOT_TEXT)
        self._tags_configured_for = None
        self._content_end = None
        self._sel_anchor  = None
        self._sel_range   = None
        self._sel_dragged = False
        self._txt.bind("<Button-1>",       self._sel_click)
        self._txt.bind("<B1-Motion>",      self._sel_drag)
        self._txt.bind("<ButtonRelease-1>", self._sel_release)
        self._txt.bind("<Button-3>",        self._bot_copy_menu)
        BubbleFrame._all_txt.append(self._txt)

        self._finalized     = False
        self._img_lbl       = None
        self._gdi_pending   = False
        self._last_render_t = 0.0

        if text:
            self._text = text
            self._schedule_gdi_refresh()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _bot_char_width(self):
        usable = max(60, self._wrap_px - 156 - 28)
        return max(10, int(usable / (self._font_size * 0.55)))

    def _usr_copy_menu(self, event):
        self._show_copy_menu(event, self._text)

    def _bot_copy_menu(self, event):
        from .text_utils import win_set_clipboard
        text = self._text or ""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="คัดลอกทั้งหมด",  command=lambda: win_set_clipboard(text))
        menu.add_command(label="เลือกข้อความ…", command=lambda: self._show_select_popup(event))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_select_popup(self, event):
        from .text_utils import win_set_clipboard, strip_think
        raw = strip_think(self._text or "")
        raw = _re.sub(r'\*+([^*\n]+)\*+', r'\1', raw)
        raw = _re.sub(r'^#{1,6}\s*',       '',    raw, flags=_re.MULTILINE)
        raw = _re.sub(r'^[-*]\s+',         '• ',  raw, flags=_re.MULTILINE)
        raw = _re.sub(r'`([^`]+)`',        r'\1', raw)

        popup = tk.Toplevel(self)
        popup.title("เลือกข้อความ")
        popup.configure(bg=C_BOT_BG)
        popup.resizable(True, True)

        lines = min(max(raw.count('\n') + 2, 4), 20)
        txt = tk.Text(
            popup,
            font=(_FONT, self._font_size),
            fg=C_BOT_TEXT, bg=C_BOT_BG,
            relief="flat", bd=0, highlightthickness=0,
            wrap=tk.WORD, width=60, height=lines,
            padx=12, pady=10,
        )
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", raw)

        def _copy_sel(e=None):
            try:
                sel = txt.get(tk.SEL_FIRST, tk.SEL_LAST)
                if sel:
                    win_set_clipboard(sel)
            except tk.TclError:
                pass
            return "break"

        def _key_handler(e):
            # Allow Ctrl+C (keycode 67), Ctrl+A (65) regardless of keyboard layout
            if e.state & 0x4:
                if e.keycode == 67:   # Ctrl+C
                    return _copy_sel()
                if e.keycode == 65:   # Ctrl+A
                    txt.tag_add(tk.SEL, "1.0", tk.END)
                    return "break"
            return "break"           # block all other typing

        def _popup_scroll(e):
            txt.yview_scroll(int(-1 * (e.delta / 120)), "units")
            return "break"           # stop main window from scrolling

        txt.bind("<Key>",        _key_handler)
        txt.bind("<MouseWheel>", _popup_scroll)
        popup.bind("<MouseWheel>", _popup_scroll)
        popup.bind("<Escape>", lambda e: popup.destroy())
        win_h = min(500, lines * 28 + 40)
        popup.geometry(f"560x{win_h}+{event.x_root - 20}+{event.y_root - 20}")
        popup.maxsize(900, 700)
        txt.focus_set()

    def _show_copy_menu(self, event, text):
        from .text_utils import win_set_clipboard
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="คัดลอก", command=lambda: win_set_clipboard(text))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ── Public API ────────────────────────────────────────────────────────────

    def finalize_with_pil(self):
        if self._is_user:
            return
        self._finalized = True
        if self._text:
            self._schedule_gdi_refresh()

    def set_portrait(self, img):
        if self._portrait_lbl is not None:
            self._portrait_lbl.configure(image=img)

    def stream_append(self, chunk: str):
        if self._finalized or not chunk:
            return
        self._text = (self._text or "") + chunk
        self._schedule_gdi_refresh()

    _RENDER_INTERVAL_MS = 40

    def _schedule_gdi_refresh(self):
        if self._gdi_pending:
            return
        self._gdi_pending = True
        if self._finalized:
            self.after(0, self._do_gdi_refresh)
        else:
            elapsed_ms = int((_time.monotonic() - self._last_render_t) * 1000)
            self.after(max(0, self._RENDER_INTERVAL_MS - elapsed_ms), self._do_gdi_refresh)

    def _do_gdi_refresh(self):
        self._gdi_pending = False
        self._last_render_t = _time.monotonic()
        if self._is_user or not self._text:
            return
        from .text_utils import strip_think
        text = strip_think(self._text)
        self._render_gen = getattr(self, '_render_gen', 0) + 1
        gen = self._render_gen
        import threading as _threading
        usable = max(60, self._wrap_px - 156 - 28)
        _threading.Thread(
            target=self._render_bg,
            args=(text, usable, self._font_size, gen),
            daemon=True,
        ).start()

    def _render_bg(self, text, usable, fs, gen):
        try:
            img = _gdi_render_text(text, _FONT, fs, usable, C_BOT_TEXT)
        except Exception:
            img = None
        if img is None and _PIL_REG:
            try:
                img = _pil_render_text(text, fs, usable, C_BOT_TEXT)
            except Exception:
                img = None
        if img is not None and gen == self._render_gen:
            self.after(0, lambda: self._apply_img(img, gen))
        elif img is None:
            self.after(0, lambda: self._apply_text_fallback(text, gen))

    def _apply_text_fallback(self, text, gen):
        if gen != self._render_gen or self._txt is None:
            return
        from .text_utils import strip_think as _st
        display = _st(text)
        fs = self._font_size
        fg = C_BOT_TEXT

        if (fs, fg) != self._tags_configured_for:
            self._txt.tag_configure("norm",  font=(_FONT, fs),               foreground=fg)
            self._txt.tag_configure("bold",  font=("Tahoma", fs, "bold"),    foreground=fg)
            self._txt.tag_configure("h1",    font=("Tahoma", fs+10, "bold"), foreground=fg, spacing1=8, spacing3=3)
            self._txt.tag_configure("h2",    font=("Tahoma", fs+6,  "bold"), foreground=fg, spacing1=6, spacing3=2)
            self._txt.tag_configure("h3",    font=("Tahoma", fs+3,  "bold"), foreground=fg, spacing1=4, spacing3=2)
            self._txt.tag_configure("code",  font=("Consolas", max(8,fs-2)), background="#ddd0a0", foreground="#2d1400")
            self._tags_configured_for = (fs, fg)
        self._txt.tag_raise("mysel")

        self._txt.configure(state=tk.NORMAL)
        self._txt.delete("1.0", tk.END)
        self._txt.tag_remove("mysel", "1.0", tk.END)
        self._txt.tag_remove("sel",   "1.0", tk.END)
        self._sel_range   = None
        self._sel_anchor  = None
        self._sel_dragged = False

        def _ins_mixed(seg, base_tag):
            self._txt.insert(tk.END, seg, base_tag)

        def _ins_inline(line, base_tag):
            for part in _RE_BOLD_SPLIT.split(line):
                bm = _RE_BOLD_MATCH.match(part)
                if bm: _ins_mixed(bm.group(1), "bold")
                else:  _ins_mixed(part, base_tag)

        in_code = False; code_buf = []
        _MD_LANGS = {'markdown', 'md'}
        for raw in display.split('\n'):
            if raw.startswith('```'):
                lang = raw[3:].strip().lower()
                if in_code:
                    if code_buf:
                        self._txt.insert(tk.END, '\n'.join(code_buf) + '\n', "code")
                    code_buf.clear(); in_code = False
                elif lang not in _MD_LANGS:
                    in_code = True
                continue
            if in_code:
                code_buf.append(raw); continue
            rs = raw.strip()
            hm = _RE_HEADING.match(rs)
            bm = _RE_BULLET.match(rs)
            if hm:
                tag = ("h1", "h2", "h3")[min(len(hm.group(1)), 3) - 1]
                _ins_inline(hm.group(2).strip(), tag)
                self._txt.insert(tk.END, '\n')
            elif bm:
                self._txt.insert(tk.END, '• ', "norm")
                _ins_inline(bm.group(1), "norm")
                self._txt.insert(tk.END, '\n')
            elif not rs:
                self._txt.insert(tk.END, '\n')
            else:
                _ins_inline(rs, "norm")
                self._txt.insert(tk.END, '\n')

        if code_buf:
            self._txt.insert(tk.END, '\n'.join(code_buf), "code")
        self._txt.tag_remove("mysel", "1.0", tk.END)
        self._txt.tag_remove("sel",   "1.0", tk.END)
        self._txt.configure(state=tk.DISABLED)

        _ce = self._txt.index("end-1c")
        while self._txt.compare(_ce, ">", "1.0"):
            if self._txt.get(f"{_ce}-1c") != '\n':
                break
            _ce = self._txt.index(f"{_ce}-1c")
        self._content_end = _ce

        _px = self._txt.winfo_width()
        if _px > 1:
            _new_w = max(10, int(_px / max(6, self._font_size * 0.7)))
            if _new_w != int(self._txt.cget("width")):
                self._txt.configure(width=_new_w)

        _m = _get_font_metrics(fs)

        def _tag_dl(tag):
            total = 0
            for s, e in zip(*[iter(self._txt.tag_ranges(tag))] * 2):
                r = self._txt.count(s, e, "displaylines")
                total += (r[0] if isinstance(r, tuple) else r) or 0
            return total

        _raw     = self._txt.count("1.0", "end", "update", "displaylines")
        _dlines  = (_raw[0] if isinstance(_raw, tuple) else _raw) or 1
        _h1_dl   = _tag_dl("h1");  _h2_dl = _tag_dl("h2")
        _h3_dl   = _tag_dl("h3");  _cd_dl = _tag_dl("code")
        _norm_dl = max(0, _dlines - _h1_dl - _h2_dl - _h3_dl - _cd_dl)

        _total_px = (_norm_dl * _m['base'] + _h1_dl * _m['h1'] +
                     _h2_dl  * _m['h2']   + _h3_dl * _m['h3'] + _cd_dl * _m['cd'])
        _new_h = max(1, (_total_px + _m['ls'] - 1) // _m['ls'])
        if _new_h != int(self._txt.cget("height")):
            self._txt.configure(height=_new_h)

    def _apply_img(self, img, gen):
        if gen != self._render_gen:
            return
        from PIL import ImageTk as _ITK
        photo = _ITK.PhotoImage(img)
        if self._img_lbl is None:
            self._img_lbl = tk.Label(
                self._bubble, bd=0, highlightthickness=0,
                bg=C_BOT_BG, anchor="nw",
            )
            self._img_lbl.bind("<Button-3>", self._bot_copy_menu)
            if self._txt is not None:
                if self._txt in BubbleFrame._all_txt:
                    BubbleFrame._all_txt.remove(self._txt)
                self._txt.pack_forget()
                self._txt.destroy()
                self._txt = None
            self._img_lbl.pack(padx=14, pady=10, fill="x", anchor="nw")
        self._img_lbl.configure(image=photo)
        self._img_lbl._photo = photo

    def _copy_selection(self, event=None):
        if self._txt is None:
            return "break"
        sel_range = getattr(self, '_sel_range', None)
        if sel_range:
            try:
                sel = self._txt.get(*sel_range)
                if sel:
                    from .text_utils import win_set_clipboard
                    win_set_clipboard(sel)
            except tk.TclError:
                pass
        return "break"

    def _select_all(self, event=None):
        if self._txt is None:
            return "break"
        end = self._txt.index("end-1c")
        while self._txt.compare(end, ">", "1.0"):
            prev = self._txt.index(f"{end}-1c")
            if self._txt.get(prev) != '\n':
                break
            end = prev
        self._txt.tag_remove("mysel", "1.0", tk.END)
        self._txt.tag_add("mysel", "1.0", end)
        self._txt.tag_remove("mysel", end, tk.END)
        self._sel_anchor = "1.0"
        self._sel_range  = ("1.0", end)
        return "break"

    @staticmethod
    def _is_combining(ch):
        return _ucd.category(ch) in ('Mn', 'Mc')

    def _snap_cluster_start(self, idx):
        while True:
            ch = self._txt.get(idx)
            if not ch or not self._is_combining(ch):
                break
            prev = self._txt.index(f"{idx}-1c")
            if prev == idx:
                break
            idx = prev
        return idx

    def _snap_cluster_end(self, idx):
        end_limit = self._content_end or self._txt.index("end-1c")
        if self._txt.compare(idx, ">=", end_limit):
            return end_limit
        while True:
            ch = self._txt.get(idx)
            if not ch or ch == '\n' or not self._is_combining(ch):
                break
            nxt = self._txt.index(f"{idx}+1c")
            if nxt == idx or self._txt.compare(nxt, ">=", end_limit):
                break
            idx = nxt
        return idx

    def _sel_click(self, event):
        for w in BubbleFrame._all_txt:
            if w is not self._txt:
                try:
                    if w.winfo_exists():
                        w.tag_remove("mysel", "1.0", tk.END)
                        w.tag_remove("sel",   "1.0", tk.END)
                except Exception:
                    pass
        self._sel_anchor  = self._txt.index(f"@{event.x},{event.y}")
        self._sel_dragged = False
        self._txt.tag_remove("mysel", "1.0", tk.END)
        self._txt.tag_remove("sel",   "1.0", tk.END)
        self._sel_range = None
        return "break"

    def _sel_drag(self, event):
        anchor = self._sel_anchor
        if anchor is None:
            return "break"
        self._sel_dragged = True
        cur = self._txt.index(f"@{event.x},{event.y}")
        if self._txt.compare(anchor, "<=", cur):
            start = self._snap_cluster_start(anchor)
            end   = self._snap_cluster_end(cur)
        else:
            start = self._snap_cluster_start(cur)
            end   = self._snap_cluster_end(anchor)
        while self._txt.compare(end, ">", "1.0"):
            prev = self._txt.index(f"{end}-1c")
            if self._txt.get(prev) != '\n':
                break
            end = prev
        self._txt.tag_remove("mysel", "1.0", tk.END)
        if self._txt.compare(start, "<", end):
            self._txt.tag_add("mysel", start, end)
            self._txt.tag_remove("mysel", end, tk.END)
            self._sel_range = (start, end)
        else:
            self._sel_range = None
        return "break"

    def _sel_release(self, event):
        if not self._sel_dragged:
            self._txt.tag_remove("mysel", "1.0", tk.END)
            self._txt.tag_remove("sel",   "1.0", tk.END)
            self._sel_range = None
        self._sel_dragged = False
        return "break"

    def _sel_clear(self, event=None):
        self._txt.tag_remove("mysel", "1.0", tk.END)
        self._txt.tag_remove("sel",   "1.0", tk.END)
        self._sel_range   = None
        self._sel_anchor  = None
        self._sel_dragged = False

    def update_text(self, text, wrap=None):
        if wrap is not None:
            self._wrap_px = wrap
        self._text = text
        if self._is_user:
            w = self._user_wrap_for(text) if text else self._user_max_wrap()
            self._lbl.configure(text=text, wraplength=w)
        else:
            if self._finalized:
                return
            self._schedule_gdi_refresh()

    def set_wrap(self, wrap_px):
        if wrap_px == self._wrap_px:
            return
        self._wrap_px = wrap_px
        if self._is_user:
            w = self._user_wrap_for(self._text) if self._text else self._user_max_wrap()
            self._lbl.configure(wraplength=w)
        else:
            if self._img_lbl is not None:
                self.after_idle(self._do_gdi_refresh)
            elif self._txt is not None:
                self._txt.configure(width=self._bot_char_width())

    def set_font_size(self, size):
        self._font_size = size
        if self._is_user:
            w = self._user_wrap_for(self._text) if self._text else self._user_max_wrap()
            self._lbl.configure(font=ctk.CTkFont(_FONT, size + 3), wraplength=w)
        else:
            if self._img_lbl is not None:
                self.after_idle(self._do_gdi_refresh)
            elif self._txt is not None:
                self._txt.configure(font=(_FONT, size), width=self._bot_char_width())

    def allow_shrink(self):
        pass
