# 快速开始指南

## 一、环境准备

### 系统要求
- Python 3.8+
- NVIDIA GPU（推荐，至少 4GB 显存）
- ffmpeg（必须）

### 安装步骤

```bash
# 1. 运行安装脚本（跨平台）
python scripts/setup.py

# 2. 验证安装
python -c "import torch; print('GPU:', torch.cuda.is_available())"
ffmpeg -version
```

---

## 二、5分钟快速体验

### 功能1: 同声传译（分段模式，推荐，无需参考音频）

**准备工作：**
- 无需录制参考音频

**运行：**
```bash
# 整句模式（默认）— 说完一句停顿1.5秒后翻译
python seamless_interpreter.py --src-lang zh --tgt-lang eng

# 分段模式 — 每3秒翻译一次，适合长时间持续说话
python seamless_interpreter.py --src-lang zh --tgt-lang eng --mode chunk
```

**效果：**
- 对着麦克风说中文，自动翻译成英文
- 无需参考音频，内置多说话人声码器
- 支持 101 种语言

**两种模式区别：**
- 整句模式（默认）：说完一整句后停顿1.5秒触发翻译，适合短句对话
- 分段模式（--mode chunk）：每N秒触发一次翻译，适合长时间持续说话

> ⚠️ **关于流式同传（SeamlessStreaming + EMMA）：** `streaming/` 目录下曾有基于 EMMA 机制的流式同传实现，**当前无法正常运行，仅作为技术思路保留**。该方案依赖 fairseq2 + seamless_communication + SimulEval，存在严重的环境兼容性问题（仅限 Linux/WSL、fairseq2 无 Windows 支持、Blackwell GPU 需要大量 monkey-patch 等），实际运行效果不稳定。如需同声传译功能，请使用本功能（分段模式）或功能3（级联模式）。

---

### 功能2: 级联同传 + 声音克隆（需要参考音频）

**准备工作：**
1. 录制10秒参考音频（你自己的声音）
   - 打开录音软件（Windows录音机/macOS QuickTime）
   - 说一段英文（如 "Hello, this is a test of voice cloning technology."）
   - 保存为 `my_voice.wav`

**运行：**
```bash
python apps/cascade_interpreter.py \
  --ref-audio my_voice.wav \
  --ref-text "Hello, this is a test of voice cloning technology."
```

**效果：**
- 对着麦克风说中文
- 实时听到英文翻译（用你的声音）
- 延迟 < 2秒（从说话结束到播放开始）
- 注意：这不是真正的流式同传，而是分段翻译。

---

### 功能3: 音频文件翻译

**准备工作：**
1. 录制10秒参考音频（你自己的声音）
   - 保存为 `my_voice.wav`
2. 准备一段中文音频（如会议录音、播客片段）
   - 保存为 `chinese_audio.wav`

**运行：**
```bash
python interpreter.py \
  --ref-audio my_voice.wav \
  --ref-text "Hello, this is a test of voice cloning technology." \
  --mode file \
  --input chinese_audio.wav \
  --output translated.wav
```

**效果：**
- 自动识别中文
- 翻译成英文
- 用你的声音配音
- 输出音频文件 + 文本文件（带时间戳）

---

### 功能4: 声音克隆对比

**零样本克隆（F5-TTS）：**
```bash
# 1. 注册你的声音（10秒）
python apps/voice_manager.py register \
  --name "我的声音" \
  --audio my_voice.wav \
  --text "Hello, this is a test of voice cloning technology."

# 2. 立即使用
python apps/voice_manager.py speak \
  --name "我的声音" \
  --text "Artificial intelligence is transforming the world." \
  --output zero_shot.wav
```

**传统微调方案（XTTS）：**
```bash
# 1. 准备数据集（需要 10-30 分钟音频）
python apps/voice_finetune.py prepare \
  --audio-dir ./voice_samples \
  --output ./dataset

# 2. 微调模型（需要 2-8 小时 + GPU）
python apps/voice_finetune.py train \
  --dataset ./dataset \
  --output ./models/my_voice \
  --steps 1000

# 3. 使用微调模型
python apps/voice_finetune.py infer \
  --model ./models/my_voice \
  --text "Artificial intelligence is transforming the world." \
  --output finetuned.wav
```

**对比总结：**
| 维度 | 零样本（F5-TTS） | 微调（XTTS） |
|---|---|---|
| 数据需求 | 10秒音频 | 10-30分钟音频 |
| 处理时间 | 0（无需处理） | 1-2小时 |
| 训练时间 | 0（无需训练） | 2-8小时 |
| 总时间 | **10秒** | **3-10天** |
| 速度提升 | **100-1000倍** | - |
| 音质 | 自然度高 | 还原度极高 |
| 适用场景 | 快速迭代、多声音 | 长期使用、品牌声音 |

---

### 功能5: 视频翻译+配音

**准备工作：**
- 找一个中文短视频（1-2分钟，有说话内容）
- 保存为 `test_video.mp4`

**运行：**
```bash
python apps/video_translate.py test_video.mp4 \
  --ref-audio my_voice.wav \
  --ref-text "Hello, this is a test of voice cloning technology." \
  --output translated.mp4
```

**效果：**
- 自动识别中文
- 翻译成英文
- 用你的声音配音
- 生成双语字幕

---

## 三、同声传译方案对比

| 维度 | 分段翻译（SeamlessM4T） | 级联方案（Whisper+F5-TTS） | ⚠️ 流式同传（EMMA，不可用） |
|---|---|---|---|
| **实时性** | ❌ 攒一段翻一段 | ❌ 攒一段翻一段 | 理论上边听边翻 |
| **延迟** | 1.5-5秒 | < 2秒 | 理论320ms+ |
| **声音克隆** | ❌ 不支持（内置声码器） | ✅ 用你的声音 | ❌ 不支持 |
| **语言支持** | 101种 | 取决于Whisper | 37种 |
| **GPU需求** | 4GB+ | 4GB+ | 8GB+ |
| **环境** | 跨平台 | 跨平台 | 仅Linux/WSL |
| **安装复杂度** | 低 | 低 | 极高（不可用） |
| **可用状态** | ✅ 可用 | ✅ 可用 | ❌ 仅作思路参考 |
| **适用场景** | 对话、演讲 | 需要特定声音 | — |

---

## 四、常见问题

### Q1: 没有 GPU 怎么办？
**A:** 可以运行，但速度会很慢。建议：
- `interpreter.py`: 改用 `--model-size small`（更快）
- `video_translate.py`: 添加 `--model-size small`

### Q2: ffmpeg 未安装
**A:** 
- Windows: https://ffmpeg.org/download.html 下载后添加到 PATH
- Linux: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`

### Q3: 首次运行很慢
**A:** 正常，首次运行会下载模型：
- Whisper large-v3: ~3GB
- F5-TTS: ~1.5GB
- SeamlessM4T v2: ~9GB
- SeamlessStreaming: ~5GB
- 国内自动使用 hf-mirror.com 加速下载
- 下载完成后会缓存，后续运行很快

### Q4: SeamlessM4T 和 Whisper+F5-TTS 方案怎么选？
**A:**
- **需要声音克隆（用特定人的声音）** → 选 Whisper+F5-TTS 级联方案（cascade_interpreter.py）
- **不想录制参考音频** → 选 SeamlessM4T（seamless_interpreter.py）
- **追求翻译质量（避免级联误差）** → 选 SeamlessM4T

### Q5: 流式同传（SeamlessStreaming）能用吗？
**A:** **当前不可用，仅作为技术思路保留。** `streaming/` 目录下的流式同传代码存在严重的环境兼容性问题：fairseq2 仅支持 Linux、0.2.x 与 0.8.x API 不兼容、Blackwell GPU 需要大量 monkey-patch、WSL 音频设备支持不完善等。如需同声传译功能，请使用 `seamless_interpreter.py`（分段模式）或 `cascade_interpreter.py`（级联模式）。

### Q6: WSL 下麦克风不工作
**A:** WSL 需要配置 PulseAudio 来访问 Windows 麦克风：
```bash
# 在 Windows 上安装 PulseAudio 服务器
# 在 WSL 中设置环境变量
export PULSE_SERVER=tcp:$(hostname).local
```

### Q7: 声音克隆效果不好
**A:** 检查参考音频质量：
- 时长：10-15秒最佳
- 格式：WAV，16kHz 或 24kHz
- 质量：无背景噪音，说话清晰
- 内容：最好是完整句子，不要单个词

### Q8: 视频翻译报错
**A:** 检查：
1. 视频格式是否支持（MP4/AVI/MOV）
2. 视频是否损坏（用播放器测试）
3. 磁盘空间是否充足（临时文件需要空间）

---

## 五、进阶使用

### 批量处理多个视频
```bash
# 创建批处理脚本
for video in *.mp4; do
  python apps/video_translate.py "$video" \
    --ref-audio my_voice.wav \
    --ref-text "..." \
    --output "translated_$video"
done
```

### 自定义字幕区域（去字幕）
```bash
# 手动指定字幕位置（更快更准）
python apps/remove_subtitles.py input.mp4 \
  --subtitle-region "0,900,1920,180" \
  --output clean.mp4
```

### 流式同传自定义参数（⚠️ 实验性，当前不可用）

> ⚠️ 以下参数仅适用于 `streaming/seamless_streaming_mic.py`，该方案当前无法正常运行，仅作思路参考。

```bash
# 调整分段大小（更小=更低延迟，但可能断句不准）
python seamless_streaming_mic.py --src-lang cmn --tgt-lang eng --segment-size 160

# 调整决策阈值（更低=更早开始翻译）
python seamless_streaming_mic.py --src-lang cmn --tgt-lang eng --decision-threshold 0.3
```

---

## 六、性能优化

### GPU 显存不足
```bash
# 使用更小的模型
python interpreter.py --ref-audio voice.wav --ref-text "..." --model-size small

# video_translate.py 同理
python apps/video_translate.py input.mp4 --model-size small ...
```

### 加速视频处理
```bash
# 降低输出视频质量（更快）
# 修改 video_translate.py 中的 ffmpeg 参数：
# -c:v libx264 -preset ultrafast -crf 28
```

### 流式同传优化（⚠️ 实验性，当前不可用）
- 该方案当前无法正常运行，仅作思路参考
- 理论优化方向：减小 `--segment-size` 降低延迟（但可能影响质量）

---

## 七、故障排查

### 日志查看
所有模块都会输出详细日志，出错时查看：
- 模型加载是否成功
- 文件路径是否正确
- GPU 是否可用

### 测试单个模块
```bash
# 测试 Whisper
python -c "from faster_whisper import WhisperModel; m = WhisperModel('small'); print('OK')"

# 测试 F5-TTS
python -c "from f5_tts.api import F5TTS; t = F5TTS(); print('OK')"

# 测试 SeamlessM4T
python -c "from transformers import AutoProcessor, SeamlessM4Tv2Model; print('OK')"

# 测试 ffmpeg
ffmpeg -version
```

### 重新安装
```bash
# 清理缓存
rm -rf ~/.cache/huggingface
rm -rf ~/.cache/torch

# 重新安装主项目
pip uninstall -y faster-whisper f5-tts
pip install faster-whisper f5-tts
```

---

## 八、更多文档

- 查看 [docs/design/](docs/design/) 目录的技术设计文档
- 查看 [docs/dependencies.md](docs/dependencies.md) 了解依赖安装详情
- 查看 [docs/streaming_usage.md](docs/streaming_usage.md) 了解流式同传详细说明
