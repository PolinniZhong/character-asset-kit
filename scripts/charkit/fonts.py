# -*- coding: utf-8 -*-
"""字体解析：统一无衬线排版字体。

规范（结构规范 v0.2 增补）：
- 首选苹方 PingFang SC；本机缺失时回退冬青黑体 Hiragino Sans GB；
- 弃用 STHeiti 华文黑体（小字号发虚毛躁、近似衬线）。
- W3/常规用于正文、meta、HEX；W6/粗体用于标题、分区名、资产标签。
"""
import os
from PIL import ImageFont

# (路径, 常规 index, 粗体 index)
_CANDIDATES = [
    ("/System/Library/Fonts/PingFang.ttc", 4, 6),       # Regular / Semibold（存在时）
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0, 2),  # W3 / W6（已验证清晰）
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0, 0),  # 最后兜底（不推荐）
]

_RESOLVED = None


def _resolve():
    global _RESOLVED
    if _RESOLVED is not None:
        return _RESOLVED
    for path, ri, bi in _CANDIDATES:
        if not os.path.exists(path):
            continue
        # 校验 index 可加载
        try:
            ImageFont.truetype(path, 20, index=ri)
            ImageFont.truetype(path, 20, index=bi)
        except Exception:
            continue
        _RESOLVED = (path, ri, bi)
        return _RESOLVED
    raise RuntimeError("未找到可用的中文字体（PingFang / Hiragino Sans GB 均缺失）")


def font_path():
    return _resolve()[0]


def f(size, bold=False):
    """返回指定字号字体；bold=True 用 W6/Semibold，否则 W3/Regular。"""
    path, ri, bi = _resolve()
    return ImageFont.truetype(path, size, index=(bi if bold else ri))


def font_name():
    p = font_path()
    return "PingFang SC" if "PingFang" in p else ("Hiragino Sans GB" if "Hiragino" in p else os.path.basename(p))
