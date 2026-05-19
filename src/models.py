import os, atexit, datetime
from .config import BASE_DIR, _EXE_DIR

llm = None

import sys as _sys
_LOG_DIR = os.path.dirname(_sys.executable) if hasattr(_sys, "_MEIPASS") else BASE_DIR
_ERR_LOG = os.path.join(_LOG_DIR, "app_error.log")

def log_err(msg: str) -> None:
    try:
        with open(_ERR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%H:%M:%S}] {msg}\n")
    except Exception:
        pass


@atexit.register
def _cleanup_llm():
    global llm
    if llm is not None:
        try:
            llm.close()
        except Exception:
            pass
        llm = None
