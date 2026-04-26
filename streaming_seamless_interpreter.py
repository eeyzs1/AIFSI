"""
基于 SeamlessM4T 的增量式流式同声传译

与 seamless_interpreter.py（整句翻译）的区别：
  - 增量式：将音频流分成小段（如 3 秒），每段独立翻译并立即输出
  - 更低延迟：不等整句话说完就开始翻译，每段延迟约 3-5 秒
  - 持续输出：翻译结果持续输出，不是等整句结束后才输出

注意：
  这是基于 SeamlessM4T v2 的增量式方案，不是 Meta 官方的 SeamlessStreaming（EMMA 机制）。
  SeamlessStreaming 依赖 fairseq2，目前仅支持 Linux/macOS，不支持 Windows。
  本方案通过短分段 + 增量翻译来模拟流式效果，适合 Windows 用户。

真正的流式同传方案（仅 Linux/macOS）：
  - Meta SeamlessStreaming: https://github.com/facebookresearch/seamless_communication
  - StreamSpeech: https://github.com/ictnlp/StreamSpeech

用法：
    # 实时流式同传（中文→英文，每3秒翻译一次）
    python streaming_seamless_interpreter.py --src-lang zh --tgt-lang eng

    # 调整分段时长（更短=更低延迟但可能断句不准）
    python streaming_seamless_interpreter.py --src-lang zh --tgt-lang eng --chunk-duration 2

依赖：
    pip install transformers torch sounddevice soundfile numpy webrtcvad sentencepiece protobuf
"""

import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['HF_HUB_DISABLE_XET'] = '1'

import sys
import argparse
import time
import queue
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
RMS_THRESHOLD = 0.01
MIN_SPEECH_DURATION = 1.0

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
}


def resolve_lang(lang: str) -> str:
    lang_lower = lang.lower().strip()
    if lang_lower in LANG_MAP:
        return LANG_MAP[lang_lower]
    return lang_lower


def compute_rms(audio: np.ndarray) -> float:
    return np.sqrt(np.mean(audio ** 2))


class StreamingSeamlessInterpreter:

    def __init__(self, src_lang: str, tgt_lang: str, speaker_id: int = 0, chunk_duration: float = 3.0):
        self.src_lang = resolve_lang(src_lang)
        self.tgt_lang = resolve_lang(tgt_lang)
        self.speaker_id = speaker_id
        self.chunk_duration = chunk_duration
        self.chunk_samples = int(chunk_duration * SAMPLE_RATE)

        print("初始化 SeamlessM4T v2 模型（增量式流式模式）...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        model_name = "facebook/seamless-m4t-v2-large"
        print(f"  [1/3] 加载处理器 ({model_name})...")
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

        print("  初始化 VAD...")
        self.vad = webrtcvad.Vad(VAD_MODE)

        self._lock = threading.Lock()
        self._is_playing = False
        self._audio_buffer = []
        self._audio_duration = 0.0
        self._is_speaking = False
        self._speech_frames = 0
        self._silence_start = None

        self.translate_queue = queue.Queue()
        self.total_latency = []
        self._chunk_count = 0

        print(f"✓ 模型就绪  源语言: {self.src_lang}  目标语言: {self.tgt_lang}")
        print(f"  分段时长: {self.chunk_duration}s  每段采样: {self.chunk_samples}\n")

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
                self._speech_frames = 0
                self._audio_buffer = []
                self._audio_duration = 0.0
            self._is_playing = value

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            return

        if self.is_playing:
            return

        sample = indata[:, 0]
        rms = compute_rms(sample)

        audio_int16 = (sample * 32767).astype(np.int16)
        is_speech = self.vad.is_speech(audio_int16.tobytes(), SAMPLE_RATE)

        with self._lock:
            if rms >= RMS_THRESHOLD and is_speech:
                self._speech_frames += 1
                self._audio_buffer.append(sample.copy())
                self._audio_duration += len(sample) / SAMPLE_RATE
                self._silence_start = None

                if not self._is_speaking:
                    self._is_speaking = True
                    print("[说话中]", end=" ", flush=True)

                if self._audio_duration >= self.chunk_duration:
                    self._flush_chunk()
            else:
                if self._is_speaking:
                    if self._silence_start is None:
                        self._silence_start = time.time()
                    elif time.time() - self._silence_start > 1.5:
                        if self._audio_duration >= MIN_SPEECH_DURATION:
                            self._flush_chunk(final=True)
                        else:
                            self._audio_buffer = []
                            self._audio_duration = 0.0
                        self._is_speaking = False
                        self._silence_start = None
                        self._speech_frames = 0

    def _flush_chunk(self, final: bool = False):
        if not self._audio_buffer:
            return

        audio = np.concatenate(self._audio_buffer)
        self._audio_buffer = []
        self._audio_duration = 0.0

        duration = len(audio) / SAMPLE_RATE
        if duration < 0.5:
            return

        rms = compute_rms(audio)
        if rms < RMS_THRESHOLD * 2:
            return

        self._chunk_count += 1
        tag = "末段" if final else f"段{self._chunk_count}"
        self.translate_queue.put((audio, time.time(), tag))

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
                audio, start_time, tag = self.translate_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                duration = len(audio) / SAMPLE_RATE
                print(f"\n[{tag} {duration:.1f}s 翻译中...]", end=" ", flush=True)

                audio_inputs = self.processor(
                    audio=audio,
                    sampling_rate=SAMPLE_RATE,
                    return_tensors="pt",
                ).to(self.device)

                source_text = self._s2tt(audio_inputs, self.src_lang)
                translated_text = self._s2tt(audio_inputs, self.tgt_lang)

                print()
                if source_text:
                    print(f"  [原文] {source_text}")
                if translated_text:
                    print(f"  [译文] {translated_text}")

                if not translated_text:
                    print("  [无译文，跳过]")
                    continue

                print("  [合成语音...]", end=" ", flush=True)
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
                    print("[完成]")

                    latency = time.time() - start_time
                    self.total_latency.append(latency)
                    print(f"  [延迟] {latency:.2f}s")
                else:
                    print("[无音频]")

            except Exception as e:
                print(f"\n翻译错误: {e}")
                self.is_playing = False

            self.translate_queue.task_done()

    def run(self):
        print("=" * 60)
        print("SeamlessM4T 增量式流式同声传译")
        print(f"  源语言: {self.src_lang}")
        print(f"  目标语言: {self.tgt_lang}")
        print(f"  分段时长: {self.chunk_duration}s")
        print("  模式: 持续输入→分段翻译→持续输出")
        print("  提示: 正常说话即可，每段自动翻译输出")
        print("=" * 60)
        print("\n开始说话 — 按 Ctrl+C 停止\n")

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

            try:
                self.translate_queue.join()
            except Exception:
                pass

            if self.total_latency:
                avg = sum(self.total_latency) / len(self.total_latency)
                print(f"\n统计: {len(self.total_latency)}段  平均延迟: {avg:.2f}s")

            print("已停止。")
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="SeamlessM4T 增量式流式同声传译",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
支持的语言: zh(中文) en(英文) ja(日文) ko(韩文) fr(法文) de(德文) es(西班牙文) ru(俄文)

真正的流式同传（仅 Linux/macOS）:
  Meta SeamlessStreaming: https://github.com/facebookresearch/seamless_communication
  StreamSpeech: https://github.com/ictnlp/StreamSpeech
        """,
    )
    parser.add_argument("--src-lang", default="zh", help="源语言（默认 zh）")
    parser.add_argument("--tgt-lang", default="eng", help="目标语言（默认 eng）")
    parser.add_argument("--speaker-id", type=int, default=0, help="说话人 ID（0-199）")
    parser.add_argument("--chunk-duration", type=float, default=3.0, help="分段时长秒数（默认 3.0，越小延迟越低但断句可能不准）")
    args = parser.parse_args()

    interpreter = StreamingSeamlessInterpreter(
        args.src_lang, args.tgt_lang, args.speaker_id, args.chunk_duration
    )
    interpreter.run()


if __name__ == "__main__":
    main()
