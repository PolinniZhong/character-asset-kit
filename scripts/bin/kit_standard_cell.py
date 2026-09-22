#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型 raw 图 → 标准格（白底接触阴影版 + 透明版）。

流程：subjectmask 抠图 → 按统一身高/足底基线放进标准格 → 双底输出。
用法：
  python3 kit_standard_cell.py --char /path/to/library/CHAR-01-demo \
      --in  99_过程稿/raw_A1挥手.jpg \
      --white 06_动作姿态/单图/CHAR-01_动作-A1挥手_v1.0_白.png \
      --transparent 06_动作姿态/单图/CHAR-01_动作-A1挥手_v1.0_透明.png \
      [--cell 1773x2364] [--fig-ratio 0.80] [--sole-ratio 0.88]
      [--scale-factor 1.0]   # 坐姿等非站姿给 0.58 左右
      [--no-shadow] [--already-cutout]
道具单体方格（细节/道具，完整不裁顶）：--square --no-shadow
  方格边长默认取标准格长边 2364；需要 2048 显式 --cell 2048x2048。
Vision 抠图失败（深色道具 no subject found）：先用 kit_colorkey_cutout.py 色键兜底，再传 --already-cutout。
"""
import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from charkit.assets import cutout, load, standard_cell, bust_cell, square_cell  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--white", required=True)
    ap.add_argument("--transparent", required=True)
    ap.add_argument("--cell", default="1773x2364")
    ap.add_argument("--fig-ratio", type=float, default=0.80)
    ap.add_argument("--sole-ratio", type=float, default=0.88)
    ap.add_argument("--scale-factor", type=float, default=1.0)
    ap.add_argument("--no-shadow", action="store_true")
    ap.add_argument("--bust", action="store_true", help="头肩胸像落格（表情板）：高度归一、顶部3.5%%边距、无阴影")
    ap.add_argument("--square", action="store_true", help="细节/道具方格：边长取标准格长边（默认2364），双向居中、占格86%%、无阴影")
    ap.add_argument("--already-cutout", action="store_true", help="输入已是透明抠图")
    args = ap.parse_args()

    char_dir = os.path.abspath(os.path.expanduser(args.char))
    src = args.src if os.path.isabs(args.src) else os.path.join(char_dir, args.src)
    cw, ch = (int(x) for x in args.cell.split("x"))

    if args.already_cutout:
        cut_path = src
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
        try:
            cut_path = cutout(src, tmp, char_dir=char_dir)
        except RuntimeError as e:
            print(f"[cutout] {e}", file=sys.stderr)
            sys.exit(2)

    cut_im = load(cut_path)
    if args.square:
        white, transparent = square_cell(cut_im, cell=max(cw, ch))
    elif args.bust:
        white, transparent = bust_cell(cut_im, cell_w=cw, cell_h=ch)
    else:
        white, transparent = standard_cell(
            cut_im, cell_w=cw, cell_h=ch, fig_ratio=args.fig_ratio,
            sole_ratio=args.sole_ratio, scale_factor=args.scale_factor,
            shadow=not args.no_shadow)

    for rel, im in [(args.white, white), (args.transparent, transparent)]:
        out = rel if os.path.isabs(rel) else os.path.join(char_dir, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im.save(out, "PNG")
        print("saved", out)


if __name__ == "__main__":
    main()
