@echo off
chcp 65001 >nul
setlocal

set "BASE=%~dp0"
set "BASE=%BASE:~0,-1%"

echo.
echo  ======================================
echo   Uninstall fahsai Chatbot
echo  ======================================
echo.
echo  Folder: %BASE%
echo.
echo  Will delete:
echo    %BASE%\miniconda
echo    %BASE%\pip-cache
echo    %BASE%\cache
echo    %BASE%\fahsai.lnk
echo.
echo  (model folder is kept - delete manually if not needed)
echo.
echo  Press Ctrl+C to cancel, or
set /p CONFIRM= press Enter to continue:
echo.

REM --- Remove shortcut ---
if exist "%BASE%\fahsai.lnk" (
    del /f "%BASE%\fahsai.lnk"
    echo  [OK] Removed fahsai.lnk
) else (
    echo  [--] fahsai.lnk not found
)

REM --- Remove miniconda ---
echo  Checking: %BASE%\miniconda
if exist "%BASE%\miniconda" (
    echo  Removing miniconda ^(may take a moment^)...
    rmdir /s /q "%BASE%\miniconda"
    if exist "%BASE%\miniconda" (
        echo  [!] Failed to remove miniconda
    ) else (
        echo  [OK] Removed miniconda
    )
) else (
    echo  [--] Not found
)

REM --- Remove pip-cache ---
echo  Checking: %BASE%\pip-cache
if exist "%BASE%\pip-cache" (
    rmdir /s /q "%BASE%\pip-cache"
    if exist "%BASE%\pip-cache" (
        echo  [!] Failed to remove pip-cache
    ) else (
        echo  [OK] Removed pip-cache
    )
) else (
    echo  [--] Not found
)

REM --- Remove cache ---
echo  Checking: %BASE%\cache
if exist "%BASE%\cache" (
    rmdir /s /q "%BASE%\cache"
    if exist "%BASE%\cache" (
        echo  [!] Failed to remove cache
    ) else (
        echo  [OK] Removed cache
    )
) else (
    echo  [--] Not found
)

echo.
echo  ======================================
echo   Done - run setup.bat to reinstall
echo  ======================================
echo.
pause
