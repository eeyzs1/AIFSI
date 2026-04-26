# 依赖安装说明

## 问题总结

1. ✅ **torchcodec 错误** — 已修复（使用 soundfile 替代 torchaudio）
2. ✅ **HuggingFace 下载慢** — 已修复（使用 hf-mirror.com）
3. ✅ **Ctrl+C 卡住** — 已修复（立即停止音频流）
4. ⚠️ **FFmpeg 依赖** — 需要正确安装

---

## 必需依赖

### 1. Python 包

**级联方案（Whisper + F5-TTS）：**
```bash
pip install faster-whisper f5-tts sounddevice soundfile numpy torch webrtcvad
```

**端到端方案（SeamlessM4T）：**
```bash
pip install transformers torch sounddevice soundfile numpy webrtcvad sentencepiece protobuf
```

**全部安装：**
```bash
pip install faster-whisper f5-tts transformers torch sounddevice soundfile numpy webrtcvad sentencepiece protobuf
```

**各包说明：**
- `faster-whisper` — 语音识别和翻译（级联方案）
- `f5-tts` — 零样本声音克隆（级联方案）
- `transformers` — HuggingFace 模型加载（端到端方案，SeamlessM4T）
- `sentencepiece` — 文本分词（端到端方案）
- `protobuf` — 协议缓冲区（端到端方案）
- `sounddevice` — 麦克风录音和音频播放
- `soundfile` — 音频文件读写（替代 torchaudio）
- `numpy` — 数组处理
- `torch` — PyTorch（深度学习框架）
- `webrtcvad` — 语音活动检测（VAD）

### 2. FFmpeg（系统级依赖）

**重要：** Python 的 `ffmpeg` 包不是真正的 FFmpeg！

#### Windows 安装 FFmpeg

**方法1：使用 Chocolatey（推荐）**
```bash
# 1. 安装 Chocolatey（如果没有）
# 以管理员身份运行 PowerShell，执行：
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 2. 安装 FFmpeg
choco install ffmpeg
```

**方法2：手动安装**
1. 下载 FFmpeg：https://www.gyan.dev/ffmpeg/builds/
   - 选择 "ffmpeg-release-full-shared.7z"（重要：必须是 shared 版本）
2. 解压到 `C:\ffmpeg`
3. 添加到系统 PATH：
   - 右键"此电脑" → 属性 → 高级系统设置 → 环境变量
   - 在"系统变量"中找到 `Path`，点击编辑
   - 添加 `C:\ffmpeg\bin`
4. 重启终端，验证：
   ```bash
   ffmpeg -version
   ```

#### Linux 安装 FFmpeg

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

#### macOS 安装 FFmpeg

```bash
# 使用 Homebrew
brew install ffmpeg
```

---

## 已修复的问题

### 1. torchcodec 错误 ✅

**原因：** `torchaudio.load()` 依赖 `torchcodec`，而 `torchcodec` 需要 FFmpeg 的特定版本和 DLL 文件。

**解决方案：** 使用 `soundfile` 替代 `torchaudio`

**代码修改：**
```python
# 之前（会报错）
import torchaudio
audio, sr = torchaudio.load(audio_path)

# 现在（不会报错）
import soundfile as sf
audio, sr = sf.read(audio_path)
```

### 2. HuggingFace 下载慢 ✅

**解决方案：** 设置环境变量使用镜像

**代码修改：**
```python
# 在文件开头添加
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
```

**效果：**
- Whisper 模型从 hf-mirror.com 下载
- F5-TTS 模型从 hf-mirror.com 下载
- 速度提升 10-100 倍

### 3. Ctrl+C 卡住 ✅

**原因：** 使用 `with sd.InputStream()` 时，Ctrl+C 会等待 context manager 退出，但队列可能还在处理。

**解决方案：** 手动管理音频流，立即停止

**代码修改：**
```python
# 之前（会卡住）
with sd.InputStream(...) as stream:
    while True:
        time.sleep(0.1)

# 现在（不会卡住）
stream = sd.InputStream(...)
stream.start()
try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    stream.stop()  # 立即停止
    stream.close()
```

---

## 验证安装

### 1. 验证 Python 包

**级联方案：**
```bash
python -c "import faster_whisper; print('faster-whisper: OK')"
python -c "import f5_tts; print('f5-tts: OK')"
python -c "import sounddevice; print('sounddevice: OK')"
python -c "import soundfile; print('soundfile: OK')"
python -c "import webrtcvad; print('webrtcvad: OK')"
python -c "import torch; print('torch: OK')"
```

**端到端方案：**
```bash
python -c "import transformers; print('transformers: OK')"
python -c "import sentencepiece; print('sentencepiece: OK')"
python -c "import sounddevice; print('sounddevice: OK')"
python -c "import soundfile; print('soundfile: OK')"
python -c "import webrtcvad; print('webrtcvad: OK')"
python -c "import torch; print('torch: OK')"
```

### 2. 验证 FFmpeg

```bash
ffmpeg -version
```

应该看到类似输出：
```
ffmpeg version 6.0 Copyright (c) 2000-2023 the FFmpeg developers
...
```

### 3. 验证麦克风

```bash
python -c "import sounddevice as sd; print(sd.query_devices())"
```

应该看到你的麦克风设备列表。

---

## 常见问题

### Q1: 提示 "Could not load libtorchcodec"

**A:** 已修复，代码不再使用 torchaudio。如果还有问题，确保使用最新版本的 `streaming_interpreter.py`。

### Q2: FFmpeg 安装了但还是报错

**A:** 确保：
1. 安装的是 **shared** 版本（Windows）
2. FFmpeg 在系统 PATH 中
3. 重启终端后再测试

### Q3: 模型下载很慢

**A:** 已修复，代码自动使用 hf-mirror.com。如果还慢，手动设置：
```bash
export HF_ENDPOINT=https://hf-mirror.com  # Linux/macOS
set HF_ENDPOINT=https://hf-mirror.com     # Windows CMD
$env:HF_ENDPOINT="https://hf-mirror.com"  # Windows PowerShell
```

### Q4: Ctrl+C 后卡住

**A:** 已修复，代码会立即停止音频流。如果还卡住，强制退出：
- Windows: Ctrl+Break 或关闭窗口
- Linux/macOS: Ctrl+\ 或 `kill -9 <pid>`

---

## 完整安装流程

### Windows

```bash
# 1. 安装 FFmpeg（使用 Chocolatey）
choco install ffmpeg

# 2. 安装 Python 包
pip install faster-whisper f5-tts sounddevice soundfile numpy torch webrtcvad

# 3. 验证
ffmpeg -version
python -c "import sounddevice; print(sounddevice.query_devices())"

# 4. 运行
python streaming_interpreter.py --ref-audio voice.wav --ref-text "..."
```

### Linux/macOS

```bash
# 1. 安装 FFmpeg
sudo apt install ffmpeg  # Ubuntu/Debian
brew install ffmpeg      # macOS

# 2. 安装 Python 包
pip install faster-whisper f5-tts sounddevice soundfile numpy torch webrtcvad

# 3. 验证
ffmpeg -version
python -c "import sounddevice; print(sounddevice.query_devices())"

# 4. 运行
python streaming_interpreter.py --ref-audio voice.wav --ref-text "..."
```

---

## 总结

✅ **所有问题已修复**

1. 不再依赖 torchaudio（避免 torchcodec 错误）
2. 自动使用 hf-mirror.com（加速模型下载）
3. 立即停止音频流（Ctrl+C 不卡住）
4. 需要正确安装 FFmpeg（系统级依赖）

**现在可以正常运行了！** 🎉
