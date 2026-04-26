#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$SCRIPT_DIR/wsl_workspace"

HF_MIRROR="https://hf-mirror.com"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

MODE="s2st"
SRC_LANG="cmn"
TGT_LANG="eng"
INPUT=""
INPUT_MIC=false
SEGMENT_SIZE=320
MODEL_CKPT=""
VOCODER_CKPT=""
USE_MIRROR=true
USE_FP16=true

usage() {
    cat << EOF
用法: bash wsl_run_seamless_streaming.sh [选项]

SeamlessStreaming 实时流式同声传译 (Meta, EMMA 机制)

选项:
  --mode MODE         翻译模式: s2st (语音→语音), s2tt (语音→文本), t2tt (文本→文本)
                      默认: s2st
  --src-lang LANG     源语言代码 (默认: cmn)
                      常用: cmn(中文), eng(英文), jpn(日语), kor(韩语),
                            fra(法语), deu(德语), spa(西班牙语), rus(俄语)
  --tgt-lang LANG     目标语言代码 (默认: eng)
  --input FILE        输入音频文件路径 (WAV 16kHz 单声道)
  --mic               使用麦克风实时输入
  --segment-size N    每段音频帧数 (默认: 320, 即 20ms@16kHz, 越小延迟越低)
  --model-ckpt PATH   模型检查点路径 (默认: 自动下载 facebook/seamless-streaming)
  --vocoder-ckpt PATH 声码器检查点路径 (S2ST 模式, 默认同 model-ckpt)
  --no-mirror         不使用国内镜像
  --no-fp16           不使用 FP16 半精度
  -h, --help          显示此帮助

示例:
  # 麦克风实时中文→英文语音翻译
  bash wsl_run_seamless_streaming.sh --mic --src-lang cmn --tgt-lang eng

  # 麦克风实时英文→中文文本翻译
  bash wsl_run_seamless_streaming.sh --mic --mode s2tt --src-lang eng --tgt-lang cmn

  # 音频文件翻译
  bash wsl_run_seamless_streaming.sh --input audio.wav --src-lang cmn --tgt-lang eng

  # 低延迟模式 (更小的 segment size)
  bash wsl_run_seamless_streaming.sh --mic --segment-size 160 --src-lang eng --tgt-lang jpn
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)        MODE="$2"; shift 2 ;;
        --src-lang)    SRC_LANG="$2"; shift 2 ;;
        --tgt-lang)    TGT_LANG="$2"; shift 2 ;;
        --input)       INPUT="$2"; shift 2 ;;
        --mic)         INPUT_MIC=true; shift ;;
        --segment-size) SEGMENT_SIZE="$2"; shift 2 ;;
        --model-ckpt)  MODEL_CKPT="$2"; shift 2 ;;
        --vocoder-ckpt) VOCODER_CKPT="$2"; shift 2 ;;
        --no-mirror)   USE_MIRROR=false; shift ;;
        --no-fp16)     USE_FP16=false; shift ;;
        -h|--help)     usage ;;
        *) error "未知选项: $1 (使用 -h 查看帮助)" ;;
    esac
done

if [ "$INPUT_MIC" = false ] && [ -z "$INPUT" ]; then
    error "请指定输入方式: --mic (麦克风) 或 --input <音频文件>"
fi

if [ "$INPUT_MIC" = true ] && [ -n "$INPUT" ]; then
    error "不能同时指定 --mic 和 --input"
fi

eval "$(conda shell.bash hook)"
conda activate seamless_streaming 2>/dev/null || error "conda 环境 seamless_streaming 不存在，请先运行 bash wsl_setup.sh"

if [ "$USE_MIRROR" = true ]; then
    export HF_ENDPOINT="$HF_MIRROR"
    export HF_HUB_DISABLE_XET=1
    info "使用国内镜像: $HF_MIRROR"
fi

if [ -z "$MODEL_CKPT" ]; then
    if [ -d "$WORK_DIR/models/seamless-streaming" ]; then
        MODEL_CKPT="$WORK_DIR/models/seamless-streaming"
        info "使用本地模型: $MODEL_CKPT"
    else
        MODEL_CKPT="facebook/seamless-streaming"
        info "使用 HuggingFace 模型: $MODEL_CKPT"
    fi
fi

if [ -z "$VOCODER_CKPT" ]; then
    VOCODER_CKPT="$MODEL_CKPT"
fi

case "$MODE" in
    s2st)
        AGENT_CLASS="seamless_communication.streaming.agents.seamless_streaming_s2st.SeamlessStreamingS2STAgent"
        MODE_DESC="语音→语音"
        ;;
    s2tt)
        AGENT_CLASS="seamless_communication.streaming.agents.seamless_streaming_s2tt.SeamlessStreamingS2TTAgent"
        MODE_DESC="语音→文本"
        ;;
    t2tt)
        AGENT_CLASS="seamless_communication.streaming.agents.seamless_streaming_text.SeamlessStreamingTextAgent"
        MODE_DESC="文本→文本"
        ;;
    *)
        error "不支持的模式: $MODE (可选: s2st, s2tt, t2tt)"
        ;;
esac

echo ""
echo "=========================================="
echo "SeamlessStreaming 实时流式同声传译"
echo "=========================================="
echo "  模式:     $MODE_DESC ($MODE)"
echo "  源语言:   $SRC_LANG"
echo "  目标语言: $TGT_LANG"
echo "  输入:     $([ "$INPUT_MIC" = true ] && echo "麦克风" || echo "$INPUT")"
echo "  段大小:   $SEGMENT_SIZE 帧 ($(( SEGMENT_SIZE * 1000 / 16000 ))ms)"
echo "  模型:     $MODEL_CKPT"
echo "  半精度:   $USE_FP16"
echo "=========================================="
echo ""

if [ "$INPUT_MIC" = true ]; then
    info "启动麦克风实时翻译 (按 Ctrl+C 停止)..."
    echo ""

    SIMULEVAL_CMD="simuleval \
        --agent-class $AGENT_CLASS \
        --source-segment-size $SEGMENT_SIZE \
        --input-mic \
        --source-lang $SRC_LANG \
        --target-lang $TGT_LANG \
        --model-ckpt $MODEL_CKPT"

    if [ "$MODE" = "s2st" ]; then
        SIMULEVAL_CMD="$SIMULEVAL_CMD --vocoder-ckpt $VOCODER_CKPT"
    fi

    eval $SIMULEVAL_CMD

else
    if [ ! -f "$INPUT" ]; then
        error "输入文件不存在: $INPUT"
    fi

    OUTPUT_DIR="$WORK_DIR/output/seamless_streaming_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$OUTPUT_DIR"

    info "翻译音频文件: $INPUT"
    info "输出目录: $OUTPUT_DIR"
    echo ""

    simuleval \
        --agent-class $AGENT_CLASS \
        --source-segment-size $SEGMENT_SIZE \
        --input "$INPUT" \
        --output "$OUTPUT_DIR" \
        --source-lang $SRC_LANG \
        --target-lang $TGT_LANG \
        --model-ckpt $MODEL_CKPT \
        $( [ "$MODE" = "s2st" ] && echo "--vocoder-ckpt $VOCODER_CKPT" )

    info "翻译完成！结果保存在: $OUTPUT_DIR"
fi
