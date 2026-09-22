# -*- coding: utf-8 -*-
"""资产图像处理：bbox 裁切、contain/cover 适配、接触阴影、标准格合成、抠图封装。

标准格口径（结构规范 v0.2）：
- 全身标准格 1773×2364；角色（含所持道具整体 bbox）高 0.80＝1891px；
  足底基线 sole_y = 2364×0.88 ≈ 2080；
- 白底版脚下仅极淡接触阴影 fill(30,42,75,22) 高斯模糊 14；透明版无阴影；
- 坐姿等非站姿 bbox 天然偏矮，需在 manifest 给 scale_factor（如端坐 0.58）。
注意：bbox 必须读透明 alpha；白底图直接逐像素判白会误判整幅（白板鞋/白 T）。
"""
import os
import subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CELL_W, CELL_H = 1773, 2364
FIG_H_RATIO = 0.80
SOLE_RATIO = 0.88

HERE = os.path.dirname(os.path.abspath(__file__))
BIN_SUBJECTMASK = os.path.join(HERE, "..", "bin", "subjectmask")


# ---------- 读取与 bbox ----------
def load(path, mode="RGBA"):
    return Image.open(path).convert(mode)


def bbox_alpha(im, alpha_thr=8):
    """读透明通道的内容 bbox；无 alpha 时回退判白。"""
    im = im.convert("RGBA")
    alpha = im.split()[3]
    bb = alpha.point(lambda a: 255 if a > alpha_thr else 0).getbbox()
    if bb:
        return bb
    return bbox_white(im)


def bbox_white(im, thr=247):
    """白底图内容 bbox（逐像素判非白，较慢；仅用于没有透明版的白底图）。"""
    px = im.convert("RGB").load()
    w, h = im.size
    x0 = y0 = w + 1
    x1 = y1 = -1
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if min(r, g, b) < thr:
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
                if y < y0:
                    y0 = y
                if y > y1:
                    y1 = y
    if x1 < 0:
        return (0, 0, w, h)
    return (x0, y0, x1 + 1, y1 + 1)


def trim(im, by="alpha", **kw):
    """按内容 bbox 裁切，返回新图。"""
    bb = bbox_alpha(im) if by == "alpha" else bbox_white(im, **kw)
    return im.crop(bb)


# ---------- 适配 ----------
def fit_contain(im, bw, bh, cover=False, crop=None):
    if crop:
        im = im.crop(crop)
    iw, ih = im.size
    s = (max(bw / iw, bh / ih) if cover else min(bw / iw, bh / ih))
    im = im.resize((round(iw * s), round(ih * s)), Image.LANCZOS)
    if cover:
        x0 = (im.size[0] - bw) // 2
        y0 = (im.size[1] - bh) // 2
        im = im.crop((x0, y0, x0 + bw, y0 + bh))
    return im


def fit_trim_white(path, bw, bh):
    """读白底图→先按白底内容 bbox 裁切→contain（解决整幅 contain 人物偏小）。"""
    im = load(path)
    x0, y0, x1, y1 = bbox_white(im)
    im = im.crop((x0, y0, x1, y1))
    return fit_contain(im, bw, bh)


def fit_trim_height(path, target_h):
    """读白底图→按内容 bbox 裁切→**按高度精确缩放**（忽略宽度）。

    全身视图/动作必须按高度归一，否则手臂张开的正面被宽度限缩、侧身被高度放大，
    导致五视角不等高、足底基线虽齐而头顶不齐。
    """
    im = load(path)
    x0, y0, x1, y1 = bbox_white(im)
    im = im.crop((x0, y0, x1, y1))
    iw, ih = im.size
    return im.resize((round(iw * target_h / ih), target_h), Image.LANCZOS)


# ---------- 抠图 ----------
def cutout(src_path, dst_path, char_dir=None):
    """调用 subjectmask 生成透明抠图。优先角色目录下的二进制，其次工具链 bin。"""
    candidates = []
    if char_dir:
        candidates.append(os.path.join(char_dir, "subjectmask"))
    candidates.append(os.path.normpath(BIN_SUBJECTMASK))
    binary = next((p for p in candidates if os.path.exists(p)), None)
    if binary is None:
        raise RuntimeError("找不到 subjectmask；新机需 `swiftc subjectmask.swift -o subjectmask`")
    os.makedirs(os.path.dirname(os.path.abspath(dst_path)), exist_ok=True)
    r = subprocess.run([binary, src_path, dst_path], capture_output=True, text=True)
    if not os.path.exists(dst_path) or os.path.getsize(dst_path) == 0:
        tip = ("（macOS Vision 对深色道具/面部微距可能确定性返回 no subject found，"
               "非偶发失败：道具用 kit_colorkey_cutout.py 色键兜底，面部微距让皮肤满幅到四边后用 --already-cutout）")
        raise RuntimeError(
            f"subjectmask 未产出抠图（returncode={r.returncode}）："
            f"{(r.stderr or r.stdout).strip() or '无输出'} {tip}")
    return dst_path


# ---------- 接触阴影 ----------
def contact_shadow(canvas_w, canvas_h, cx, sole_y, foot_w, opacity=22, blur=14):
    """在透明图层上画脚底椭圆软阴影，返回 RGBA 图层。"""
    layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rw = max(40, int(foot_w * 0.62))
    rh = max(16, int(foot_w * 0.10))
    d.ellipse([cx - rw // 2, sole_y - rh // 2 + 14, cx + rw // 2, sole_y + rh // 2 + 14],
              fill=(30, 42, 75, opacity))
    return layer.filter(ImageFilter.GaussianBlur(blur))


# ---------- 标准格 ----------
def standard_cell(cut_im, cell_w=CELL_W, cell_h=CELL_H, fig_ratio=FIG_H_RATIO,
                  sole_ratio=SOLE_RATIO, scale_factor=1.0, shadow=True):
    """把透明抠图按统一身高/足底基线放进标准格，返回 (白底RGBA, 透明RGBA)。"""
    cut_im = trim(cut_im, by="alpha")
    target_h = round(cell_h * fig_ratio * scale_factor)
    iw, ih = cut_im.size
    s = target_h / ih
    cut_im = cut_im.resize((round(iw * s), round(ih * s)), Image.LANCZOS)
    w, h = cut_im.size
    sole_y = round(cell_h * sole_ratio)
    x = round((cell_w - w) / 2)
    y = sole_y - h
    if y < 0:
        raise ValueError(
            f"主体顶部越界 {y}px：fig_ratio={fig_ratio} 与 sole_ratio={sole_ratio} 不相容。"
            "道具单体请改用 --square --no-shadow（bbox 双向居中），不要用本组合。")

    transparent = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
    transparent.alpha_composite(cut_im, (x, y))

    white = Image.new("RGBA", (cell_w, cell_h), (255, 255, 255, 255))
    if shadow:
        white.alpha_composite(contact_shadow(cell_w, cell_h, cell_w // 2, sole_y, w))
    white.alpha_composite(cut_im, (x, y))
    return white, transparent


def bust_cell(cut_im, cell_w=CELL_W, cell_h=CELL_H, h_ratio=0.925, top_ratio=0.035):
    """头肩胸像落格（表情板专用）：按主体高度归一、水平居中、顶部留 3.5% 边距，
    画面下沿自然切在上胸；无足底基线、无接触阴影。口径对齐主资产线表情单图。"""
    cut_im = trim(cut_im, by="alpha")
    target_h = round(cell_h * h_ratio)
    iw, ih = cut_im.size
    s = target_h / ih
    cut_im = cut_im.resize((round(iw * s), round(ih * s)), Image.LANCZOS)
    w, h = cut_im.size
    x = round((cell_w - w) / 2)
    y = round(cell_h * top_ratio)
    transparent = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
    transparent.alpha_composite(cut_im, (x, y))
    white = Image.new("RGBA", (cell_w, cell_h), (255, 255, 255, 255))
    white.alpha_composite(cut_im, (x, y))
    return white, transparent


def square_cell(cut_im, cell=2364, ratio=0.86):
    """细节特写/道具单体落方格：抠图按 bbox 等比缩放到占格 86%、双向居中、无阴影。
    边长由 CLI 传入（默认取标准格长边 2364；需要 2048 显式 --cell 2048x2048）。"""
    cut_im = trim(cut_im, by="alpha")
    iw, ih = cut_im.size
    s = min(cell * ratio / iw, cell * ratio / ih)
    cut_im = cut_im.resize((round(iw * s), round(ih * s)), Image.LANCZOS)
    w, h = cut_im.size
    x, y = round((cell - w) / 2), round((cell - h) / 2)
    transparent = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
    transparent.alpha_composite(cut_im, (x, y))
    white = Image.new("RGBA", (cell, cell), (255, 255, 255, 255))
    white.alpha_composite(cut_im, (x, y))
    return white, transparent
