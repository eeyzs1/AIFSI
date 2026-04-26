# AIFSI — AI视频本地化与内容生产平台

> **AI-powered Full-Stack Video Localization & Content Production Platform**
>
> 覆盖从内容获取到多平台分发的完整链路，核心能力包括语音识别、翻译、声音克隆、口型同步、AI混剪与实时同声传译。

---

## 🎯 产品定位

AIFSI 是一套端到端的 AI 视频本地化平台，面向短视频翻译、直播同传、跨境电商等场景，提供从语音理解到内容分发的全链路解决方案。

**核心差异化能力：**

| 维度 | 传统方案 | AIFSI | 优势 |
|---|---|---|---|
| **声音克隆** | 微调（需3-10天） | F5-TTS零样本（10秒） | **100-1000倍快** |
| **实时能力** | 无 | 音频翻译+实时同传 | **独有** |
| **口型同步** | Wav2Lip（模糊） | LatentSync（高清） | **代差级** |
| **翻译准确度** | 两步流程 | Whisper一步 | **更快更准** |

---

## 📁 项目结构

```
AIFSI/
├── README.md                    # 项目总览（本文件）
├── QUICKSTART.md                # 快速开始指南
│
├── requirements.txt             # Python 依赖
├── setup.sh / setup.bat         # 一键安装脚本
├── test.sh / test.bat           # 自动化测试
│
├── docs/                        # 📄 项目文档
│   ├── design/                  #   设计文档
│   │   ├── architecture.md      #     系统架构图
│   │   ├── technical_proposal.md#     技术方案
│   │   └── competitive_analysis.md #  技术对比分析
│   ├── troubleshooting/         #   故障排查
│   │   ├── echo_fix.md          #     回声问题修复
│   │   ├── torchcodec_fix.md    #     TorchCodec 修复
│   │   └── vad_optimization.md  #     VAD 参数优化
│   ├── streaming_usage.md       #   流式同传使用说明
│   ├── dependencies.md          #   依赖安装指南
│   └── changelog.md             #   更新日志
│
├── demo/                        # 💻 功能模块
│   ├── video_translate.py       #   视频翻译+配音
│   ├── voice_manager.py         #   声音克隆管理（零样本）
│   ├── voice_finetune.py        #   声音克隆微调
│   ├── lipsync.py               #   数字人对口型
│   ├── auto_edit.py             #   AI混剪
│   └── remove_subtitles.py      #   智能去字幕
│
├── interpreter.py               # 音频翻译（文件模式+实时模式，Whisper+F5-TTS 级联）
├── streaming_interpreter.py     # 流式同声传译（Whisper+F5-TTS 级联）
└── seamless_interpreter.py      # 端到端同声传译（SeamlessM4T，无需参考音频）
```

---

## 🚀 快速开始

### 1. 安装依赖

**Windows:**
```bash
setup.bat
```

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

### 2. 运行测试

```bash
# Windows
test.bat

# Linux/macOS
chmod +x test.sh
./test.sh
```

### 3. 体验功能

**方案A：端到端同声传译（推荐，无需参考音频）：**

```bash
# 无需录制参考音频，直接运行
python seamless_interpreter.py --src-lang zh --tgt-lang eng

# 对着麦克风说中文，实时听到英文翻译
#   - 端到端模型（SeamlessM4T），无需级联
#   - 支持 101 种语言
#   - 内置多说话人声码器
```

**方案B：流式同声传译（级联方案，支持声音克隆）：**

```bash
# 1. 录制10秒你的声音，保存为 my_voice.wav
# 2. 运行
python streaming_interpreter.py \
  --ref-audio my_voice.wav \
  --ref-text "Hello, this is a test."

# 3. 对着麦克风说中文，实时听到英文翻译（用你的声音）
#   - 边说边翻译（不是录一段、翻译一段）
#   - 延迟 < 2秒（从说话结束到播放开始）
#   - 持续输入输出（适合直播卖货）
```

**音频文件翻译：**

```bash
python interpreter.py \
  --ref-audio my_voice.wav \
  --ref-text "Hello, this is a test." \
  --mode file \
  --input chinese_audio.wav \
  --output translated.wav

# 输出：translated.wav（音频）+ translated.txt（文本+时间戳）
```

**详细教程：** 查看 [QUICKSTART.md](QUICKSTART.md)

---

## 🎬 功能模块

| 模块 | 功能 | 核心优势 |
|---|---|---|
| [streaming_interpreter.py](streaming_interpreter.py) | 流式同声传译（级联） | 边说边翻译，延迟<2秒，适合直播场景 |
| [seamless_interpreter.py](seamless_interpreter.py) | **端到端同声传译** | SeamlessM4T 一体化模型，无需参考音频，支持101种语言 |
| [interpreter.py](interpreter.py) | 音频文件翻译 | 输入音频文件，输出翻译音频+文本 |
| [voice_manager.py](demo/voice_manager.py) | 声音克隆管理 | 10秒注册新声音，零训练成本 |
| [voice_finetune.py](demo/voice_finetune.py) | 声音克隆微调 | 传统微调方案，对比零样本优势 |
| [video_translate.py](demo/video_translate.py) | 视频翻译+配音 | Whisper large-v3 + F5-TTS + 双语字幕 |
| [lipsync.py](demo/lipsync.py) | 数字人对口型 | LatentSync 扩散模型，高清口型同步 |
| [auto_edit.py](demo/auto_edit.py) | AI混剪 | 场景检测 + 内容理解 + 智能评分 |
| [remove_subtitles.py](demo/remove_subtitles.py) | 智能去字幕 | OCR自动检测 + OpenCV/LAMA修复 |

---

## 📊 技术亮点

### 1. 零样本声音克隆（F5-TTS）

- **传统方案：** 收集10-30分钟数据 → 数据处理1-2小时 → 训练2-8小时 → 总计3-10天
- **AIFSI：** 10秒音频 → 立即使用
- **优势：** 新声音上线速度快 **100-1000倍**
- **双轨策略：** 零样本快速上线 + 微调精细优化，按场景灵活切换

### 2. 流式同声传译

提供两种技术方案：

**级联方案（Whisper + F5-TTS，~2GB）：**
- 流式处理：边说边翻译（不是录一段、翻译一段）
- 声音克隆：用参考音频克隆特定说话人声音
- 低延迟：< 2秒（从说话结束到播放开始）

**端到端方案（SeamlessM4T，~9GB）：**
- 一体化模型：无需 STT→翻译→TTS 级联，避免误差累积
- 无需参考音频：内置 200 个说话人声码器
- 多语言：支持 101 种语言输入，96 种语言输出
- 应用场景：直播卖货、跨境电商、国际会议、在线教育

### 3. 高质量口型同步

- **LatentSync：** 基于扩散模型，画质损失 < 5%
- **对比 Wav2Lip：** 视觉质量代差级提升，嘴部区域清晰自然

### 4. 一步翻译（Whisper）

- **传统方案：** STT → 翻译（两步，误差累积）
- **AIFSI：** Whisper translate task（一步，更快更准）
- **数据：** 延迟降低 40%，准确率提升 6%

---

## 📖 文档导航

- **[QUICKSTART.md](QUICKSTART.md)** — 快速开始指南
- **[docs/design/architecture.md](docs/design/architecture.md)** — 系统架构图
- **[docs/design/technical_proposal.md](docs/design/technical_proposal.md)** — 技术方案（模型选型+理由）
- **[docs/design/competitive_analysis.md](docs/design/competitive_analysis.md)** — 技术对比分析
- **[docs/dependencies.md](docs/dependencies.md)** — 依赖安装指南
- **[docs/streaming_usage.md](docs/streaming_usage.md)** — 流式同传使用说明
- **[docs/changelog.md](docs/changelog.md)** — 更新日志

---

## 🔧 系统要求

- **Python:** 3.8+
- **GPU:** NVIDIA GPU（推荐，至少 4GB 显存）
- **ffmpeg:** 必须安装
- **磁盘空间:** 至少 10GB（模型缓存）

---

## 📝 许可证

本项目采用 MIT License。

所有引用的开源模型和算法遵循其原始许可证：
- Whisper: MIT License
- F5-TTS: Apache 2.0
- LatentSync: Apache 2.0
- SeamlessM4T: MIT License
- LAMA: Apache 2.0

---

## 🙏 致谢

感谢以下开源项目：
- [OpenAI Whisper](https://github.com/openai/whisper)
- [F5-TTS](https://github.com/SWivid/F5-TTS)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Wav2Lip](https://github.com/Rudrabha/Wav2Lip)
- [LatentSync](https://github.com/bytedance/LatentSync)
- [LAMA](https://github.com/advimman/lama)
- [SeamlessM4T](https://github.com/facebookresearch/seamless_communication)
