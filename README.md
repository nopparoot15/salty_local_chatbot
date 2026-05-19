# ฟ้าใส — AI Chat (Thai)

แอปแชทภาษาไทยแบบ Local ที่รันบนเครื่องตัวเอง 100% ไม่ผ่าน Cloud ไม่มีค่าใช้จ่ายรายเดือน

---

## ความต้องการของระบบ

| รายการ | ขั้นต่ำ | แนะนำ |
|---|---|---|
| OS | Windows 10/11 (64-bit) | Windows 11 |
| RAM | 16 GB | 24 GB+ |
| GPU | — (CPU ได้) | NVIDIA 8 GB VRAM+ |
| พื้นที่ว่าง | 15 GB | 20 GB+ |
| โฟลเดอร์ | **ห้ามมีช่องว่างในชื่อ path** | `C:\fahsai` |

> CPU-only ใช้ได้ แต่ตอบช้ากว่า GPU มาก

### GPU ที่รองรับ

| GPU | สถานะ | หมายเหตุ |
|---|---|---|
| NVIDIA (GTX 10xx+) | รองรับอัตโนมัติ | ต้องการ driver 525+ |
| AMD Radeon (RX 6000/7000) | รองรับ (ROCm) | ต้องลง [AMD HIP SDK](https://rocm.docs.amd.com/en/latest/deploy/windows/) ก่อน |
| Intel / อื่นๆ | CPU mode | — |

---

## การติดตั้ง

### Windows

```
ดับเบิลคลิก setup.bat
```

Script จะทำทุกอย่างให้อัตโนมัติ:
- ตรวจสอบ GPU (NVIDIA / AMD / CPU)
- ดาวน์โหลด Model LLM (~5.5 GB) ถ้ายังไม่มี
- ดาวน์โหลด Python 3.11 (Miniconda) ลงในโฟลเดอร์ — ไม่กระทบ Python ที่มีอยู่
- ติดตั้ง llama-cpp-python พร้อม CUDA/ROCm DLLs ทั้งหมด
- สร้าง shortcut `fahsai.lnk`

> ใช้เวลา 5–20 นาที ขึ้นอยู่กับความเร็วอินเทอร์เน็ต

> **AMD GPU**: ต้องติดตั้ง [AMD HIP SDK for Windows](https://rocm.docs.amd.com/en/latest/deploy/windows/) ก่อนรัน setup.bat — ถ้ายังไม่มีจะใช้ CPU mode ไปก่อนได้ แล้วค่อยรัน setup.bat ใหม่

> หากต้องการโหลดโมเดลเองล่วงหน้า: **[⬇ โหลดโดยตรง](https://huggingface.co/nopparoot15/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m/resolve/main/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf)** — วางไว้ในโฟลเดอร์ `model/`

### Linux

```bash
chmod +x setup.sh
./setup.sh
```

รองรับ NVIDIA (CUDA), AMD (ROCm), และ CPU

### Portable

โฟลเดอร์นี้ portable ทั้งหมด — copy ไปเครื่องอื่นที่มี NVIDIA driver แล้วดับเบิลคลิก `fahsai.lnk` ได้เลย ไม่ต้องลงอะไรเพิ่ม

### เปิดแอป

```
ดับเบิลคลิก fahsai.lnk
```

ครั้งแรกโหลด LLM ใช้เวลาประมาณ 1–2 นาที หลังจากนั้นจะรวดเร็วขึ้น

---

## การถอนการติดตั้ง

```
ดับเบิลคลิก uninstall.bat
```

จะลบเฉพาะ: `miniconda/`, `pip-cache/`, `cache/`, `fahsai.lnk`  
ไฟล์อื่น (model, avatar, source code) **ไม่ถูกลบ**

---

## โครงสร้างโฟลเดอร์

```
fahsai-dist/
├── app.py                  # entry point
├── setup.bat               # ติดตั้ง (Windows)
├── setup.sh                # ติดตั้ง (Linux)
├── uninstall.bat           # ถอนการติดตั้ง (Windows)
├── src/
│   ├── gui.py              # UI หลัก
│   ├── bubble.py           # chat bubble + heart bar
│   ├── config.py           # system prompt + สีธีม
│   ├── llm_utils.py        # prompt builder
│   ├── text_utils.py       # ทำความสะอาดข้อความ
│   └── models.py           # LLM / TTS / Whisper instances
├── model/
│   └── *.gguf              # วางโมเดล LLM ที่นี่
├── avatar.png              # sprite sheet ของตัวละคร
├── icon.ico
└── ref_ser_3.wav           # reference audio สำหรับ TTS
```

---

## โมเดลที่ใช้

| โมเดล | หน้าที่ | ดาวน์โหลด |
|---|---|---|
| Typhoon2.5-Qwen3-30B-A3B (Q3_K_M) | LLM — ตอบภาษาไทย | [⬇ โหลดตรง](https://huggingface.co/nopparoot15/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m/resolve/main/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf) · [หน้า HF](https://huggingface.co/nopparoot15/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m) |

---

## License

โค้ดนี้เผยแพร่ภายใต้ [MIT License](LICENSE)  
โมเดล LLM และ TTS มี license แยกต่างหาก ดูรายละเอียดที่หน้า Hugging Face ของแต่ละโมเดล
