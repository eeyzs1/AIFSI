# VAD 优化说明

## 问题

> "我说一句话，他有好几个英文音频出现"

## 原因

VAD（语音活动检测）太敏感，把一句话中的短暂停顿（如换气、思考）当作说话结束，导致一句话被分成多段。

## 解决方案

### 1. 调整 VAD 参数

```python
# 之前（太激进）
VAD_MODE = 3  # 最激进模式
SILENCE_THRESHOLD = 0.5  # 静音0.5秒就触发
MIN_SPEECH_DURATION = 0.3  # 最短0.3秒

# 现在（更宽容）
VAD_MODE = 2  # 平衡模式
SILENCE_THRESHOLD = 1.0  # 静音1秒才触发
MIN_SPEECH_DURATION = 0.5  # 最短0.5秒
```

### 2. 添加连续帧检测

```python
# 之前：检测到一帧静音就开始计时
if is_speech:
    self.is_speaking = True
else:
    if self.silence_start is None:
        self.silence_start = time.time()

# 现在：需要连续3帧（90ms）才认为开始/结束说话
if is_speech:
    self.speech_frames += 1
    if self.speech_frames >= 3:  # 连续3帧
        self.is_speaking = True
else:
    self.silence_frames += 1
```

### 3. 优化输出显示

```python
# 之前
print(f"[原文] (检测中...)")
print(f"[译文] {text}")

# 现在
print(f"\n[中文] (识别中...)")
print(f"[英文] {text}")
print("[检测到说话]", "[说话结束]")  # 实时反馈
```

---

## 使用建议

### 说话方式

**推荐：**
- 说完一句话后，**停顿1秒以上**
- 一句话说完整，不要频繁停顿
- 语速正常，不要太快或太慢

**示例：**
```
你说："大家好，欢迎来到我的直播间。"
（停顿1秒）
系统：[检测到说话] [说话结束]
      [英文] Hello everyone, welcome to my live stream.
      （播放英文音频）

你说："今天给大家介绍一款新产品。"
（停顿1秒）
系统：[检测到说话] [说话结束]
      [英文] Today I will introduce a new product to you.
      （播放英文音频）
```

### 调整参数

如果还是出现多段，可以进一步调整：

**增加静音阈值（更宽容）：**
```python
SILENCE_THRESHOLD = 1.5  # 改为1.5秒
```

**降低 VAD 灵敏度：**
```python
VAD_MODE = 1  # 改为1（最不敏感）
```

**增加最短说话时长：**
```python
MIN_SPEECH_DURATION = 1.0  # 改为1秒
```

---

## 参数说明

### VAD_MODE（灵敏度）
- `0` — 最不敏感（容易漏检，但不会误触发）
- `1` — 较不敏感
- `2` — 平衡（推荐）
- `3` — 最敏感（容易误触发）

### SILENCE_THRESHOLD（静音阈值）
- 说话中检测到连续静音多久才认为说话结束
- 太小：一句话被分成多段
- 太大：延迟增加
- **推荐：1.0-1.5秒**

### MIN_SPEECH_DURATION（最短说话时长）
- 说话时长小于此值会被忽略
- 避免短暂噪音被识别
- **推荐：0.5-1.0秒**

---

## 测试

```bash
# 1. 运行脚本
python streaming_interpreter.py \
  --ref-audio my_voice.wav \
  --ref-text "Hello, this is a test of voice cloning technology."

# 2. 测试说话
说："你好，这是一个测试。"
（停顿1秒）

# 3. 观察输出
应该只有一个英文音频：
[检测到说话] [说话结束]
[中文] (识别中...)
[英文] Hello, this is a test.
[延迟] 2.5s
```

---

## 如果还有问题

### 问题1：还是出现多段

**解决：** 增加静音阈值
```python
SILENCE_THRESHOLD = 2.0  # 改为2秒
```

### 问题2：延迟太大

**解决：** 减少静音阈值
```python
SILENCE_THRESHOLD = 0.8  # 改为0.8秒
```

### 问题3：说话没有被检测到

**解决：** 增加 VAD 灵敏度
```python
VAD_MODE = 3  # 改为最敏感
```

### 问题4：噪音被误识别

**解决：** 降低 VAD 灵敏度
```python
VAD_MODE = 1  # 改为最不敏感
MIN_SPEECH_DURATION = 1.0  # 增加最短时长
```

---

## 总结

✅ **已优化 VAD 参数**
- VAD_MODE: 3 → 2（更宽容）
- SILENCE_THRESHOLD: 0.5s → 1.0s（更长）
- 添加连续帧检测（避免误触发）

✅ **使用建议**
- 说完一句话停顿1秒以上
- 不要频繁停顿
- 根据实际情况调整参数

**现在应该不会出现多段音频了！** 🎉
