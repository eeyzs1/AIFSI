# 同声传译使用说明

本项目提供两种同声传译技术方案，适用于不同场景。

---

## 方案对比

| 维度 | 级联方案（Whisper + F5-TTS） | 端到端方案（SeamlessM4T） |
|---|---|---|
| 脚本 | `streaming_interpreter.py` | `seamless_interpreter.py` |
| 架构 | STT → 翻译 → TTS 三步级联 | 端到端一体化模型 |
| 参考音频 | 必须提供 10 秒参考音频 | 不需要，内置 200 个说话人 |
| 语言支持 | 中→英为主 | 101 种语言输入，96 种语言输出 |
| 误差累积 | 有（级联每步都可能出错） | 无（端到端联合训练） |
| 声音克隆 | 支持（用参考音频克隆特定声音） | 不支持自定义声音 |
| 模型大小 | Whisper small ~500MB + F5-TTS ~1.5GB | ~9GB |
| 国内下载 | hf-mirror.com | hf-mirror.com |
| 适用场景 | 需要特定声音的直播、配音 | 多语言同传、快速部署 |

---

## 方案一：级联方案（streaming_interpreter.py）

### 工作原理

```
麦克风输入（持续）
    ↓
VAD 检测（实时检测说话/静音）
    ↓
音频缓冲区（累积有效语音）
    ↓
检测到静音 → 触发处理
    ↓
转录队列 → 转录线程（Whisper）
    ↓
TTS 队列 → TTS 线程（F5-TTS）
    ↓
扬声器输出（实时播放）
```

### 使用方法

```bash
# 1. 录制10秒参考音频
# 2. 运行
python streaming_interpreter.py \
  --ref-audio my_voice.wav \
  --ref-text "Hello, this is a test of voice cloning technology."

# 3. 对着麦克风说中文
# 4. 实时听到英文翻译（用你的声音）
```

### 参数说明

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--ref-audio` | 参考音频（译员声音，~10s WAV） | 必需 |
| `--ref-text` | 参考音频的文本（英文） | 必需 |
| `--model-size` | Whisper 模型大小（tiny/base/small/medium/large-v3） | small |

### 延迟优化

- VAD 延迟：< 100ms（WebRTC VAD）
- ASR 延迟：< 500ms（Whisper small）
- TTS 延迟：< 1秒（F5-TTS）
- **总延迟：< 2秒**

---

## 方案二：端到端方案（seamless_interpreter.py）

### 工作原理

```
麦克风输入（持续）
    ↓
VAD 检测（实时检测说话/静音）
    ↓
音频缓冲区（累积有效语音）
    ↓
检测到静音 → 触发处理
    ↓
SeamlessM4T 模型（语音→语音，一步完成）
    ↓
扬声器输出（实时播放）
```

### 使用方法

```bash
# 实时同传（中文→英文）
python seamless_interpreter.py --src-lang zh --tgt-lang eng

# 实时同传（中文→日文）
python seamless_interpreter.py --src-lang zh --tgt-lang jpn

# 音频文件翻译
python seamless_interpreter.py --src-lang zh --tgt-lang eng \
  --mode file --input audio.wav --output translated.wav
```

### 参数说明

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--src-lang` | 源语言代码 | zh |
| `--tgt-lang` | 目标语言代码 | eng |
| `--speaker-id` | 说话人 ID（0-199） | 0 |
| `--mode` | 模式（live/file） | live |
| `--input` | 输入音频文件（mode=file 时必需） | - |
| `--output` | 输出音频文件（mode=file 时必需） | - |

### 支持的语言代码

常用语言：

| 语言 | 代码 |
|---|---|
| 中文 | zh / cmn |
| 英文 | en / eng |
| 日文 | ja / jpn |
| 韩文 | ko / kor |
| 法文 | fr / fra |
| 德文 | de / deu |
| 西班牙文 | es / spa |
| 俄文 | ru / rus |
| 阿拉伯文 | ar / ara |

完整语言列表：https://huggingface.co/facebook/seamless-m4t-v2-large

---

## 通用使用建议

### 最佳实践

1. **戴耳机**（强烈推荐）
   - 完全避免回声
   - 可以边听边说
   - 体验最好

2. **不戴耳机**
   - 等播放完成后再说话
   - 播放时会显示 `[播放中...]`
   - 看到 `[播放完成]` 后再说话

### 说话方式

- 说完一句话后，**停顿1秒以上**
- 一句话说完整，不要频繁停顿
- 语速正常，不要太快或太慢

---

## 常见问题

### Q: 麦克风没有激活？
```bash
python -c "import sounddevice as sd; print(sd.query_devices())"
```

### Q: 没有检测到说话？
VAD 灵敏度问题，可在脚本中调整：
- `VAD_MODE`: 0-3，3最激进
- `SILENCE_THRESHOLD`: 静音持续时间（秒）

### Q: 延迟太大？
级联方案可使用更小的模型：
```bash
python streaming_interpreter.py --ref-audio voice.wav --ref-text "..." --model-size tiny
```

### Q: 模型下载慢？
国内自动使用 hf-mirror.com 镜像。如仍慢，手动设置：
```bash
# PowerShell
$env:HF_ENDPOINT="https://hf-mirror.com"
$env:HF_HUB_DISABLE_XET="1"

# Linux/macOS
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1
```

如果自动下载反复超时，可手动下载后再运行：
```powershell
# 1. 更新 huggingface_hub（确保有 hf 命令）
pip install -U huggingface_hub

# 2. 设置环境变量（PowerShell）
$env:HF_ENDPOINT="https://hf-mirror.com"
$env:HF_HUB_DISABLE_XET="1"

# 3. 手动下载模型
hf download facebook/seamless-m4t-v2-large

# 4. 下载完成后再运行脚本
python seamless_interpreter.py --src-lang zh --tgt-lang eng
```

### Q: Ctrl+C 后卡住？
代码已处理立即停止。如仍卡住：
- Windows: Ctrl+Break 或关闭窗口
- Linux/macOS: Ctrl+\ 或 `kill -9 <pid>`
