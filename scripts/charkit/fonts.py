# -*- coding: utf-8 -*-
"""字体解析：统一无衬线排版字体（跨平台）。

规范（结构规范 v0.2 增补）：
- macOS：首选苹方 PingFang SC；缺失时回退冬青黑体 Hiragino Sans GB；弃用 STHeiti（小字发虚）。
- Linux（CI/Docker）：Noto Sans CJK SC（fonts-noto-cjk）→ 文泉驿正黑 → Droid Sans Fallback。
- Windows：微软雅黑 msyh → 黑体 simhei。
- 任何平台都可用环境变量**显式覆盖**（精简镜像 / 非主流发行版 / 无预装字体的容器）：
  `CHARKIT_FONT=/path/to/font.ttc`、`CHARKIT_FONT_INDEX=2`（.ttc 子字体序号，默认 0）、
  `CHARKIT_FONT_BOLD=/path/to/bold.ttc`、`CHARKIT_FONT_BOLD_INDEX=2`（可选；缺省沿用常规字体）。
- W3/常规用于正文、meta、HEX；W6/粗体用于标题、分区名、资产标签。

历史事故（2026-09-23，CI run 35859680856）：候选表只有 macOS 路径，CI 在 ubuntu 上
第一个需要画字的测试即抛 RuntimeError；本地 macOS 全绿掩盖了这一点。新增平台/覆盖时请连带更新本候选表。
"""
import os
from PIL import ImageFont


def _idx(*names, default=0):
    """从环境变量读子字体 index；非法值静默退回 default（不在字体解析里抛异常）。"""
    for n in names:
        v = os.environ.get(n)
        if v not in (None, ""):
            try:
                return int(v)
            except ValueError:
                pass
    return default


_OVERRIDE = os.environ.get("CHARKIT_FONT", "")

# 每项：(常规路径, 常规 index, 粗体路径, 粗体 index)
_CANDIDATES = [
    # ---- 显式覆盖（优先级最高；任何平台可用）----
    (_OVERRIDE, _idx("CHARKIT_FONT_INDEX"),
     os.environ.get("CHARKIT_FONT_BOLD") or _OVERRIDE,
     _idx("CHARKIT_FONT_BOLD_INDEX", "CHARKIT_FONT_INDEX")),
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
    # ---- Windows ----
    ("C:/Windows/Fonts/msyh.ttc", 0,
     "C:/Windows/Fonts/msyhbd.ttc", 0),                             # 微软雅黑 / 雅黑粗体
    ("C:/Windows/Fonts/simhei.ttf", 0,
     "C:/Windows/Fonts/simhei.ttf", 0),                             # 黑体（单字重）兜底
]

_RESOLVED = None


def _resolve():
    global _RESOLVED
    if _RESOLVED is not None:
        return _RESOLVED
    for reg_p, ri, bold_p, bi in _CANDIDATES:
        if not reg_p or not bold_p:
            continue
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
        "未找到可用的中文字体（拼板/商卡的中文标题必需）。按平台任选其一：\n"
        "  · macOS    ：系统自带 PingFang / Hiragino（检查 /System/Library/Fonts）\n"
        "  · Ubuntu   ：sudo apt-get install -y fonts-noto-cjk fonts-wqy-zenhei\n"
        "  · Windows  ：应自带 msyh.ttc / simhei.ttf（检查 C:/Windows/Fonts）\n"
        "  · 其他/容器：显式指定字体文件（.ttc 需带子字体序号）：\n"
        "      export CHARKIT_FONT=/path/to/font.ttc\n"
        "      export CHARKIT_FONT_INDEX=2                    # 可选，默认 0\n"
        "      export CHARKIT_FONT_BOLD=/path/to/bold.ttc     # 可选，缺省同常规字体\n")


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
    if "msyh" in p:
        return "Microsoft YaHei"
    if "simhei" in p:
        return "SimHei"
    return os.path.basename(p)
