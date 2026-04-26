# 系统架构图

## 整体架构（Mermaid）

```mermaid
graph TB
    subgraph INPUT["输入层"]
        V[短视频文件]
        L[直播流 RTMP/HLS]
        M[麦克风]
    end

    subgraph STT["语音理解层"]
        VAD[Silero VAD\n句子边界检测]
        ASR[faster-whisper large-v3\nSTT + 中→英翻译]
        DIA[pyannote-audio\n说话人分离]
    end

    subgraph TRANS["语言转换层"]
        TR1[Whisper translate task\n直播/实时场景]
        TR2[NLLB-200\n多语种字幕精修]
        SUM[LLM 文案提炼/改写\nQwen2.5 / Llama 3.1]
    end

    subgraph TTS["语音合成层"]
        F5[F5-TTS\n零样本声音克隆\n10秒参考音频]
        XTTS[XTTS v2\n微调声音\n1-5分钟训练数据]
        ROUTER{声音路由\n新声音→F5\n固定声音→XTTS}
    end

    subgraph VIDEO["视频生产层"]
        SYNC[LatentSync\n口型同步]
        MIX[ffmpeg\n音视频合成]
        CUT[PySceneDetect + MoviePy\nAI混剪]
        SUB[双语字幕烧录]
    end

    subgraph DIST["分发层"]
        QUEUE[任务队列 Celery]
        PUB[矩阵发布\n抖音/YouTube/B站/小红书]
        CHAT[AI聊天机器人\nOllama + RAG]
    end

    V --> VAD
    L --> VAD
    M --> VAD
    VAD --> ASR
    ASR --> DIA
    ASR --> TR1
    ASR --> TR2
    TR2 --> SUM
    TR1 --> ROUTER
    TR2 --> ROUTER
    ROUTER --> F5
    ROUTER --> XTTS
    F5 --> MIX
    XTTS --> MIX
    MIX --> SYNC
    SYNC --> CUT
    CUT --> SUB
    SUB --> QUEUE
    QUEUE --> PUB
    SUM --> CHAT
```

---

## 数据流说明

### 短视频翻译流程
```
视频文件
  → 提取音轨（ffmpeg）
  → VAD 切句
  → faster-whisper（转录 + 翻译）
  → 字幕时间轴对齐
  → F5-TTS / XTTS 合成目标语言语音
  → LatentSync 口型同步（可选）
  → ffmpeg 合成输出视频
  → 矩阵发布
```

### 直播同声传译流程
```
直播音频流
  → Silero VAD（实时切句，~300ms延迟）
  → faster-whisper streaming（~500ms）
  → F5-TTS 流式合成（首包~200ms）
  → 实时混流输出
  总延迟目标：< 2秒
```

### 声音克隆工作流
```
新声音需求
  → 录制/获取 10秒参考音频
  → F5-TTS 零样本注册（立即可用）
  ↓（可选，后台异步）
  → 收集 1-5 分钟干净录音
  → XTTS v2 微调（GPU，约2-4小时）
  → 替换为微调模型，质量提升
```

---

## 模块依赖关系

```
核心依赖（必须）：
  faster-whisper → 所有语音输入场景
  F5-TTS → 所有语音输出场景
  ffmpeg → 所有视频处理场景
  Silero VAD → 所有实时场景

可选增强：
  LatentSync → 真人出镜视频口型同步
  XTTS v2 → 高频声音微调
  NLLB-200 → 非英语目标语言
  pyannote-audio → 多人对话场景
  Ollama + LLM → AI聊天 + 文案改写
```

---

## 部署拓扑（单机方案）

```
┌─────────────────────────────────────────┐
│              GPU 服务器                   │
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │ Whisper  │  │  F5-TTS  │  │ XTTS  │ │
│  │ Service  │  │ Service  │  │Service│ │
│  │ :8001    │  │ :8002    │  │ :8003 │ │
│  └──────────┘  └──────────┘  └───────┘ │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │     Celery Worker (任务队列)      │   │
│  └──────────────────────────────────┘   │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │     FastAPI 主服务 :8000          │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```
