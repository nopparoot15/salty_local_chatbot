# ฟ้าใส — AI Companion (Thai)

แอปแชทภาษาไทยแบบ Local 100% รันบนเครื่องตัวเอง ไม่ผ่าน Cloud ไม่มีค่าใช้จ่ายรายเดือน

---

## ฟีเจอร์

- **ฟ้าใส** — AI สาวไทยวัย 21 บุคลิกเป็นธรรมชาติ คุยได้ทุกเรื่องรวมถึง 18+
- **ระบบความสัมพันธ์** — 5 ระดับ (ห่างเหิน → รักมาก) ปรับบุคลิกการตอบอัตโนมัติ บันทึกลงไฟล์
- **Heart bar** — หัวใจ pixel art 5 ดวง แสดงระดับความสัมพันธ์แบบ real-time
- **Avatar อารมณ์** — sprite sheet 8 อารมณ์ เปลี่ยนอัตโนมัติตามบทสนทนา
- **Streaming** — ตอบแบบ real-time พิมพ์ทีละตัวอักษร กด ◼ หยุดได้ตลอด
- **Markdown** — รองรับ bold, heading, bullet, code block พร้อม color emoji
- **เวลาจริง** — รู้วัน/เวลาปัจจุบันในทุก message (ปฏิทินไทย)
- **Cross-platform** — Windows (หลัก) และ Linux

---

## ความต้องการของระบบ

| รายการ | ขั้นต่ำ | แนะนำ |
|---|---|---|
| OS | Windows 10/11 64-bit · Linux | Windows 11 |
| RAM | 16 GB | 24 GB+ |
| GPU | — (CPU ได้) | NVIDIA 8 GB VRAM+ |
| พื้นที่ว่าง | 15 GB | 20 GB+ |
| Path | **ห้ามมีช่องว่างในชื่อ path** | `C:\fahsai` |

> CPU-only ใช้ได้แต่ตอบช้ากว่า GPU มาก

### GPU ที่รองรับ

| GPU | สถานะ | หมายเหตุ |
|---|---|---|
| NVIDIA GTX 10xx+ | รองรับอัตโนมัติ | ต้องการ driver 525+ |
| AMD RX 6000/7000 | รองรับ (ROCm) | ต้องลง [AMD HIP SDK](https://rocm.docs.amd.com/en/latest/deploy/windows/) ก่อน |
| Intel / อื่นๆ | CPU mode | — |

---

## การติดตั้ง

### Windows

```
ดับเบิลคลิก setup.bat
```

Script ทำทุกอย่างให้อัตโนมัติ:
- ตรวจ GPU (NVIDIA / AMD / CPU) แล้วเลือก build ที่เหมาะสม
- ดาวน์โหลด Python 3.11 (Miniconda) ลงในโฟลเดอร์ — ไม่กระทบ Python ที่มีอยู่
- ติดตั้ง llama-cpp-python พร้อม CUDA/ROCm DLLs
- ดาวน์โหลด Model LLM (~5.5 GB) ถ้ายังไม่มี
- สร้าง shortcut `fahsai.lnk`

> ใช้เวลา 5–20 นาที ขึ้นอยู่กับความเร็วอินเทอร์เน็ต

> **AMD GPU:** ต้องติดตั้ง [AMD HIP SDK for Windows](https://rocm.docs.amd.com/en/latest/deploy/windows/) ก่อนรัน setup.bat

> **โหลดโมเดลเองล่วงหน้า:** วางไฟล์ `.gguf` ไว้ในโฟลเดอร์ `model/` แล้วค่อยรัน setup.bat

### Linux

```bash
chmod +x setup.sh
./setup.sh
```

รองรับ NVIDIA (CUDA), AMD (ROCm), และ CPU

```bash
# NixOS / nix-shell
nix-shell --run 'bash fahsai.sh'
```

### เปิดแอป

```
ดับเบิลคลิก fahsai.lnk   (Windows)
bash fahsai.sh             (Linux)
```

โหลด LLM ครั้งแรกใช้เวลา 1–2 นาที ครั้งต่อไปเร็วขึ้น

---

## วิธีใช้

| สิ่งที่ทำ | วิธี |
|---|---|
| ส่งข้อความ | พิมพ์แล้วกด Enter หรือ ▲ |
| หยุดสร้าง response | กด ◼ |
| ปรับขนาดตัวหนังสือ | กดปุ่ม A- / A+ |
| ล้างประวัติ | กดปุ่ม "ลบแชท" |
| คัดลอกข้อความ | คลิกขวาที่ bubble → เลือก คัดลอก |
| Ctrl+C/V | ใช้ได้ทุก keyboard layout รวมถึง layout ไทย |

### ระบบความสัมพันธ์

คะแนนเริ่มต้น 30/100 (ระดับ "รู้จักกัน") บันทึกลง `fahsai_save.json`

| ระดับ | คะแนน | บุคลิกที่เปลี่ยน |
|---|---|---|
| ห่างเหิน | 0–19 | ตอบสั้น ภาษาสุภาพ ไม่สนิท |
| รู้จักกัน | 20–39 | บุคลิกปกติ (default) |
| เพื่อนสนิท | 40–59 | เป็นกันเอง แซวได้ ถามกลับบ้าง |
| ชอบพอ | 60–79 | แสดงความรู้สึกอ้อมๆ เขินง่าย |
| รักมาก | 80–100 | บอกตรงๆ ทะเล้นและอ่อนหวาน |

คะแนนเพิ่มจาก: พูดคุย (+0.3), compliment (+2), romantic (+3.5), 18+ (+5)  
คะแนนลดจาก: ด่าเบา (-5), ด่าหนัก (-10)

---

## โครงสร้างโฟลเดอร์

```
fahsai-dist/
├── app.py                  # entry point — UTF-8, no-window, DLL loading
├── setup.bat               # ติดตั้ง (Windows)
├── setup.sh                # ติดตั้ง (Linux)
├── uninstall.bat           # ถอนการติดตั้ง (Windows)
├── src/
│   ├── gui.py              # UI หลัก — sidebar, chat, emotion detection, poll loop
│   ├── bubble.py           # BubbleFrame — GDI/PIL markdown renderer, select popup
│   ├── config.py           # system prompt, theme colors, font detection
│   ├── affection.py        # ระบบความสัมพันธ์ 5 ระดับ, scoring, heart display
│   ├── renderer.py         # pixel heart renderer, GDI text engine, PIL fallback
│   ├── text_utils.py       # clipboard (Win32 API), fix_gender, strip_think
│   ├── models.py           # LLM instance holder, error logging
│   ├── llm_utils.py        # prompt utilities
│   └── translate_utils.py  # translation utilities
├── model/
│   └── *.gguf              # วางโมเดล LLM ที่นี่
├── avatar.png              # sprite sheet 64×64 px/frame, อ่านอัตโนมัติ
├── fahsai_save.json        # บันทึกคะแนนความสัมพันธ์ (สร้างอัตโนมัติ)
├── app_error.log           # log ข้อผิดพลาด (สร้างเมื่อมี error)
├── icon.ico
└── ref_ser_3.wav           # reference audio (TTS)
```

---

## โมเดลที่ใช้

| โมเดล | หน้าที่ | ขนาด |
|---|---|---|
| [Typhoon2.5-Qwen3-30B-A3B Q3_K_M](https://huggingface.co/nopparoot15/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m) | LLM ตอบภาษาไทย | ~5.5 GB |

[⬇ ดาวน์โหลดโมเดลโดยตรง](https://huggingface.co/nopparoot15/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m/resolve/main/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf)

LLM พารามิเตอร์: `n_ctx=8192`, `temperature=0.8`, `min_p=0.05`, `repeat_penalty=1.08`  
Context เต็มจะตัด message เก่าออกอัตโนมัติ (สงวน 2048 tokens สำหรับ response)

---

## Avatar

ไฟล์ `avatar.png` คือ sprite sheet แถวละ 8 frame ขนาด 64×64 px ต่อ frame

| Index | อารมณ์ | trigger |
|---|---|---|
| 0 | neutral | default |
| 1 | happy / ยิ้ม | ขำ, 555, ฮ่า, ขอบคุณ, เจ๋ง … |
| 2 | sad / เศร้า | เสียใจ, เหนื่อย, ร้องไห้, sorry … |
| 3 | mild anger | โง่, บ้า, กาก (จาก user) |
| 4 | blush / เขิน | รักพี่, เขิน, ฟิน, อาย, จูบ … |
| 5 | heavy anger | แม่ง, เหี้ย, fuck … |
| 6 | pout / งอน | เบื่อ, เซ็ง, งอน, ไม่ชอบ … |
| 7 | shock / กลัว | โอ้โห, เฮ้ย, กลัว, ผี … |

ใส่ sprite sheet ใหม่แทนไฟล์เดิมได้เลย ขอให้แต่ละ frame เป็น 64×64 px

---

## การถอนการติดตั้ง

```
ดับเบิลคลิก uninstall.bat
```

ลบเฉพาะ: `miniconda/`, `pip-cache/`, `cache/`, `fahsai.lnk`  
ไฟล์อื่น (model, avatar, source code, fahsai_save.json) **ไม่ถูกลบ**

---

## Portable

โฟลเดอร์นี้ portable ทั้งหมด — copy ไปเครื่องอื่นที่มี NVIDIA driver แล้วดับเบิลคลิก `fahsai.lnk` ได้เลย ไม่ต้องลงอะไรเพิ่ม

---

## License

โค้ดเผยแพร่ภายใต้ [MIT License](LICENSE)  
โมเดล LLM มี license แยกต่างหาก ดูที่ [หน้า Hugging Face](https://huggingface.co/nopparoot15/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m)
