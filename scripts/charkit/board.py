# -*- coding: utf-8 -*-
"""拼板基类：白底画布、标题/meta、分区标记、画面外标签、HEX 色板条、验收对齐线。

铁律：标签/编号/说明一律画在资产画面之外（框下/栏外），禁止压在角色或道具像素上。
"""
from PIL import Image, ImageDraw
from .fonts import f
from .assets import fit_contain, fit_trim_white, fit_trim_height, load

INK = (20, 27, 40)
SUB = (100, 116, 139)
BLUE = (37, 99, 235)
BORDER = (216, 224, 236)
GUIDE = (148, 163, 184)


def _luminance(hexcolor):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


class Board:
    def __init__(self, w, h, title, meta="", margin=40):
        self.w, self.h, self.M = w, h, margin
        self.im = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        self.d = ImageDraw.Draw(self.im)
        self.title = title
        self.meta = meta
        self._header()

    def _header(self):
        self.d.text((self.M, 26), self.title, font=f(32, True), fill=INK)
        if self.meta:
            fnt = f(20)
            tw = self.d.textlength(self.meta, font=fnt)
            self.d.text((self.w - self.M - tw, 38), self.meta, font=fnt, fill=SUB)

    # ---- 基础元件 ----
    def section(self, y, text, x=None):
        x = self.M if x is None else x
        self.d.rectangle([x, y + 7, x + 13, y + 20], fill=BLUE)
        self.d.text((x + 22, y), text, font=f(26, True), fill=INK)

    def caption(self, cx, y, text, size=30, bold=True, fill=INK):
        """居中标签（必须在资产画面之外）。"""
        fnt = f(size, bold)
        tw = self.d.textlength(text, font=fnt)
        self.d.text((cx - tw / 2, y), text, font=fnt, fill=fill)

    def frame(self, x, y, w, h, radius=14, width=2):
        self.d.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                                 outline=BORDER, width=width)

    def paste_bottom(self, cell, cx, baseline):
        """以足底/内容底边对齐 baseline 居中贴入。"""
        self.im.alpha_composite(cell, (round(cx - cell.size[0] / 2),
                                       round(baseline - cell.size[1])))

    def cell_white(self, rel, bw, bh, root=None, cover=False, crop=None):
        """白底资产→bbox 裁切→适配格。rel 相对 root。"""
        path = rel if root is None else f"{root.rstrip('/')}/{rel}"
        if cover or crop:
            im = fit_contain(load(path), bw, bh, cover=cover, crop=crop)
        else:
            im = fit_trim_white(path, bw, bh)
        return im

    def cell_h(self, rel, target_h, root=None):
        """白底全身资产→按高度精确归一（五视角/动作等高对齐用）。"""
        path = rel if root is None else f"{root.rstrip('/')}/{rel}"
        return fit_trim_height(path, target_h)

    # ---- HEX 色板条 ----
    def hex_strip(self, palette, y, pill_h=44, label_size=18, pill_size=18):
        """palette: [{'name':..,'hex':'#xxxxxx'}]；药丸在版心均分。label_size=0 不画标题。"""
        if label_size:
            self.d.text((self.M, y - 26), "配色锁定值 HEX", font=f(label_size), fill=INK)
        n = len(palette)
        span = self.w - 2 * self.M
        for i, c in enumerate(palette):
            hx = c["hex"]
            txt_color = c.get("text")
            if txt_color is None:
                txt_color = "#FFFFFF" if _luminance(hx) < 0.62 else "#332A26"
            fill = tuple(int(hx.lstrip("#")[j:j + 2], 16) for j in (0, 2, 4))
            label = f"{c['name']} {hx}"
            fnt = f(pill_size)
            tw = self.d.textlength(label, font=fnt)
            pw = tw + 26
            cx = self.M + span * (i + 0.5) / n
            x0, x1 = cx - pw / 2, cx + pw / 2
            y0, y1 = y, y + pill_h
            light = _luminance(hx) >= 0.62
            self.d.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=fill,
                                     outline=BORDER if light else None)
            self.d.text((x0 + 13, y0 + (pill_h - pill_size) / 2 - 3),
                        label, font=fnt, fill=tuple(int(txt_color.lstrip("#")[j:j + 2], 16) for j in (0, 2, 4)))

    # ---- 验收对齐线 ----
    def hguide(self, y, label=None, x0=None, x1=None, dash=14, gap=10):
        x0 = self.M if x0 is None else x0
        x1 = self.w - self.M if x1 is None else x1
        x = x0
        while x < x1:
            self.d.line([x, y, min(x + dash, x1), y], fill=GUIDE, width=2)
            x += dash + gap
        if label:
            self.d.text((x0, y - 26), label, font=f(18), fill=GUIDE)

    def save(self, out_path):
        import os
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        self.im.convert("RGB").save(out_path, "PNG")
        return out_path
