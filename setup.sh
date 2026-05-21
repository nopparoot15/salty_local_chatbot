#!/bin/bash
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA="$BASE/miniconda"
PYTHON="$CONDA/bin/python"
PIP="$CONDA/bin/pip"
CACHE="$BASE/pip-cache"
GPU_TYPE="cpu"
IS_NIXOS=false
export PIP_NO_WARN_SCRIPT_LOCATION=1

# ── NixOS detection ───────────────────────────────────────────────────────────
if [ -f /etc/NIXOS ] || grep -qi 'NixOS' /etc/os-release 2>/dev/null; then
    IS_NIXOS=true
fi

# On NixOS, auto re-launch inside nix-shell if not already inside
if [ "$IS_NIXOS" = true ] && [ -z "${IN_NIX_SHELL:-}" ]; then
    if command -v nix-shell &>/dev/null && [ -f "$BASE/shell.nix" ]; then
        echo " NixOS detected - re-launching inside nix-shell..."
        exec nix-shell "$BASE/shell.nix" --run "bash \"$BASE/setup.sh\""
    fi
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
progress() {
    local step=$1 total=$2 label=$3
    local pct=$(( step * 100 / total ))
    echo -ne "\033]0;fahsai setup [${step}/${total} - ${pct}%] ${label}\007"
}

dl() {
    # dl <url> <dest>  — download with resume, works with curl or wget
    local url=$1 dest=$2
    if command -v curl &>/dev/null; then
        curl -L -C - --retry 5 --retry-delay 10 --progress-bar "$url" -o "$dest"
    elif command -v wget &>/dev/null; then
        wget -q --show-progress --continue "$url" -O "$dest"
    else
        echo " [!] curl or wget required - install one and retry"
        exit 1
    fi
}

check_size() {
    # check_size <file> <min_bytes>  — returns 0 if file exists and is large enough
    local file=$1 min=$2 actual=0
    [ -f "$file" ] || return 1
    if command -v stat &>/dev/null; then
        actual=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo 0)
    else
        actual=$(wc -c < "$file" 2>/dev/null || echo 0)
    fi
    [ "$actual" -ge "$min" ]
}

echo ""
echo " ======================================"
echo "  Install fahsai Chatbot"
echo " ======================================"
echo ""

# ── Check path has no spaces ──────────────────────────────────────────────────
case "$BASE" in
    *\ *)
        echo " [!] Path contains spaces: $BASE"
        echo "     Please move this folder to a path without spaces, e.g. /opt/fahsai"
        exit 1
        ;;
esac

# ── Check disk space (~25 GB needed) ─────────────────────────────────────────
FREE_KB=$(df -k "$BASE" 2>/dev/null | awk 'NR==2{print $4}')
if [ -n "$FREE_KB" ] && [ "$FREE_KB" -lt 25000000 ]; then
    FREE_GB=$(( FREE_KB / 1024 / 1024 ))
    echo " [!] Low disk space: ~${FREE_GB} GB free, need at least 25 GB"
    echo "     Free up space then re-run setup.sh"
    exit 1
fi

# ── 1. GPU ────────────────────────────────────────────────────────────────────
echo " Checking GPU..."
if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null 2>&1; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    echo " [OK] NVIDIA: $GPU_NAME"
    GPU_TYPE="nvidia"
elif command -v rocminfo &>/dev/null && rocminfo &>/dev/null 2>&1; then
    GPU_NAME=$(rocminfo 2>/dev/null | grep "Marketing Name" | head -1 | awk -F: '{print $2}' | xargs)
    echo " [OK] AMD ROCm: $GPU_NAME"
    GPU_TYPE="amd"
else
    echo " [!] No supported GPU found - running in CPU mode (slow)"
    GPU_TYPE="cpu"
fi
progress 1 6 "GPU done"

# ── 2. Model ──────────────────────────────────────────────────────────────────
echo " Checking model..."
mkdir -p "$BASE/model"
MODEL_FILE=$(ls "$BASE/model/"*.gguf 2>/dev/null | head -1 || true)

if [ -z "$MODEL_FILE" ]; then
    MODEL_URL="https://huggingface.co/nopparoot15/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m/resolve/main/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf"
    MODEL_DEST="$BASE/model/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf"
    MODEL_TMP="${MODEL_DEST}.tmp"

    echo " Downloading model (~5.5 GB - this will take a while)..."
    echo " If interrupted, re-run setup.sh to resume automatically."
    echo ""

    dl "$MODEL_URL" "$MODEL_TMP"

    # Verify file is complete (model should be > 5 GB)
    if ! check_size "$MODEL_TMP" 5000000000; then
        ACTUAL=$(stat -c%s "$MODEL_TMP" 2>/dev/null || stat -f%z "$MODEL_TMP" 2>/dev/null || echo "?")
        echo " [!] Download incomplete (got ${ACTUAL} bytes, expected ~5.5 GB)"
        echo "     Re-run setup.sh to resume."
        exit 1
    fi

    mv "$MODEL_TMP" "$MODEL_DEST"
    MODEL_FILE="$MODEL_DEST"
fi
echo " [OK] Model: $(basename "$MODEL_FILE")"
progress 2 6 "Model done"

# ── 3. Python (Miniconda) ─────────────────────────────────────────────────────
echo " Checking Python 3.11..."

if [ "$IS_NIXOS" = true ] && [ ! -f "$PYTHON" ]; then
    if [ -n "${IN_NIX_SHELL:-}" ] && command -v python3 &>/dev/null; then
        echo " NixOS + nix-shell detected - creating venv..."
        python3 -m venv "$CONDA"
        if [ ! -f "$PYTHON" ]; then
            echo " [!] Failed to create venv"
            exit 1
        fi
        "$PYTHON" -m pip install --upgrade pip --no-warn-script-location -q
    else
        echo " [!] NixOS detected - Miniconda ไม่ทำงานบน NixOS โดยตรง"
        echo "     วิธีแก้ (เลือกอย่างใดอย่างหนึ่ง):"
        echo ""
        echo "     1. เปิดใช้ nix-ld (แนะนำ):"
        echo "        เพิ่มใน /etc/nixos/configuration.nix:"
        echo "          programs.nix-ld.enable = true;"
        echo "        จากนั้น: sudo nixos-rebuild switch"
        echo "        แล้วรัน setup.sh ใหม่"
        echo ""
        echo "     2. รันผ่าน nix-shell:"
        echo "        nix-shell -p python311 python311Packages.pip --run 'bash setup.sh'"
        echo ""
        exit 1
    fi
fi

if [ ! -f "$PYTHON" ]; then
    echo " Downloading Miniconda (Python 3.11)..."
    ARCH=$(uname -m)
    MC_URL=""
    MC_FALLBACK=""
    case "$ARCH" in
        x86_64)
            MC_URL="https://repo.anaconda.com/miniconda/Miniconda3-py311_24.9.2-0-Linux-x86_64.sh"
            MC_FALLBACK="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
            ;;
        aarch64|arm64)
            MC_URL="https://repo.anaconda.com/miniconda/Miniconda3-py311_24.9.2-0-Linux-aarch64.sh"
            MC_FALLBACK="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
            ;;
        *)
            echo " [!] Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac

    MC_INSTALLER="$BASE/miniconda_setup.sh"
    dl "$MC_URL" "$MC_INSTALLER"
    if [ ! -f "$MC_INSTALLER" ] || ! check_size "$MC_INSTALLER" 50000000; then
        echo " [!] Primary URL failed - trying fallback..."
        rm -f "$MC_INSTALLER"
        dl "$MC_FALLBACK" "$MC_INSTALLER"
    fi
    if [ ! -f "$MC_INSTALLER" ]; then
        echo " [!] Miniconda download failed - check your internet connection"
        exit 1
    fi

    echo " Installing Python 3.11 (please wait ~1 min)..."
    bash "$MC_INSTALLER" -b -p "$CONDA"
    rm -f "$MC_INSTALLER"

    if [ ! -f "$PYTHON" ]; then
        echo " [!] Miniconda install failed"
        exit 1
    fi

    echo " Upgrading pip..."
    "$PYTHON" -m pip install --upgrade pip --no-warn-script-location -q
fi
echo " [OK] Python 3.11 ready"
progress 3 6 "Python done"

# ── 4. llama-cpp-python ───────────────────────────────────────────────────────
mkdir -p "$CACHE"
echo " Installing llama-cpp-python..."

# Use import test (not just pip show) to detect broken installations
if ! "$PYTHON" -c "from llama_cpp import Llama" &>/dev/null 2>&1; then

    install_cpu() {
        "$PIP" install "llama-cpp-python>=0.3.9" --only-binary :all: \
            --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
            --cache-dir "$CACHE" --no-warn-script-location --progress-bar on || {
            echo " [!] Failed to install llama-cpp-python"
            exit 1
        }
    }

    if [ "$GPU_TYPE" = "nvidia" ]; then
        "$PIP" install "llama-cpp-python>=0.3.9" --only-binary :all: \
            --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 \
            --cache-dir "$CACHE" --no-warn-script-location --progress-bar on

        if "$PYTHON" -c "from llama_cpp import Llama" &>/dev/null 2>&1; then
            echo " [OK] CUDA ready"
        else
            echo " [!] CUDA import failed:"
            "$PYTHON" -c "from llama_cpp import Llama" 2>&1 | head -5 || true
            echo " [!] Falling back to CPU mode"
            "$PIP" uninstall llama-cpp-python -y &>/dev/null || true
            install_cpu
        fi

    elif [ "$GPU_TYPE" = "amd" ]; then
        echo " Compiling llama-cpp-python with ROCm (15-30 min)..."
        CMAKE_ARGS="-DGGML_HIPBLAS=on -DGGML_HIP=on" \
        "$PIP" install llama-cpp-python --no-binary :all: \
            --cache-dir "$CACHE" --no-warn-script-location --progress-bar on || true

        if "$PYTHON" -c "from llama_cpp import Llama" &>/dev/null 2>&1; then
            echo " [OK] ROCm ready"
        else
            echo " [!] ROCm build failed - falling back to CPU mode"
            "$PIP" uninstall llama-cpp-python -y &>/dev/null || true
            install_cpu
        fi

    else
        install_cpu
    fi
fi
echo " [OK] llama-cpp-python ready"
progress 4 6 "llama-cpp-python done"

# ── 5. Core packages ──────────────────────────────────────────────────────────
echo " Installing core packages..."
"$PIP" install customtkinter Pillow platformdirs deep-translator duckduckgo-search \
    --cache-dir "$CACHE" --no-warn-script-location --progress-bar on || {
    echo " [!] Failed to install core packages"
    exit 1
}
echo " [OK] Core packages ready"
progress 5 6 "Core packages done"

# ── 6. Launcher ───────────────────────────────────────────────────────────────
echo " Creating launcher..."

if [ "$IS_NIXOS" = true ]; then
    cat > "$BASE/fahsai.sh" << LAUNCHER
#!/bin/bash
cd "${BASE}"
exec nix-shell "${BASE}/shell.nix" --run "${PYTHON} ${BASE}/app.py"
LAUNCHER
else
    cat > "$BASE/fahsai.sh" << LAUNCHER
#!/bin/bash
cd "${BASE}"
exec "${PYTHON}" "${BASE}/app.py"
LAUNCHER
fi
chmod +x "$BASE/fahsai.sh"

# Desktop entry (optional)
if [ -d "$HOME/.local/share/applications" ]; then
    cat > "$HOME/.local/share/applications/fahsai.desktop" << DESKTOP
[Desktop Entry]
Name=ฟ้าใส
Exec=bash -c 'cd "${BASE}" && "${PYTHON}" "${BASE}/app.py"'
Icon=${BASE}/icon.ico
Terminal=false
Type=Application
Categories=Utility;
DESKTOP
    echo " [OK] Desktop entry created"
fi

echo " [OK] Launcher: $BASE/fahsai.sh"
progress 6 6 "Complete"

echo ""
echo " ======================================"
echo "  Done! Run ./fahsai.sh to start"
echo "  First launch loads LLM (~1-2 min)"
echo " ======================================"
echo ""
read -rp "Press Enter to close..."
