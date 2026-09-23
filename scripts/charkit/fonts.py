# -*- coding: utf-8 -*-
"""字体解析：统一无衬线排版字体（跨平台）。

规范（结构规范 v0.2 增补）：
- macOS：首选苹方 PingFang SC；缺失时回退冬青黑体 Hiragino Sans GB；弃用 STHeiti（小字发虚）。
- Linux（CI/Docker）：Noto Sans CJK SC（fonts-noto-cjk）→ 文泉驿正黑 → Droid Sans Fallback。
- W3/常规用于正文、meta、HEX；W6/粗体用于标题、分区名、资产标签。
"""
import os
from PIL import ImageFont

# 每项：(常规路径, 常规 index, 粗体路径, 粗体 index)
_CANDIDATES = [
    # ---- macOS ----
    ("/System/Library/Fonts/PingFang.ttc", 4,
     "/System/Library/Fonts/PingFang.ttc", 6),                      # Regular / Semibold
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0,
     "/System/Library/Fonts/Hiragino Sans GB.ttc", 2),              # W3 / W6
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0,
     "/System/Library/Fonts/STHeiti Medium.ttc", 0),                # 最后兜底（不推荐）
    # ---- Linux（CI / 容器；apt: fonts-noto-cjk fonts-wqy-zenhei）----
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2,
     "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2),     # Noto CJK SC
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0,
     "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),            # 文泉驿（单字重）
    ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", 0,
     "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", 0),  # Droid 兜底
]

_RESOLVED = None


def _resolve():
    global _RESOLVED
    if _RESOLVED is not None:
        return _RESOLVED
    for reg_p, ri, bold_p, bi in _CANDIDATES:
        if not (os.path.exists(reg_p) and os.path.exists(bold_p)):
            continue
        # 校验常规/粗体 index 均可加载
        try:
            ImageFont.truetype(reg_p, 20, index=ri)
            ImageFont.truetype(bold_p, 20, index=bi)
        except Exception:
            continue
        _RESOLVED = (reg_p, ri, bold_p, bi)
        return _RESOLVED
    raise RuntimeError(
        "未找到可用的中文字体（macOS: PingFang/Hiragino；Linux: fonts-noto-cjk/fonts-wqy-zenhei）")


def font_path():
    return _resolve()[0]


def f(size, bold=False):
    """返回指定字号字体；bold=True 用 W6/Semibold，否则 W3/Regular。"""
    reg_p, ri, bold_p, bi = _resolve()
    return ImageFont.truetype(bold_p if bold else reg_p, size,
                              index=(bi if bold else ri))


def font_name():
    p = font_path()
    if "PingFang" in p:
        return "PingFang SC"
    if "Hiragino" in p:
        return "Hiragino Sans GB"
    if "NotoSansCJK" in p:
        return "Noto Sans CJK SC"
    if "wqy" in p:
        return "WenQuanYi Zen Hei"
    return os.path.basename(p)
