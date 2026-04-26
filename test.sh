#!/bin/bash
# 自动化测试脚本 - 验证所有 demo 是否可运行

echo "=========================================="
echo "AI视频本地化平台 - 自动化测试"
echo "=========================================="

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数
TOTAL=0
PASSED=0
FAILED=0

# 测试函数
test_command() {
    TOTAL=$((TOTAL + 1))
    echo -e "\n[测试 $TOTAL] $1"
    if eval "$2" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 通过${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ 失败${NC}"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

echo -e "\n========== 环境检查 =========="

test_command "Python 版本" "python --version"
test_command "ffmpeg 安装" "ffmpeg -version"
test_command "GPU 可用性" "python -c 'import torch; assert torch.cuda.is_available()'"

echo -e "\n========== Python 依赖检查 =========="

test_command "faster-whisper" "python -c 'import faster_whisper'"
test_command "f5-tts" "python -c 'from f5_tts.api import F5TTS'"
test_command "sounddevice" "python -c 'import sounddevice'"
test_command "opencv-python" "python -c 'import cv2'"
test_command "moviepy" "python -c 'import moviepy'"
test_command "scenedetect" "python -c 'import scenedetect'"

echo -e "\n========== 模型加载测试 =========="

test_command "Whisper small 模型" "python -c 'from faster_whisper import WhisperModel; m = WhisperModel(\"small\", device=\"cpu\")'"
test_command "F5-TTS 模型" "python -c 'from f5_tts.api import F5TTS; t = F5TTS()'"

echo -e "\n========== Demo 脚本语法检查 =========="

test_command "interpreter.py" "python -m py_compile interpreter.py"
test_command "video_translate.py" "python -m py_compile demo/video_translate.py"
test_command "voice_manager.py" "python -m py_compile demo/voice_manager.py"
test_command "lipsync.py" "python -m py_compile demo/lipsync.py"
test_command "auto_edit.py" "python -m py_compile demo/auto_edit.py"
test_command "remove_subtitles.py" "python -m py_compile demo/remove_subtitles.py"

echo -e "\n=========================================="
echo "测试完成"
echo "  总计: $TOTAL"
echo -e "  ${GREEN}通过: $PASSED${NC}"
echo -e "  ${RED}失败: $FAILED${NC}"
echo "=========================================="

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！环境配置正确。${NC}"
    echo ""
    echo "下一步："
    echo "  1. 录制10秒参考音频: my_voice.wav"
    echo "  2. 运行: python interpreter.py --ref-audio my_voice.wav --ref-text 'Hello world'"
    exit 0
else
    echo -e "${RED}✗ 部分测试失败，请检查环境配置。${NC}"
    echo ""
    echo "常见问题："
    echo "  - GPU 不可用: 可以继续使用 CPU（速度较慢）"
    echo "  - 依赖缺失: 运行 pip install -r requirements.txt"
    echo "  - ffmpeg 未安装: 访问 https://ffmpeg.org/download.html"
    exit 1
fi
