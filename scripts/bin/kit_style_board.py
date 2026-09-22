#!/usr/bin/env python3
# -*- coding: utf-8
"""风格变体五视图板（G13）：扫描 09_风格变体/<插槽>/ 下的风格母版与单图，
一行五视图（正面取风格母版，其余取 单图/），标签在排版层、
使用 charkit.fonts 统一无衬线中文字体；深色底衬托白底黏土图。
用法：python3 kit_style_board.py --char <角色目录名> [--slot S2-黏土] [--version v1.0]
"""
import argparse, os, re, sys, glob, json
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from charkit.fonts import f as _font  # noqa: E402

BG = (10, 17, 38, 255)
TITLE = (255, 255, 255, 255)
SUB = (176, 199, 245, 255)
LABEL = (228, 237, 255, 255)
CARD_PAD = 14
VIEWS = ["正面", "前四分之三", "正侧", "后四分之三", "背面"]


def font(size, bold=False):
    return _font(size, bold=bold)


def text_w(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0]


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


def slot_tag(slot):
    # S2-黏土 → S2黏土
    return slot.replace("-", "", 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--root", default=os.getcwd(), help="库根（--char 为目录名时使用，默认当前目录）")
    ap.add_argument("--slot", default="S2-黏土")
    ap.add_argument("--version", default="v1.0")
    args = ap.parse_args()

    cdir = resolve_char(args.char, args.root)
    sdir = os.path.join(cdir, "09_风格变体", args.slot)
    if not os.path.isdir(sdir):
        sys.exit(f"找不到风格插槽目录：{sdir}")
    code = code_of(cdir, os.path.basename(cdir))
    tag = slot_tag(args.slot)

    masters = sorted(glob.glob(os.path.join(sdir, "风格母版", "*.png")))
    singles = {os.path.basename(p): p for p in glob.glob(os.path.join(sdir, "单图", "*.png"))}

    cells = []
    for view in VIEWS:
        if view == "正面":
            if masters:
                cells.append((view, masters[-1]))
                continue
            hit = [v for k, v in singles.items() if f"_{view}_" in k]
        else:
            hit = [v for k, v in singles.items() if f"_{view}_" in k]
        if not hit:
            sys.exit(f"缺少视角单图：{view}（在 {sdir}/单图/）")
        cells.append((view, sorted(hit)[-1]))

    M, GAP, HEAD_H, LABEL_H = 90, 44, 170, 66
    CELL_W = 560
    CELL_H = round(CELL_W * 4 / 3)
    n = len(cells)
    W = 2 * M + n * CELL_W + (n - 1) * GAP
    H = HEAD_H + CELL_H + LABEL_H + 90
    board = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(board)
    f_title, f_sub, f_lab = font(56, True), font(28), font(30)

    slot_name = args.slot.split("-", 1)[1] if "-" in args.slot else args.slot
    title = f"{code} · {slot_name}风格 · 五视图 {args.version}"
    d.text((M, 52), title, font=f_title, fill=TITLE)
    d.text((M, 124), "正面为风格母版；标签位于排版层，资产本体零文字", font=f_sub, fill=SUB)

    y0 = HEAD_H
    for i, (view, path) in enumerate(cells):
        x0 = M + i * (CELL_W + GAP)
        im = Image.open(path).convert("RGBA")
        th = CELL_H - 2 * CARD_PAD
        tw = CELL_W - 2 * CARD_PAD
        scale = min(tw / im.width, th / im.height)
        nw, nh = round(im.width * scale), round(im.height * scale)
        im = im.resize((nw, nh), Image.LANCZOS)
        card = Image.new("RGBA", (CELL_W, CELL_H), (255, 255, 255, 255))
        card.alpha_composite(im, ((CELL_W - nw) // 2, (CELL_H - nh) // 2))
        board.alpha_composite(card, (x0, y0))
        d.rectangle([x0, y0, x0 + CELL_W - 1, y0 + CELL_H - 1],
                    outline=(79, 157, 255, 180), width=2)
        lab = view
        d.text((x0 + (CELL_W - text_w(d, lab, f_lab)) // 2, y0 + CELL_H + 16),
               lab, font=f_lab, fill=LABEL)

    outdir = os.path.join(sdir, "拼板")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{code}_{tag}_五视图_{args.version}_干净版.png")
    board.convert("RGB").save(out, quality=95)
    print("saved", out)


if __name__ == "__main__":
    main()
