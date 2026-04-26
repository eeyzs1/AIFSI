#!/bin/bash
# 一键安装所有依赖

echo "=========================================="
echo "AI视频本地化平台 - 依赖安装脚本"
echo "=========================================="

# 检查Python版本
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "检测到 Python 版本: $python_version"

if ! command -v python &> /dev/null; then
    echo "错误: 未检测到 Python，请先安装 Python 3.8+"
    exit 1
fi

# 检查CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "✓ 检测到 NVIDIA GPU"
    nvidia-smi --query-gpu=name --format=csv,noheader
else
    echo "⚠ 未检测到 NVIDIA GPU，部分功能将使用CPU（速度较慢）"
fi

# 检查ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠ 未检测到 ffmpeg，请手动安装:"
    echo "  Windows: https://ffmpeg.org/download.html"
    echo "  Linux: sudo apt install ffmpeg"
    echo "  macOS: brew install ffmpeg"
    read -p "按回车继续安装Python依赖..."
fi

# 升级pip
echo ""
echo "[1/3] 升级 pip..."
python -m pip install --upgrade pip

# 安装PyTorch（根据系统自动选择）
echo ""
echo "[2/3] 安装 PyTorch..."
if command -v nvidia-smi &> /dev/null; then
    echo "  安装 CUDA 版本..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
else
    echo "  安装 CPU 版本..."
    pip install torch torchvision torchaudio
fi

# 安装其他依赖
echo ""
echo "[3/3] 安装其他依赖..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "✓ 安装完成！"
echo ""
echo "快速测试："
echo "  1. 录制10秒参考音频: voice.wav"
echo "  2. 运行: python interpreter.py --ref-audio voice.wav --ref-text 'Hello world'"
echo ""
echo "详细文档: 查看 DEMO_GUIDE.md"
echo "=========================================="
