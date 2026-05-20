import os, sys as _sys, threading, queue, traceback, unicodedata, time as _time
import customtkinter as ctk
import tkinter as tk

# Prevent Windows from throttling this process when it is in the background.
# timeBeginPeriod(1) fixes multimedia-timer resolution (15.6 ms → 1 ms).
# SetProcessInformation(ProcessPowerThrottling) disables EcoQoS / Windows 11
# power-throttling, which can starve after() callbacks even with fine timers.
if _sys.platform == "win32":
    try:
        import ctypes as _ct_mm
        _ct_mm.windll.winmm.timeBeginPeriod(1)

        class _PPTS(_ct_mm.Structure):
            _fields_ = [("Version",     _ct_mm.c_ulong),
                        ("ControlMask", _ct_mm.c_ulong),
                        ("StateMask",   _ct_mm.c_ulong)]
        _s = _PPTS(1, 0x1, 0)   # Version=1, ControlMask=EXECUTION_SPEED, StateMask=0 (off)
        _ct_mm.windll.kernel32.SetProcessInformation(
            _ct_mm.windll.kernel32.GetCurrentProcess(),
            9,                   # ProcessPowerThrottling
            _ct_mm.byref(_s), _ct_mm.sizeof(_s),
        )
    except Exception:
        pass

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

from .config import (
    BASE_DIR, _EXE_DIR, MODEL_PATH, AUTO_TRANSLATE, get_system_prompt,
    C_BG, C_SIDEBAR, C_INPUT_BG, C_BORDER, C_TEXT, C_DIM, C_ACCENT, C_ONLINE,
    C_PORTRAIT_BG,
    _FONT_UI, _FONT_SYS,
)
from .translate_utils import is_thai, th_to_en
from .text_utils import _strip_md, strip_think, fix_gender, win_get_clipboard, win_set_clipboard
from .bubble import BubbleFrame
from . import models, affection

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

import re as _re


class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ฟ้าใส")
        self.geometry("960x540")
        self.minsize(600, 380)
        self.configure(fg_color=C_BG)
        icon_path = os.path.join(BASE_DIR, "icon.ico")
        if os.path.exists(icon_path):
            if _sys.platform == "win32":
                self.iconbitmap(icon_path)
            else:
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(icon_path)
                    self._icon_img = ImageTk.PhotoImage(img)
                    self.iconphoto(True, self._icon_img)
                except Exception:
                    pass

        affection.load()
        self.messages           = [{"role": "system", "content": get_system_prompt(affection.get_tier_prompt())}]
        self.busy               = True
        self.font_size          = 14
        self._type_speed        = 0
        self._type_buf          = ""
        self._type_pos          = 0
        self._type_active       = False
        self._type_last_t       = 0.0
        self._pending_user_text = ""
        self._last_user_display = ""
        self._last_bot_display  = ""
        self.gui_q              = queue.Queue()
        self._bot_bbl           = None
        self._bot_text          = ""
        self._bubbles           = []
        self._avatar_frames     = []
        self._stop_event        = threading.Event()
        self._auto_scroll       = True

        self._build()
        if _sys.platform != "win32":
            from .text_utils import win_set_clipboard as _wsc
            import src.text_utils as _tu
            _tu._tk_clipboard_set = lambda t: (self.clipboard_clear(), self.clipboard_append(t))
            _tu._tk_clipboard_get = self.clipboard_get
        self.after(0, self._init_avatar)
        self._poll()
        self.bind("<Configure>", self._on_resize)
        threading.Thread(target=self._load_models, daemon=True).start()
        self.bind_all("<MouseWheel>", self._on_chat_wheel, add="+")

    _SIDEBAR_W = 210

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, minsize=self._SIDEBAR_W)
        self.grid_columnconfigure(1, weight=1)

        # ── Left sidebar ──────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(self, fg_color=C_SIDEBAR, corner_radius=0,
                               width=self._SIDEBAR_W)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(4, weight=1)

        # Spacer aligns avatar top with chat scroll area (below 48px ctrl_bar)
        ctk.CTkFrame(sidebar, fg_color="transparent", height=48).grid(
            row=0, column=0, sticky="ew")

        # Avatar
        av_size = self._SIDEBAR_W - 20
        self._sidebar_avatar_lbl = ctk.CTkLabel(
            sidebar, text="", fg_color=C_PORTRAIT_BG,
            width=av_size, height=av_size, corner_radius=6,
        )
        self._sidebar_avatar_lbl.grid(row=1, column=0, padx=10, pady=(0, 0), sticky="n")

        self._heart_lbl = ctk.CTkLabel(sidebar, text="", fg_color="transparent",
                                       width=av_size, height=30)
        self._heart_lbl.grid(row=2, column=0, pady=(10, 2))

        self._tier_lbl = ctk.CTkLabel(
            sidebar, text="",
            font=ctk.CTkFont(_FONT_UI, 14),
            text_color=C_DIM,
        )
        self._tier_lbl.grid(row=3, column=0, pady=(0, 0))

        # row 4 is weight=1 spacer — pushes name/status to bottom

        ctk.CTkLabel(sidebar, text="ฟ้าใส",
                     font=ctk.CTkFont(_FONT_UI, 14, "bold"),
                     text_color=C_TEXT).grid(row=5, column=0, pady=(0, 3))

        status_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        status_row.grid(row=6, column=0, pady=(0, 14))
        self._status_dot = ctk.CTkLabel(status_row, text="●", text_color=C_DIM,
                                        font=ctk.CTkFont(_FONT_SYS, 11))
        self._status_dot.pack(side=tk.LEFT, padx=(0, 4))
        self._status_lbl = ctk.CTkLabel(status_row, text="กำลังโหลด…",
                                        font=ctk.CTkFont(_FONT_UI, 13),
                                        text_color=C_DIM)
        self._status_lbl.pack(side=tk.LEFT)

        # ── Main area ─────────────────────────────────────────────────────────
        main = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")

        # ── Use pack for the three main rows — more reliable than grid on Linux ──

        # Top bar (pack first at TOP)
        ctrl_bar = ctk.CTkFrame(main, fg_color=C_SIDEBAR, corner_radius=0, height=48)
        ctrl_bar.pack(side=tk.TOP, fill=tk.X)
        ctrl_bar.pack_propagate(False)
        ctrl_bar.grid_columnconfigure(0, weight=1)

        # Right: buttons
        btn_kw = dict(width=42, height=34, corner_radius=8,
                      fg_color=C_BORDER, hover_color=C_ACCENT,
                      text_color=C_TEXT, font=ctk.CTkFont(_FONT_SYS, 13, "bold"))
        ctrl = ctk.CTkFrame(ctrl_bar, fg_color="transparent")
        ctrl.grid(row=0, column=1, padx=10, pady=7)
        ctk.CTkButton(ctrl, text="A-", **btn_kw,
                      command=self._font_smaller).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(ctrl, text="A+", **btn_kw,
                      command=self._font_larger).pack(side=tk.LEFT, padx=2)
        self._clear_btn = ctk.CTkButton(
            ctrl, text="ลบแชท", width=64, height=34, corner_radius=8,
            fg_color="#5a1a1a", hover_color="#8b2020",
            text_color=C_TEXT, font=ctk.CTkFont(_FONT_UI, 12),
            command=self._clear_chat,
        )
        self._clear_btn.pack(side=tk.LEFT, padx=(8, 2))

        # Input bar (pack at BOTTOM before scroll so it stays pinned)
        inp_bar = ctk.CTkFrame(main, fg_color=C_SIDEBAR, corner_radius=0, height=84)
        inp_bar.pack(side=tk.BOTTOM, fill=tk.X)
        inp_bar.pack_propagate(False)
        inp_bar.grid_columnconfigure(0, weight=1)
        inp_bar.grid_rowconfigure(0, weight=1)

        # Chat scroll area (fills remaining space)
        self._scroll = ctk.CTkScrollableFrame(
            main, fg_color=C_BG, corner_radius=0,
            scrollbar_button_color=C_BORDER,
            scrollbar_button_hover_color=C_ACCENT,
        )
        self._scroll.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._scroll.grid_columnconfigure(0, weight=1)
        try:
            self._scroll._scrollable_frame.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        self._scroll_row = 0

        _entry_bw = 1 if _sys.platform == "win32" else 2
        self._entry = ctk.CTkEntry(
            inp_bar, placeholder_text="พิมพ์ข้อความ…",
            fg_color=C_INPUT_BG, border_color=C_BORDER,
            text_color=C_TEXT, placeholder_text_color=C_DIM,
            font=ctk.CTkFont(_FONT_UI, 16),
            corner_radius=25, height=50, border_width=_entry_bw,
        )
        self._entry.grid(row=0, column=0, padx=(14, 8), pady=15, sticky="ew")
        self._entry.bind("<Return>",   lambda _: self._send())
        self._entry.bind("<KeyPress>", self._entry_keypress)
        self._entry.bind("<Button-3>", self._entry_menu)
        try:
            self._entry._entry.bind("<KeyPress>", self._entry_keypress)
            self._entry._entry.bind("<Return>",   lambda _: self._send())
            self._entry._entry.bind("<Button-3>", self._entry_menu)
        except Exception:
            pass

        self._send_btn = ctk.CTkButton(
            inp_bar, text="▲", width=50, height=50,
            fg_color=C_ACCENT, hover_color="#c8a020",
            text_color="#1a0e04", corner_radius=25,
            font=ctk.CTkFont(_FONT_SYS, 18, "bold"),
            command=self._send,
        )
        self._send_btn.grid(row=0, column=1, padx=(0, 14), pady=15)

        self._set_ui(False)
        self._update_hearts()

    # ── Avatar ────────────────────────────────────────────────────────────────

    def _init_avatar(self):
        self._avatar_frames = self._load_avatar_frames()
        if self._avatar_frames:
            self._update_avatar(0)

    def _load_avatar_frames(self):
        if not _PIL_OK:
            return []
        path = os.path.join(BASE_DIR, "avatar.png")
        if not os.path.exists(path):
            return []
        try:
            sheet = Image.open(path).convert("RGBA")
            fw, fh = 64, 64
            disp = self._SIDEBAR_W - 20
            frames = []
            for r in range(sheet.height // fh):
                for c in range(sheet.width // fw):
                    crop = sheet.crop((c * fw, r * fh, (c+1) * fw, (r+1) * fh))
                    frames.append(crop.resize((disp, disp), Image.NEAREST))
            return frames  # list of PIL Images
        except Exception:
            return []

    def _composite_avatar(self, frame_pil):
        from .renderer import _make_heart_strip
        from PIL import ImageDraw
        av = frame_pil.copy().convert("RGBA")
        av_w, av_h = av.size

        n_full, n_half = affection.hearts()
        full5 = n_full // 2
        half5 = 1 if (n_full % 2 >= 1 or n_half) else 0
        hearts_pil = _make_heart_strip(full5, half5, n_total=5, scale=4, raw=True)
        if hearts_pil:
            h_w = av_w - 20
            h_h = round(hearts_pil.height * h_w / hearts_pil.width)
            hearts_r = hearts_pil.resize((h_w, h_h), Image.NEAREST)
            strip_h = h_h + 14
            strip = Image.new("RGBA", (av_w, strip_h), (0, 0, 0, 0))
            ImageDraw.Draw(strip).rectangle(
                [0, 0, av_w - 1, strip_h - 1], fill=(20, 8, 0, 160))
            av.alpha_composite(strip, (0, av_h - strip_h))
            hx = (av_w - h_w) // 2
            hy = av_h - strip_h + (strip_h - h_h) // 2
            av.paste(hearts_r, (hx, hy), hearts_r)

        return av

    def _update_avatar(self, emo_idx: int):
        if not self._avatar_frames:
            return
        self._cur_emo_idx = emo_idx % len(self._avatar_frames)
        frame = self._avatar_frames[self._cur_emo_idx]
        av_size = frame.width
        img = ctk.CTkImage(light_image=frame, dark_image=frame, size=(av_size, av_size))
        self._sidebar_avatar_lbl.configure(image=img)
        self._sidebar_avatar_lbl._img = img

    _EMO_NSFW  = ("เย็ด","ควย","หี","เงี่ยน","เสียว","น้ำแตก","อม","เลีย","นม","หัวนม",
                  "ก้น","เปียก","แข็ง","เปลือย","ถอด","ลูบ","จับ","18+","ตรงนั้น",
                  "เล้าโลม","โป๊","ซักซวย","ใส่","สอด","ดูด","ถลก","ออร์แกสม์",
                  "sex","naughty","horny","wet","cum","cock","pussy","boob","ass","naked","moan")
    _EMO_HEAVY = ("แม่ง","เหี้ย","ควาย","ห่า","สัตว์","ระยำ","ชิบหาย","สถุล",
                  "fuck","shit","bitch","asshole")
    _EMO_MILD  = ("โง่","บ้า","กาก","ขยะ","ไร้สาระ","น่าเกลียด","ไอ้","อี","มึง",
                  "stupid","idiot","dumb","เลว","ชั่ว","แย่","ห่วย")
    _EMO_BLUSH = ("รักพี่","ชอบพี่","แอบชอบ","เป็นแฟน","คิดถึงพี่","กอด","จูบ",
                  "น่ารัก","หอม","เขิน","ฟิน","อาย","ใจสั่น","หวาน","โรแมนติก",
                  "kiss","cute","love","beautiful","pretty","hug","miss","darling","honey","romantic")
    _EMO_HAPPY = ("ดีใจ","สนุก","ยินดี","เยี่ยม","สุดยอด","ดีมาก","ขอบคุณ","ขำ",
                  "555","ฮา","ฮ่า","ฮ้า","ฮิ","เฮฮา","ยิ้ม","ตลก","โอเค","เจ๋ง","เก่ง",
                  "ปัง","เลิศ","มีความสุข","สนุกมาก","ดีเลย","เฮ",
                  "happy","fun","thanks","haha","hehe","great","awesome","funny","lol","lmao","yay")
    _EMO_POUT  = ("เบื่อ","เซ็ง","ไม่อยาก","งอน","หงุดหงิด","ไม่สนุก","เฉยๆ","ก็ได้",
                  "ไม่ชอบ","ไม่โอเค","งอนนะ","เซ็งเลย","หน้าบึ้ง",
                  "bored","annoyed","sulking","whatever","meh")
    _EMO_SAD   = ("เสียใจ","เศร้า","น่าเสียดาย","ขอโทษ","โชคไม่ดี","เป็นห่วง","หดหู่",
                  "ร้องไห้","น้ำตา","หัวใจหัก","เหนื่อย","ท้อ","เจ็บปวด","เจ็บใจ",
                  "sad","sorry","unfortunate","worried","upset","heartbroken","cry","tired")
    _EMO_SHOCK = ("โอ้โห","ว้าว","น่าแปลก","ไม่น่าเชื่อ","จริงเหรอ","อ้าว","ตกใจ",
                  "เฮ้ย","เอ้ย","ช็อค","แปลกมาก","ไม่คิดว่า",
                  "wow","no way","seriously","omg","whoa","what the")
    _EMO_FEAR  = ("กลัว","น่ากลัว","สยอง","ขนลุก","หลอน","ผี","วิญญาณ","ปีศาจ",
                  "ไม่กล้า","สะพรึง","น่าหวาดเสียว",
                  "scary","horror","ghost","creepy","terrifying","dark","fear")

    def _detect_emotion(self, bot_text, user_text=""):
        # .lower() only affects ASCII — Thai chars are unaffected
        combined = (bot_text + user_text).lower()
        bot_lo   = bot_text.lower()
        user_lo  = user_text.lower()

        if any(c in combined for c in "😡🤬💢😤"):                       return 5
        if any(c in combined for c in "😒😑🙄"):                         return 6
        if any(c in combined for c in "😢😭😔💔😿"):                     return 2
        if any(c in combined for c in "😱😮😲🤯"):                       return 7
        if any(c in combined for c in "😳😘💋🫦😏🤤😈💕💗❤🥰😍🔞💦"):  return 4
        if any(c in combined for c in "😊😄😁🎉✨😆😂🤣😋😜🥳"):         return 1

        if any(k in combined for k in self._EMO_NSFW):   return 4
        if any(k in user_lo  for k in self._EMO_HEAVY):  return 5
        if any(k in user_lo  for k in self._EMO_MILD):   return 3
        if any(k in combined for k in self._EMO_BLUSH):  return 4
        if any(k in bot_lo   for k in self._EMO_HAPPY):  return 1
        if any(k in bot_lo   for k in self._EMO_POUT):   return 6
        if any(k in bot_lo   for k in self._EMO_SAD):    return 2
        if any(k in combined for k in self._EMO_FEAR):   return 7
        if any(k in combined for k in self._EMO_SHOCK):  return 7
        return 0

    # ── Font size ─────────────────────────────────────────────────────────────

    def _wrap_width(self):
        return max(200, self.winfo_width() - self._SIDEBAR_W - 40)

    def _on_resize(self, _=None):
        try:
            self.after_cancel(self._resize_job)
        except AttributeError:
            pass
        self._resize_job = self.after(300, self._apply_resize)

    def _apply_resize(self):
        wrap = self._wrap_width()
        for bbl, _ in self._bubbles:
            bbl.set_wrap(wrap)

    # ── Typing speed ─────────────────────────────────────────────────────────

    _SPEED_CPS = [0, 20, 50, 120, 300, 999]

    def _type_tick(self):
        bbl = self._bot_bbl
        if bbl is None:
            self._type_active = False
            return
        buf = self._type_buf
        pos = self._type_pos
        cps = self._SPEED_CPS[self._type_speed]
        if pos < len(buf):
            if cps == 0:
                step = len(buf) - pos
            else:
                # Use actual elapsed time so throttled/late ticks still keep up
                now = _time.monotonic()
                elapsed = max(0.016, now - self._type_last_t)
                step = max(1, int(cps * elapsed))
                self._type_last_t = now
            end = min(len(buf), pos + step)
            while end < len(buf) and unicodedata.category(buf[end]) in ('Mn', 'Mc'):
                end += 1
            chunk = buf[pos:end]
            self._type_pos = end
            bbl.stream_append(chunk)
            self._scroll_to_bottom()
        if self._type_pos >= len(self._type_buf):
            self._type_active = False
            return
        self.after(16, self._type_tick)

    def _font_smaller(self):
        if self.font_size > 9:
            self.font_size -= 1
            self._refresh_fonts()

    def _font_larger(self):
        if self.font_size < 20:
            self.font_size += 1
            self._refresh_fonts()

    def _refresh_fonts(self):
        for bbl, _ in self._bubbles:
            bbl.set_font_size(self.font_size)

    # ── Affection ─────────────────────────────────────────────────────────────

    def _update_hearts(self):
        if self._avatar_frames:
            self._update_avatar(getattr(self, '_cur_emo_idx', 0))
        from .renderer import _make_heart_strip
        n_full, n_half = affection.hearts()
        full5 = n_full // 2
        half5 = 1 if (n_full % 2 >= 1 or n_half) else 0
        heart_img = _make_heart_strip(full5, half5, n_total=5, scale=4)
        if heart_img:
            self._heart_lbl.configure(image=heart_img)
            self._heart_lbl._img = heart_img
        self._tier_lbl.configure(text=affection.get_tier_name(), text_color=C_DIM)

    _TIER_UP_MSGS = [
        "ฟ้าใสเริ่มสนิทกับพี่มากขึ้นแล้ว ♥",
        "ฟ้าใสนับพี่เป็นเพื่อนสนิทแล้วนะ ♥",
        "ฟ้าใสชอบพี่มากเลย... ♥",
        "ฟ้าใสรักพี่มากๆ เลยนะ ♥♥",
    ]
    _TIER_DOWN_MSGS = [
        "ฟ้าใสน้อยใจนิดนึงนะพี่...",
        "พี่ทำให้ฟ้าใสเสียใจเลย",
        "ฟ้าใสไม่ชอบแบบนี้เลยนะพี่",
        "ฟ้าใสห่วงพี่นะ แต่แบบนี้...",
    ]

    def _show_affection_note(self, new_tier: int, went_up: bool):
        msgs = self._TIER_UP_MSGS if went_up else self._TIER_DOWN_MSGS
        idx  = min(new_tier if went_up else (3 - new_tier), len(msgs) - 1)
        color = C_ACCENT if went_up else "#c05020"
        self._tier_lbl.configure(text=msgs[idx], text_color=color)
        def _revert():
            try:
                self._tier_lbl.configure(
                    text=affection.get_tier_name(), text_color=C_DIM)
            except Exception:
                pass
        self.after(4000, _revert)

    # ── Bubbles ───────────────────────────────────────────────────────────────

    _MAX_BUBBLES = 40

    def _add_bubble(self, text, role):
        bbl = BubbleFrame(self._scroll, text, role, avatar_img=None, wrap_width=self._wrap_width())
        bbl.set_font_size(self.font_size)

        if len(self._bubbles) >= self._MAX_BUBBLES:
            old_bbl, _ = self._bubbles.pop(0)
            try:
                old_bbl.destroy()
            except Exception:
                pass
            for i, (b, _) in enumerate(self._bubbles):
                b.grid(row=i, column=0, sticky="ew", padx=0, pady=1)
            self._scroll_row = len(self._bubbles)

        bbl.grid(row=self._scroll_row, column=0, sticky="ew", padx=0, pady=1)
        self._scroll_row += 1
        self._bubbles.append((bbl, role))
        self._scroll_to_bottom()
        return bbl

    def _on_chat_wheel(self, event):
        if event.delta > 0:          # scrolling up → user is browsing
            self._auto_scroll = False
        else:                        # scrolling down → re-enable if near bottom
            self.after(80, self._recheck_auto_scroll)

    def _recheck_auto_scroll(self):
        try:
            if self._scroll._parent_canvas.yview()[1] >= 0.97:
                self._auto_scroll = True
        except Exception:
            pass

    def _scroll_to_bottom(self):
        if not self._auto_scroll:
            return
        if getattr(self, "_scroll_queued", False):
            return
        self._scroll_queued = True
        def _do():
            self._scroll_queued = False
            try:
                self._scroll._parent_canvas.yview_moveto(1.0)
            except Exception:
                pass
        self.after(80, _do)

    def _start_bot_bubble(self):
        self._bot_bbl     = self._add_bubble("", "bot")
        self._bot_text    = ""
        self._type_buf    = ""
        self._type_pos    = 0
        self._type_active = False

    def _append_token(self, token):
        if self._bot_bbl is None:
            self._start_bot_bubble()
        prev_len       = len(self._type_buf)
        self._bot_text += token
        display = fix_gender(strip_think(self._bot_text))
        if not display:
            return
        self._type_buf = display
        if not self._type_active:
            self._type_active = True
            self._type_last_t = _time.monotonic()
            self.after(16, self._type_tick)
        if self._avatar_frames and (prev_len // 50 != len(display) // 50):
            self._update_avatar(self._detect_emotion(display, self._last_user_display))
        self._scroll_to_bottom()

    def _finish_bot_bubble(self):
        if self._bot_bbl is not None and self._type_pos < len(self._type_buf):
            self._bot_bbl.stream_append(self._type_buf[self._type_pos:])
        self._type_active = False
        self._bot_bbl  = None
        self._bot_text = ""
        self._type_buf = ""
        self._type_pos = 0

    # ── Queue poll ────────────────────────────────────────────────────────────

    def _poll(self):
        try:
            while True:
                try:
                    msg = self.gui_q.get_nowait()
                except queue.Empty:
                    break
                try:
                    act = msg[0]
                    if act == "status":
                        self._status_lbl.configure(text=msg[1])
                    elif act == "dot":
                        self._status_dot.configure(text_color=msg[1])
                    elif act == "token":
                        self._append_token(msg[1])
                    elif act == "user_bubble":
                        self._add_bubble(msg[1], "user")
                        if self._avatar_frames:
                            self._update_avatar(self._detect_emotion("", msg[1]))
                    elif act == "ready":
                        self.busy = False
                        self._set_ui(True)
                        self._status_lbl.configure(text="ออนไลน์")
                        self._status_dot.configure(text_color=C_ONLINE)
                        self._entry.focus()
                    elif act == "done":
                        if len(msg) > 1:
                            self._last_bot_display = msg[1]
                        self.busy = False
                        self._set_ui(True)
                        self._status_lbl.configure(text="ออนไลน์")
                        self._status_dot.configure(text_color=C_ONLINE)
                        self._finish_bot_bubble()
                        bot_txt  = self._last_bot_display
                        user_txt = self._last_user_display
                        if self._avatar_frames and (bot_txt or user_txt):
                            self._update_avatar(self._detect_emotion(bot_txt, user_txt))
                        for bbl, role in reversed(self._bubbles):
                            if role == "bot":
                                bbl.finalize_with_pil()
                                break
                        old_tier = affection.get_tier()
                        affection.apply_delta(affection.compute_delta(user_txt, bot_txt))
                        new_tier = affection.get_tier()
                        affection.save()
                        self._update_hearts()
                        if new_tier != old_tier:
                            self._show_affection_note(new_tier, new_tier > old_tier)
                except Exception:
                    models.log_err("POLL ERROR:\n" + traceback.format_exc())
        finally:
            self.after(40, self._poll)

    # keycode 86=V, 67=C, 88=X, 65=A — physical keys, layout-independent
    def _entry_keypress(self, event):
        if not (event.state & 0x4):   # no Ctrl held
            return
        kc = event.keycode
        if kc == 86:                  # Ctrl+V → paste
            return self._on_paste()
        if kc == 67:                  # Ctrl+C → copy selection
            return self._on_copy()
        if kc == 88:                  # Ctrl+X → cut
            return self._on_cut()
        if kc == 65:                  # Ctrl+A → select all
            self._entry.select_range(0, tk.END)
            return "break"

    def _on_copy(self, event=None):
        try:
            text = self._entry.selection_get()
        except tk.TclError:
            text = self._entry.get()
        if text:
            win_set_clipboard(text)
        return "break"

    def _on_cut(self, event=None):
        try:
            sel_start = self._entry.index(tk.SEL_FIRST)
            sel_end   = self._entry.index(tk.SEL_LAST)
            text = self._entry.get()[sel_start:sel_end]
            win_set_clipboard(text)
            self._entry.delete(sel_start, sel_end)
        except tk.TclError:
            pass
        return "break"

    def _on_paste(self, event=None):
        text = win_get_clipboard()
        if text:
            try:
                sel_start = self._entry.index(tk.SEL_FIRST)
                sel_end   = self._entry.index(tk.SEL_LAST)
                self._entry.delete(sel_start, sel_end)
            except tk.TclError:
                pass
            self._entry.insert(tk.INSERT, text)
        return "break"

    def _entry_menu(self, event=None):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="วาง",    command=self._on_paste)
        menu.add_command(label="คัดลอก", command=lambda: win_set_clipboard(self._entry.get()))
        menu.add_command(label="ล้าง",   command=lambda: self._entry.delete(0, tk.END))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _clear_chat(self):
        # Signal any running generation thread to stop
        self._stop_event.set()
        # Drain stale queue items so no leftover "token"/"done" messages fire after clear
        while True:
            try:
                self.gui_q.get_nowait()
            except queue.Empty:
                break
        # Force-reset state regardless of busy flag
        self.busy           = False
        self._type_active   = False
        for bbl, _ in self._bubbles:
            try:
                bbl.destroy()
            except Exception:
                pass
        self._bubbles.clear()
        self._scroll_row    = 0
        self.messages       = [{"role": "system", "content": get_system_prompt(affection.get_tier_prompt())}]
        self._bot_bbl       = None
        self._bot_text      = ""
        self._type_buf      = ""
        self._type_pos      = 0
        self._auto_scroll   = True
        self._stop_event.clear()
        self._set_ui(True)
        self._status_lbl.configure(text="ออนไลน์")
        self._status_dot.configure(text_color=C_ONLINE)
        self.after(10, lambda: self._entry._entry.focus_set())

    def _set_ui(self, on):
        self._entry.configure(state="normal" if on else "disabled")
        self._clear_btn.configure(state="normal" if on else "disabled")
        if on:
            self._send_btn.configure(state="normal", text="▲",
                                     fg_color=C_ACCENT, hover_color="#c8a020")
            # CTkEntry may rebind its internal widget on state change — re-apply ours
            try:
                self._entry._entry.bind("<KeyPress>", self._entry_keypress)
            except Exception:
                pass
        else:
            self._send_btn.configure(state="normal", text="◼",
                                     fg_color="#8b2020", hover_color="#c0392b")

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load_models(self):
        errs = []
        self.gui_q.put(("status", "โหลด LLM…"))
        try:
            from llama_cpp import Llama as _Llama
            _n_threads = max(1, (os.cpu_count() or 4) - 1)
            _common = dict(
                model_path=MODEL_PATH,
                n_ctx=8192,
                n_batch=2048,       # larger prefill batch → faster prompt processing
                n_threads=_n_threads,
                n_threads_batch=_n_threads,
                offload_kqv=True,   # KV cache on GPU
                flash_attn=True,    # Flash Attention 2 — big speedup on Ampere/Ada
                use_mlock=True,     # pin CPU-side tensors in RAM
                verbose=False,
                chat_format="chatml",
            )
            try:
                models.llm = _Llama(n_gpu_layers=-1, **_common)
            except Exception:
                # GPU failed — retry CPU-only without flash_attn (not all CPU builds support it)
                _common_cpu = {k: v for k, v in _common.items() if k not in ("flash_attn", "offload_kqv", "use_mlock")}
                models.llm = _Llama(n_gpu_layers=0, **_common_cpu)
        except Exception:
            errs.append("LLM:\n" + traceback.format_exc())

        if errs:
            with open(os.path.join(_EXE_DIR, "app_error.log"), "w", encoding="utf-8") as f:
                f.write("\n".join(errs))
            self.gui_q.put(("status", "โหลด LLM ล้มเหลว — ดู app_error.log"))

        self.gui_q.put(("ready",))

    # ── Send / chat ───────────────────────────────────────────────────────────

    def _stop_generation(self):
        self._stop_event.set()
        if self._bot_bbl is not None and self._type_pos < len(self._type_buf):
            self._bot_bbl.stream_append(self._type_buf[self._type_pos:])
            self._type_pos = len(self._type_buf)
        self._type_active = False

    def _send(self):
        if self.busy:
            self._stop_generation()
            return
        text = self._entry.get().strip()
        if not text:
            return
        self._entry.delete(0, "end")
        self.busy = True
        self._auto_scroll = True
        self._stop_event.clear()
        self._set_ui(False)
        self.gui_q.put(("user_bubble", text))
        self._pending_user_text = text
        self._last_user_display = text
        self.gui_q.put(("status", "กำลังคิด…"))
        self.gui_q.put(("dot", C_DIM))
        threading.Thread(target=self._chat_thread, daemon=True).start()

    def _chat_thread(self):
        _done_sent = False
        try:
            self.__chat_body()
            _done_sent = True
        except Exception:
            models.log_err("CHAT CRASH:\n" + traceback.format_exc())
        finally:
            if not _done_sent:
                try:
                    self.gui_q.put(("done",))
                except Exception:
                    pass

    _N_CTX            = 8192
    _RESPONSE_RESERVE = 2048  # tokens reserved for the next response

    def _trim_to_tokens(self, messages):
        """Return a copy of messages with history trimmed to fit the context budget."""
        if models.llm is None:
            return messages

        def _tok(msg):
            try:
                return len(models.llm.tokenize(
                    (msg["role"] + ": " + msg["content"]).encode("utf-8"),
                    add_bos=False,
                ))
            except Exception:
                return len(msg["content"]) // 3

        sys_msg  = messages[0]
        history  = messages[1:]
        budget   = self._N_CTX - _tok(sys_msg) - self._RESPONSE_RESERVE

        kept = []
        for msg in reversed(history):
            cost = _tok(msg)
            if cost > budget:
                break
            budget -= cost
            kept.append(msg)

        return [sys_msg] + list(reversed(kept))

    def __chat_body(self):
        user_text = self._pending_user_text
        en_text   = th_to_en(user_text) if (AUTO_TRANSLATE and is_thai(user_text)) else user_text
        self.messages.append({"role": "user", "content": en_text})
        self.messages[0]["content"] = get_system_prompt(affection.get_tier_prompt())
        self.messages = self._trim_to_tokens(self.messages)

        raw    = ""
        llm_ok = False

        try:
            msgs = list(self.messages)

            self.gui_q.put(("status", "กำลังพิมพ์…"))
            for chunk in models.llm.create_chat_completion(
                messages=msgs, stream=True,
                temperature=0.8,
                top_k=0, min_p=0.05,
                repeat_penalty=1.08,
                frequency_penalty=0.25,
                max_tokens=-1,
            ):
                token = (chunk["choices"][0]["delta"].get("content") or "")
                raw += token
                if token:
                    self.gui_q.put(("token", token))
                if self._stop_event.is_set():
                    break

            llm_ok = True
        except Exception:
            models.log_err("LLM ERROR:\n" + traceback.format_exc())

        clean = fix_gender(strip_think(raw))

        if llm_ok and raw:
            self.messages.append({"role": "assistant", "content": _strip_md(clean)})

        if not clean and not self._stop_event.is_set():
            clean = "ขอโทษนะพี่ หนูสับสนนิดหน่อย ลองถามใหม่ได้เลย"
            self.gui_q.put(("token", clean))

        self.gui_q.put(("done", clean))
