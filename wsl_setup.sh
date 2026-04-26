#!/bin/bash
set -e

HF_MIRROR="https://hf-mirror.com"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step()  { echo -e "\n${CYAN}===== $1 =====${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$SCRIPT_DIR/wsl_workspace"

mkdir -p "$WORK_DIR"

step "0/7 环境检查"

if ! command -v nvidia-smi &> /dev/null; then
    warn "未检测到 NVIDIA GPU，将使用 CPU 模式（速度较慢）"
    GPU_AVAILABLE=false
else
    info "检测到 NVIDIA GPU:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    GPU_AVAILABLE=true
fi

if ! command -v conda &> /dev/null; then
    error "未检测到 conda，请先安装 Miniconda: https://docs.conda.io/en/latest/miniconda.html"
fi

info "conda 可用: $(conda --version)"

step "1/7 安装系统依赖"

sudo apt update
sudo apt install -y \
    build-essential cmake git git-lfs \
    ffmpeg libportaudio2 portaudio19-dev \
    pulseaudio-utils \
    sox libsox-dev

git lfs install

if command -v pactl &> /dev/null; then
    info "PulseAudio 可用"
    pactl info 2>/dev/null || warn "PulseAudio 未运行，麦克风可能不可用"
else
    warn "PulseAudio 不可用，WSL 麦克风输入可能需要额外配置"
fi

step "2/7 选择安装方案"

echo ""
echo "请选择要安装的方案:"
echo "  1) 仅 SeamlessStreaming (Meta, EMMA 机制, 多语言)"
echo "  2) 仅 StreamSpeech (ICTNLP, ACL 2024, 多策略)"
echo "  3) 两者都安装"
echo ""
read -p "请输入选项 [1/2/3]: " INSTALL_CHOICE

case "$INSTALL_CHOICE" in
    1) INSTALL_SEAMLESS=true;  INSTALL_STREAMSPEECH=false ;;
    2) INSTALL_SEAMLESS=false; INSTALL_STREAMSPEECH=true  ;;
    3) INSTALL_SEAMLESS=true;  INSTALL_STREAMSPEECH=true  ;;
    *) error "无效选项: $INSTALL_CHOICE" ;;
esac

step "3/7 安装 SeamlessStreaming 环境"

if [ "$INSTALL_SEAMLESS" = true ]; then
    info "创建 conda 环境: seamless_streaming (Python 3.10)"
    conda create -n seamless_streaming python=3.10 -y 2>/dev/null || true

    info "激活环境并安装依赖..."
    eval "$(conda shell.bash hook)"
    conda activate seamless_streaming

    pip install --upgrade pip

    if [ "$GPU_AVAILABLE" = true ]; then
        info "安装 PyTorch (CUDA 11.8)..."
        pip install torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu118
    else
        info "安装 PyTorch (CPU)..."
        pip install torch==2.1.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cpu
    fi

    info "安装 fairseq2..."
    pip install fairseq2==0.2.0 2>/dev/null || {
        warn "fairseq2 pip 安装失败，尝试从源码安装..."
        cd "$WORK_DIR"
        if [ ! -d "fairseq2" ]; then
            git clone https://github.com/facebookresearch/fairseq2.git
        fi
        cd fairseq2
        git checkout v0.2.0 2>/dev/null || true
        pip install -e .
    }

    info "克隆 seamless_communication 仓库..."
    cd "$WORK_DIR"
    if [ ! -d "seamless_communication" ]; then
        git clone https://github.com/facebookresearch/seamless_communication.git
    fi
    cd seamless_communication

    info "安装 seamless_communication..."
    pip install -e .

    info "安装 SimulEval..."
    pip install simuleval

    info "安装其他依赖..."
    pip install soundfile scipy pydub sounddevice webrtcvad

    info "下载 SeamlessStreaming 模型 (使用国内镜像)..."
    export HF_ENDPOINT="$HF_MIRROR"
    export HF_HUB_DISABLE_XET=1
    python -c "
from huggingface_hub import snapshot_download
snapshot_download('facebook/seamless-streaming', local_dir='$WORK_DIR/models/seamless-streaming')
print('SeamlessStreaming 模型下载完成')
" || warn "模型下载失败，可稍后手动运行: HF_ENDPOINT=$HF_MIRROR python -c \"from huggingface_hub import snapshot_download; snapshot_download('facebook/seamless-streaming')\""

    conda deactivate
    info "SeamlessStreaming 环境安装完成 ✓"
else
    info "跳过 SeamlessStreaming 安装"
fi

step "4/7 安装 StreamSpeech 环境"

if [ "$INSTALL_STREAMSPEECH" = true ]; then
    info "创建 conda 环境: streamspeech (Python 3.8)"
    conda create -n streamspeech python=3.8 -y 2>/dev/null || true

    info "激活环境并安装依赖..."
    eval "$(conda shell.bash hook)"
    conda activate streamspeech

    pip install --upgrade pip

    if [ "$GPU_AVAILABLE" = true ]; then
        info "安装 PyTorch (CUDA 11.8)..."
        pip install torch==2.0.1 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
    else
        info "安装 PyTorch (CPU)..."
        pip install torch==2.0.1 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cpu
    fi

    info "安装 fairseq..."
    pip install fairseq 2>/dev/null || {
        warn "fairseq pip 安装失败，尝试从源码安装..."
        cd "$WORK_DIR"
        if [ ! -d "fairseq" ]; then
            git clone https://github.com/facebookresearch/fairseq.git
        fi
        cd fairseq
        pip install --editable ./
    }

    info "克隆 StreamSpeech 仓库..."
    cd "$WORK_DIR"
    if [ ! -d "StreamSpeech" ]; then
        git clone https://github.com/ictnlp/StreamSpeech.git
    fi
    cd StreamSpeech

    info "安装 StreamSpeech 依赖..."
    pip install -r requirements.txt 2>/dev/null || true
    pip install g2p-en soundfile scipy sentencepiece sacrebleu editdistance

    info "下载 SpaCy 英文模型..."
    python -m spacy download en_core_web_sm 2>/dev/null || warn "SpaCy 模型下载失败，可稍后手动运行"

    info "下载 StreamSpeech 模型 (使用国内镜像)..."
    export HF_ENDPOINT="$HF_MIRROR"
    export HF_HUB_DISABLE_XET=1
    python -c "
from huggingface_hub import snapshot_download
snapshot_download('ictnlp/StreamSpeech', local_dir='$WORK_DIR/models/StreamSpeech')
print('StreamSpeech 模型下载完成')
" || warn "模型下载失败，可稍后手动运行: HF_ENDPOINT=$HF_MIRROR python -c \"from huggingface_hub import snapshot_download; snapshot_download('ictnlp/StreamSpeech')\""

    conda deactivate
    info "StreamSpeech 环境安装完成 ✓"
else
    info "跳过 StreamSpeech 安装"
fi

step "5/7 安装本项目 (AIFSI) 依赖"

info "创建 conda 环境: aifsi (Python 3.10)"
conda create -n aifsi python=3.10 -y 2>/dev/null || true

eval "$(conda shell.bash hook)"
conda activate aifsi

pip install --upgrade pip

if [ "$GPU_AVAILABLE" = true ]; then
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
else
    pip install torch torchvision torchaudio
fi

cd "$SCRIPT_DIR"
pip install -r requirements.txt
pip install transformers accelerate sentencepiece

conda deactivate
info "AIFSI 环境安装完成 ✓"

step "6/7 验证安装"

VERIFY_OK=true

if [ "$INSTALL_SEAMLESS" = true ]; then
    info "验证 SeamlessStreaming 环境..."
    eval "$(conda shell.bash hook)"
    conda activate seamless_streaming
    python -c "import fairseq2; print('  fairseq2:', fairseq2.__version__)" 2>/dev/null || { warn "fairseq2 导入失败"; VERIFY_OK=false; }
    python -c "import seamless_communication; print('  seamless_communication: OK')" 2>/dev/null || { warn "seamless_communication 导入失败"; VERIFY_OK=false; }
    python -c "import simuleval; print('  simuleval: OK')" 2>/dev/null || { warn "simuleval 导入失败"; VERIFY_OK=false; }
    python -c "import sounddevice; print('  sounddevice: OK')" 2>/dev/null || { warn "sounddevice 导入失败，麦克风可能不可用"; }
    conda deactivate
fi

if [ "$INSTALL_STREAMSPEECH" = true ]; then
    info "验证 StreamSpeech 环境..."
    eval "$(conda shell.bash hook)"
    conda activate streamspeech
    python -c "import fairseq; print('  fairseq: OK')" 2>/dev/null || { warn "fairseq 导入失败"; VERIFY_OK=false; }
    python -c "import soundfile; print('  soundfile: OK')" 2>/dev/null || { warn "soundfile 导入失败"; VERIFY_OK=false; }
    conda deactivate
fi

step "7/7 安装总结"

echo ""
echo "=========================================="
if [ "$VERIFY_OK" = true ]; then
    echo -e "${GREEN}✓ 所有环境安装完成！${NC}"
else
    echo -e "${YELLOW}⚠ 部分组件安装异常，请检查上方日志${NC}"
fi
echo ""
echo "工作目录: $WORK_DIR"
echo ""
echo "可用环境:"
if [ "$INSTALL_SEAMLESS" = true ]; then
    echo "  SeamlessStreaming: conda activate seamless_streaming"
    echo "    推理脚本: bash wsl_run_seamless_streaming.sh"
fi
if [ "$INSTALL_STREAMSPEECH" = true ]; then
    echo "  StreamSpeech:     conda activate streamspeech"
    echo "    推理脚本: bash wsl_run_streamspeech.sh"
fi
echo "  AIFSI (本项目):   conda activate aifsi"
echo ""
echo "国内镜像: export HF_ENDPOINT=$HF_MIRROR"
echo "=========================================="
