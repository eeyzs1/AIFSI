"""
基于 SeamlessM4T 的端到端同声传译

与现有方案（Whisper + F5-TTS 级联）的核心区别：
  - 端到端：一个模型完成语音→语音翻译，无需 STT→翻译→TTS 的级联
  - 无需参考音频：内置多说话人声码器，不需要提供参考音频
  - 翻译质量更高：联合训练的模型避免了级联误差累积
  - 支持 101 种语言输入，96 种语言输出

技术方案：
  - VAD（语音活动检测）：检测说话开始/结束
  - RMS 音量阈值：过滤环境噪声，避免误触发
  - SeamlessM4T v2 S2TT：语音→文本翻译（输出原文和译文文字）
  - SeamlessM4T v2 S2ST：语音→语音翻译（输出译文语音）
  - 并行处理：录音、翻译、播放并行

用法：
    # 实时流式同传（中文→英文）
    python seamless_interpreter.py --src-lang zh --tgt-lang eng

    # 指定其他语言
    python seamless_interpreter.py --src-lang zh --tgt-lang jpn

    # 音频文件翻译
    python seamless_interpreter.py --src-lang zh --tgt-lang eng --mode file --input audio.wav --output translated.wav

依赖：
    pip install transformers torch sounddevice soundfile numpy webrtcvad sentencepiece protobuf

模型下载：
    首次运行会自动从 HuggingFace 下载模型（约 9GB）
    国内用户自动使用 hf-mirror.com 镜像加速
    如果下载超时，可手动下载：
      1. pip install -U huggingface_hub
      2. PowerShell: $env:HF_ENDPOINT="https://hf-mirror.com"; $env:HF_HUB_DISABLE_XET="1"
      3. hf download facebook/seamless-m4t-v2-large
      4. 下载完成后再运行本脚本
"""

import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HUB_DISABLE_XET'] = '1'

import sys
import argparse
import subprocess
import time
import queue
import traceback
import tempfile
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
import webrtcvad

try:
    from transformers import AutoProcessor, SeamlessM4Tv2ForSpeechToText, SeamlessM4Tv2ForSpeechToSpeech
except ImportError:
    print("错误: 请安装 transformers")
    print("  pip install transformers sentencepiece protobuf")
    sys.exit(1)

SAMPLE_RATE = 16000
CHUNK_SIZE = 480
VAD_MODE = 1
SILENCE_THRESHOLD = 1.5
MIN_SPEECH_DURATION = 0.8
RMS_THRESHOLD = 0.01
MAX_AUDIO_DURATION = 20.0

LANG_MAP = {
    "zh": "cmn", "chinese": "cmn", "中文": "cmn",
    "en": "eng", "english": "eng", "英文": "eng",
    "ja": "jpn", "japanese": "jpn", "日文": "jpn",
    "ko": "kor", "korean": "kor", "韩文": "kor",
    "fr": "fra", "french": "fra",
    "de": "deu", "german": "deu",
    "es": "spa", "spanish": "spa",
    "ru": "rus", "russian": "rus",
    "pt": "por", "portuguese": "por",
    "it": "ita", "italian": "ita",
    "ar": "ara", "arabic": "ara",
    "hi": "hin", "hindi": "hin",
    "th": "tha", "thai": "tha",
    "vi": "vie", "vietnamese": "vie",
    "id": "ind", "indonesian": "ind",
    "ms": "zsm", "malay": "zsm",
    "uk": "ukr", "ukrainian": "ukr",
    "nl": "nld", "dutch": "nld",
    "pl": "pol", "polish": "pol",
    "tr": "tur", "turkish": "tur",
    "sv": "swe", "swedish": "swe",
}


def resolve_lang(lang: str) -> str:
    lang_lower = lang.lower().strip()
    if lang_lower in LANG_MAP:
        return LANG_MAP[lang_lower]
    return lang_lower


def compute_rms(audio: np.ndarray) -> float:
    return np.sqrt(np.mean(audio ** 2))


class SeamlessInterpreter:

    def __init__(self, src_lang: str, tgt_lang: str, speaker_id: int = 0):
        self.src_lang = resolve_lang(src_lang)
        self.tgt_lang = resolve_lang(tgt_lang)
        self.speaker_id = speaker_id

        print("初始化 SeamlessM4T v2 模型...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        model_name = "facebook/seamless-m4t-v2-large"
        print(f"  [1/3] 加载处理器 ({model_name})...")
        print(f"  提示: 首次运行会下载模型（约9GB），国内自动使用 hf-mirror.com 加速")
        print(f"  如果下载超时，请手动运行: hf download {model_name}")
        self.processor = AutoProcessor.from_pretrained(model_name)

        print(f"  [2/3] 加载 S2TT 模型（语音→文本）({device})...")
        self.s2tt_model = SeamlessM4Tv2ForSpeechToText.from_pretrained(
            model_name,
            torch_dtype=dtype,
        ).to(device)

        print(f"  [3/3] 加载 S2ST 模型（语音→语音）({device})...")
        self.s2st_model = SeamlessM4Tv2ForSpeechToSpeech.from_pretrained(
            model_name,
            torch_dtype=dtype,
        ).to(device)
        self.device = device

        print("  [4/4] 初始化 VAD...")
        self.vad = webrtcvad.Vad(VAD_MODE)

        self._lock = threading.Lock()
        self._is_playing = False
        self._is_speaking = False
        self._silence_start = None
        self._silence_frames = 0
        self._speech_frames = 0
        self._audio_buffer = []
        self._audio_duration = 0.0

        self.translate_queue = queue.Queue()
        self.total_latency = []

        print(f"✓ 模型就绪  源语言: {self.src_lang}  目标语言: {self.tgt_lang}\n")

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
                self._audio_duration = 0.0
            self._is_playing = value

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"音频输入错误: {status}")

        if self.is_playing:
            return

        sample = indata[:, 0]
        rms = compute_rms(sample)

        if rms < RMS_THRESHOLD:
            with self._lock:
                if self._is_speaking:
                    self._silence_frames += 1
                    self._speech_frames = 0
                    if self._silence_start is None:
                        self._silence_start = time.time()
                    elif time.time() - self._silence_start > SILENCE_THRESHOLD:
                        print("[说话结束]")
                        self._flush_speech()
                        self._is_speaking = False
                        self._silence_start = None
                        self._silence_frames = 0
                        self._speech_frames = 0
            return

        audio_int16 = (sample * 32767).astype(np.int16)
        is_speech = self.vad.is_speech(audio_int16.tobytes(), SAMPLE_RATE)

        if not is_speech:
            return

        with self._lock:
            self._speech_frames += 1
            self._silence_frames = 0

            if not self._is_speaking:
                if self._speech_frames >= 3:
                    self._is_speaking = True
                    self._audio_duration = 0.0
                    print("[检测到说话]", end=" ", flush=True)

            if self._is_speaking:
                self._audio_buffer.append(sample.copy())
                self._audio_duration += len(sample) / SAMPLE_RATE
                self._silence_start = None

                if self._audio_duration >= MAX_AUDIO_DURATION:
                    print(f"[达到最大时长{MAX_AUDIO_DURATION:.0f}s，截断]")
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
        self._audio_duration = 0.0

        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_SPEECH_DURATION:
            return

        rms = compute_rms(audio)
        if rms < RMS_THRESHOLD * 2:
            return

        self.translate_queue.put((audio, time.time()))

    def _s2tt(self, audio_inputs, tgt_lang: str) -> str:
        with torch.no_grad():
            output = self.s2tt_model.generate(
                **audio_inputs,
                tgt_lang=tgt_lang,
            )
        if hasattr(output, 'sequences'):
            tokens = output.sequences[0].tolist()
        else:
            tokens = output[0].tolist()
            if isinstance(tokens[0], list):
                tokens = tokens[0]
        return self.processor.decode(tokens, skip_special_tokens=True).strip()

    def translate_worker(self):
        while True:
            try:
                audio, start_time = self.translate_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                duration = len(audio) / SAMPLE_RATE
                print(f"[翻译中... 音频{duration:.1f}s]")

                audio_inputs = self.processor(
                    audio=audio,
                    sampling_rate=SAMPLE_RATE,
                    return_tensors="pt",
                ).to(self.device)

                source_text = self._s2tt(audio_inputs, self.src_lang)
                translated_text = self._s2tt(audio_inputs, self.tgt_lang)

                if source_text:
                    print(f"  [原文] ({self.src_lang}) {source_text}")
                if translated_text:
                    print(f"  [译文] ({self.tgt_lang}) {translated_text}")

                if not translated_text:
                    print("  [无译文，跳过语音合成]")
                    print("-" * 60)
                    continue

                print("  [合成语音中...]", end=" ", flush=True)
                with torch.no_grad():
                    s2st_output = self.s2st_model.generate(
                        **audio_inputs,
                        tgt_lang=self.tgt_lang,
                        speaker_id=self.speaker_id,
                    )

                waveform = s2st_output[0].cpu().float().numpy().squeeze()
                sample_rate = self.s2st_model.config.sampling_rate

                if waveform is not None and len(waveform) > 0:
                    if waveform.dtype != np.float32:
                        waveform = waveform.astype(np.float32)
                    self.is_playing = True
                    print("[播放中...]", end=" ", flush=True)

                    sd.play(waveform, samplerate=sample_rate)
                    sd.wait()

                    self.is_playing = False
                    print("[播放完成]")

                    latency = time.time() - start_time
                    self.total_latency.append(latency)
                    print(f"  [延迟] {latency:.2f}s")
                    print("-" * 60)
                else:
                    print("[无有效音频输出]")
                    print("-" * 60)

            except Exception as e:
                print(f"\n翻译错误: {e}")
                traceback.print_exc()
                self.is_playing = False

            self.translate_queue.task_done()

    def translate_file(self, input_path: str, output_path: str):
        print(f"\n处理音频文件: {input_path}")

        audio, sr = sf.read(input_path)
        if sr != SAMPLE_RATE:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(tmp_fd)
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", input_path, "-ar", str(SAMPLE_RATE), "-ac", "1", tmp_path],
                    check=True, capture_output=True,
                )
                audio, sr = sf.read(tmp_path)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)

        print("  [1/3] 识别原文...")
        audio_inputs = self.processor(
            audio=audio.astype(np.float32),
            sampling_rate=SAMPLE_RATE,
            return_tensors="pt",
        ).to(self.device)

        source_text = self._s2tt(audio_inputs, self.src_lang)

        print("  [2/3] 翻译...")
        translated_text = self._s2tt(audio_inputs, self.tgt_lang)

        print("  [3/3] 合成语音...")
        with torch.no_grad():
            output = self.s2st_model.generate(
                **audio_inputs,
                tgt_lang=self.tgt_lang,
                speaker_id=self.speaker_id,
            )

        waveform = output[0].cpu().float().numpy().squeeze()
        sample_rate = self.s2st_model.config.sampling_rate

        if waveform is None or len(waveform) == 0:
            print("  [无有效音频输出]")
            return

        if waveform.dtype != np.float32:
            waveform = waveform.astype(np.float32)

        sf.write(output_path, waveform, sample_rate)

        txt_path = output_path.rsplit(".", 1)[0] + ".txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("SeamlessM4T 同声传译结果\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"源语言: {self.src_lang}\n")
            f.write(f"目标语言: {self.tgt_lang}\n\n")
            if source_text:
                f.write(f"原文:\n{source_text}\n\n")
            if translated_text:
                f.write(f"译文:\n{translated_text}\n\n")
            f.write("=" * 60 + "\n")

        print(f"\n✓ 完成！")
        print(f"  音频: {output_path}")
        print(f"  文本: {txt_path}")
        if source_text:
            print(f"  原文: {source_text[:100]}...")
        if translated_text:
            print(f"  译文: {translated_text[:100]}...")

    def run(self):
        print("=" * 60)
        print("SeamlessM4T 端到端同声传译")
        print(f"  源语言: {self.src_lang}")
        print(f"  目标语言: {self.tgt_lang}")
        print("  模式: 边说边翻译（持续输入输出）")
        print("  特点: 端到端模型，无需参考音频")
        print("  提示: 说完一句话后停顿1.5秒以上")
        print("=" * 60)
        print("\n开始说话 — 按 Ctrl+C 停止\n")
        print("-" * 60)

        translate_thread = threading.Thread(target=self.translate_worker, daemon=True)
        translate_thread.start()

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
                self.translate_queue.join()
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
    parser = argparse.ArgumentParser(
        description="SeamlessM4T 端到端同声传译（无需参考音频）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
支持的语言代码示例:
  zh / cmn  — 中文      en / eng  — 英文      ja / jpn  — 日文
  ko / kor  — 韩文      fr / fra  — 法文      de / deu  — 德文
  es / spa  — 西班牙文  ru / rus  — 俄文      ar / ara  — 阿拉伯文

完整语言列表: https://huggingface.co/facebook/seamless-m4t-v2-large
        """,
    )
    parser.add_argument("--src-lang", default="zh", help="源语言代码（默认 zh）")
    parser.add_argument("--tgt-lang", default="eng", help="目标语言代码（默认 eng）")
    parser.add_argument("--speaker-id", type=int, default=0, help="说话人 ID（默认 0，范围 0-199）")
    parser.add_argument("--mode", choices=["live", "file"], default="live", help="模式：live=实时录音，file=音频文件")
    parser.add_argument("--input", help="输入音频文件（mode=file 时必需）")
    parser.add_argument("--output", help="输出音频文件（mode=file 时必需）")
    args = parser.parse_args()

    if args.mode == "file":
        if not args.input:
            print("错误: file 模式需要 --input 参数")
            sys.exit(1)
        if not args.output:
            print("错误: file 模式需要 --output 参数")
            sys.exit(1)
        if not os.path.exists(args.input):
            print(f"错误: 输入文件不存在: {args.input}")
            sys.exit(1)

    interpreter = SeamlessInterpreter(args.src_lang, args.tgt_lang, args.speaker_id)

    if args.mode == "file":
        interpreter.translate_file(args.input, args.output)
    else:
        interpreter.run()


if __name__ == "__main__":
    main()
