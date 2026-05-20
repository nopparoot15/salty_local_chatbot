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
echo "   miniconda/       (Python environment)"
echo "   pip-cache/       (download cache)"
echo "   cache/           (runtime cache)"
echo "   fahsai.sh        (launcher)"
echo "   fahsai.desktop   (desktop entry, if present)"
echo "   app_error.log    (log file, if present)"
echo "   model/*.tmp      (incomplete downloads, if any)"
echo ""
echo " Will KEEP:"
echo "   model/           (LLM ~5.5 GB)"
echo "   fahsai_save.json (relationship save data)"
echo "   src/, app.py     (source code)"
echo ""
echo " [!] Make sure fahsai is NOT running before continuing."
echo ""
read -rp " Press Enter to continue (Ctrl+C to cancel): "
echo ""

remove_dir() {
    local path=$1 label=$2
    if [ -d "$path" ]; then
        echo " Removing $label..."
        rm -rf "$path"
        if [ -d "$path" ]; then
            echo " [!] Failed to remove $label - is fahsai still running?"
        else
            echo " [OK] Removed $label"
        fi
    else
        echo " [--] $label not found"
    fi
}

remove_file() {
    local path=$1
    if [ -f "$path" ]; then
        rm -f "$path"
        echo " [OK] Removed $(basename "$path")"
    fi
}

# --- Launcher ---
remove_file "$BASE/fahsai.sh"

# --- Desktop entry ---
remove_file "$HOME/.local/share/applications/fahsai.desktop"

# --- Log and leftover installer ---
remove_file "$BASE/app_error.log"
remove_file "$BASE/miniconda_setup.sh"

# --- Partial model downloads ---
for tmp in "$BASE"/model/*.tmp; do
    [ -f "$tmp" ] || continue
    rm -f "$tmp"
    echo " [OK] Removed $(basename "$tmp")"
done

# --- Directories ---
remove_dir "$BASE/miniconda"  "miniconda"
remove_dir "$BASE/pip-cache"  "pip-cache"
remove_dir "$BASE/cache"      "cache"

echo ""
echo " ======================================"
echo "  Done - run setup.sh to reinstall"
echo " ======================================"
echo ""
read -rp "Press Enter to close..."
