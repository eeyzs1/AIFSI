#!/usr/bin/env python3
"""
StreamSpeech 实时流式同声传译脚本 (WSL)

用法:
    # 麦克风实时翻译 (英文→德文)
    conda activate streamspeech
    python wsl_streamspeech_live.py --mic --src-lang en --tgt-lang de

    # 音频文件翻译
    python wsl_streamspeech_live.py --input audio.wav --src-lang en --tgt-lang de

    # 指定策略
    python wsl_streamspeech_live.py --mic --src-lang en --tgt-lang de --strategy wait_k --wait-k 5
"""

import argparse
import os
import sys
import subprocess
import tempfile
import shutil
import time
import threading
import queue
import numpy as np
import soundfile as sf

try:
    import sounddevice as sd
except ImportError:
    sd = None
    print("[WARN] sounddevice 未安装，麦克风模式不可用")

try:
    import webrtcvad
except ImportError:
    webrtcvad = None
    print("[WARN] webrtcvad 未安装，将使用简单能量检测代替 VAD")

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION_MS = 30
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)

HF_MIRROR = "https://hf-mirror.com"

LANG_MAP = {
    "en": "en", "de": "de", "zh": "zh", "ja": "ja",
    "es": "es", "fr": "fr", "ko": "ko", "it": "it",
    "pt": "pt", "ru": "ru", "nl": "nl", "pl": "pl",
    "ar": "ar", "tr": "tr",
}

TASK_CONFIG_MAP = {
    "asr": "streamspeech_asr",
    "st": "streamspeech_st",
    "s2st": "streamspeech_s2st",
}

STRATEGY_HELP = {
    "wait_if_worse": "当前假设变差时等待更多输入 (推荐, 质量高)",
    "wait_k": "等待 K 个源语音块后开始翻译 (可调延迟)",
    "fixed_stride": "固定步长策略 (低延迟, 中等质量)",
}


def find_streamspeech_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "wsl_workspace", "StreamSpeech"),
        os.path.join(script_dir, "..", "StreamSpeech"),
        os.path.expanduser("~/wsl_workspace/StreamSpeech"),
    ]
    for c in candidates:
        if os.path.isdir(c) and os.path.isfile(os.path.join(c, "setup.py")):
            return os.path.abspath(c)
    result = subprocess.run(
        ["python", "-c", "import streamspeech; print(streamspeech.__file__)"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return os.path.dirname(os.path.dirname(result.stdout.strip()))
    return None


def find_model_ckpt(task, model_dir):
    task_dir = os.path.join(model_dir, f"streamspeech_{task}")
    if os.path.isdir(task_dir):
        ckpt = os.path.join(task_dir, "checkpoint_best.pt")
        if os.path.isfile(ckpt):
            return ckpt
    for root, dirs, files in os.walk(model_dir):
        for f in files:
            if f.endswith(".pt") and task in root:
                return os.path.join(root, f)
    return None


def prepare_data_dir(wav_path, data_dir):
    os.makedirs(data_dir, exist_ok=True)
    audio, sr = sf.read(wav_path)
    if sr != SAMPLE_RATE:
        print(f"  重采样: {sr}Hz -> {SAMPLE_RATE}Hz")
        import scipy.signal as signal
        audio = signal.resample_poly(audio, SAMPLE_RATE, sr)
    if len(audio.shape) > 1:
        audio = audio[:, 0]
    audio = audio.astype(np.float32)
    norm_path = os.path.join(data_dir, "audio.wav")
    sf.write(norm_path, audio, SAMPLE_RATE)
    n_frames = len(audio)
    tsv_path = os.path.join(data_dir, "audio.tsv")
    with open(tsv_path, "w") as f:
        f.write("audio\n")
        f.write(f"audio.wav\t{n_frames}\n")
    tgt_path = os.path.join(data_dir, "audio.de")
    with open(tgt_path, "w") as f:
        f.write("\n")
    return norm_path


def run_streamspeech_validate(ss_root, config_name, data_dir, ckpt_path, strategy, wait_k, results_path, fp16=True):
    cmd = [
        sys.executable, os.path.join(ss_root, "examples", "simultaneous_translation", "validate.py"),
        "--config-dir", os.path.join(ss_root, "examples", "simultaneous_translation", "conf"),
        "--config-name", config_name,
        f"task.data={data_dir}",
        f"common_eval.path={ckpt_path}",
        f"decoding.strategy={strategy}",
        f"common_eval.results_path={results_path}",
    ]
    if strategy == "wait_k" and wait_k is not None:
        cmd.append(f"decoding.wait_k={wait_k}")
    if fp16:
        cmd.append("common.fp16=true")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ss_root}:{env.get('PYTHONPATH', '')}"
    print(f"  执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ss_root)
    return result


def translate_file(args):
    ss_root = find_streamspeech_root()
    if ss_root is None:
        print("[ERROR] 找不到 StreamSpeech 仓库，请确认已运行 wsl_setup.sh")
        sys.exit(1)
    print(f"[INFO] StreamSpeech 根目录: {ss_root}")

    model_dir = args.model_dir
    if not model_dir:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_dir = os.path.join(script_dir, "wsl_workspace", "models", "StreamSpeech")
    if not os.path.isdir(model_dir):
        print(f"[ERROR] 模型目录不存在: {model_dir}")
        print("  请先运行 wsl_setup.sh 下载模型，或用 --model-dir 指定路径")
        sys.exit(1)

    config_name = TASK_CONFIG_MAP.get(args.task)
    if config_name is None:
        print(f"[ERROR] 不支持的任务: {args.task} (可选: asr, st, s2st)")
        sys.exit(1)

    ckpt_path = find_model_ckpt(args.task, model_dir)
    if ckpt_path is None:
        print(f"[ERROR] 找不到 {args.task} 的模型检查点")
        print(f"  模型目录: {model_dir}")
        print("  期望结构: models/StreamSpeech/streamspeech_{task}/checkpoint_best.pt")
        sys.exit(1)
    print(f"[INFO] 模型检查点: {ckpt_path}")

    input_path = args.input
    if not os.path.isfile(input_path):
        print(f"[ERROR] 输入文件不存在: {input_path}")
        sys.exit(1)

    tmp_dir = tempfile.mkdtemp(prefix="streamspeech_")
    results_path = tempfile.mkdtemp(prefix="streamspeech_results_")

    try:
        print(f"[INFO] 准备数据...")
        prepare_data_dir(input_path, tmp_dir)
        print(f"[INFO] 运行 StreamSpeech ({args.task}, 策略: {args.strategy})...")
        result = run_streamspeech_validate(
            ss_root, config_name, tmp_dir, ckpt_path,
            args.strategy, args.wait_k, results_path, args.fp16
        )
        if result.stdout:
            print(result.stdout)
        if result.returncode != 0:
            print(f"[ERROR] 推理失败 (返回码: {result.returncode})")
            if result.stderr:
                print(result.stderr)
        else:
            print(f"\n[INFO] 翻译完成！结果保存在: {results_path}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def translate_mic(args):
    if sd is None:
        print("[ERROR] sounddevice 未安装，无法使用麦克风模式")
        print("  安装: pip install sounddevice")
        print("  系统依赖: sudo apt install libportaudio2 portaudio19-dev")
        sys.exit(1)

    ss_root = find_streamspeech_root()
    if ss_root is None:
        print("[ERROR] 找不到 StreamSpeech 仓库，请确认已运行 wsl_setup.sh")
        sys.exit(1)

    model_dir = args.model_dir
    if not model_dir:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_dir = os.path.join(script_dir, "wsl_workspace", "models", "StreamSpeech")
    if not os.path.isdir(model_dir):
        print(f"[ERROR] 模型目录不存在: {model_dir}")
        sys.exit(1)

    config_name = TASK_CONFIG_MAP.get(args.task)
    ckpt_path = find_model_ckpt(args.task, model_dir)
    if ckpt_path is None:
        print(f"[ERROR] 找不到 {args.task} 的模型检查点")
        sys.exit(1)

    print(f"[INFO] StreamSpeech 实时同传")
    print(f"  任务: {args.task}")
    print(f"  源语言: {args.src_lang} → 目标语言: {args.tgt_lang}")
    print(f"  策略: {args.strategy}")
    print(f"  模型: {ckpt_path}")
    print()

    vad = webrtcvad.Vad(2) if webrtcvad else None
    audio_buffer = []
    is_speaking = False
    silence_start = None
    audio_duration = 0.0
    chunk_queue = queue.Queue()
    MIN_SPEECH_DURATION = 1.0
    SILENCE_THRESHOLD = 1.5
    RMS_THRESHOLD = 0.02
    lock = threading.Lock()
    segment_count = 0

    def compute_rms(samples):
        return float(np.sqrt(np.mean(samples ** 2)))

    def audio_callback(indata, frames, time_info, status):
        nonlocal audio_buffer, is_speaking, silence_start, audio_duration, segment_count
        if status:
            return
        sample = indata[:, 0]
        rms = compute_rms(sample)

        if vad:
            audio_int16 = (sample * 32767).astype(np.int16)
            is_speech = vad.is_speech(audio_int16.tobytes(), SAMPLE_RATE)
        else:
            is_speech = rms >= RMS_THRESHOLD

        with lock:
            if is_speech:
                audio_buffer.append(sample.copy())
                audio_duration += len(sample) / SAMPLE_RATE
                silence_start = None
                if not is_speaking:
                    is_speaking = True
                    print("[说话中]", end=" ", flush=True)
            else:
                if is_speaking:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > SILENCE_THRESHOLD:
                        if audio_duration >= MIN_SPEECH_DURATION:
                            segment_count += 1
                            audio_data = np.concatenate(audio_buffer)
                            chunk_queue.put((segment_count, audio_data))
                            print(f"[段{segment_count}: {audio_duration:.1f}s]", end=" ", flush=True)
                        audio_buffer = []
                        audio_duration = 0.0
                        is_speaking = False
                        silence_start = None

    def translate_worker():
        while True:
            try:
                seg_num, audio_data = chunk_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            tmp_dir = tempfile.mkdtemp(prefix="streamspeech_mic_")
            results_path = tempfile.mkdtemp(prefix="streamspeech_results_")
            wav_path = os.path.join(tmp_dir, "audio.wav")
            try:
                sf.write(wav_path, audio_data, SAMPLE_RATE)
                prepare_data_dir(wav_path, tmp_dir)
                print(f"\n[翻译段{seg_num}...]", end=" ", flush=True)
                result = run_streamspeech_validate(
                    ss_root, config_name, tmp_dir, ckpt_path,
                    args.strategy, args.wait_k, results_path, args.fp16
                )
                if result.returncode == 0:
                    for root, dirs, files in os.walk(results_path):
                        for f in files:
                            if f.endswith(".txt") or f.endswith(".hyp"):
                                fpath = os.path.join(root, f)
                                with open(fpath, "r") as fh:
                                    text = fh.read().strip()
                                if text:
                                    print(f"\n[段{seg_num} 译文]: {text}")
                else:
                    print(f"\n[段{seg_num} 翻译失败]")
                    if result.stderr:
                        for line in result.stderr.split("\n")[-5:]:
                            if line.strip():
                                print(f"  {line}")
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                shutil.rmtree(results_path, ignore_errors=True)

    worker = threading.Thread(target=translate_worker, daemon=True)
    worker.start()

    print("[INFO] 开始录音，请说话... (按 Ctrl+C 停止)")
    print()
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS,
            dtype="float32", blocksize=CHUNK_SIZE,
            callback=audio_callback
        ):
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n[INFO] 停止录音")
        with lock:
            if audio_buffer and audio_duration >= MIN_SPEECH_DURATION:
                audio_data = np.concatenate(audio_buffer)
                chunk_queue.put(("final", audio_data))
        print("[INFO] 等待最后一段翻译完成...")
        time.sleep(5)
        print("[INFO] 已停止")


def main():
    parser = argparse.ArgumentParser(
        description="StreamSpeech 实时流式同声传译 (WSL)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 麦克风实时英文→德文语音翻译
  python wsl_streamspeech_live.py --mic --src-lang en --tgt-lang de

  # 麦克风实时英文→中文语音翻译
  python wsl_streamspeech_live.py --mic --src-lang en --tgt-lang zh --task st

  # 音频文件翻译
  python wsl_streamspeech_live.py --input audio.wav --src-lang en --tgt-lang de

  # 使用 wait_k 策略 (K=5)
  python wsl_streamspeech_live.py --mic --strategy wait_k --wait-k 5 --src-lang en --tgt-lang de

注意:
  - StreamSpeech 官方主要支持英文作为源语言 (En→De/Zh/Ja/Es 等)
  - 中文作为源语言的模型需要自行训练
  - 麦克风模式需要 PortAudio: sudo apt install libportaudio2 portaudio19-dev
        """
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--mic", action="store_true", help="使用麦克风实时输入")
    input_group.add_argument("--input", type=str, help="输入音频文件路径 (WAV 16kHz)")

    parser.add_argument("--task", type=str, default="st", choices=["asr", "st", "s2st"],
                        help="任务类型: asr(语音识别), st(语音翻译), s2st(语音→语音翻译) (默认: st)")
    parser.add_argument("--src-lang", type=str, default="en",
                        help="源语言代码 (默认: en, StreamSpeech 主要支持英文源)")
    parser.add_argument("--tgt-lang", type=str, default="de",
                        help="目标语言代码 (默认: de)")
    parser.add_argument("--strategy", type=str, default="wait_if_worse",
                        choices=["wait_if_worse", "wait_k", "fixed_stride"],
                        help="同步策略 (默认: wait_if_worse)")
    parser.add_argument("--wait-k", type=int, default=None,
                        help="wait_k 策略的 K 值 (默认: 自动)")
    parser.add_argument("--model-dir", type=str, default=None,
                        help="模型目录路径 (默认: wsl_workspace/models/StreamSpeech)")
    parser.add_argument("--no-fp16", action="store_true", help="不使用 FP16 半精度")
    parser.add_argument("--no-mirror", action="store_true", help="不使用国内镜像")

    args = parser.parse_args()
    args.fp16 = not args.no_fp16

    if not args.no_mirror:
        os.environ["HF_ENDPOINT"] = HF_MIRROR
        os.environ["HF_HUB_DISABLE_XET"] = "1"

    if args.mic:
        translate_mic(args)
    else:
        translate_file(args)


if __name__ == "__main__":
    main()
