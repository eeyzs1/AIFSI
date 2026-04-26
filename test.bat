@echo off
REM 自动化测试脚本 - Windows 版本

echo ==========================================
echo AI视频本地化平台 - 自动化测试
echo ==========================================

set TOTAL=0
set PASSED=0
set FAILED=0

echo.
echo ========== 环境检查 ==========

call :test "Python 版本" "python --version"
call :test "ffmpeg 安装" "ffmpeg -version"
call :test "GPU 可用性" "python -c \"import torch; assert torch.cuda.is_available()\""

echo.
echo ========== Python 依赖检查 ==========

call :test "faster-whisper" "python -c \"import faster_whisper\""
call :test "f5-tts" "python -c \"from f5_tts.api import F5TTS\""
call :test "sounddevice" "python -c \"import sounddevice\""
call :test "opencv-python" "python -c \"import cv2\""
call :test "moviepy" "python -c \"import moviepy\""
call :test "scenedetect" "python -c \"import scenedetect\""

echo.
echo ========== 模型加载测试 ==========

call :test "Whisper small 模型" "python -c \"from faster_whisper import WhisperModel; m = WhisperModel('small', device='cpu')\""
call :test "F5-TTS 模型" "python -c \"from f5_tts.api import F5TTS; t = F5TTS()\""

echo.
echo ========== Demo 脚本语法检查 ==========

call :test "interpreter.py" "python -m py_compile interpreter.py"
call :test "video_translate.py" "python -m py_compile demo/video_translate.py"
call :test "voice_manager.py" "python -m py_compile demo/voice_manager.py"
call :test "lipsync.py" "python -m py_compile demo/lipsync.py"
call :test "auto_edit.py" "python -m py_compile demo/auto_edit.py"
call :test "remove_subtitles.py" "python -m py_compile demo/remove_subtitles.py"

echo.
echo ==========================================
echo 测试完成
echo   总计: %TOTAL%
echo   通过: %PASSED%
echo   失败: %FAILED%
echo ==========================================

if %FAILED% EQU 0 (
    echo 所有测试通过！环境配置正确。
    echo.
    echo 下一步：
    echo   1. 录制10秒参考音频: my_voice.wav
    echo   2. 运行: python interpreter.py --ref-audio my_voice.wav --ref-text "Hello world"
) else (
    echo 部分测试失败，请检查环境配置。
    echo.
    echo 常见问题：
    echo   - GPU 不可用: 可以继续使用 CPU（速度较慢）
    echo   - 依赖缺失: 运行 pip install -r requirements.txt
    echo   - ffmpeg 未安装: 访问 https://ffmpeg.org/download.html
)

pause
exit /b

:test
set /a TOTAL+=1
echo.
echo [测试 %TOTAL%] %~1
%~2 >nul 2>&1
if %errorlevel% EQU 0 (
    echo [32m✓ 通过[0m
    set /a PASSED+=1
) else (
    echo [31m✗ 失败[0m
    set /a FAILED+=1
)
goto :eof
