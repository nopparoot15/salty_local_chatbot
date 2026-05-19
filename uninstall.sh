#!/bin/bash
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo " ======================================"
echo "  Uninstall fahsai Chatbot"
echo " ======================================"
echo ""
echo " Folder: $BASE"
echo ""
echo " Will delete:"
echo "   $BASE/miniconda"
echo "   $BASE/pip-cache"
echo "   $BASE/cache"
echo "   $BASE/fahsai.sh"
echo ""
echo " (model folder is kept - delete manually if not needed)"
echo ""
echo " Press Ctrl+C to cancel, or"
read -p " press Enter to continue: "
echo ""

# --- Remove launcher ---
if [ -f "$BASE/fahsai.sh" ]; then
    rm -f "$BASE/fahsai.sh"
    echo " [OK] Removed fahsai.sh"
else
    echo " [--] fahsai.sh not found"
fi

# --- Remove .desktop entry ---
DESKTOP_FILE="$HOME/.local/share/applications/fahsai.desktop"
if [ -f "$DESKTOP_FILE" ]; then
    rm -f "$DESKTOP_FILE"
    echo " [OK] Removed fahsai.desktop"
fi

# --- Remove miniconda ---
echo " Checking: $BASE/miniconda"
if [ -d "$BASE/miniconda" ]; then
    echo " Removing miniconda (may take a moment)..."
    rm -rf "$BASE/miniconda"
    if [ -d "$BASE/miniconda" ]; then
        echo " [!] Failed to remove miniconda"
    else
        echo " [OK] Removed miniconda"
    fi
else
    echo " [--] Not found"
fi

# --- Remove pip-cache ---
echo " Checking: $BASE/pip-cache"
if [ -d "$BASE/pip-cache" ]; then
    rm -rf "$BASE/pip-cache"
    echo " [OK] Removed pip-cache"
else
    echo " [--] Not found"
fi

# --- Remove cache ---
echo " Checking: $BASE/cache"
if [ -d "$BASE/cache" ]; then
    rm -rf "$BASE/cache"
    echo " [OK] Removed cache"
else
    echo " [--] Not found"
fi

echo ""
echo " ======================================"
echo "  Done - run setup.sh to reinstall"
echo " ======================================"
echo ""
read -p "Press Enter to close..."
