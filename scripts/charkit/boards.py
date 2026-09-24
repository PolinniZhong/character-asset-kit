# -*- coding: utf-8 -*-
"""角色资产拼板的通用构建器，全部由角色目录下的 `资产清单.json` 驱动。

板型：multiview 五视图 / expression 表情 / detail 细节 / pose 动作 /
      prop 道具手持 / micro_expression 微表情矩阵（G10）/ gaze 机位视线（G11）/
      card 商卡 / character_sheet 角色设定板（ref 版式的确定性版本）。
所有标签均在资产画面之外；guides=True 出验收版（对齐线/格框）。
"""
import os
from PIL import Image, ImageDraw
from .board import Board, INK, SUB, BLUE, BORDER, GUIDE
from .fonts import f
from .assets import fit_contain, fit_trim_white, load


def _root(char_dir):
    return os.path.abspath(os.path.expanduser(char_dir))


def _items_cells(b, items, root, cols, y, cw, ch, gap, caption_y, caption_size=30,
                 cover=False, crop=None, frames=False):
    """等宽网格铺资产，标签在格框外下方。"""
    for i, it in enumerate(items):
        x = b.M + i * (cw + gap)
        if frames:
            b.frame(x, y, cw, ch)
        bw, bh = it.get("box", [cw, ch])
        im = b.cell_white(it["white"], bw, bh, root=root, cover=cover, crop=crop)
        # 底边对齐格框底、水平居中
        b.im.alpha_composite(im, (round(x + (cw - im.size[0]) / 2),
                                  round(y + ch - im.size[1])))
        b.caption(x + cw / 2, caption_y, it["label"], size=caption_size)


# ============ 1. 五视图 ============
def build_multiview(char_dir, mf, guides=False):
    cfg = mf["boards"]["multiview"]
    W, H, M = 2730, 1820, 40
    b = Board(W, H, "角色多视图设定",
              meta=f"{cfg['version']} · {cfg.get('meta', '')}".strip(" ·"))
    root = _root(char_dir)
    n = len(cfg["items"])
    pitch = (W - 2 * M) / n
    bw, bh = 500, 1280
    top, baseline = 190, 1470
    for i, it in enumerate(cfg["items"]):
        cx = M + pitch * (i + 0.5)
        im = b.cell_h(it["white"], 1280, root=root)
        b.paste_bottom(im, cx, baseline)
        b.caption(cx, baseline + 34, it["label"], size=30)
    # 对齐线最后画（压在资产之上，旧验收版样式）
    if guides:
        for frac, name in [(0.0, "头顶"), (0.105, "下巴"), (0.18, "肩线"),
                           (0.45, "腰胯"), (0.70, "膝线"), (1.0, "足底")]:
            b.hguide(round(top + (baseline - top) * frac), name)
    b.hex_strip(mf["palette"], 1720)
    out = os.path.join(root, cfg["out_review" if guides else "out_clean"])
    return b.save(out)


# ============ 2. 表情 ============
def build_expression(char_dir, mf, guides=False):
    cfg = mf["boards"]["expression"]
    W, H, M = 4320, 1400, 40
    b = Board(W, H, "角色表情设定",
              meta=f"{cfg['version']} · {cfg.get('meta', '')}".strip(" ·"))
    root = _root(char_dir)
    n = len(cfg["items"])
    pitch = (W - 2 * M) / n
    cw, ch, y = 660, 960, 120
    # 表情板用竖构图头肩裁切（cover 填满竖格）；商卡横框用 cfg["crop"]
    crop = tuple(cfg.get("board_crop", [250, 30, 1523, 1780]))
    for i, it in enumerate(cfg["items"]):
        cx = M + pitch * (i + 0.5)
        x = cx - cw / 2
        # 表情板用竖构图头肩裁切 cover 填满竖格（board_crop）；商卡横框用 crop
        im = b.cell_white(it["white"], cw, ch, root=root, cover=True, crop=crop)
        b.im.alpha_composite(im, (round(x), y))
        b.caption(cx, y + ch + 26, it["label"], size=30)
    if guides:
        for yy, name in [(y + 30, "头顶"), (y + 245, "眼高"), (y + 445, "下巴")]:
            b.hguide(yy, name)
    b.hex_strip(mf["palette"], 1290, pill_h=46)
    out = os.path.join(root, cfg["out_review" if guides else "out_clean"])
    return b.save(out)


# ============ 3. 细节特写 ============
def build_detail(char_dir, mf, guides=False):
    cfg = mf["boards"]["detail"]
    W, H, M, gap = 2900, 2320, 40, 30
    b = Board(W, H, "角色细节特写设定",
              meta=f"{cfg['version']} · {cfg.get('meta', '')}".strip(" ·"))
    root = _root(char_dir)
    cw, ch = 920, 880
    rows = [cfg["items"][i:i + 3] for i in range(0, len(cfg["items"]), 3)]
    for r, row in enumerate(rows):
        y = 120 + r * 1030
        for c, it in enumerate(row):
            x = M + c * (cw + gap)
            im = b.cell_white(it["white"], cw, ch, root=root, cover=True)
            b.im.alpha_composite(im, (x, y))
            if guides:
                b.frame(x, y, cw, ch, radius=4, width=2)
            label = f"{it.get('num', c + 1 + r * 3)} · {it['label']}"
            b.caption(x + cw / 2, y + ch + 26, label, size=30)
    b.hex_strip(mf["palette"], 2200)
    out = os.path.join(root, cfg["out_review" if guides else "out_clean"])
    return b.save(out)


# ============ 4. 动作姿态 ============
def build_pose(char_dir, mf, guides=False):
    cfg = mf["boards"]["pose"]
    W, H, M, gap = 3600, 2120, 40, 40
    b = Board(W, H, "角色动作姿态设定",
              meta=f"{cfg['version']} · {cfg.get('meta', '')}".strip(" ·"))
    root = _root(char_dir)
    cw, ch = 850, 820
    rows = [cfg["items"][i:i + 4] for i in range(0, len(cfg["items"]), 4)]
    baselines = [950, 1850]
    for r, row in enumerate(rows):
        baseline = baselines[r]
        for c, it in enumerate(row):
            cx = M + cw / 2 + c * (cw + gap)
            target_h = it.get("box", [cw, ch])[1]
            im = b.cell_h(it["white"], target_h, root=root)
            b.paste_bottom(im, cx, baseline)
            b.caption(cx, baseline + 30, it["label"], size=28)
    if guides:
        for r in range(len(rows)):
            b.hguide(baselines[r], "足底基线" if r == 0 else None)
    b.hex_strip(mf["palette"], 2010)
    out = os.path.join(root, cfg["out_review" if guides else "out_clean"])
    return b.save(out)


# ============ 5. 道具与手持 ============
def build_prop(char_dir, mf, guides=False):
    cfg = mf["boards"]["prop"]
    W, M = 3600, 80
    root = _root(char_dir)
    # 动态高度：solo 一行；held 按每行 held_cols 个自动多行（向后兼容 ≤held_cols 个旧包）
    n_solo = len(cfg["solo"])
    held_cols = 3
    held_rows = [cfg["held"][i:i + held_cols] for i in range(0, len(cfg["held"]), held_cols)]
    held_h = 1120
    held_row_gap = 150
    held_section_y = 1260
    held_baselines = []
    y = held_section_y + held_h + 40
    for _r in range(len(held_rows)):
        held_baselines.append(y)
        y += held_h + held_row_gap
    H = held_baselines[-1] + 170
    b = Board(W, H, "角色道具与手持关系设定",
              meta=f"{cfg['version']} · {cfg.get('meta', '')}".strip(" ·"))
    # 基类标题字号偏小，本板重画标题
    b.im = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    from PIL import ImageDraw
    b.d = ImageDraw.Draw(b.im)
    b.d.text((M, 46), "角色道具与手持关系设定", font=f(46, True), fill=INK)
    mt = f"{cfg['version']} · {cfg.get('meta', '')}".strip(" ·")
    b.d.text((W - M - b.d.textlength(mt, font=f(26)), 62), mt, font=f(26), fill=SUB)

    def section(y, text):
        b.d.rectangle([M, y + 8, M + 14, y + 22], fill=BLUE)
        b.d.text((M + 30, y), text, font=f(28, True), fill=INK)

    section(150, "单体独立图")
    solo_cx = [round(M + (W - 2 * M) * (i + 0.5) / n_solo) for i in range(n_solo)]
    for i, it in enumerate(cfg["solo"]):
        im = b.cell_white(it["white"], 820, 880, root=root)
        b.paste_bottom(im, solo_cx[i], 1110)
        b.caption(solo_cx[i], 1130, it["label"], size=34, fill=(51, 65, 85))

    section(held_section_y, "手持关系")
    held_cx = [660, 1800, 2940]
    for r, row in enumerate(held_rows):
        baseline = held_baselines[r]
        for c, it in enumerate(row):
            im = b.cell_h(it["white"], held_h, root=root)
            b.paste_bottom(im, held_cx[c], baseline)
            b.caption(held_cx[c], baseline + 14, it["label"], size=34, fill=(51, 65, 85))

    b.hex_strip(mf["palette"], H - 58, pill_h=40, label_size=22, pill_size=20)
    out = os.path.join(root, cfg["out_clean"])
    return b.save(out)


# ============ 6. 商卡 ============
def build_card(char_dir, mf, guides=False):
    cfg = mf["boards"]["card"]
    root = _root(char_dir)
    W, M = 2400, 64
    H = cfg.get("height", 5020)
    b = Board(W, H, "", margin=M)
    # 清掉基类标题，商卡用自己的标题体系
    from PIL import ImageDraw
    b.im = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    b.d = ImageDraw.Draw(b.im)
    b.d.text((M, 44), mf.get("card_title", "角色设定图"), font=f(52, True), fill=INK)
    meta = f"{cfg['version']} · {mf.get('tagline', '')}".strip(" ·")
    b.d.text((W - M - b.d.textlength(meta, font=f(24)), 64), meta, font=f(24), fill=SUB)

    def ctext(cx, y, txt, size, bold=True, fill=INK):
        b.caption(cx, y, txt, size=size, bold=bold, fill=fill)

    # 主视觉 + 母版站姿
    b.section(128, "主视觉胸像")
    b.section(128, "标准站姿 · 正面", x=1280)
    bust = b.cell_white(mf["master"]["bust"], 1080, 1040, root=root)
    b.paste_bottom(bust, 600, 1230)
    mast = b.cell_h(mf["master"]["white"], 1060, root=root)
    b.paste_bottom(mast, 1760, 1230)

    # 五视图
    b.section(1290, "全身五视图")
    mv = mf["boards"]["multiview"]["items"]
    pitch = (W - 2 * M) / 5
    for i, it in enumerate(mv):
        cx = M + pitch * (i + 0.5)
        im = b.cell_h(it["white"], 560, root=root)
        b.paste_bottom(im, cx, 1880)
        ctext(cx, 1892, it["label"], 26)

    # 表情（标签在框外）
    b.section(1980, "基础表情")
    ex = mf["boards"]["expression"]["items"]
    gap, chh = 20, 280
    cw = (W - 2 * M - 5 * gap) / 6
    crop = tuple(mf["boards"]["expression"].get("crop", [0, 40, 1773, 1440]))
    ey = 2012
    for i, it in enumerate(ex):
        x = M + i * (cw + gap)
        b.frame(x, ey, cw, chh)
        im = b.cell_white(it["white"], cw, chh, root=root, cover=True, crop=crop)
        b.im.alpha_composite(im, (round(x), ey))
        ctext(x + cw / 2, ey + chh + 12, it.get("card_label", it["label"]), 22)

    # 细节
    b.section(2368, "细节特写")
    dt = mf["boards"]["detail"]["items"]
    dy = 2400
    for i, it in enumerate(dt):
        x = M + i * (cw + gap)
        b.frame(x, dy, cw, chh)
        im = b.cell_white(it["white"], cw, chh, root=root, cover=True)
        b.im.alpha_composite(im, (round(x), dy))
        ctext(x + cw / 2, dy + chh + 12, it["card_label"], 22)

    # 动作 4×2
    b.section(2760, "动作姿态")
    po = mf["boards"]["pose"]["items"]
    pgap, pcw, pch = 32, (W - 2 * M - 3 * 32) / 4, 600
    for i, it in enumerate(po):
        r, c = divmod(i, 4)
        cx = M + pcw / 2 + c * (pcw + pgap)
        baseline = 3420 + r * 660
        target_h = it.get("card_box", [pcw, it.get("box", [pcw, pch])[1]])[1]
        im = b.cell_h(it["white"], target_h, root=root)
        b.paste_bottom(im, cx, baseline)
        ctext(cx, baseline + 10, it.get("card_label", it["label"]), 24)

    # 道具与手持
    b.section(4170, "道具与手持关系")
    pr = mf["boards"]["prop"]
    solo_imgs = [(b.cell_white(x["white"], x.get("card_box", [380, 500])[0],
                               x.get("card_box", [380, 500])[1], root=root),
                  x["card_label"]) for x in pr["solo"]]
    held_imgs = [(b.cell_h(x["white"], x.get("card_box", [380, 500])[1], root=root),
                  x["card_label"]) for x in pr["held"]]
    props = solo_imgs + held_imgs
    ppitch = (W - 2 * M) / len(props)
    for i, (im, lab) in enumerate(props):
        cx = M + ppitch * (i + 0.5)
        b.paste_bottom(im, cx, 4730)
        ctext(cx, 4742, lab, 22)

    # HEX
    b.hex_strip(mf["palette"], 4860, pill_h=40, label_size=0, pill_size=19)
    b.d.text((M, 4820), "配色锁定值 HEX", font=f(26, True), fill=INK)
    default_note = ("一致性锚点：约 5.5 头身 · 皮克斯/盲盒手办 3D ｜ 图中标签均为排版层文字，角色资产本体除签名印花外零文字")
    b.d.text((M, 4940), mf.get("card_note", default_note), font=f(20), fill=SUB)

    out = os.path.join(root, cfg["out"])
    return b.save(out)


# ============ 7. 微表情矩阵（G10，封存后扩展） ============

def build_micro_expression(char_dir, mf, guides=False):
    cfg = mf["boards"]["micro_expression"]
    W, M = 4320, 40
    band, cw, ch = 300, 900, 1080
    fams = [fam for fam in cfg["families"] if fam.get("levels")]  # 空 levels 的可选族不占行（#008）
    n_rows = 1 + len(fams)            # 首行中性基准轴，其后每族一行
    row_pitch = ch + 150
    H = 120 + n_rows * row_pitch + 120
    b = Board(W, H, "角色微表情矩阵",
              meta=f"{cfg['version']} · {cfg.get('meta', '')}".strip(" ·"))
    root = _root(char_dir)
    grid_x0 = M + band
    pitch = (W - 2 * M - band) / 3
    col_cx = [grid_x0 + pitch * (i + 0.5) for i in range(3)]

    # 列头：L1/L2/L3
    for i, t in enumerate(["强度 L1", "强度 L2", "强度 L3"]):
        b.caption(col_cx[i], 78, t, size=28, bold=False, fill=SUB)

    crop = tuple(cfg.get("board_crop", [250, 30, 1523, 1780]))

    def row_label(r, text):
        # 左侧族名带：竖排居中（逐字换行），标签在资产画面外
        chars = list(text)
        line_h = 40
        y0 = r + ch / 2 - line_h * (len(chars) - 1) / 2
        for i, ch_ in enumerate(chars):
            tw = b.d.textlength(ch_, font=f(30, True))
            b.d.text((M + band / 2 - tw / 2, y0 + i * line_h - 16),
                     ch_, font=f(30, True), fill=INK)

    def put_cell(cx, y, rel, label):
        im = b.cell_white(rel, cw, ch, root=root, cover=True, crop=crop)
        b.im.alpha_composite(im, (round(cx - cw / 2), y))
        if guides:
            b.frame(cx - cw / 2, y, cw, ch)
        b.caption(cx, y + ch + 24, label, size=28)

    y = 130
    # 基准轴行
    row_label(y, "基准轴")
    put_cell(col_cx[0], y, cfg["neutral_ref"], "0 中性（基准）")
    y += row_pitch
    # 情绪族行
    for fam in fams:
        row_label(y, fam["label"])
        for i, lv in enumerate(fam["levels"][:3]):
            put_cell(col_cx[i], y, lv["white"], lv["label"])
        y += row_pitch

    b.hex_strip(mf["palette"], H - 70, pill_h=42)
    out = os.path.join(root, cfg["out_review" if guides else "out_clean"])
    return b.save(out)


# ============ 8. 机位与视线（G11，封存后扩展） ============

def build_gaze(char_dir, mf, guides=False):
    cfg = mf["boards"]["gaze"]
    W, H, M = 3600, 2580, 80
    b = Board(W, H, "机位与视线设定",
              meta=f"{cfg['version']} · {cfg.get('meta', '')}".strip(" ·"))
    b.im = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    b.d = ImageDraw.Draw(b.im)
    b.d.text((M, 46), "机位与视线设定", font=f(46, True), fill=INK)
    mt = f"{cfg['version']} · {cfg.get('meta', '')}".strip(" ·")
    b.d.text((W - M - b.d.textlength(mt, font=f(26)), 62), mt, font=f(26), fill=SUB)
    root = _root(char_dir)

    def section(y, text):
        b.d.rectangle([M, y + 8, M + 14, y + 22], fill=BLUE)
        b.d.text((M + 30, y), text, font=f(28, True), fill=INK)

    # 上：机位俯仰（全身）
    section(150, "机位俯仰 · 前 3/4 全身")
    cams = cfg.get("camera", [])
    n_c = len(cams)
    for i, it in enumerate(cams):
        cx = M + (W - 2 * M) * (i + 0.5) / max(n_c, 1)
        im = b.cell_h(it["white"], 1000, root=root)
        b.paste_bottom(im, cx, 1110)
        b.caption(cx, 1130, it["label"], size=32, fill=(51, 65, 85))

    # 下：视线方向（头肩胸像，cover 竖格）
    section(1260, "视线方向 · 头肩胸像（只动眼珠）")
    eyes = list(cfg.get("eyes", []))
    if cfg.get("front_ref"):
        eyes = [{"label": "G0 正视（引用 G3）", "white": cfg["front_ref"]}] + eyes
    n_e = len(eyes)
    cw, chh, ey = 620, 900, 1310
    gap = (W - 2 * M - n_e * cw) / max(n_e - 1, 1) if n_e > 1 else 0
    crop = tuple(cfg.get("board_crop", [250, 30, 1523, 1780]))
    for i, it in enumerate(eyes):
        x = M + i * (cw + gap)
        im = b.cell_white(it["white"], cw, chh, root=root, cover=True, crop=crop)
        b.im.alpha_composite(im, (round(x), ey))
        if guides:
            b.frame(x, ey, cw, chh)
        b.caption(x + cw / 2, ey + chh + 20, it["label"], size=26)

    b.hex_strip(mf["palette"], 2522, pill_h=40, label_size=22, pill_size=20)
    out = os.path.join(root, cfg["out_review" if guides else "out_clean"])
    return b.save(out)


# ============ 9. 角色设定板（character_sheet） ============
#
# 版式来自《角色设定图板·通用提示词框架 v1.1》附录 A 的反推提示词——
# 那份刷屏的"3:4 竖版角色设定图"的信息架构是：
#   上部 左 40% 大型前四分之三胸像 ｜ 右 60% 2×2 全身网格
#   → 中部紧凑字段栏 → 表情一排 5 格 → 底部 3 列 2 行细节特写
#
# 这里做的是**同一套信息架构的确定性版本**：所有格子由单图资产拼出，
# 标签、字段、HEX 全部排版层绘制，不靠模型画字（模型画字必然有乱码/漂移）。
# 用途：与"整板直出"做同版式对照，证明差异在范式而不在模型画质。
#
# 高度由各区块累加算出（不写死 H），所以改字段数/表情数不会撞版。

def _fit_text(d, text, size, max_w, bold=False, min_size=15):
    """把文字收进 max_w：先缩字号，缩到底仍放不下才截断加省略号。

    拼板的硬要求是"任何两个标签都不许互相压字"。字段栏的值长短不可控
    （角色越多、描述越细就越容易溢出），所以这里不靠人工控制字数。
    """
    s = size
    while s > min_size:
        fnt = f(s, bold)
        if d.textlength(text, font=fnt) <= max_w:
            return text, fnt
        s -= 1
    fnt = f(min_size, bold)
    out = text
    while out and d.textlength(out + "…", font=fnt) > max_w:
        out = out[:-1]
    return ((out + "…") if out else ""), fnt


def build_character_sheet(char_dir, mf, guides=False):
    cfg = mf["boards"]["character_sheet"]
    root = _root(char_dir)

    # ---- 版心与区块预算（集中在这里，不散落魔法数字） ----
    W, M = cfg.get("width", 2430), 64
    USABLE = W - 2 * M
    TITLE_H = 46          # 区块小标题占高
    BLOCK_GAP = 40        # 区块之间
    HEADER_H = 112        # 大标题占 44+62；区块小标题必须落在它之下（曾叠 12px）
    UPPER_H = cfg.get("upper_h", 1280)     # 上部：胸像 + 2×2 全身（弹性最大的一块）
    INFO_H = cfg.get("info_h", 220)        # 字段栏
    PALETTE_H = 74 if mf.get("palette") else 0
    EXPR_H = cfg.get("expr_h", 320)
    DETAIL_H = cfg.get("detail_h", 340)
    LABEL_H = 40
    ROW_GAP = 16
    FOOT_H = 46

    def total_height(upper_h):
        return (HEADER_H
                + TITLE_H + upper_h + BLOCK_GAP
                + TITLE_H + INFO_H + PALETTE_H + BLOCK_GAP
                + TITLE_H + EXPR_H + LABEL_H + BLOCK_GAP
                + TITLE_H + 2 * (DETAIL_H + LABEL_H) + ROW_GAP
                + BLOCK_GAP + FOOT_H + M)

    # 高度优先由内容算出；清单若声明了 height（如 3:4 的 3240），
    # 差值全部由上部的 2×2 网格吸收——既不写死高度，也不留断版风险。
    H = total_height(UPPER_H)
    if cfg.get("height"):
        H = int(cfg["height"])
        UPPER_H = UPPER_H + (H - total_height(UPPER_H))
        if UPPER_H < 900:
            raise ValueError(
                f"character_sheet: height={H} 太小，上部只剩 {UPPER_H}px，装不下 2×2 全身")

    # 上部左右配比：左 40% 胸像 / 右 60% 全身网格（ref 的原始口径）
    left_w = int(round(USABLE * cfg.get("left_ratio", 0.40)))
    right_x = M + left_w + 24
    right_w = W - M - right_x

    # 2×2 格。PIL 的 resize 只吃整数尺寸，格宽高一律取整
    cell_gap = 22
    cell_w = int((right_w - cell_gap) / 2)
    cell_h = int((UPPER_H - 2 * LABEL_H - ROW_GAP) / 2)
    bust_h = int(UPPER_H - LABEL_H)

    b = Board(W, H, "", margin=M)
    # 换掉基类标题：设定板用自己的标题体系（与商卡一致）
    from PIL import ImageDraw
    b.im = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    b.d = ImageDraw.Draw(b.im)
    b.d.text((M, 44), mf.get("card_title", "角色设定图"), font=f(52, True), fill=INK)
    meta = f"{cfg['version']} · {cfg.get('meta') or mf.get('tagline', '')}".strip(" ·")
    b.d.text((W - M - b.d.textlength(meta, font=f(22)), 62), meta, font=f(22), fill=SUB)

    y = HEADER_H

    # ---------------- 上部：左 40% 胸像 + 右 60% 的 2×2 全身 ----------------
    b.section(y, cfg.get("upper_title", "主视觉 · 前四分之三胸像 ｜ 全身四视角"))
    cy = y + TITLE_H
    bx = M
    b.frame(bx, cy, left_w, bust_h)
    bust = b.cell_white(cfg.get("bust") or mf["master"]["bust"],
                        left_w - 24, bust_h - 24, root=root)
    b.paste_bottom(bust, bx + left_w / 2, cy + bust_h - 12)
    b.caption(bx + left_w / 2, cy + bust_h + 6, cfg.get("bust_label", "前四分之三胸像"), 24)

    mv = {it["label"]: it for it in mf["boards"]["multiview"]["items"]}
    want = cfg.get("views_2x2", ["正面", "正侧面", "后四分之三", "背面"])
    chosen = [mv[k] for k in want if k in mv] or list(mv.values())[:4]
    for i, it in enumerate(chosen[:4]):
        r, c = divmod(i, 2)
        x = right_x + c * (cell_w + cell_gap)
        fy = cy + r * (cell_h + LABEL_H + ROW_GAP)
        b.frame(x, fy, cell_w, cell_h)
        im = b.cell_h(it["white"], cell_h - 60, root=root)
        b.paste_bottom(im, x + cell_w / 2, fy + cell_h - 14)
        b.caption(x + cell_w / 2, fy + cell_h + 6, it["label"], 24)

    # ---------------- 中部：字段栏 ----------------
    y = cy + UPPER_H + BLOCK_GAP
    b.section(y, cfg.get("info_title", "角色信息"))
    iy = y + TITLE_H
    fields = cfg.get("fields", [])
    if fields:
        cols = cfg.get("field_cols", 4)
        rows = (len(fields) + cols - 1) // cols
        cw = USABLE / cols
        rh = INFO_H / max(rows, 1)
        b.d.rounded_rectangle([M, iy, W - M, iy + INFO_H], radius=12,
                              fill=(246, 247, 249), outline=BORDER, width=2)
        for i, fd in enumerate(fields):
            r, c = divmod(i, cols)
            fx = M + 22 + c * cw
            fy = iy + 18 + r * rh
            lab, lfnt = _fit_text(b.d, fd["label"], 19, cw - 40)
            b.d.text((fx, fy), lab, font=lfnt, fill=SUB)
            val, vfnt = _fit_text(b.d, fd["value"], 24, cw - 40, bold=True)
            b.d.text((fx, fy + 26), val, font=vfnt, fill=INK)

    # ---------------- 配色锁定值（确定性拼板才画得准） ----------------
    py = iy + INFO_H + 10
    if PALETTE_H:
        b.hex_strip(mf["palette"], py + 18, pill_h=42, label_size=19, pill_size=18)

    # ---------------- 表情一排 ----------------
    y = iy + INFO_H + PALETTE_H + BLOCK_GAP
    b.section(y, cfg.get("expr_title", "基础表情"))
    ey = y + TITLE_H
    ex = mf["boards"]["expression"]["items"][:cfg.get("expr_count", 5)]
    egap = 20
    ecw = int((USABLE - egap * (len(ex) - 1)) / max(len(ex), 1))
    ecrop = tuple(mf["boards"]["expression"].get("crop", [0, 40, 1773, 1440]))
    for i, it in enumerate(ex):
        x = M + i * (ecw + egap)
        b.frame(x, ey, ecw, EXPR_H)
        im = b.cell_white(it["white"], ecw, EXPR_H, root=root, cover=True, crop=ecrop)
        b.im.alpha_composite(im, (round(x), ey))
        b.caption(x + ecw / 2, ey + EXPR_H + 6, it.get("card_label", it["label"]), 22)

    # ---------------- 细节 3 列 × 2 行 ----------------
    y = ey + EXPR_H + LABEL_H + BLOCK_GAP
    b.section(y, cfg.get("detail_title", "细节特写"))
    dy = y + TITLE_H
    dt = mf["boards"]["detail"]["items"][:cfg.get("detail_count", 6)]
    dcols = cfg.get("detail_cols", 3)
    dgap = 24
    dcw = int((USABLE - dgap * (dcols - 1)) / dcols)
    for i, it in enumerate(dt):
        r, c = divmod(i, dcols)
        x = M + c * (dcw + dgap)
        fy = dy + r * (DETAIL_H + LABEL_H + ROW_GAP)
        b.frame(x, fy, dcw, DETAIL_H)
        im = b.cell_white(it["white"], dcw, DETAIL_H, root=root, cover=True)
        b.im.alpha_composite(im, (round(x), fy))
        b.caption(x + dcw / 2, fy + DETAIL_H + 6, it.get("card_label", it["label"]), 22)

    # ---------------- 页脚：一致性锚点 ----------------
    fy = H - M - FOOT_H
    default_note = ("一致性锚点：同一角色 · 同一比例 · 同一服装 ｜ 图中所有文字均为排版层绘制，"
                    "角色资产本体零文字")
    b.d.text((M, fy), mf.get("sheet_note", mf.get("card_note", default_note)), font=f(20), fill=SUB)

    # ---------------- 验收版：把 40/60 分区与区块边界画出来 ----------------
    if guides:
        b.hguide(cy - 12, "上部 40/60 分区起点")
        b.d.line([right_x - 12, cy, right_x - 12, cy + UPPER_H], fill=GUIDE, width=2)
        b.d.text((right_x - 10, cy - 28), "40% ｜ 60%", font=f(18), fill=GUIDE)
        for gy, label in ((iy, "字段栏"), (ey, "表情一排"), (dy, "细节 3×2")):
            b.hguide(gy - 8, label)
        b.hguide(fy - 10, "页脚")
        # 每格脸部/主体占比的自检参考线（企业级要求 ≥30%）
        b.d.text((M, H - M - 24), f"验收版：{W}×{H}（3:4）· 区块边界与实际排版一致",
                 font=f(18), fill=GUIDE)

    out = os.path.join(root, cfg["out_review" if guides else "out_clean"])
    return b.save(out)


BUILDERS = {
    "multiview": build_multiview,
    "expression": build_expression,
    "detail": build_detail,
    "pose": build_pose,
    "prop": build_prop,
    "micro_expression": build_micro_expression,
    "gaze": build_gaze,
    "card": build_card,
    "character_sheet": build_character_sheet,
}
