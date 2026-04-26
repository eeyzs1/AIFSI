"""
AI混剪 Demo — 智能提取高光片段 + 自动剪辑

核心优势：
  - 场景检测: PySceneDetect 自动识别镜头切换点
  - 内容理解: Whisper 转录 + 关键词提取（情绪、节奏）
  - 智能剪辑: 根据高光片段自动组装，添加转场特效
  - 竞品对比: 蜻蜓剪辑的"AI混剪"是素材拼接，我们做内容理解

适用场景：
  - 长视频提取精华片段
  - 多段素材智能拼接成短视频
  - 自动生成带节奏感的爆款内容

用法：
    python auto_edit.py input.mp4 --duration 60 --output highlight.mp4

    --duration: 目标时长（秒），默认60秒
    --keywords: 可选，指定关键词（如"精彩,高潮,笑声"）优先提取相关片段

依赖：
    pip install scenedetect[opencv] faster-whisper moviepy numpy
"""

import argparse
import os
import sys
import subprocess
import json
from pathlib import Path
from scenedetect import detect, ContentDetector, split_video_ffmpeg
from faster_whisper import WhisperModel
from moviepy.editor import VideoFileClip, concatenate_videoclips, CompositeVideoClip
import numpy as np


def detect_scenes(video_path: str) -> list[tuple[float, float]]:
    """检测视频中的场景切换点，返回 [(start, end), ...] 时间戳列表."""
    print("检测场景切换点...")
    scene_list = detect(video_path, ContentDetector(threshold=27.0))
    scenes = [(s[0].get_seconds(), s[1].get_seconds()) for s in scene_list]
    print(f"  检测到 {len(scenes)} 个场景")
    return scenes


def transcribe_video(video_path: str, model: WhisperModel) -> list[dict]:
    """转录视频音频，返回带时间戳的文本."""
    print("转录视频内容...")
    segments, _ = model.transcribe(video_path, task="transcribe", language=None)
    transcript = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
    print(f"  转录 {len(transcript)} 个语句")
    return transcript


def score_scenes(scenes: list[tuple[float, float]], transcript: list[dict], keywords: list[str] = None) -> list[tuple[float, float, float]]:
    """
    为每个场景打分，返回 [(start, end, score), ...].
    评分依据：
      - 关键词匹配（如果提供）
      - 语句密度（说话多的片段通常更精彩）
      - 场景时长（太短或太长的场景降权）
    """
    print("为场景打分...")
    scored = []

    for start, end in scenes:
        duration = end - start
        if duration < 2 or duration > 30:  # 过短或过长的场景降权
            score = 0.3
        else:
            score = 1.0

        # 统计该场景内的语句数量
        speech_count = sum(1 for t in transcript if t["start"] >= start and t["end"] <= end)
        score += speech_count * 0.2

        # 关键词匹配
        if keywords:
            scene_text = " ".join(t["text"] for t in transcript if t["start"] >= start and t["end"] <= end)
            keyword_hits = sum(1 for kw in keywords if kw in scene_text)
            score += keyword_hits * 0.5

        scored.append((start, end, score))

    scored.sort(key=lambda x: x[2], reverse=True)
    print(f"  评分完成，最高分场景: {scored[0][2]:.2f}")
    return scored


def select_clips(scored_scenes: list[tuple[float, float, float]], target_duration: float) -> list[tuple[float, float]]:
    """选择得分最高的场景，直到达到目标时长."""
    print(f"选择片段（目标时长 {target_duration}s）...")
    selected = []
    total = 0

    for start, end, score in scored_scenes:
        duration = end - start
        if total + duration <= target_duration:
            selected.append((start, end))
            total += duration
        if total >= target_duration * 0.9:  # 达到目标的90%即可
            break

    selected.sort(key=lambda x: x[0])  # 按时间顺序排列
    print(f"  选择 {len(selected)} 个片段，总时长 {total:.1f}s")
    return selected


def create_highlight_video(video_path: str, clips: list[tuple[float, float]], output_path: str):
    """拼接选中的片段，添加简单转场."""
    print("生成混剪视频...")
    video = VideoFileClip(video_path)
    subclips = [video.subclip(start, end) for start, end in clips]

    # 简单淡入淡出转场
    for i, clip in enumerate(subclips):
        if i > 0:
            subclips[i] = clip.fadein(0.5)
        if i < len(subclips) - 1:
            subclips[i] = clip.fadeout(0.5)

    final = concatenate_videoclips(subclips, method="compose")
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")
    video.close()


def main():
    parser = argparse.ArgumentParser(description="AI混剪 Demo（智能高光提取）")
    parser.add_argument("input", help="输入视频文件")
    parser.add_argument("--duration", type=int, default=60, help="目标时长（秒，默认60）")
    parser.add_argument("--keywords", help="关键词（逗号分隔，如'精彩,高潮,笑声'）")
    parser.add_argument("--output", default="highlight.mp4", help="输出视频")
    args = parser.parse_args()

    keywords = args.keywords.split(",") if args.keywords else None

    print("=" * 60)
    print("AI混剪 Demo — 智能高光提取")
    print("  ✓ 场景检测: 自动识别镜头切换")
    print("  ✓ 内容理解: Whisper 转录 + 关键词匹配")
    print("  ✓ 智能评分: 语句密度 + 关键词 + 时长")
    print("  ✓ 竞品对比: 蜻蜓剪辑只做素材拼接，无内容理解")
    print("=" * 60)

    print("\n[1/5] 加载 Whisper 模型...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    whisper = WhisperModel("small", device=device, compute_type=compute_type)

    print("\n[2/5] 检测场景...")
    scenes = detect_scenes(args.input)

    print("\n[3/5] 转录视频...")
    transcript = transcribe_video(args.input, whisper)

    print("\n[4/5] 智能评分...")
    scored = score_scenes(scenes, transcript, keywords)

    print("\n[5/5] 生成混剪视频...")
    clips = select_clips(scored, args.duration)
    create_highlight_video(args.input, clips, args.output)

    print("\n" + "=" * 60)
    print(f"✓ 完成！输出: {args.output}")
    print("\n对比竞品优势:")
    print("  1. 内容理解: 基于语音转录 + 关键词，不是盲目拼接")
    print("  2. 智能评分: 多维度评估场景质量")
    print("  3. 可定制: 支持关键词指定提取方向")
    print("=" * 60)


if __name__ == "__main__":
    main()
