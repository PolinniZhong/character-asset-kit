#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯白底 raw 图 → 透明 PNG（色键兜底抠图）。

用途：macOS Vision（subjectmask）对深色小道具、面部微距等主体会确定性
返回 "no subject found" 或过度语义分割（把皮肤当背景剥掉）。本脚本只做
"从四边泛洪的近白背景"转透明，不碰被主体围住的白色区域（白板鞋、白 T），
是 subjectmask 失败时的确定性兜底，产出可直接喂给：
  kit_standard_cell.py --already-cutout ...

算法：从四条边所有像素出发，对"近白"像素做泛洪（PIL floodfill，thresh
控制容差），被染到的区域即背景 → alpha=0；再对 alpha 做 1px 收缩＋轻微
羽化，收掉白边。

用法：
  python3 kit_colorkey_cutout.py --in raw_道具.png --out cut_道具.png
      [--white 247] [--flood-thr 25] [--feather 1.0]

注意：仅适用于纯白/近白无缝背景；带场景、阴影或花纹背景的图不要用。
"""
import argparse
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageChops


def colorkey_cutout(src, dst, white_thr=247, flood_thr=25, feather=1.0):
    im = Image.open(src).convert("RGB")
    w, h = im.size

    # 近白种子图：四边所有近白点作为泛洪起点（用标记色在副本上染色）
    work = im.copy()
    MARK = (255, 0, 255)  # 品红标记，角色资产不含该纯色
    # 先把四边近白点全部染成标记色（直接判定，避免逐点 floodfill 漏连通）
    px = work.load()
    from collections import deque
    seen = bytearray(w * h)
    dq = deque()

    def is_white(rgb):
        return min(rgb) >= white_thr

    for x in range(w):
        for y in (0, h - 1):
            if is_white(im.getpixel((x, y))):
                i = y * w + x
                if not seen[i]:
                    seen[i] = 1
                    dq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if is_white(im.getpixel((x, y))):
                i = y * w + x
                if not seen[i]:
                    seen[i] = 1
                    dq.append((x, y))

    # 泛洪：相邻像素与白色的色差在 flood_thr 内即视为背景
    src_px = im.load()
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                i = ny * w + nx
                if not seen[i]:
                    r, g, b = src_px[nx, ny]
                    # 近白判定：三通道都高且彼此接近（去饱和的亮灰也算背景）
                    if min(r, g, b) >= white_thr - flood_thr and (max(r, g, b) - min(r, g, b)) <= 12:
                        seen[i] = 1
                        dq.append((nx, ny))

    mask = Image.new("L", (w, h), 255)  # 全不透明
    mp = mask.load()
    for i, v in enumerate(seen):
        if v:
            mp[i % w, i // w] = 0      # 背景 → 透明

    if feather > 0:
        # 收缩 1px 去白边，再高斯羽化
        mask = mask.filter(ImageFilter.MinFilter(3))
        mask = mask.filter(ImageFilter.GaussianBlur(feather))

    out = im.convert("RGBA")
    out.putalpha(mask)
    out.save(dst, "PNG")

    # 简单自检：透明比例过低可能是背景没识别到
    total = w * h
    bg_ratio = sum(seen) / total
    return bg_ratio


def main():
    ap = argparse.ArgumentParser(description="纯白底色键兜底抠图（subjectmask 失败时使用）")
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--white", type=int, default=247, help="近白阈值，三通道最小值（默认247）")
    ap.add_argument("--flood-thr", type=int, default=25, help="泛洪容差（默认25）")
    ap.add_argument("--feather", type=float, default=1.0, help="边缘羽化像素（默认1.0，0 关闭）")
    args = ap.parse_args()

    ratio = colorkey_cutout(args.src, args.out, args.white, args.flood_thr, args.feather)
    print(f"saved {args.out}（背景占比 {ratio:.1%}）")
    if ratio < 0.05:
        print("[warn] 背景占比过低，可能未识别到白底背景；请检查输入是否为纯白底图。",
              file=sys.stderr)


if __name__ == "__main__":
    main()
