@echo off
chcp 65001 >nul

REM Re-launch with /k so the window stays open after the script ends
if "%1"=="__run__" goto main
cmd /k ""%~f0" __run__"
exit

:main
setlocal

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
    echo  [!] Path has spaces: %BASE%
    echo      Move folder to a path without spaces e.g. C:\fahsai
    pause & exit /b 1
)

REM --- 1. GPU ---
echo  Checking GPU...
nvidia-smi >nul 2>&1
if not errorlevel 1 (
    set "GPU_TYPE=nvidia"
    echo  [OK] NVIDIA GPU found
    goto gpu_done
)
wmic path win32_VideoController get Name 2>nul | findstr /i "Radeon" >nul 2>&1
if not errorlevel 1 (
    set "GPU_TYPE=amd"
    echo  [OK] AMD Radeon GPU found
    goto gpu_done
)
echo  [!] No supported GPU - CPU mode
:gpu_done
title fahsai setup [1/6 - 17%%] GPU done

REM --- 2. Model ---
echo  Checking model...
if not exist "%BASE%\model" mkdir "%BASE%\model"
set "MODEL_FOUND="
for %%F in ("%BASE%\model\*.gguf") do set "MODEL_FOUND=%%F"
if defined MODEL_FOUND goto model_ok

set "MODEL_URL=https://huggingface.co/nopparoot15/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m/resolve/main/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf"
set "MODEL_DEST=%BASE%\model\typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf"
echo  Downloading model (~5.5 GB - this will take a while)...
curl.exe -L --progress-bar "%MODEL_URL%" -o "%MODEL_DEST%"
if not exist "%MODEL_DEST%" (
    echo  [!] Download failed - check your internet connection and retry
    pause & exit /b 1
)
set "MODEL_FOUND=%MODEL_DEST%"

:model_ok
echo  [OK] Model: %MODEL_FOUND%
title fahsai setup [2/6 - 33%%] Model done

REM --- 3. Python ---
echo  Checking Python 3.11...
if exist "%PYTHON%" goto python_ready

echo  Downloading Miniconda (Python 3.11)...
curl.exe -L --progress-bar "https://repo.anaconda.com/miniconda/Miniconda3-py311_24.9.2-0-Windows-x86_64.exe" -o "%BASE%\miniconda_setup.exe"
if not exist "%BASE%\miniconda_setup.exe" (
    echo  [!] Download failed
    pause & exit /b 1
)

echo  Installing Python 3.11 (please wait ~1 min)...
start /wait "" "%BASE%\miniconda_setup.exe" /S /RegisterPython=0 /AddToPath=0 /D=%CONDA%
del "%BASE%\miniconda_setup.exe"
if not exist "%PYTHON%" (
    echo  [!] Miniconda install failed
    pause & exit /b 1
)

echo  Upgrading pip...
"%PYTHON%" -m pip install --upgrade pip --no-warn-script-location -q

:python_ready
echo  [OK] Python 3.11 ready
title fahsai setup [3/6 - 50%%] Python done

REM --- 4. llama-cpp-python ---
echo  Installing llama-cpp-python...
"%PIP%" show llama-cpp-python >nul 2>&1
if not errorlevel 1 goto llama_done
if "%GPU_TYPE%"=="nvidia" goto llama_nvidia
if "%GPU_TYPE%"=="amd" goto llama_amd
:llama_cpu
"%PIP%" install llama-cpp-python --only-binary :all: --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --cache-dir "%CACHE%" --no-warn-script-location --progress-bar on
goto llama_check
:llama_nvidia
echo  Trying llama-cpp-python cu124...
"%PIP%" install llama-cpp-python --only-binary :all: --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --cache-dir "%CACHE%" --no-warn-script-location --progress-bar on

REM Test 1: plain import (wheel may bundle its own CUDA DLLs in llama_cpp/lib)
"%PYTHON%" -c "from llama_cpp import Llama" >nul 2>&1
if not errorlevel 1 (
    echo  [OK] CUDA ready
    goto llama_check
)

REM Show the actual error so we know what's missing
echo  [!] CUDA import failed - error details:
"%PYTHON%" -c "from llama_cpp import Llama" 2>&1 | findstr /v "^$"

REM Test 2: add nvidia PyPI DLL packages
echo  [!] Installing CUDA runtime DLLs from PyPI...
"%PIP%" install nvidia-cublas-cu12 nvidia-cuda-runtime-cu12 nvidia-cuda-nvrtc-cu12 nvidia-nvjitlink-cu12 --cache-dir "%CACHE%" --no-warn-script-location
echo  Copying CUDA DLLs into python.exe folder...
"%PYTHON%" -c "import sysconfig,os,sys,shutil;sp=sysconfig.get_path('purelib');nv=os.path.join(sp,'nvidia');dst=os.path.dirname(sys.executable);n=len([shutil.copy2(os.path.join(r,f),dst) for r,d,fs in (os.walk(nv) if os.path.exists(nv) else []) for f in fs if f.lower().endswith('.dll')]);print(' Copied',n,'DLLs to',dst)"
echo  Removing nvidia packages (DLLs already copied)...
"%PIP%" uninstall nvidia-cublas-cu12 nvidia-cuda-runtime-cu12 nvidia-cuda-nvrtc-cu12 nvidia-nvjitlink-cu12 -y >nul 2>&1
"%PYTHON%" -c "from llama_cpp import Llama" >nul 2>&1
if not errorlevel 1 (
    echo  [OK] CUDA ready
    goto llama_check
)
echo  [!] CUDA copy failed - error:
"%PYTHON%" -c "from llama_cpp import Llama" 2>&1 | findstr /v "^$"

echo  [!] CUDA still unavailable - falling back to CPU
"%PIP%" uninstall llama-cpp-python -y >nul 2>&1
goto llama_cpu

:llama_amd
echo  Checking AMD ROCm (HIP SDK)...
set "HIP_FOUND="
if defined HIP_PATH set "HIP_FOUND=1"
if not defined HIP_FOUND (
    for /d %%d in ("C:\Program Files\AMD\ROCm\*") do set "HIP_FOUND=1" & set "HIP_PATH=%%d"
)
if not defined HIP_FOUND (
    echo  [!] HIP SDK not found - CPU mode
    echo      For AMD GPU acceleration install ROCm for Windows:
    echo      https://rocm.docs.amd.com/en/latest/deploy/windows/
    echo      Then re-run setup.bat
    goto llama_cpu
)
echo  [OK] HIP SDK: %HIP_PATH%
echo  Installing build tools...
"%PIP%" install cmake ninja --cache-dir "%CACHE%" --no-warn-script-location -q
echo  Compiling llama-cpp-python with ROCm (15-30 min)...
set "CMAKE_ARGS=-DGGML_HIPBLAS=on"
"%PIP%" install llama-cpp-python --no-binary :all: --cache-dir "%CACHE%" --no-warn-script-location --progress-bar on
set "CMAKE_ARGS="
"%PYTHON%" -c "from llama_cpp import Llama" >nul 2>&1
if not errorlevel 1 (
    echo  [OK] ROCm ready
    goto llama_check
)
echo  [!] ROCm build failed - falling back to CPU
"%PIP%" uninstall llama-cpp-python -y >nul 2>&1
goto llama_cpu

:llama_check
"%PIP%" show llama-cpp-python >nul 2>&1
if errorlevel 1 (
    echo  [!] Failed to install llama-cpp-python
    pause & exit /b 1
)
:llama_done
title fahsai setup [4/6 - 67%%] llama-cpp-python done

REM --- 5. Core packages ---
echo  Installing core packages...
"%PIP%" install customtkinter Pillow platformdirs deep-translator --cache-dir "%CACHE%" --no-warn-script-location --progress-bar on
"%PIP%" show customtkinter >nul 2>&1
if errorlevel 1 (
    echo  [!] Failed to install core packages
    pause & exit /b 1
)
title fahsai setup [5/6 - 83%%] Core packages done

REM --- 6. Shortcut ---
echo  Creating shortcut in folder...
set "VBS=%TEMP%\mk_lnk.vbs"
if exist "%VBS%" del "%VBS%"
echo Set ws = CreateObject("WScript.Shell") > "%VBS%"
echo Set s = ws.CreateShortcut("%BASE%\fahsai.lnk") >> "%VBS%"
echo s.TargetPath = "%PYTHONW%" >> "%VBS%"
echo s.Arguments = "%BASE%\app.py" >> "%VBS%"
echo s.WorkingDirectory = "%BASE%" >> "%VBS%"
echo s.IconLocation = "%BASE%\icon.ico,0" >> "%VBS%"
echo s.Save >> "%VBS%"
cscript //nologo "%VBS%"
del "%VBS%"
echo  [OK] Shortcut created: fahsai.lnk
title fahsai setup [6/6 - 100%%] Complete

echo.
echo  ======================================
echo   Done - Double-click fahsai.lnk to run
echo   First run loads LLM (~1-2 min)
echo  ======================================
echo.
pause & exit
