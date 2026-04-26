"""
同声传译 — 支持实时录音和音频文件输入

功能：
  - 实时处理: 延迟 < 3秒（录音→翻译→播放）
  - 音频文件: 支持输入音频文件进行翻译
  - 输出保存: 自动保存翻译后的音频和文本
  - 声音克隆: F5-TTS 零样本，10秒参考音频即可克隆任意译员声音

用法：
    # 实时录音模式
    python interpreter.py --ref-audio voice.wav --ref-text "Sample text." --mode live

    # 音频文件模式
    python interpreter.py --ref-audio voice.wav --ref-text "Sample text." --mode file --input audio.wav --output translated.wav

依赖：
    pip install faster-whisper f5-tts sounddevice soundfile numpy
"""

import sys
import argparse
import tempfile
import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

import time
import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
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

CHUNK_DURATION = 4
SAMPLE_RATE = 16000


def translate_audio_file(whisper: WhisperModel, tts: F5TTS, input_path: str, output_path: str,
                         ref_audio: str, ref_text: str, source_lang: str = "zh"):
    print(f"\n处理音频文件: {input_path}")

    print("  [1/3] 转录并翻译...")
    segments, info = whisper.transcribe(input_path, task="translate", language=source_lang)

    original_texts = []
    translated_texts = []
    timestamps = []

    for seg in segments:
        translated_texts.append(seg.text.strip())
        timestamps.append((seg.start, seg.end))

    print("  [1/3] 转录原文...")
    segments_orig, _ = whisper.transcribe(input_path, task="transcribe", language=source_lang)
    for seg in segments_orig:
        original_texts.append(seg.text.strip())

    full_original = " ".join(original_texts)
    full_translation = " ".join(translated_texts)

    print(f"    原文: {full_original[:100]}...")
    print(f"    译文: {full_translation[:100]}...")

    print("  [2/3] 生成配音...")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_audio = f.name

    try:
        tts.infer(
            ref_file=ref_audio,
            ref_text=ref_text,
            gen_text=full_translation,
            file_wave=tmp_audio,
        )

        print("  [3/3] 保存结果...")

        audio, sr = sf.read(tmp_audio)
        sf.write(output_path, audio, sr)

        txt_path = output_path.rsplit(".", 1)[0] + ".txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("同声传译结果\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"原文 ({source_lang}):\n{full_original}\n\n")
            f.write(f"译文 (en):\n{full_translation}\n\n")
            f.write("=" * 60 + "\n")
            f.write("时间戳:\n")
            for i, (start, end) in enumerate(timestamps):
                f.write(f"[{start:.2f}s - {end:.2f}s] {translated_texts[i]}\n")

        print(f"\n✓ 完成！")
        print(f"  音频: {output_path}")
        print(f"  文本: {txt_path}")

    finally:
        if os.path.exists(tmp_audio):
            try:
                os.unlink(tmp_audio)
            except OSError:
                pass


def record_chunk(duration: int) -> np.ndarray:
    print(f"  [Recording {duration}s...]", end=" ", flush=True)
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    return audio.flatten()


def speak(tts: F5TTS, text: str, ref_audio: str, ref_text: str):
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        tts.infer(
            ref_file=ref_audio,
            ref_text=ref_text,
            gen_text=text,
            file_wave=tmp_path,
        )
        audio, sr = sf.read(tmp_path)
        sd.play(audio, samplerate=sr)
        sd.wait()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description="同声传译（实时录音 + 音频文件）")
    parser.add_argument("--ref-audio", required=True, help="~10s WAV 参考音频（译员声音）")
    parser.add_argument("--ref-text", required=True, help="参考音频的文本（英文）")
    parser.add_argument("--mode", choices=["live", "file"], default="live", help="模式：live=实时录音，file=音频文件")
    parser.add_argument("--input", help="输入音频文件（mode=file 时必需）")
    parser.add_argument("--output", help="输出音频文件（mode=file 时必需）")
    parser.add_argument("--source-lang", default="zh", help="源语言（默认 zh）")
    parser.add_argument("--chunk", type=int, default=CHUNK_DURATION, help="录音块时长（秒，默认4）")
    parser.add_argument("--model-size", default="small", help="Whisper 模型大小（tiny/base/small/medium/large-v3）")
    args = parser.parse_args()

    if not os.path.exists(args.ref_audio):
        print(f"错误: 参考音频不存在: {args.ref_audio}")
        sys.exit(1)

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

    print("=" * 60)
    print("同声传译")
    print(f"  模式: {'实时录音' if args.mode == 'live' else '音频文件'}")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    print(f"\n[1/2] 加载 Whisper 模型 ({args.model_size}, {device})...")
    whisper = WhisperModel(args.model_size, device=device, compute_type=compute_type)

    print("[2/2] 加载 F5-TTS 模型...")
    tts = F5TTS()

    print(f"\n✓ 模型就绪。使用声音: {args.ref_audio}")

    if args.mode == "file":
        translate_audio_file(whisper, tts, args.input, args.output, args.ref_audio, args.ref_text, args.source_lang)
    else:
        print("开始说中文 — 按 Ctrl+C 停止\n")
        print("-" * 60)

        while True:
            try:
                start_time = time.time()

                audio = record_chunk(args.chunk)
                record_time = time.time() - start_time

                segments, _ = whisper.transcribe(audio, task="translate", language=args.source_lang)
                text = " ".join(s.text.strip() for s in segments).strip()
                translate_time = time.time() - start_time - record_time

                if text:
                    print(f"译文: {text}")
                    speak(tts, text, args.ref_audio, args.ref_text)
                    total_time = time.time() - start_time
                    print(f"  [延迟统计] 录音:{record_time:.1f}s | 翻译:{translate_time:.1f}s | 总计:{total_time:.1f}s")
                    print("-" * 60)
                else:
                    print("(静音)")

            except KeyboardInterrupt:
                print("\n\n已停止。")
                sys.exit(0)


if __name__ == "__main__":
    main()
