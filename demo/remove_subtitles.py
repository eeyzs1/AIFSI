"""
智能去字幕 Demo — 基于 OpenCV Inpainting（可运行版本）

输入：带硬字幕的视频
输出：去除字幕后的干净视频

技术说明：
  - 当前实现: OpenCV Inpainting (Telea/NS算法)
  - 优势: 开箱即用，无需额外模型下载
  - 劣势: 大面积修复效果一般
  - 未来升级: LAMA Inpainting (SOTA) — 修复质量更好

用法：
    python remove_subtitles.py input.mp4 --output clean.mp4

    可选参数：
      --subtitle-region: 手动指定字幕区域（格式: x,y,w,h，如 "0,800,1920,280"）
      --method: 修复算法（telea 或 ns，默认 telea）

依赖：
    pip install opencv-python numpy easyocr

注意：
    - 字幕区域越小，修复效果越好
    - 建议手动指定字幕区域以提高速度
    - 复杂背景可能有轻微痕迹

竞品对比：
    - 蜻蜓剪辑的"智能去字幕"可能也用类似算法
    - 我们的优势：可快速升级到 LAMA（代码架构已预留）
"""

import argparse
import os
import sys
import cv2
import numpy as np
import tempfile
import subprocess
import torch
from pathlib import Path


def check_dependencies():
    """检查依赖."""
    try:
        import easyocr
    except ImportError:
        print("⚠ 警告: easyocr 未安装，将使用默认字幕区域（底部20%）")
        print("  安装 easyocr 可自动检测字幕位置: pip install easyocr")
        return False
    return True


def detect_subtitle_region_simple(frame: np.ndarray) -> tuple:
    """简单方法：假设字幕在底部 15%."""
    h, w = frame.shape[:2]
    return 0, int(h * 0.85), w, int(h * 0.15)


def detect_subtitle_region_ocr(frame: np.ndarray, reader=None) -> tuple:
    """使用 OCR 自动检测字幕区域."""
    try:
        import easyocr
        if reader is None:
            use_gpu = torch.cuda.is_available()
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=use_gpu)

        h, w = frame.shape[:2]
        bottom_region = frame[int(h * 0.7):, :]

        results = reader.readtext(bottom_region)
        if not results:
            return detect_subtitle_region_simple(frame), reader

        boxes = [r[0] for r in results]
        all_points = np.array([pt for box in boxes for pt in box])
        x_min, y_min = all_points.min(axis=0).astype(int)
        x_max, y_max = all_points.max(axis=0).astype(int)

        padding = 20
        x = max(0, x_min - padding)
        y = max(0, y_min - padding + int(h * 0.7))
        width = min(w - x, x_max - x_min + 2 * padding)
        height = min(h - y, y_max - y_min + 2 * padding)

        return (x, y, width, height), reader
    except Exception as e:
        print(f"  OCR检测失败: {e}，使用默认区域")
        return detect_subtitle_region_simple(frame), reader


def inpaint_frame(frame: np.ndarray, mask: np.ndarray, method: str = "telea") -> np.ndarray:
    """使用 OpenCV inpainting 修复帧."""
    if method == "telea":
        return cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
    else:
        return cv2.inpaint(frame, mask, 3, cv2.INPAINT_NS)


def process_video(video_path: str, output_path: str, subtitle_region: tuple = None, method: str = "telea", use_ocr: bool = True):
    """处理整个视频，去除字幕."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    temp_video_fd, temp_video = tempfile.mkstemp(suffix=".mp4")
    os.close(temp_video_fd)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

    print(f"处理视频: {total_frames} 帧，{fps} FPS")

    ret, first_frame = cap.read()
    ocr_reader = None
    if subtitle_region is None:
        print("检测字幕区域...")
        if use_ocr:
            subtitle_region, ocr_reader = detect_subtitle_region_ocr(first_frame)
        else:
            subtitle_region = detect_subtitle_region_simple(first_frame)

    x, y, w, h = subtitle_region
    print(f"  字幕区域: x={x}, y={y}, w={w}, h={h}")

    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y:y+h, x:x+w] = 255

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        inpainted = inpaint_frame(frame, mask, method)
        out.write(inpainted)

        frame_count += 1
        if frame_count % 30 == 0:
            print(f"  处理进度: {frame_count}/{total_frames} ({frame_count/total_frames*100:.1f}%)")

    cap.release()
    out.release()

    print("合并音频...")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", temp_video, "-i", video_path,
            "-c:v", "libx264", "-map", "0:v", "-map", "1:a",
            "-shortest", output_path
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("  ⚠ 音频合并失败，输出无音频视频")
        os.rename(temp_video, output_path)
        return

    os.unlink(temp_video)


def main():
    parser = argparse.ArgumentParser(description="智能去字幕 Demo (OpenCV Inpainting)")
    parser.add_argument("input", help="输入视频文件")
    parser.add_argument("--output", default="clean.mp4", help="输出视频")
    parser.add_argument("--subtitle-region", help="手动指定字幕区域（格式: x,y,w,h）")
    parser.add_argument("--method", choices=["telea", "ns"], default="telea", help="修复算法")
    parser.add_argument("--no-ocr", action="store_true", help="禁用OCR自动检测")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 输入视频不存在: {args.input}")
        sys.exit(1)

    subtitle_region = None
    if args.subtitle_region:
        subtitle_region = tuple(map(int, args.subtitle_region.split(",")))

    has_ocr = check_dependencies()
    use_ocr = has_ocr and not args.no_ocr

    print("=" * 60)
    print("智能去字幕 Demo")
    print("  当前实现: OpenCV Inpainting (可运行版本)")
    print("  未来升级: LAMA Inpainting (SOTA修复)")
    print(f"  修复算法: {args.method.upper()}")
    print(f"  自动检测: {'开启' if use_ocr else '关闭'}")
    print("=" * 60)

    print("\n处理中...")
    process_video(args.input, args.output, subtitle_region, args.method, use_ocr)

    print("\n" + "=" * 60)
    print(f"✓ 完成！输出: {args.output}")
    print("\n技术路线说明:")
    print("  当前: OpenCV Inpainting — 快速但大面积修复效果一般")
    print("  升级: LAMA Inpainting — 大面积修复无痕迹，纹理连续性好")
    print("\n对比竞品优势:")
    print("  1. 自动检测: OCR 自动识别字幕区域")
    print("  2. 架构可扩展: 预留 LAMA 升级接口")
    print("  3. 开源可控: 不依赖云端API")
    print("\n生产部署步骤:")
    print("  1. 当前版本已可用于简单场景")
    print("  2. 升级到 LAMA: git clone https://github.com/advimman/lama")
    print("  3. 替换 inpaint_frame 为 LAMA 推理")
    print("=" * 60)


if __name__ == "__main__":
    main()
