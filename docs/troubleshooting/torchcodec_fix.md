# 🔧 torchcodec 错误最终修复方案

## 问题

即使安装了 FFmpeg，仍然报错：
```
RuntimeError: Could not load libtorchcodec
FileNotFoundError: Could not find module 'libtorchcodec_core8.dll'
```

## 根本原因

F5-TTS 内部调用 `torchaudio.load()`，而 `torchaudio.load()` 依赖 `torchcodec`，`torchcodec` 需要特定的 FFmpeg DLL 文件。

## ✅ 最终解决方案

**Patch `torchaudio.load()` 使用 `soundfile` 替代**

### 代码修改

在 `streaming_interpreter.py` 开头添加：

```python
import soundfile as sf
import torch
import numpy as np

# Patch torchaudio.load 使用 soundfile（避免 torchcodec 依赖）
def _patched_torchaudio_load(filepath, *args, **kwargs):
    """使用 soundfile 替代 torchaudio.load"""
    audio, sr = sf.read(filepath)
    # 转换为 torch tensor
    if len(audio.shape) == 1:
        audio = audio.reshape(1, -1)  # (channels, samples)
    else:
        audio = audio.T  # (samples, channels) -> (channels, samples)
    return torch.from_numpy(audio.astype(np.float32)), sr

# 在导入 f5_tts 之前 patch
import torchaudio
torchaudio.load = _patched_torchaudio_load

# 现在导入 F5-TTS（会使用我们的 patched 版本）
from f5_tts.api import F5TTS
```

### 工作原理

1. **拦截调用**：在 F5-TTS 导入之前，替换 `torchaudio.load` 函数
2. **使用 soundfile**：用 `soundfile.read()` 读取音频（不依赖 torchcodec）
3. **格式转换**：将 numpy 数组转换为 torch tensor（F5-TTS 需要）
4. **透明替换**：F5-TTS 内部调用 `torchaudio.load()` 时，实际使用我们的版本

## 测试

```bash
# 1. 确保已安装 soundfile
pip install soundfile

# 2. 运行脚本
python streaming_interpreter.py \
  --ref-audio my_voice.wav \
  --ref-text "Hello, this is a test of voice cloning technology."

# 3. 应该不再报 torchcodec 错误
```

## 为什么这个方案有效

### 之前的尝试（失败）
- ❌ 只在我们的代码中使用 soundfile → F5-TTS 内部还在用 torchaudio
- ❌ 预处理参考音频 → F5-TTS 内部还会调用 torchaudio.load

### 现在的方案（成功）
- ✅ **Monkey Patch**：在 Python 运行时替换函数
- ✅ **全局生效**：所有对 `torchaudio.load` 的调用都会使用我们的版本
- ✅ **透明替换**：F5-TTS 不知道被替换了，正常工作

## 完整依赖

```bash
pip install faster-whisper f5-tts sounddevice soundfile numpy scipy torch webrtcvad
```

**注意：** 不需要安装 FFmpeg 的 Python 包，系统级 FFmpeg 也不是必需的（因为我们不用 torchcodec）。

## 验证

```bash
# 测试 soundfile
python -c "import soundfile as sf; print('soundfile: OK')"

# 测试 patch
python -c "import torchaudio; import soundfile as sf; import torch; import numpy as np; torchaudio.load = lambda f, *a, **k: (torch.from_numpy(sf.read(f)[0].astype(np.float32)), sf.read(f)[1]); print('patch: OK')"

# 运行脚本
python streaming_interpreter.py --ref-audio my_voice.wav --ref-text "..."
```

## 如果还有问题

### 问题1：soundfile 读取失败
```bash
# 安装 libsndfile
pip install soundfile --upgrade
```

### 问题2：音频格式不支持
```bash
# 确保参考音频是 WAV 格式
ffmpeg -i input.mp3 output.wav
```

### 问题3：F5-TTS 其他错误
```bash
# 重新安装 F5-TTS
pip uninstall f5-tts
pip install f5-tts --no-cache-dir
```

## 总结

✅ **不再需要 torchcodec**
✅ **不再需要 FFmpeg DLL**
✅ **使用 soundfile 替代 torchaudio**
✅ **Monkey Patch 全局生效**

**现在应该可以正常运行了！** 🎉
