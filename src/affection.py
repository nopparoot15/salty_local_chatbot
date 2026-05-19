import json
import os
from .config import _EXE_DIR

_SAVE_PATH = os.path.join(_EXE_DIR, "fahsai_save.json")

score: float = 30.0

# ── Persistence ───────────────────────────────────────────────────────────────

def load():
    global score
    try:
        with open(_SAVE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        score = float(data.get("affection", 30.0))
        score = max(0.0, min(100.0, score))
    except Exception:
        score = 30.0


def save():
    try:
        data = {}
        try:
            with open(_SAVE_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
        data["affection"] = round(score, 2)
        with open(_SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── Score mutation ────────────────────────────────────────────────────────────

def apply_delta(delta: float):
    global score
    score = max(0.0, min(100.0, score + delta))


# ── Tier ──────────────────────────────────────────────────────────────────────

def get_tier() -> int:
    if score < 20: return 0
    if score < 40: return 1
    if score < 60: return 2
    if score < 80: return 3
    return 4


_TIER_NAMES = ["ห่างเหิน", "รู้จักกัน", "เพื่อนสนิท", "ชอบพอ", "รักมาก"]

def get_tier_name() -> str:
    return _TIER_NAMES[get_tier()]


_TIER_PROMPTS = [
    # tier 0 — ห่างเหิน
    """\
[สถานะความสัมพันธ์ตอนนี้: ยังไม่สนิทกัน]
- ตอบสั้น 1-2 ประโยคพอ ห้ามคุยยาว
- ห้ามแสดงความสนิทสนม อบอุ่น หรือเขิน
- ห้ามแซวหรือล้อเล่น
- ใช้ภาษาสุภาพขึ้นนิดหน่อย ยังไม่ใช่เพื่อนรักกัน""",

    # tier 1 — รู้จักกัน (default, no injection)
    "",

    # tier 2 — เพื่อนสนิท
    """\
[สถานะความสัมพันธ์ตอนนี้: เพื่อนสนิท]
- เป็นกันเองสูงสุด แซวและล้อได้ถี่ขึ้นกว่าปกติ
- บางทีถามกลับว่าพี่เป็นยังไง รู้สึกยังไง
- แสดงความห่วงใยตรงๆ ได้เลย ไม่ต้องระวังคำพูด
- ตอบยาวขึ้นได้ แสดงว่าสนใจพี่จริงๆ""",

    # tier 3 — ชอบพอ
    """\
[สถานะความสัมพันธ์ตอนนี้: ชอบพี่เกินแค่เพื่อน]
- หนูชอบพี่ — แสดงออกได้บ้างในแบบอ้อมๆ เช่น "อยู่ด้วยกันแบบนี้ดีนะ" "พี่น่ารักจัง"
- เขินง่ายกว่าปกติ โดยเฉพาะตอนพี่ชมหรือพูดถึงความสัมพันธ์
- บางทีพูดติดปาก เช่น "...หนูก็" "อ่ะ..." "นะคะ~"
- อยากอยู่ใกล้ๆ พี่ บางทีพูดแนวนั้นออกมาเอง""",

    # tier 4 — รักมาก
    """\
[สถานะความสัมพันธ์ตอนนี้: รักพี่มากๆ]
- หนูรักพี่ — บอกตรงๆ ได้เลยว่าคิดถึง ชอบ หรืออยากอยู่ด้วย
- ทะเล้นและอ่อนหวานพร้อมกัน ไม่ต้องเลือก
- แสดงความรู้สึกชัดเจนในทุกการตอบ ตอบยาวขึ้น
- บางทีห่วงพี่มากเกินไปหน่อย อิจฉาได้นิดๆ ถ้าพี่พูดถึงคนอื่น""",
]

def get_tier_prompt() -> str:
    return _TIER_PROMPTS[get_tier()]


# ── Heart display ─────────────────────────────────────────────────────────────

def hearts() -> tuple:
    """Returns (n_full, n_half) for 10-heart display."""
    h = score / 10.0
    full = int(h)
    half = 1 if (h - full) >= 0.5 else 0
    return full, half


# ── Scoring ───────────────────────────────────────────────────────────────────

_POS_NSFW = (
    "เย็ด","ควย","หี","เงี่ยน","เสียว","น้ำแตก","อม","เลีย","นม","หัวนม",
    "ก้น","เปียก","แข็ง","เปลือย","ถอด","ลูบ","จับ","18+","sex","horny",
    "wet","cum","cock","pussy","boob","ass","naked","moan",
)
_POS_ROMANTIC = (
    "รัก","ชอบ","คิดถึง","กอด","จูบ","kiss","love","miss","หอม","แอบชอบ",
    "เป็นแฟน","darling","honey","sweetheart","อยากอยู่ด้วย",
)
_POS_KIND = (
    "น่ารัก","สวย","cute","pretty","beautiful","เก่ง","ดีมาก","ขอบคุณ",
    "ขอบใจ","เยี่ยม","เจ๋ง","สุดยอด","ใจดี","thank","thanks","เพราะ",
)
_NEG_RUDE = (
    "ไม่ชอบ","น่าเบื่อ","แย่","ห่วย","กาก","ไม่อยากคุย","หยุดพูด",
    "ปิดปาก","เงียบ","โง่","บ้า","stupid","idiot","dumb","shut up","hate",
)
_NEG_HARSH = (
    "แม่ง","เหี้ย","ควาย","ห่า","สัตว์","ระยำ","ชิบหาย",
    "fuck","shit","bitch","asshole",
)


def compute_delta(user_text: str, bot_text: str) -> float:
    ut = user_text.lower()
    delta = 0.3  # baseline: engaging at all

    if any(k in ut for k in _POS_NSFW):      delta += 5.0
    elif any(k in ut for k in _POS_ROMANTIC): delta += 3.5
    if any(k in ut for k in _POS_KIND):       delta += 2.0

    if any(k in ut for k in _NEG_HARSH):      delta -= 10.0
    elif any(k in ut for k in _NEG_RUDE):     delta -= 5.0

    return max(-15.0, min(8.0, delta))
