@echo off
REM Windows 一键安装脚本

echo ==========================================
echo AI视频本地化平台 - 依赖安装脚本 (Windows)
echo ==========================================

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

echo 检测到 Python:
python --version

REM 检查CUDA
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo 警告: 未检测到 NVIDIA GPU，将使用CPU（速度较慢）
) else (
    echo 检测到 NVIDIA GPU:
    nvidia-smi --query-gpu=name --format=csv,noheader
)

REM 检查ffmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo.
    echo 警告: 未检测到 ffmpeg，请手动安装:
    echo   下载地址: https://ffmpeg.org/download.html
    echo   安装后将 ffmpeg.exe 添加到系统 PATH
    echo.
    pause
)

echo.
echo [1/3] 升级 pip...
python -m pip install --upgrade pip

echo.
echo [2/3] 安装 PyTorch...
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo   安装 CPU 版本...
    pip install torch torchvision torchaudio
) else (
    echo   安装 CUDA 版本...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
)

echo.
echo [3/3] 安装其他依赖...
pip install -r requirements.txt

echo.
echo ==========================================
echo 安装完成！
echo.
echo 快速测试:
echo   1. 录制10秒参考音频: voice.wav
echo   2. 运行: python interpreter.py --ref-audio voice.wav --ref-text "Hello world"
echo.
echo 详细文档: 查看 DEMO_GUIDE.md
echo ==========================================
pause
