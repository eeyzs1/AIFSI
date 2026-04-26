# 更新日志

## 2026-04-25 同声传译重构与新增端到端方案

### 新增功能

#### 1. 端到端同声传译（SeamlessM4T）
- 新增 `seamless_interpreter.py`
- 基于 Meta SeamlessM4T v2 大模型，端到端语音→语音翻译
- 无需参考音频，内置 200 个说话人声码器
- 支持 101 种语言输入，96 种语言输出
- 国内自动使用 hf-mirror.com 镜像加速模型下载
- 支持实时流式和音频文件两种模式
  ```bash
  # 实时同传
  python seamless_interpreter.py --src-lang zh --tgt-lang eng

  # 音频文件翻译
  python seamless_interpreter.py --src-lang zh --tgt-lang eng --mode file --input audio.wav --output translated.wav
  ```

### Bug 修复

#### streaming_interpreter.py
- 修复线程安全问题：`is_playing`、`is_speaking` 等共享状态变量添加 `threading.Lock` 保护
- 修复 VAD 静音帧写入缓冲区的问题：静音帧不再追加到 audio_buffer，减少翻译音频中的无效静音
- 将 `import tempfile` 从函数内部移到文件顶部
- 将 bare except 替换为具体异常类型（`OSError`、`Exception`）
- 删除退出时的竞品对比打印（面试遗留内容）

#### interpreter.py
- 修复 `translate_audio_file` 中原文/译文变量名反了的 bug：`translated_texts` 现在正确存储翻译结果，`original_texts` 存储原文
- 补充 `HF_ENDPOINT` 镜像设置和 `_patched_torchaudio_load` 补丁
- 修复 `speak` 函数中 `os.unlink` 无异常保护的问题
- 删除面试遗留内容

### 两种同声传译方案对比

| 维度 | 级联方案（Whisper + F5-TTS） | 端到端方案（SeamlessM4T） |
|---|---|---|
| 架构 | STT → 翻译 → TTS 三步级联 | 端到端一体化模型 |
| 参考音频 | 必须提供 10 秒参考音频 | 不需要，内置多说话人 |
| 语言支持 | 中→英为主 | 101 种语言输入，96 种语言输出 |
| 误差累积 | 有（级联每步都可能出错） | 无（端到端联合训练） |
| 声音克隆 | 支持（用参考音频克隆特定声音） | 不支持自定义声音 |
| 适用场景 | 需要特定声音的直播、配音 | 多语言同传、快速部署 |
| 模型大小 | Whisper small ~500MB + F5-TTS ~1.5GB | ~9GB |

---

## 2024-01-XX 初始版本

### 新增功能

#### 1. interpreter.py 双模式支持
- **文件模式**：输入音频文件，输出翻译音频 + 文本
  ```bash
  python interpreter.py --mode file --input audio.wav --output result.wav
  ```
  - 自动保存音频文件（.wav）
  - 自动保存文本文件（.txt，包含原文、译文、时间戳）

- **实时模式**：麦克风实时录音，实时播放翻译
  ```bash
  python interpreter.py --mode live
  ```
  - 延迟 < 3秒
  - 适用于直播、会议

#### 2. 声音克隆微调模块
- 新增 `demo/voice_finetune.py`
- 传统微调方案的完整流程：
  - 数据准备（10-30分钟音频）
  - 数据处理（1-2小时）
  - 模型训练（2-8小时）
  - 总时间：3-10天
- 对比零样本克隆（F5-TTS）：
  - 10秒音频 → 立即使用
  - 速度提升：**100-1000倍**

### 代码优化

#### interpreter.py
- 添加 `--mode` 参数（live/file）
- 添加 `--input` 和 `--output` 参数
- 添加 `translate_audio_file()` 函数
- 自动保存文本文件（带时间戳）
- 支持 GPU/CPU 自动切换
- 添加 `--model-size` 参数

---

## 下一步计划

- [ ] 集成真实的 Wav2Lip 模型到 lipsync.py
- [ ] 集成 LAMA 模型到 remove_subtitles.py
- [ ] 添加 Web UI（Gradio/Streamlit）
- [ ] 性能基准测试
- [ ] Docker 镜像
