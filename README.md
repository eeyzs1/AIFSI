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
| **实时能力** | 无 | 音频翻译+同声传译 | **独有** |
| **口型同步** | Wav2Lip（模糊） | LatentSync（高清） | **代差级** |
| **翻译准确度** | 两步流程 | Whisper一步 | **更快更准** |

---

## 📁 项目结构

```
AIFSI/
├── README.md                    # 项目总览（本文件）
├── QUICKSTART.md                # 快速开始指南
├── requirements.txt             # Python 依赖
│
├── apps/                        # 💻 功能应用
│   ├── video_translate.py       #   视频翻译+配音
│   ├── voice_manager.py         #   声音克隆管理（零样本）
│   ├── voice_finetune.py        #   声音克隆微调
│   ├── lipsync.py               #   数字人对口型
│   ├── remove_subtitles.py      #   智能去字幕
│   ├── interpreter.py           #   音频翻译（Whisper+F5-TTS 级联）
│   ├── cascade_interpreter.py   #   级联同传（Whisper+F5-TTS+声音克隆）
│   └── seamless_interpreter.py  #   同声传译（SeamlessM4T，无需参考音频）
│
├── streaming/                   # 🎙️ 流式同传专区（⚠️ 实验性，当前不可用）
│   ├── seamless_streaming_mic.py    #   麦克风实时流式同传（⚠️ 仅作思路参考，无法运行）
│   ├── fairseq2_compat.py           #   fairseq2 0.8.x 兼容层
│   ├── patch_fairseq2_compat.py     #   源码补丁工具
│   ├── seamless_communication/      #   [git clone, 不提交] 源码
│   └── models/                      #   [不提交] 本地模型（~8GB）
│
├── scripts/                     # 🔧 工具脚本
│   ├── setup.py                 #   主项目安装
│   ├── setup_streaming.py       #   流式同传环境安装
│   └── test.py                  #   自动化测试
│
└── docs/                        # 📄 项目文档
    ├── design/                  #   设计文档
    ├── troubleshooting/         #   故障排查
    ├── streaming_usage.md       #   流式同传使用说明
    ├── dependencies.md          #   依赖安装指南
    └── changelog.md             #   更新日志
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
python scripts/setup.py
```

### 2. 体验功能

**同声传译（分段模式，无需参考音频）：**

```bash
python apps/seamless_interpreter.py --src-lang zh --tgt-lang eng
```

**同声传译 + 声音克隆（需要参考音频）：**

```bash
python apps/cascade_interpreter.py \
  --ref-audio my_voice.wav \
  --ref-text "Hello, this is a test."
```

**音频文件翻译：**

```bash
python apps/interpreter.py \
  --ref-audio my_voice.wav \
  --ref-text "Hello, this is a test." \
  --mode file \
  --input chinese_audio.wav \
  --output translated.wav
```

> ⚠️ **关于流式同传（SeamlessStreaming + EMMA）：** `streaming/` 目录下的流式同传代码**当前无法正常运行**，仅作为技术思路保留。该方案依赖 fairseq2 + seamless_communication + SimulEval，存在严重的环境兼容性问题（仅限 Linux/WSL、fairseq2 无 Windows 支持、Blackwell GPU 需要大量 monkey-patch 等），实际运行效果不稳定。如需同声传译功能，请使用上述 `seamless_interpreter.py`（分段模式）或 `cascade_interpreter.py`（级联模式）。

**详细教程：** 查看 [QUICKSTART.md](QUICKSTART.md)

---

## 🎬 功能模块

| 模块 | 功能 | 核心优势 |
|---|---|---|
| [seamless_interpreter.py](apps/seamless_interpreter.py) | **同声传译（推荐）** | SeamlessM4T 整句/分段模式，无需参考音频，支持101种语言 |
| [cascade_interpreter.py](apps/cascade_interpreter.py) | 级联同传 + 声音克隆 | 翻译结果用你录制的声音说出 |
| [interpreter.py](apps/interpreter.py) | 音频文件翻译 | 输入音频文件，输出翻译音频+文本 |
| [voice_manager.py](apps/voice_manager.py) | 声音克隆管理 | 10秒注册新声音，零训练成本 |
| [video_translate.py](apps/video_translate.py) | 视频翻译+配音 | Whisper large-v3 + F5-TTS + 双语字幕 |
| [lipsync.py](apps/lipsync.py) | 数字人对口型 | LatentSync 扩散模型，高清口型同步 |
| [remove_subtitles.py](apps/remove_subtitles.py) | 智能去字幕 | OCR自动检测 + OpenCV/LAMA修复 |
| [seamless_streaming_mic.py](streaming/seamless_streaming_mic.py) | ⚠️ 流式同传（实验性，不可用） | 仅作思路参考，当前无法正常运行 |

---

## 📊 技术亮点

### 1. 零样本声音克隆（F5-TTS）

- **传统方案：** 收集10-30分钟数据 → 数据处理1-2小时 → 训练2-8小时 → 总计3-10天
- **AIFSI：** 10秒音频 → 立即使用
- **优势：** 新声音上线速度快 **100-1000倍**
- **双轨策略：** 零样本快速上线 + 微调精细优化，按场景灵活切换

### 2. 同声传译

提供两种可用方案和一种实验性思路：

**端到端方案（SeamlessM4T，推荐，~9GB）：**
- 一体化模型：无需 STT→翻译→TTS 级联，避免误差累积
- 无需参考音频：内置 200 个说话人声码器
- 多语言：支持 101 种语言输入，96 种语言输出
- 注意：不是真正的流式同传（边听边翻），而是分段翻译

**级联方案（Whisper + F5-TTS，~2GB）：**
- 声音克隆：用参考音频克隆特定说话人声音
- 低延迟：< 2秒（从说话结束到播放开始）

**⚠️ 流式同传思路（SeamlessStreaming + EMMA，当前不可用）：**
- 基于 EMMA（Monotonic Multihead Attention）机制，理论上可实现边听边翻译
- **当前状态：仅作为技术思路保留，无法正常运行**
- 不可用原因：
  - fairseq2 仅支持 Linux，无 Windows 预编译包
  - fairseq2 0.2.x 与 0.8.x API 严重不兼容，需要大量兼容层代码
  - Blackwell GPU（RTX 5090）需要 monkey-patch PyTorch 核心运算才能运行
  - WSL 环境下音频设备支持不完善
  - 整体环境搭建极其复杂，运行效果不稳定
- 如需同声传译功能，请使用上述两种可用方案

### 3. 高质量口型同步

- **LatentSync：** 基于扩散模型，画质损失 < 5%
- **对比 Wav2Lip：** 视觉质量代差级提升，嘴部区域清晰自然

### 4. 一步翻译（Whisper）

- **传统方案：** STT → 翻译（两步，误差累积）
- **AIFSI：** Whisper translate task（一步，更快更准）
- **数据：** 延迟降低 40%，准确率提升 6%

---

## 🔧 流式同传环境搭建（⚠️ 实验性，当前不可用）

> ⚠️ **重要提示：** 以下流式同传（SeamlessStreaming + EMMA）内容**仅作为技术思路保留，当前无法正常运行**。该方案存在严重的环境兼容性问题，不建议尝试搭建。如需同声传译功能，请使用 `seamless_interpreter.py` 或 `cascade_interpreter.py`。

流式同传（SeamlessStreaming + EMMA）需要独立环境，因为 fairseq2 与主项目依赖冲突。

### 为什么需要独立环境？

| 依赖 | 主项目 | 流式同传 | 冲突 |
|---|---|---|---|
| Python | 3.8+ | **3.10**（fairseq2 硬性要求） | ✅ |
| PyTorch | 任意版本 | **2.7.1+cu128**（RTX 5090） | ✅ |
| fairseq2 | 不需要 | **0.8.x** | - |
| transformers | ✅ | ❌ 版本冲突 | ✅ |

**不需要 conda！** Python 自带的 venv 就够用，更轻量。

### 一键安装（默认 venv，推荐）

```bash
python scripts/setup_streaming.py

# 或使用 conda
python scripts/setup_streaming.py --backend conda
```

该脚本会自动：
1. 检测/安装 Python 3.10（通过 apt 或 pyenv）
2. 创建隔离环境（venv 或 conda）
3. 安装 PyTorch + fairseq2 + seamless_communication + SimulEval
4. 下载必要模型到 `streaming/models/`
5. 应用 fairseq2 0.8.x 兼容补丁

### 手动安装（venv 方式）

```bash
# 1. 安装 Python 3.10（如果没有）
sudo apt install python3.10 python3.10-venv python3.10-dev

# 2. 创建 venv
python3.10 -m venv .venvs/seamless_streaming

# 3. 激活
source .venvs/seamless_streaming/bin/activate

# 4. 安装依赖
pip install torch==2.7.1+cu128 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128
pip install fairseq2==0.8.*
pip install regex sacremoses tqdm 'numpy<2'

# 5. 安装 seamless_communication
cd streaming/seamless_communication && pip install -e .

# 6. 安装 SimulEval
pip install simuleval
pip install soundfile scipy pydub sounddevice webrtcvad
```

### 运行

```bash
source .venvs/seamless_streaming/bin/activate
cd streaming
python seamless_streaming_mic.py --src-lang cmn --tgt-lang eng
```

### fairseq2 0.8.x 兼容层

seamless_communication 原本依赖 fairseq2 0.2.x，但 0.2.x 不支持 RTX 5090。项目提供了 `fairseq2_compat.py` 兼容层，使 seamless_communication 能在 fairseq2 0.8.x 上运行。主要兼容处理：

- API 路径迁移（`fairseq2.nn.transformer` → `fairseq2.models.transformer`）
- 构造函数签名变更（`norm_order`、`layer_norm` 等参数）
- `PaddingMask` → `BatchLayout` 前向传播适配
- 缺失属性注入（`model_dim`、`embedding_dim`、`packed`/`padded` 等）
- `ModuleList.drop_iter` 方法补全
- `download_manager` 模块级函数注入

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

### 主项目
- **Python:** 3.8+
- **GPU:** NVIDIA GPU（推荐，至少 4GB 显存）
- **ffmpeg:** 必须安装
- **磁盘空间:** 至少 10GB（模型缓存）

### 流式同传（SeamlessStreaming）— ⚠️ 实验性，当前不可用
- **Python:** 3.10（独立 venv/conda 环境）
- **GPU:** NVIDIA GPU（推荐 8GB+ 显存）
- **CUDA:** 12.8+
- **OS:** 仅 Linux / WSL（fairseq2 不支持 Windows）
- **磁盘空间:** 额外 ~5GB（模型文件）
- **注意:** 该方案当前无法正常运行，仅作思路参考

---

## 📝 许可证

本项目采用 MIT License。

所有引用的开源模型和算法遵循其原始许可证：
- Whisper: MIT License
- F5-TTS: Apache 2.0
- LatentSync: Apache 2.0
- SeamlessM4T: MIT License
- SeamlessStreaming: MIT License
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
- [SeamlessM4T / SeamlessStreaming](https://github.com/facebookresearch/seamless_communication)
- [SimulEval](https://github.com/facebookresearch/SimulEval)
- [fairseq2](https://github.com/facebookresearch/fairseq2)
