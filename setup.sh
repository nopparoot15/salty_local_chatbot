#!/bin/bash
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA="$BASE/miniconda"
PYTHON="$CONDA/bin/python"
PIP="$CONDA/bin/pip"
CACHE="$BASE/pip-cache"
GPU_TYPE="cpu"
IS_NIXOS=false
export PIP_NO_WARN_SCRIPT_LOCATION=1

# Detect NixOS
if [ -f /etc/NIXOS ] || grep -qi 'NixOS' /etc/os-release 2>/dev/null; then
    IS_NIXOS=true
fi

# On NixOS, auto re-launch inside nix-shell if not already inside
if [ "$IS_NIXOS" = true ] && [ -z "$IN_NIX_SHELL" ]; then
    if command -v nix-shell &>/dev/null && [ -f "$BASE/shell.nix" ]; then
        echo " NixOS detected - re-launching inside nix-shell..."
        exec nix-shell "$BASE/shell.nix" --run "bash \"$BASE/setup.sh\""
    fi
fi

progress() {
    local step=$1 total=$2 label=$3
    local pct=$(( step * 100 / total ))
    echo -ne "\033]0;fahsai setup [${step}/${total} - ${pct}%] ${label}\007"
}

echo ""
echo " ======================================"
echo "  Install fahsai Chatbot"
echo " ======================================"
echo ""

# --- 1. GPU ---
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
    echo " [!] No GPU found - CPU mode (slow)"
    GPU_TYPE="cpu"
fi
progress 1 6 "GPU done"

# --- 2. Model ---
echo " Checking model..."
mkdir -p "$BASE/model"
MODEL_FILE=$(ls "$BASE/model/"*.gguf 2>/dev/null | head -1)
if [ -z "$MODEL_FILE" ]; then
    MODEL_URL="https://huggingface.co/nopparoot15/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m/resolve/main/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf"
    MODEL_FILE="$BASE/model/typhoon2.5-qwen3-30b-a3b-abliterated-Q3_k_m.gguf"
    echo " Downloading model (~5.5 GB - this will take a while)..."
    if command -v curl &>/dev/null; then
        curl -L --progress-bar --retry 3 --retry-delay 5 -C - "$MODEL_URL" -o "$MODEL_FILE" || {
            rm -f "$MODEL_FILE"
            echo " [!] Download failed - check your internet connection and retry"
            exit 1
        }
    elif command -v wget &>/dev/null; then
        wget -q --show-progress --continue "$MODEL_URL" -O "$MODEL_FILE" || {
            rm -f "$MODEL_FILE"
            echo " [!] Download failed - check your internet connection and retry"
            exit 1
        }
    else
        echo " [!] curl or wget required - install one and retry"
        exit 1
    fi
fi
echo " [OK] Model: $(basename "$MODEL_FILE")"
progress 2 6 "Model done"

# --- 3. Python (Miniconda) ---
echo " Checking Python 3.11..."
if [ "$IS_NIXOS" = true ] && [ ! -f "$PYTHON" ]; then
    if [ -n "$IN_NIX_SHELL" ] && command -v python3 &>/dev/null; then
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
    case "$ARCH" in
        x86_64)  MC_URL="https://repo.anaconda.com/miniconda/Miniconda3-py311_24.9.2-0-Linux-x86_64.sh" ;;
        aarch64) MC_URL="https://repo.anaconda.com/miniconda/Miniconda3-py311_24.9.2-0-Linux-aarch64.sh" ;;
        *)
            echo " [!] Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac

    if command -v curl &>/dev/null; then
        curl -L --progress-bar "$MC_URL" -o "$BASE/miniconda_setup.sh"
    elif command -v wget &>/dev/null; then
        wget -q --show-progress "$MC_URL" -O "$BASE/miniconda_setup.sh"
    else
        echo " [!] curl or wget required - install one and retry"
        exit 1
    fi

    if [ ! -f "$BASE/miniconda_setup.sh" ]; then
        echo " [!] Download failed"
        exit 1
    fi

    echo " Installing Python 3.11 (please wait ~1 min)..."
    bash "$BASE/miniconda_setup.sh" -b -p "$CONDA"
    rm -f "$BASE/miniconda_setup.sh"

    if [ ! -f "$PYTHON" ]; then
        echo " [!] Miniconda install failed"
        exit 1
    fi

    echo " Upgrading pip..."
    "$PYTHON" -m pip install --upgrade pip --no-warn-script-location -q
fi
echo " [OK] Python 3.11 ready"
progress 3 6 "Python done"

# --- 4. llama-cpp-python ---
mkdir -p "$CACHE"
echo " Installing llama-cpp-python..."
if ! "$PIP" show llama-cpp-python &>/dev/null; then
    if [ "$GPU_TYPE" = "nvidia" ]; then
        "$PIP" install llama-cpp-python --only-binary :all: \
            --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 \
            --cache-dir "$CACHE" --no-warn-script-location --progress-bar on
        CUDA_ERR=$("$PYTHON" -c "from llama_cpp import Llama" 2>&1)
        if [ $? -eq 0 ]; then
            echo " [OK] CUDA ready"
        else
            echo " [!] CUDA import failed: $CUDA_ERR"
            echo " [!] Falling back to CPU"
            "$PIP" uninstall llama-cpp-python -y &>/dev/null
            "$PIP" install llama-cpp-python --only-binary :all: \
                --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
                --cache-dir "$CACHE" --no-warn-script-location --progress-bar on || {
                echo " [!] Failed to install llama-cpp-python"
                exit 1
            }
        fi
    elif [ "$GPU_TYPE" = "amd" ]; then
        CMAKE_ARGS="-DGGML_HIPBLAS=on -DGGML_HIP=on" \
        "$PIP" install llama-cpp-python --cache-dir "$CACHE" \
            --no-warn-script-location --progress-bar on || {
            echo " [!] Failed to install llama-cpp-python (ROCm) - falling back to CPU"
            "$PIP" install llama-cpp-python --only-binary :all: \
                --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
                --cache-dir "$CACHE" --no-warn-script-location --progress-bar on || {
                echo " [!] Failed to install llama-cpp-python"
                exit 1
            }
        }
    else
        "$PIP" install llama-cpp-python --only-binary :all: \
            --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
            --cache-dir "$CACHE" --no-warn-script-location --progress-bar on || {
            echo " [!] Failed to install llama-cpp-python"
            exit 1
        }
    fi
fi
echo " [OK] llama-cpp-python ready"
progress 4 6 "llama-cpp-python done"

# --- 5. Core packages ---
echo " Installing core packages..."
"$PIP" install customtkinter Pillow platformdirs deep-translator \
    --cache-dir "$CACHE" --no-warn-script-location --progress-bar on || {
    echo " [!] Failed to install core packages"
    exit 1
}
echo " [OK] Core packages ready"
progress 5 6 "Core packages done"

# --- 6. Launcher ---
echo " Creating launcher..."

if [ "$IS_NIXOS" = true ]; then
    cat > "$BASE/fahsai.sh" << LAUNCHER
#!/bin/bash
cd ${BASE}
exec nix-shell ${BASE}/shell.nix --run "${BASE}/miniconda/bin/python ${BASE}/app.py"
LAUNCHER
else
    cat > "$BASE/fahsai.sh" << LAUNCHER
#!/bin/bash
cd ${BASE}
${PYTHON} ${BASE}/app.py
LAUNCHER
fi
chmod +x "$BASE/fahsai.sh"

if [ -d "$HOME/.local/share/applications" ]; then
    cat > "$HOME/.local/share/applications/fahsai.desktop" << DESKTOP
[Desktop Entry]
Name=fahsai
Exec=bash -c 'cd "$BASE" && "$PYTHON" "$BASE/app.py"'
Icon=$BASE/icon.ico
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
echo "  Done - run ./fahsai.sh to start"
echo "  First run loads LLM (~1-2 min)"
echo " ======================================"
echo ""
read -p "Press Enter to close..."
