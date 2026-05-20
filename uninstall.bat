@echo off
chcp 65001 >nul

REM Re-launch with /k so the window stays open after the script ends
if "%1"=="__run__" goto main
cmd /c ""%~f0" __run__"
exit

:main
setlocal

set "BASE=%~dp0"
set "BASE=%BASE:~0,-1%"

title fahsai uninstall

echo.
echo  ======================================
echo   Uninstall fahsai Chatbot
echo  ======================================
echo.
echo  Folder: %BASE%
echo.
echo  Will delete:
echo    miniconda\       (Python environment)
echo    pip-cache\       (download cache)
echo    cache\           (runtime cache)
echo    fahsai.lnk       (shortcut)
echo    app_error.log    (log file, if present)
echo    *.tmp in model\  (incomplete downloads, if any)
echo.
echo  Will KEEP:
echo    model\           (LLM ~5.5 GB)
echo    fahsai_save.json (relationship save data)
echo    src\, app.py     (source code)
echo.
echo  [!] Make sure fahsai is NOT running before continuing.
echo.
set /p CONFIRM= Press Enter to continue (Ctrl+C to cancel):
echo.

REM --- Shortcut ---
if exist "%BASE%\fahsai.lnk" (
    del /f "%BASE%\fahsai.lnk"
    echo  [OK] Removed fahsai.lnk
) else (
    echo  [--] fahsai.lnk not found
)

REM --- app_error.log ---
if exist "%BASE%\app_error.log" (
    del /f "%BASE%\app_error.log"
    echo  [OK] Removed app_error.log
)

REM --- Leftover installer (interrupted setup) ---
if exist "%BASE%\miniconda_setup.exe" (
    del /f "%BASE%\miniconda_setup.exe"
    echo  [OK] Removed miniconda_setup.exe
)

REM --- Partial model downloads ---
for %%F in ("%BASE%\model\*.tmp") do (
    del /f "%%F"
    echo  [OK] Removed %%~nxF
)

REM --- miniconda ---
echo  Removing miniconda...
if exist "%BASE%\miniconda" (
    rmdir /s /q "%BASE%\miniconda"
    if exist "%BASE%\miniconda" (
        echo  [!] Failed to remove miniconda - is fahsai still running?
    ) else (
        echo  [OK] Removed miniconda
    )
) else (
    echo  [--] miniconda not found
)

REM --- pip-cache ---
if exist "%BASE%\pip-cache" (
    rmdir /s /q "%BASE%\pip-cache"
    if exist "%BASE%\pip-cache" (
        echo  [!] Failed to remove pip-cache
    ) else (
        echo  [OK] Removed pip-cache
    )
) else (
    echo  [--] pip-cache not found
)

REM --- cache ---
if exist "%BASE%\cache" (
    rmdir /s /q "%BASE%\cache"
    if exist "%BASE%\cache" (
        echo  [!] Failed to remove cache
    ) else (
        echo  [OK] Removed cache
    )
) else (
    echo  [--] cache not found
)

echo.
echo  ======================================
echo   Done - run setup.bat to reinstall
echo  ======================================
echo.
pause
