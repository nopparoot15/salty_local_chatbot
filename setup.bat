@echo off
chcp 65001 >nul

REM Re-launch with /k so the window stays open after the script ends
if "%1"=="__run__" goto main
cmd /k ""%~f0" __run__"
exit

:main
setlocal EnableDelayedExpansion

set "BASE=%~dp0"
set "BASE=%BASE:~0,-1%"
set "CONDA=%BASE%\miniconda"
set "PYTHON=%CONDA%\python.exe"
set "PYTHONW=%CONDA%\pythonw.exe"
set "PIP=%CONDA%\Scripts\pip.exe"
set "CACHE=%BASE%\pip-cache"
set "GPU_TYPE=cpu"
set "PIP_NO_WARN_SCRIPT_LOCATION=1"

title fahsai setup

echo.
echo  ======================================
echo   Install fahsai Chatbot
echo  ======================================
echo.

REM --- Check path (no spaces allowed) ---
if not "%BASE%"=="%BASE: =%" (
    echo  [!] Path contains spaces: %BASE%
    echo      Please move this folder to a path without spaces, e.g. C:\fahsai
    pause & exit /b 1
)

REM --- Check disk space (need ~25 GB free on the drive) ---
for /f "tokens=3" %%A in ('dir /-C "%BASE:~0,2%\" 2^>nul ^| findstr /i "bytes free"') do set "FREE_BYTES=%%A"
if defined FREE_BYTES (
    REM Compare only first 11 digits to avoid integer overflow in cmd
    set "FREE_SHORT=!FREE_BYTES:~0,11!"
    if !FREE_SHORT! LSS 25000000000 (
        echo  [!] Low disk space. Need at least 25 GB free on %BASE:~0,2%\
        echo      Free space detected: !FREE_BYTES! bytes
        echo      Free up space then re-run setup.bat
        pause & exit /b 1
    )
)

REM --- 1. GPU detection ---
echo  Checking GPU...

REM Check NVIDIA
nvidia-smi >nul 2>&1
if not errorlevel 1 (
    set "GPU_TYPE=nvidia"
    echo  [OK] NVIDIA GPU found
    goto gpu_done
)

REM Check AMD — use PowerShell (wmic removed in Windows 11 24H2)
powershell -NoProfile -Command "try{Get-CimInstance Win32_VideoController -ErrorAction Stop | Select-Object -ExpandProperty Name}catch{}" 2>nul | findstr /i "Radeon" >nul
if not errorlevel 1 (
    set "GPU_TYPE=amd"
    echo  [OK] AMD Radeon GPU found
    goto gpu_done
)

echo  [!] No supported GPU found - running in CPU mode (slow)
:gpu_done
title fahsai setup [1/6] GPU done

REM --- 2. Model ---
echo  Checking model...
if not exist "%BASE%\model" mkdir "%BASE%\model"
set "MODEL_FOUND="
for %%F in ("%BASE%\model\*.gguf") do set "MODEL_FOUND=%%F"
if defined MODEL_FOUND goto model_ok

set "MODEL_URL=https://huggingface.co/nopparoot15/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m/resolve/main/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf"
set "MODEL_DEST=%BASE%\model\typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf"
set "MODEL_TMP=%MODEL_DEST%.tmp"

echo  Downloading model (~5.5 GB - this will take a while)...
echo  If download is interrupted, re-run setup.bat to resume automatically.
echo.

REM -C - enables resume; --retry 5 retries on error
curl.exe -L -C - --retry 5 --retry-delay 10 --progress-bar "%MODEL_URL%" -o "%MODEL_TMP%"
if not exist "%MODEL_TMP%" (
    echo  [!] Download failed - check your internet connection and retry
    pause & exit /b 1
)

REM Verify file is large enough (model should be > 5 GB = 5,000,000,000 bytes)
for %%A in ("%MODEL_TMP%") do set "FSIZE=%%~zA"
if !FSIZE! LSS 5000000000 (
    echo  [!] Download incomplete (got !FSIZE! bytes, expected ~5.5 GB)
    echo      Re-run setup.bat to resume.
    pause & exit /b 1
)
move /y "%MODEL_TMP%" "%MODEL_DEST%" >nul
set "MODEL_FOUND=%MODEL_DEST%"

:model_ok
echo  [OK] Model: %MODEL_FOUND%
title fahsai setup [2/6] Model done

REM --- 3. Python 3.11 ---
echo  Checking Python 3.11...
if exist "%PYTHON%" goto python_ready

echo  Downloading Miniconda (Python 3.11)...
set "MC_URL=https://repo.anaconda.com/miniconda/Miniconda3-py311_24.9.2-0-Windows-x86_64.exe"
set "MC_FALLBACK=https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
set "MC_INSTALLER=%BASE%\miniconda_setup.exe"

curl.exe -L --retry 3 --retry-delay 5 --progress-bar "%MC_URL%" -o "%MC_INSTALLER%"
if not exist "%MC_INSTALLER%" (
    echo  [!] Primary URL failed - trying fallback...
    curl.exe -L --retry 3 --retry-delay 5 --progress-bar "%MC_FALLBACK%" -o "%MC_INSTALLER%"
)
if not exist "%MC_INSTALLER%" (
    echo  [!] Miniconda download failed - check your internet connection
    pause & exit /b 1
)

echo  Installing Python 3.11 (please wait ~1 min)...
start /wait "" "%MC_INSTALLER%" /S /RegisterPython=0 /AddToPath=0 /D=%CONDA%
del "%MC_INSTALLER%"
if not exist "%PYTHON%" (
    echo  [!] Miniconda install failed
    pause & exit /b 1
)

echo  Upgrading pip...
"%PYTHON%" -m pip install --upgrade pip --no-warn-script-location -q

:python_ready
echo  [OK] Python 3.11 ready
title fahsai setup [3/6] Python done

REM --- 4. llama-cpp-python ---
echo  Installing llama-cpp-python...

REM Use import test (not just pip show) to detect broken DLL state
"%PYTHON%" -c "from llama_cpp import Llama" >nul 2>&1
if not errorlevel 1 goto llama_done

if "%GPU_TYPE%"=="nvidia" goto llama_nvidia
if "%GPU_TYPE%"=="amd"    goto llama_amd
goto llama_cpu

:llama_cpu
"%PIP%" install "llama-cpp-python>=0.3.9" --only-binary :all: --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --cache-dir "%CACHE%" --no-warn-script-location --progress-bar on
goto llama_check

:llama_nvidia
echo  Trying llama-cpp-python with CUDA 12.4...
"%PIP%" install "llama-cpp-python>=0.3.9" --only-binary :all: --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --cache-dir "%CACHE%" --no-warn-script-location --progress-bar on

REM Quick import test
"%PYTHON%" -c "from llama_cpp import Llama" >nul 2>&1
if not errorlevel 1 (
    echo  [OK] CUDA ready
    goto llama_check
)

REM Import failed — CUDA runtime DLLs missing from the wheel, install from PyPI
echo  [!] CUDA import failed - installing CUDA runtime DLLs from PyPI...
"%PIP%" install nvidia-cublas-cu12 nvidia-cuda-runtime-cu12 nvidia-cuda-nvrtc-cu12 nvidia-nvjitlink-cu12 --cache-dir "%CACHE%" --no-warn-script-location -q

echo  Copying CUDA DLLs next to python.exe...
"%PYTHON%" -c ^
"import sysconfig,os,sys,shutil;^
sp=sysconfig.get_path('purelib');^
nv=os.path.join(sp,'nvidia');^
dst=os.path.dirname(sys.executable);^
dlls=[shutil.copy2(os.path.join(r,f),dst) for r,d,fs in (os.walk(nv) if os.path.exists(nv) else []) for f in fs if f.lower().endswith('.dll')];^
print(' Copied',len(dlls),'DLLs to',dst)"

echo  Removing nvidia packages (DLLs already copied)...
"%PIP%" uninstall nvidia-cublas-cu12 nvidia-cuda-runtime-cu12 nvidia-cuda-nvrtc-cu12 nvidia-nvjitlink-cu12 -y >nul 2>&1

REM Test again
"%PYTHON%" -c "from llama_cpp import Llama" >nul 2>&1
if not errorlevel 1 (
    echo  [OK] CUDA ready
    goto llama_check
)

echo  [!] CUDA setup failed - error details:
"%PYTHON%" -c "from llama_cpp import Llama" 2>&1

echo  [!] Falling back to CPU mode
"%PIP%" uninstall llama-cpp-python -y >nul 2>&1
goto llama_cpu

:llama_amd
echo  Checking AMD ROCm / HIP SDK...
set "HIP_FOUND="
if defined HIP_PATH set "HIP_FOUND=1"
if not defined HIP_FOUND (
    for /d %%d in ("C:\Program Files\AMD\ROCm\*") do (
        set "HIP_FOUND=1"
        set "HIP_PATH=%%d"
    )
)
if not defined HIP_FOUND (
    echo  [!] AMD HIP SDK not found - falling back to CPU mode
    echo      For AMD GPU acceleration install ROCm for Windows first:
    echo      https://rocm.docs.amd.com/en/latest/deploy/windows/
    echo      Then re-run setup.bat
    goto llama_cpu
)
echo  [OK] HIP SDK: %HIP_PATH%
echo  Installing build tools...
"%PIP%" install cmake ninja --cache-dir "%CACHE%" --no-warn-script-location -q
echo  Compiling llama-cpp-python with ROCm (this takes 15-30 min)...
set "CMAKE_ARGS=-DGGML_HIPBLAS=on"
"%PIP%" install llama-cpp-python --no-binary :all: --cache-dir "%CACHE%" --no-warn-script-location --progress-bar on
set "CMAKE_ARGS="
"%PYTHON%" -c "from llama_cpp import Llama" >nul 2>&1
if not errorlevel 1 (
    echo  [OK] ROCm ready
    goto llama_check
)
echo  [!] ROCm build failed - falling back to CPU mode
"%PIP%" uninstall llama-cpp-python -y >nul 2>&1
goto llama_cpu

:llama_check
"%PIP%" show llama-cpp-python >nul 2>&1
if errorlevel 1 (
    echo  [!] Failed to install llama-cpp-python
    pause & exit /b 1
)
:llama_done
title fahsai setup [4/6] llama-cpp-python done

REM --- 5. Core packages ---
echo  Installing core packages...
"%PIP%" install customtkinter Pillow platformdirs deep-translator --cache-dir "%CACHE%" --no-warn-script-location --progress-bar on
"%PIP%" show customtkinter >nul 2>&1
if errorlevel 1 (
    echo  [!] Failed to install core packages
    pause & exit /b 1
)
title fahsai setup [5/6] Core packages done

REM --- 6. Shortcut ---
echo  Creating shortcut in folder...
set "VBS=%TEMP%\mk_lnk_%RANDOM%.vbs"
(
    echo Set ws = CreateObject^("WScript.Shell"^)
    echo Set s = ws.CreateShortcut^("%BASE%\fahsai.lnk"^)
    echo s.TargetPath = "%PYTHONW%"
    echo s.Arguments = """%BASE%\app.py"""
    echo s.WorkingDirectory = "%BASE%"
    echo s.IconLocation = "%BASE%\icon.ico,0"
    echo s.Save
) > "%VBS%"
cscript //nologo "%VBS%"
del "%VBS%"
echo  [OK] Shortcut created: fahsai.lnk
title fahsai setup [6/6] Complete

echo.
echo  ======================================
echo   Done! Double-click fahsai.lnk to run
echo   First launch loads LLM (~1-2 min)
echo  ======================================
echo.
pause & exit
