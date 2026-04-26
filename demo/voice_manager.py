"""
声音克隆管理 Demo
支持：注册新声音、列出已有声音、用指定声音合成

用法：
    # 注册新声音（只需10秒参考音频）
    python voice_manager.py register --name "张三" --audio zhang.wav --text "这是张三的声音样本。"

    # 列出所有已注册声音
    python voice_manager.py list

    # 用指定声音合成
    python voice_manager.py speak --name "张三" --text "Hello, this is a test." --output out.wav

依赖：
    pip install f5-tts soundfile
"""

import argparse
import json
import os
import soundfile as sf
from f5_tts.api import F5TTS

REGISTRY_PATH = "voices.json"


def load_registry() -> dict:
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {}


def save_registry(registry: dict):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def cmd_register(args):
    registry = load_registry()
    registry[args.name] = {"audio": os.path.abspath(args.audio), "text": args.text}
    save_registry(registry)
    print(f"Registered voice: {args.name}")


def cmd_list(args):
    registry = load_registry()
    if not registry:
        print("No voices registered.")
        return
    for name, info in registry.items():
        print(f"  {name}: {info['audio']}")


def cmd_speak(args):
    registry = load_registry()
    if args.name not in registry:
        print(f"Voice '{args.name}' not found. Run 'register' first.")
        return
    voice = registry[args.name]
    tts = F5TTS()
    tts.infer(
        ref_file=voice["audio"],
        ref_text=voice["text"],
        gen_text=args.text,
        file_wave=args.output,
    )
    print(f"Saved to: {args.output}")


def main():
    parser = argparse.ArgumentParser(description="Voice clone manager")
    sub = parser.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register")
    r.add_argument("--name", required=True)
    r.add_argument("--audio", required=True, help="~10s WAV reference audio")
    r.add_argument("--text", required=True, help="Transcript of reference audio")

    sub.add_parser("list")

    s = sub.add_parser("speak")
    s.add_argument("--name", required=True)
    s.add_argument("--text", required=True)
    s.add_argument("--output", default="output.wav")

    args = parser.parse_args()
    {"register": cmd_register, "list": cmd_list, "speak": cmd_speak}[args.cmd](args)


if __name__ == "__main__":
    main()
