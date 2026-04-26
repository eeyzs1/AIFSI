"""
实时流式同声传译

核心需求：
  - 持续输入：对着麦克风说话，程序持续接收音频流
  - 持续输出：实时翻译并播放，延迟越小越好
  - 流式处理：不是"录一段→翻译一段"，而是边说边翻译
  - 应用场景：直播卖货、跨境电商、国际会议

技术方案：
  - VAD（语音活动检测）：检测说话开始/结束
  - 流式 ASR：Whisper 流式转录
  - 增量翻译：检测到句子结束立即翻译
  - 流式 TTS：F5-TTS 快速合成
  - 并行处理：录音、转录、翻译、播放并行

延迟优化：
  - 目标延迟：< 2秒（从说话结束到播放开始）
  - VAD 延迟：< 100ms
  - ASR 延迟：< 500ms
  - TTS 延迟：< 1秒

用法：
    python streaming_interpreter.py --ref-audio voice.wav --ref-text "Sample text."

依赖：
    pip install faster-whisper f5-tts sounddevice soundfile numpy webrtcvad
"""

import sys
import argparse
import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

import time
import queue
import tempfile
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
import webrtcvad
from faster_whisper import WhisperModel


def _patched_torchaudio_load(filepath, *args, **kwargs):
    frame_offset = kwargs.get('frame_offset', 0)
    num_frames = kwargs.get('num_frames', -1)
    audio, sr = sf.read(filepath, start=frame_offset, frames=num_frames if num_frames > 0 else -1)
    if len(audio.shape) == 1:
        audio = audio.reshape(1, -1)
    else:
        audio = audio.T
    return torch.from_numpy(audio.astype(np.float32)), sr


try:
    import torchaudio
    if not hasattr(torchaudio, '_original_load_patched'):
        torchaudio._original_load = torchaudio.load
        torchaudio.load = _patched_torchaudio_load
        torchaudio._original_load_patched = True
except ImportError:
    pass

try:
    from f5_tts.api import F5TTS
except ImportError:
    print("错误: 请安装 f5-tts")
    print("  pip install f5-tts")
    sys.exit(1)

SAMPLE_RATE = 16000
CHUNK_SIZE = 480
VAD_MODE = 2
SILENCE_THRESHOLD = 1.0
MIN_SPEECH_DURATION = 0.5


class StreamingInterpreter:

    def __init__(self, ref_audio: str, ref_text: str, model_size: str = "small", source_lang: str = "zh"):
        self.ref_audio = ref_audio
        self.ref_text = ref_text
        self.source_lang = source_lang

        print("初始化模型...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"

        print(f"  [1/3] 加载 Whisper ({model_size}, {device})...")
        self.whisper = WhisperModel(model_size, device=device, compute_type=compute_type)

        print("  [2/3] 加载 F5-TTS...")
        self.tts = F5TTS()

        print("  [3/3] 初始化 VAD...")
        self.vad = webrtcvad.Vad(VAD_MODE)

        self._lock = threading.Lock()
        self._is_playing = False
        self._is_speaking = False
        self._silence_start = None
        self._silence_frames = 0
        self._speech_frames = 0
        self._audio_buffer = []

        self.transcribe_queue = queue.Queue()
        self.tts_queue = queue.Queue()

        self.total_latency = []

        print("✓ 模型就绪\n")

    @property
    def is_playing(self):
        with self._lock:
            return self._is_playing

    @is_playing.setter
    def is_playing(self, value):
        with self._lock:
            if value and not self._is_playing:
                self._is_speaking = False
                self._silence_start = None
                self._silence_frames = 0
                self._speech_frames = 0
                self._audio_buffer = []
            self._is_playing = value

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"音频输入错误: {status}")

        if self.is_playing:
            return

        audio_int16 = (indata[:, 0] * 32767).astype(np.int16)
        is_speech = self.vad.is_speech(audio_int16.tobytes(), SAMPLE_RATE)

        with self._lock:
            if is_speech:
                self._speech_frames += 1
                self._silence_frames = 0

                if not self._is_speaking:
                    if self._speech_frames >= 3:
                        self._is_speaking = True
                        print("[检测到说话]", end=" ", flush=True)

                if self._is_speaking:
                    self._audio_buffer.append(indata[:, 0].copy())
                    self._silence_start = None
            else:
                self._silence_frames += 1
                self._speech_frames = 0

                if self._is_speaking:
                    if self._silence_start is None:
                        self._silence_start = time.time()
                    elif time.time() - self._silence_start > SILENCE_THRESHOLD:
                        print("[说话结束]")
                        self._flush_speech()
                        self._is_speaking = False
                        self._silence_start = None
                        self._silence_frames = 0
                        self._speech_frames = 0

    def _flush_speech(self):
        if not self._audio_buffer:
            return

        audio = np.concatenate(self._audio_buffer)
        self._audio_buffer = []

        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_SPEECH_DURATION:
            return

        self.transcribe_queue.put((audio, time.time()))

    def transcribe_worker(self):
        while True:
            try:
                audio, start_time = self.transcribe_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                segments, _ = self.whisper.transcribe(audio, task="translate", language=self.source_lang)
                text = " ".join(s.text.strip() for s in segments).strip()

                if text:
                    print(f"\n[英文] {text}")
                    self.tts_queue.put((text, start_time))
                else:
                    print("[无有效内容]")
            except Exception as e:
                print(f"转录错误: {e}")

            self.transcribe_queue.task_done()

    def tts_worker(self):
        while True:
            try:
                text, start_time = self.tts_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp_path = f.name

                self.tts.infer(
                    ref_file=self.ref_audio,
                    ref_text=self.ref_text,
                    gen_text=text,
                    file_wave=tmp_path,
                )

                audio, sr = sf.read(tmp_path)

                self.is_playing = True
                print("[播放中...]", end=" ", flush=True)

                sd.play(audio, samplerate=sr)
                sd.wait()

                self.is_playing = False
                print("[播放完成]")

                latency = time.time() - start_time
                self.total_latency.append(latency)
                print(f"  [延迟] {latency:.2f}s")
                print("-" * 60)

            except Exception as e:
                print(f"TTS 错误: {e}")
                self.is_playing = False
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

            self.tts_queue.task_done()

    def run(self):
        print("=" * 60)
        print("实时流式同声传译")
        print("  模式: 边说边翻译（持续输入输出）")
        print("  目标延迟: < 2秒")
        print("=" * 60)
        print("\n开始说话 — 按 Ctrl+C 停止\n")
        print("-" * 60)

        transcribe_thread = threading.Thread(target=self.transcribe_worker, daemon=True)
        tts_thread = threading.Thread(target=self.tts_worker, daemon=True)
        transcribe_thread.start()
        tts_thread.start()

        stream = None
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='float32',
                blocksize=CHUNK_SIZE,
                callback=self.audio_callback
            )
            stream.start()

            while True:
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\n停止中...")

            if stream:
                stream.stop()
                stream.close()

            print("  等待处理完成...")
            try:
                self.transcribe_queue.join()
                self.tts_queue.join()
            except Exception:
                pass

            if self.total_latency:
                avg_latency = sum(self.total_latency) / len(self.total_latency)
                min_latency = min(self.total_latency)
                max_latency = max(self.total_latency)

                print("\n" + "=" * 60)
                print("性能统计")
                print("=" * 60)
                print(f"  处理次数: {len(self.total_latency)}")
                print(f"  平均延迟: {avg_latency:.2f}s")
                print(f"  最小延迟: {min_latency:.2f}s")
                print(f"  最大延迟: {max_latency:.2f}s")
                print("=" * 60)

            print("\n已停止。")
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="实时流式同声传译")
    parser.add_argument("--ref-audio", required=True, help="参考音频（译员声音，~10s WAV）")
    parser.add_argument("--ref-text", required=True, help="参考音频的文本（英文）")
    parser.add_argument("--model-size", default="small", help="Whisper 模型大小（tiny/base/small/medium/large-v3）")
    parser.add_argument("--source-lang", default="zh", help="源语言（默认 zh）")
    args = parser.parse_args()

    if not os.path.exists(args.ref_audio):
        print(f"错误: 参考音频不存在: {args.ref_audio}")
        sys.exit(1)

    interpreter = StreamingInterpreter(args.ref_audio, args.ref_text, args.model_size, args.source_lang)
    interpreter.run()


if __name__ == "__main__":
    main()
