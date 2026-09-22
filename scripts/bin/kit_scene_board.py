#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""场景包总览板（G12）：扫描 12_场景包/单图/ 下的 SCN 竖/横成图，
两行排版（上＝竖版 3:4 主图，下＝横版 16:9 头图），标签在排版层、
使用 macOS 平方（PingFang SC）无衬线字体；深色底以衬托场景图。
用法：python3 kit_scene_board.py --char <角色目录名> [--version v1.0]
"""
import argparse, os, re, sys, glob, json
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from charkit.fonts import f as _font, font_name  # 统一无衬线中文字体（苹方/冬青黑体）


def resolve_char(arg, root):
    """--char 可以是包路径，也可以是 --root 下的包目录名。"""
    p = os.path.abspath(os.path.expanduser(arg))
    if os.path.isdir(p):
        return p
    p = os.path.join(os.path.abspath(os.path.expanduser(root)), arg)
    if os.path.isdir(p):
        return p
    sys.exit(f"找不到角色包：{arg}")


def code_of(cdir, fallback):
    try:
        with open(os.path.join(cdir, "资产清单.json"), encoding="utf-8") as fp:
            code = json.load(fp).get("code")
            if code:
                return code
    except (OSError, json.JSONDecodeError):
        pass
    return "-".join(fallback.split("-")[:2]) or fallback.upper()

BG = (10, 17, 38, 255)        # 深藏青底
TITLE = (255, 255, 255, 255)
SUB = (176, 199, 245, 255)
LABEL = (228, 237, 255, 255)
ROWKEY = (79, 157, 255, 255)  # 电光蓝
CARD_PAD = 14
HEXES = [("藏青", "#0E1A3A", (14, 26, 58)), ("电光蓝", "#4F9DFF", (79, 157, 255)),
         ("柔光蓝", "#BFD4FF", (191, 212, 255)), ("白", "#FFFFFF", (255, 255, 255))]


def font(size, bold=False):
    return _font(size, bold=bold)


def text_w(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--root", default=os.getcwd(), help="库根（--char 为目录名时使用，默认当前目录）")
    ap.add_argument("--version", default="v1.0")
    args = ap.parse_args()
    cdir = resolve_char(args.char, args.root)
    sdir = os.path.join(cdir, "12_场景包", "单图")
    if not os.path.isdir(sdir):
        sys.exit(f"找不到场景单图目录：{sdir}")
    code = code_of(cdir, os.path.basename(cdir))

    rows = {}  # scene id -> {'name':..., 'v':path, 'h':path}
    pat = re.compile(r"SCN-(\d+)_(.+?)_(竖3x4|横16x9)\.png$")
    for p in sorted(glob.glob(os.path.join(sdir, "*.png"))):
        m = pat.search(os.path.basename(p))
        if not m:
            continue
        sid, name, fmt = f"SCN-{m.group(1)}", m.group(2), m.group(3)
        rows.setdefault(sid, {"name": name})["v" if fmt.startswith("竖") else "h"] = p
    if not rows:
        sys.exit("未匹配到 SCN 成图")
    scenes = [(sid, rows[sid]) for sid in sorted(rows)]

    # 版式参数
    M = 90                 # 页边距
    GAP = 44               # 格间距
    CELL_W = 720
    V_H = round(CELL_W * 4 / 3)    # 竖格高 960
    H_H = round(CELL_W * 9 / 16)   # 横格高 405
    HEAD_H = 150
    ROWKEY_H = 64
    LABEL_H = 66
    HEX_H = 96
    n = len(scenes)
    W = 2 * M + n * CELL_W + (n - 1) * GAP
    H = HEAD_H + ROWKEY_H + V_H + LABEL_H + 110 + H_H + LABEL_H + 70 + HEX_H
    board = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(board)

    f_title = font(58, True)
    f_sub = font(30)
    f_key = font(30, True)
    f_lab = font(30)
    f_hex = font(24)

    d.text((M, 56), "角色场景包总览", font=f_title, fill=TITLE)
    meta = f"{args.version} · {n} 个场景 × 竖 3:4 主图 / 横 16:9 头图 · 整幅成图（不抠图）"
    d.text((W - M - text_w(d, meta, f_sub), 78), meta, font=f_sub, fill=SUB)

    def paste_cell(path, x, y, w, h):
        im = Image.open(path).convert("RGB")
        im = im.resize((w, h), Image.LANCZOS).convert("RGBA")
        # 卡片：电光蓝极细描边
        card = Image.new("RGBA", (w + 2 * CARD_PAD, h + 2 * CARD_PAD), (16, 28, 62, 255))
        cd = ImageDraw.Draw(card)
        cd.rectangle([0, 0, card.size[0] - 1, card.size[1] - 1], outline=(79, 157, 255, 120), width=2)
        card.alpha_composite(im, (CARD_PAD, CARD_PAD))
        board.alpha_composite(card, (x - CARD_PAD, y - CARD_PAD))
        return y + h + 2 * CARD_PAD

    x0 = M
    # 第一行：竖版
    yk = HEAD_H
    d.rectangle([M, yk + 18, M + 10, yk + 46], fill=ROWKEY)
    d.text((M + 24, yk + 14), "竖版 3:4 主图", font=f_key, fill=ROWKEY)
    y = yk + ROWKEY_H
    for i, (sid, info) in enumerate(scenes):
        x = x0 + i * (CELL_W + GAP)
        yb = paste_cell(info.get("v"), x, y, CELL_W, V_H)
        lab = f"{sid} {info['name']}"
        d.text((x + CELL_W / 2 - text_w(d, lab, f_lab) / 2, yb + 12), lab, font=f_lab, fill=LABEL)
    # 第二行：横版
    yk2 = y + V_H + LABEL_H + 70
    d.rectangle([M, yk2 + 18, M + 10, yk2 + 46], fill=ROWKEY)
    d.text((M + 24, yk2 + 14), "横版 16:9 头图（负空间留给后期标题）", font=f_key, fill=ROWKEY)
    y2 = yk2 + ROWKEY_H
    for i, (sid, info) in enumerate(scenes):
        x = x0 + i * (CELL_W + GAP)
        yb = paste_cell(info.get("h"), x, y2, CELL_W, H_H)
        lab = f"{sid} {info['name']}"
        d.text((x + CELL_W / 2 - text_w(d, lab, f_lab) / 2, yb + 12), lab, font=f_lab, fill=LABEL)

    # HEX 条
    yh = H - HEX_H + 20
    d.text((M, yh), "配色锁定 HEX", font=f_hex, fill=SUB)
    x = M + 220
    for name, hx, rgb in HEXES:
        d.rounded_rectangle([x, yh - 4, x + 44, yh + 36], radius=6, fill=rgb,
                            outline=(255, 255, 255, 90), width=1)
        d.text((x + 56, yh), f"{name} {hx}", font=f_hex, fill=LABEL)
        x += 300

    outdir = os.path.join(cdir, "12_场景包", "拼板")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{code}_场景包总览_{args.version}.png")
    board.convert("RGB").save(out, quality=95)
    print("saved", out, board.size)


if __name__ == "__main__":
    main()
