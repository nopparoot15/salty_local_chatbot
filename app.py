import sys, io, os

os.environ["HF_HOME"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

os.environ["PYTHONIOENCODING"] = "utf-8"

if sys.platform == "win32":
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.FreeConsole()
        _hnul = k32.CreateFileW("nul", 0xC0000000, 3, None, 3, 0x80, None)
        if _hnul and _hnul != -1:
            k32.SetStdHandle(-10, _hnul)
            k32.SetStdHandle(-11, _hnul)
            k32.SetStdHandle(-12, _hnul)
    except Exception:
        pass
    try:
        _nul_fd = os.open("nul", os.O_RDWR)
        os.dup2(_nul_fd, 1)
        os.dup2(_nul_fd, 2)
        os.close(_nul_fd)
    except Exception:
        pass

    import subprocess as _sp
    _orig_popen_init = _sp.Popen.__init__
    def _popen_no_window(self, *args, **kwargs):
        if sys.platform == "win32":
            kwargs.setdefault("startupinfo", _sp.STARTUPINFO())
            kwargs["startupinfo"].dwFlags |= _sp.STARTF_USESHOWWINDOW
            kwargs["startupinfo"].wShowWindow = 0
            kwargs["creationflags"] = (
                kwargs.get("creationflags", 0) | _sp.CREATE_NO_WINDOW
            )
        _orig_popen_init(self, *args, **kwargs)
    _sp.Popen.__init__ = _popen_no_window

import platformdirs.windows as _pdw
def _fix(n):
    m = {
        "CSIDL_APPDATA":        os.environ.get("APPDATA", ""),
        "CSIDL_COMMON_APPDATA": os.environ.get("ALLUSERSPROFILE", ""),
        "CSIDL_LOCAL_APPDATA":  os.environ.get("LOCALAPPDATA", ""),
    }
    return m.get(n, os.path.expanduser("~"))
_pdw._resolve_win_folder = _fix

if sys.platform == "win32":
    _base = os.path.dirname(os.path.abspath(__file__))
    _dll_dirs = [
        os.path.join(_base, "miniconda", "Lib", "site-packages", "torch", "lib"),
        os.path.join(_base, "miniconda", "Lib", "site-packages", "llama_cpp", "lib"),
    ]
    for _d in _dll_dirs:
        if os.path.isdir(_d):
            try:
                os.add_dll_directory(_d)
            except Exception:
                pass
            if _d not in os.environ.get("PATH", ""):
                os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")

import warnings, logging
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)

if __name__ == "__main__":
    import traceback
    try:
        from src.gui import ChatApp
        app = ChatApp()
        app.mainloop()
    except Exception:
        err = traceback.format_exc()
        try:
            import tkinter.messagebox as mb
            mb.showerror("Error", err)
        except Exception:
            pass
        from src.config import BASE_DIR
        with open(os.path.join(BASE_DIR, "app_error.log"), "w", encoding="utf-8") as f:
            f.write(err)
