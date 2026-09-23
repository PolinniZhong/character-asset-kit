#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G14 训练素材备料：从已定稿白底单图构建角色 LoRA 数据集（派生物，可随时重建）。

设计依据：Skill references/gates-g10-g14.md 中的训练素材章节（双 caption profile、
取景三分组、差异化 repeats、分层 val、字节哈希校验）。
  - 只收过门定稿白底单图；排除拼板/透明/单体道具/配饰/场景/风格变体/过程稿；
  - 取景分 01_face / 02_medium / 03_full 三组（差异化 repeats，不删全身图）；
  - 双 caption profile：
      profile-A（ai-toolkit/Flux/Z-Image，默认）：default_caption.txt 写身份块一次，
              img/ 内同名 .txt 只写「触发词 + 变量块」；
      profile-B（kohya/SDXL）：cap_kohya/ 内同名 .txt 写「身份块 + 变量块」全量句；
  - val 数量与分层由 config.val_slugs 决定；train.txt/val.txt 确定性；附 smoke_test_prompts.txt；
  - 图片只复制不改字节（copy2），--check 用文件大小+哈希核对。

角色相关的一切（触发词、身份英文块、表情/细节槽位英文映射、val slug）都在
角色包 `11_训练素材/trainset.config.json` 里；模板见 Skill templates/trainset.config.example.json。

用法：
  python3 kit_trainset.py --build --root /path/to/library --char CHAR-01-slug
  python3 kit_trainset.py --check                 # 只读校验库内全部带 config 的包，有 ERROR 退出码 1
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys

SLOT = "S1-盲盒3D_v1.0"
CONFIG_REL = os.path.join("11_训练素材", "trainset.config.json")

FRAMING_DIR = {"face": "01_face", "medium": "02_medium", "full": "03_full"}
REPEATS_HINT = {"face": 12, "medium": 8, "full": 6}

# ------------------------------------------------------------ 变量块词表（英文，通用默认）

VIEWS = {
    "前四分之三": ("view-front34", "three-quarter front view"),
    "正侧": ("view-side", "side profile view"),
    "后四分之三": ("view-back34", "three-quarter back view"),
    "背面": ("view-back", "back view"),
}
GAZE = {"左": ("gaze-left", "eyes looking to the left"),
        "右": ("gaze-right", "eyes looking to the right"),
        "斜上": ("gaze-up", "eyes looking upward"),
        "斜下": ("gaze-down", "eyes looking downward")}
PITCH = {"俯15": ("pitch-high", "high-angle camera looking down at 15 degrees"),
         "仰15": ("pitch-low", "low-angle camera looking up at 15 degrees")}
MICRO_FAMILY = {"E1": "joyful", "E2": "surprised", "E3": "contemplative", "E4": "serious"}
MICRO_LEVEL = {"L1": "subtle intensity", "L2": "moderate intensity", "L3": "strong intensity"}

# 动作/手持词表可用 config 的 "pose" / "held" 键覆盖或追加
POSE_DEFAULT = {
    "A1挥手": "waving one hand in greeting", "A2讲解": "explaining with a raised-hand gesture",
    "A3摊开": "open palms gesture", "A4抱胸": "arms crossed",
    "A5托腮": "hand resting on the chin", "B1行走": "walking", "B2奔跑": "running",
    "B3端坐": "sitting upright",
}
HELD_DEFAULT = {
    "C1握笔记本": "typing on a laptop computer held in both hands",
    "C2持平板": "holding a tablet computer in both hands",
    "C3指屏幕": "pointing at a tablet screen",
    "C3看手机": "looking at a smartphone held in both hands",
}

SMOKE_TEMPLATE = [
    ("正脸微笑", "head-and-shoulders bust, gentle smile, looking at camera, plain white studio background"),
    ("正侧全身", "full body, side profile view, neutral standing pose"),
    ("正面A站", "full body, front view, neutral A-pose, arms relaxed at sides"),
    ("挥手动作", "full body, waving one hand in greeting"),
    ("背景泛化", "full body, standing outdoors in a park, daylight, greenery behind"),
]


# ------------------------------------------------------------ 角色配置（R1）

def resolve_pkg(root, char):
    """--char 可以是包路径，也可以是库根下的包目录名。"""
    if char:
        p = os.path.abspath(os.path.expanduser(char))
        if os.path.isdir(p):
            return p
        p = os.path.join(root, char)
        if os.path.isdir(p):
            return p
        raise SystemExit(f"找不到角色包：{char}")
    return None


def discover_pkgs(root):
    """库根下所有含 11_训练素材/trainset.config.json 的包。"""
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, CONFIG_REL)):
            out.append(d)
    return out


def load_config(char_dir):
    p = os.path.join(char_dir, CONFIG_REL)
    if not os.path.exists(p):
        raise SystemExit(
            f"缺训练配置：{os.path.relpath(p, char_dir)}\n"
            f"请按 Skill templates/trainset.config.example.json 填写（触发词/身份块/表情细节映射/val）。")
    with open(p, encoding="utf-8") as fp:
        cfg = json.load(fp)
    required = ["code", "trigger", "style_token", "gender", "master_rel",
                "identity", "expr", "detail", "val_slugs"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise SystemExit(f"{p} 缺字段：{missing}")
    cfg.setdefault("pose", {})
    cfg.setdefault("held", {})
    return cfg


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def white_pngs_under(folder):
    out = []
    if not os.path.isdir(folder):
        return out
    for root, _, files in os.walk(folder):
        if "拼板" in root.split(os.sep):
            continue
        for n in sorted(files):
            if n.endswith("_白.png") or n.endswith("_白底_v1.0.png"):
                out.append(os.path.join(root, n))
    return out


# ------------------------------------------------------------ 选图与变量映射

def select_units(char_dir, cfg):
    """返回 [(source_abs, stage, slug, framing, variable_en, zh)]，顺序即全局序号。"""
    pose_map = {**POSE_DEFAULT, **cfg.get("pose", {})}
    held_map = {**HELD_DEFAULT, **cfg.get("held", {})}
    expr_map = cfg["expr"]
    detail_map = cfg["detail"]
    units = []

    def add(src, stage, slug, framing, variable, zh):
        if os.path.exists(src):
            units.append((src, stage, slug, framing, variable, zh))
        else:
            print(f"  [warn] 缺源文件，跳过：{os.path.relpath(src, char_dir)}")

    # G1 母版（full）
    add(os.path.join(char_dir, cfg["master_rel"]), "G1", "master", "full",
        "full body, front view, neutral A-pose, arms relaxed at sides, friendly gentle smile",
        "标准母版")

    # G2/G11 多视图目录：五视图（正面去重排除）+ 视线 + 俯仰
    d = os.path.join(char_dir, "02_多视图")
    for p in white_pngs_under(d):
        n = os.path.basename(p)
        if "多视图-正面" in n:
            continue
        if "多视图-" in n:
            for zh, (slug, en) in VIEWS.items():
                if zh in n:
                    add(p, "G2", slug, "full",
                        f"full body, {en}, neutral standing A-pose", f"多视图-{zh}")
        elif "视线-" in n:
            for zh, (slug, en) in GAZE.items():
                if zh in n:
                    add(p, "G11", slug, "face",
                        f"head-and-shoulders bust, {en}, neutral expression", f"视线-{zh}")
        elif "机位-" in n:
            for zh, (slug, en) in PITCH.items():
                if zh in n:
                    add(p, "G11", slug, "full",
                        f"full body, {en}, neutral standing pose", f"机位-{zh}")

    # G3/G10 表情（基础 + 微表情，face）
    for p in white_pngs_under(os.path.join(char_dir, "03_表情")):
        n = os.path.basename(p)
        m = re.search(r"表情-(\d)([^_]+)", n)
        if m:
            key = f"{m.group(1)}{m.group(2)}"
            if key not in expr_map:
                print(f"  [warn] config.expr 无此槽位，跳过：{key}")
                continue
            slug, en = expr_map[key]
            add(p, "G3", slug, "face",
                f"head-and-shoulders bust, {en}", f"表情-{key}")
            continue
        m = re.search(r"微表情-(E\d)(L\d)", n)
        if m:
            fam, lvl = m.group(1), m.group(2)
            add(p, "G10", f"micro-{fam}-{lvl}", "face",
                f"head-and-shoulders bust, {MICRO_FAMILY[fam]} expression, {MICRO_LEVEL[lvl]}",
                f"微表情-{fam}{lvl}")

    # G4 细节（face 组的极端特写）
    for p in white_pngs_under(os.path.join(char_dir, "04_细节特写")):
        n = os.path.basename(p)
        m = re.search(r"细节-(\d[^_]+)", n)
        if m:
            key = m.group(1)
            if key not in detail_map:
                print(f"  [warn] config.detail 无此槽位，跳过：{key}")
                continue
            slug, en = detail_map[key]
            add(p, "G4", slug, "face", f"extreme close-up of {en}", f"细节-{key}")

    # G5 营销胸像（face）
    for p in white_pngs_under(os.path.join(char_dir, "05_营销胸像")):
        add(p, "G5", "bust-front34", "face",
            "head-and-shoulders three-quarter portrait, friendly smile", "营销胸像")

    # G6 动作（full）
    for p in white_pngs_under(os.path.join(char_dir, "06_动作姿态")):
        n = os.path.basename(p)
        m = re.search(r"动作-([AB]\d[^_]+)", n)
        if m:
            key = m.group(1)
            if key not in pose_map:
                print(f"  [warn] config/默认词表无此动作，跳过：{key}")
                continue
            c = key[:2]
            slug = "pose-" + c + "-" + pose_map[key].split(",")[0].replace(" ", "-")
            add(p, "G6", slug, "full", f"full body, {pose_map[key]}", f"动作-{key}")

    # G7 仅手持关系（medium）；单体道具/配饰排除
    d7 = os.path.join(char_dir, "07_道具")
    if os.path.isdir(d7):
        held_idx = 0
        for root, _, files in os.walk(d7):
            parts = root.split(os.sep)
            if "拼板" in parts or "手持关系" not in parts:
                continue
            for n in sorted(files):
                if not n.endswith("_白.png"):
                    continue
                p = os.path.join(root, n)
                # 旧 3D 命名「手持关系-C1xxx」；真人命名「手持-<名>_v」
                m = re.search(r"手持关系-(C\d[^_]+)", n)
                if m:
                    key = m.group(1)
                    slug = f"held-{key[:2]}"
                    zh = f"手持关系-{key}"
                else:
                    m = re.search(r"手持-([^_]+?)_v", n)
                    if not m:
                        continue
                    key = m.group(1)
                    held_idx += 1
                    slug = f"held-H{held_idx}"
                    zh = f"手持-{key}"
                en = held_map.get(key)
                if en:
                    add(p, "G7", slug, "medium", f"medium shot, {en}", zh)
    return units


# ------------------------------------------------------------ 构建

def build_char(char_dir, wipe=True):
    cfg = load_config(char_dir)
    code, trig = cfg["code"], cfg["trigger"]
    slot = cfg.get("dataset_slot", SLOT)
    out_dir = os.path.join(char_dir, "11_训练素材", "datasets", slot)
    if wipe and os.path.isdir(out_dir):
        shutil.rmtree(out_dir)

    units = select_units(char_dir, cfg)
    records = []
    for i, (src, stage, slug, framing, variable, zh) in enumerate(units, 1):
        dst_name = f"{code}_{i:04d}_{stage}_{slug}.png"
        rel_img = os.path.join("img", FRAMING_DIR[framing], dst_name)
        dst = os.path.join(out_dir, rel_img)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

        cap_a = f"{trig}, {variable}"
        cap_b = f"{cfg['identity']}, {variable}"
        cap_a_rel = rel_img[:-4] + ".txt"
        cap_b_rel = os.path.join("cap_kohya", FRAMING_DIR[framing], dst_name[:-4] + ".txt")
        with open(os.path.join(out_dir, cap_a_rel), "w", encoding="utf-8") as fp:
            fp.write(cap_a + "\n")
        os.makedirs(os.path.dirname(os.path.join(out_dir, cap_b_rel)), exist_ok=True)
        with open(os.path.join(out_dir, cap_b_rel), "w", encoding="utf-8") as fp:
            fp.write(cap_b + "\n")

        records.append({
            "file": rel_img, "framing": framing, "stage": stage, "slug": slug,
            "label_zh": zh, "source": os.path.relpath(src, char_dir).replace(os.sep, "/"),
            "caption_profile_a": cap_a, "caption_profile_b": cap_b,
            "sha256": file_sha(dst), "bytes": os.path.getsize(dst),
        })

    # val 分层固定：母版/正侧/微笑/行走/眼部（slug 在 config.val_slugs 里）
    def find_val(slug):
        for r in records:
            if r["slug"] == slug:
                return r["file"]
        return None
    val_files = [f for f in (find_val(s) for s in cfg["val_slugs"]) if f]
    train_files = [r["file"] for r in records if r["file"] not in set(val_files)]
    for name, lines in (("train.txt", train_files), ("val.txt", val_files)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fp:
            fp.write("\n".join(lines) + "\n")

    with open(os.path.join(out_dir, "default_caption.txt"), "w", encoding="utf-8") as fp:
        fp.write(cfg["identity"] + "\n")

    with open(os.path.join(out_dir, "manifest.jsonl"), "w", encoding="utf-8") as fp:
        for r in records:
            r2 = dict(r)
            r2["split"] = "val" if r["file"] in set(val_files) else "train"
            fp.write(json.dumps(r2, ensure_ascii=False) + "\n")

    with open(os.path.join(out_dir, "smoke_test_prompts.txt"), "w", encoding="utf-8") as fp:
        for zh, tail in SMOKE_TEMPLATE:
            fp.write(f"# {zh}\n{trig}, {tail}\n\n")

    counts = {f: sum(1 for r in records if r["framing"] == f) for f in FRAMING_DIR}
    summary = {
        "code": code, "trigger": trig, "style_token": cfg["style_token"],
        "profile_a": "img/ 同名 .txt = 触发词+变量；default_caption.txt 贴入训练器 Default Caption",
        "profile_b": "cap_kohya/ 同名 .txt = 身份块+变量全量句（kohya/SDXL 用）",
        "repeats_hint": REPEATS_HINT, "counts": {**counts, "total": len(records)},
        "val_count": len(val_files), "val_slugs": cfg["val_slugs"],
    }
    with open(os.path.join(out_dir, "dataset.json"), "w", encoding="utf-8") as fp:
        json.dump(summary, fp, ensure_ascii=False, indent=2)
        fp.write("\n")

    # 让**生成器自己**声明"哪些是故意为之"，供审计工具（如 lora-audit）把对应规则降级为 info。
    with open(os.path.join(out_dir, ".lora-audit-ignore"), "w", encoding="utf-8") as fp:
        fp.write(
            "# 本文件由 kit_trainset.py --build 生成（派生物）。手改会被下次构建覆盖。\n"
            "# 用途：告诉审计工具哪些「问题」是本管线的既定设计。\n"
            "# 格式：一行一个规则 ID，# 之后写理由。\n"
            "\n"
            "# 标准格（全身/胸像）为 1773x2364；方形细节特写为 2048x2048。\n"
            "# 两种尺寸是**分桶训练**的既定设计，不是选图时混入了来源不同的图。\n"
            "W008 # 方形细节图 2048x2048 与标准格 1773x2364 并存 —— 有意分桶，非混入\n"
        )

    # 构建后清理混入的系统杂物（Finder 之后还会再生成，故只保证构建那一刻是干净的）
    for _r, _dirs, _files in os.walk(out_dir):
        for _n in _files:
            if _n in (".DS_Store", "Thumbs.db", "desktop.ini") or _n.startswith("._"):
                os.remove(os.path.join(_r, _n))

    with open(os.path.join(char_dir, "11_训练素材", "训练外执行指南_v1.0.md"), "w",
              encoding="utf-8") as fp:
        fp.write(training_guide(cfg, summary))
    return summary


def training_guide(cfg, summary):
    trig, code = cfg["trigger"], cfg["code"]
    style = cfg["style_token"]
    gender = cfg.get("gender", "character")
    slot = cfg.get("dataset_slot", SLOT)
    c = summary["counts"]
    return f"""# {code} 训练外执行指南 v1.0（LoRA）

> 本文件由 `kit_trainset.py --build` 生成。**备料侧只负责数据集，训练在库外执行**；
> 以下参数是业界口径的**起点区间，不是承诺值**，必须以 smoke test 预览为准调参。
> 规范依据见 Skill references/gates-g10-g14.md 的训练素材章节。

## 1. 数据集在哪、怎么用

- 位置：本目录下 `datasets/{slot}/`
- 规模：{c['total']} 张（face {c['face']} / medium {c['medium']} / full {c['full']}），val 固定 {summary['val_count']} 张。
- 图片是定稿资产的**字节级副本**，未缩放未重压；对齐/裁切/桶形分辨率由训练器处理。

### profile-A（推荐：ostris ai-toolkit / Flux / Z-Image / Qwen 等现代底模）

1. Trigger Word 栏填 `{trig}`；
2. Default Caption 栏粘贴 `default_caption.txt` 全文（身份块，配置一次）；
3. 数据集指向 `img/`：同名 .txt 只含「触发词 + 本张变量」；
4. 三个取景组按不同 repeats 配三个 dataset 条目（见 §3）。

### profile-B（kohya-ss/sd-scripts / SDXL 系）

- sidecar 用 `cap_kohya/` 下的全量句（身份块 + 变量），训练前把它们按相同相对结构覆盖到 `img/` 旁，
  或直接让训练器读取 `cap_kohya/`；触发词仍是 `{trig}`，每张 caption 均以它开头。

## 2. 触发词与召回

- 角色 token：`{trig}`（自造稀有词，所有 caption 拼写完全一致）；风格 token：`{style}`；
- 推理：`{trig}, 3d cartoon {gender} character, …`；
  换背景时显式写目标环境（白底已被 caption 条件化，可被提示替换或负向）；
- LoRA 强度从 **0.8** 起调，过高会僵硬、过低召不回身份。

## 3. 训练剂量起点（20–50 张角色 LoRA 口径）

| 取景组 | 张数 | repeats 起点 |
|---|---|---|
| 01_face | {c['face']} | 12 |
| 02_medium | {c['medium']} | 8 |
| 03_full | {c['full']} | 6 |

- 有效剂量目标：每张图约 **50–100 个 repeat**；总量参考 **2000–4000 step**；
- 先跑 **1000–1500 step smoke test**（固定 seed + `smoke_test_prompts.txt` 5 条），
  看身份是否出现、表情/角度/动作是否仍可变，再决定加量还是停；
- rank/dim：**16–32** 起步（复杂服装可到 32），alpha ≈ rank；
- 学习率：SDXL 系约 1e-4 量级；Flux 系更低且分层（UNet/transformer 与 text encoder 分设）；
- 输出"炸了/发僵/每张都同构图"＝过训，减 step 或减 repeats；脸不稳加 face 组 repeats，服装/比例不稳加 full 组。

## 4. 验证（固定 seed，每次只改一个变量）

`smoke_test_prompts.txt` 五条：正脸微笑 / 正侧全身 / 正面 A 站 / 挥手 / 户外背景泛化。
val 的分层图（母版、正侧、微笑、行走、眼部细节）用于对照身份保持。

## 5. 边界与注意

- **LoRA 与底模强绑定**：换底模（SDXL→Flux→Z/Qwen）需重训，数据集可原样复用、caption profile 按新底模切换；
- 不同渲染风格/环境绝不混训（需要时另立数据集插槽）；
- 全部素材为自有角色资产，训练产物的对外授权范围另行声明。
"""


def build(root, pkg=None):
    pkg_dirs = [resolve_pkg(root, pkg)] if pkg else discover_pkgs(root)
    if not pkg_dirs:
        print("没有找到含 11_训练素材/trainset.config.json 的角色包。")
    for char_dir in pkg_dirs:
        print(f"[build] {os.path.basename(char_dir)}")
        s = build_char(char_dir)
        slot = load_config(char_dir).get("dataset_slot", SLOT)
        rel = os.path.join(os.path.basename(char_dir), "11_训练素材", "datasets", slot)
        print(f"   → {rel}")
        print(f"   face {s['counts']['face']} / medium {s['counts']['medium']} / "
              f"full {s['counts']['full']}，合计 {s['counts']['total']}，val {s['val_count']}")
    print("[build] 完成")


# ------------------------------------------------------------ 校验

FORBIDDEN_TOKENS = ("拼板", "验收版", "干净版", "商卡", "_透明", "道具-P", "配饰",
                    "场景包", "风格变体", "过程稿", "-净面")


def check_char(char_dir):
    cfg = load_config(char_dir)
    root = os.path.dirname(char_dir)
    slot = cfg.get("dataset_slot", SLOT)
    out_dir = os.path.join(char_dir, "11_训练素材", "datasets", slot)
    errs, warns = [], []
    if not os.path.isdir(out_dir):
        return [f"数据集目录不存在：{os.path.relpath(out_dir, root)}"], warns

    manifest = os.path.join(out_dir, "manifest.jsonl")
    if not os.path.exists(manifest):
        errs.append("缺 manifest.jsonl")
        return errs, warns
    records = [json.loads(l) for l in open(manifest, encoding="utf-8") if l.strip()]
    min_images = cfg.get("min_images", 40)
    if len(records) < min_images:
        errs.append(f"图片数 {len(records)} < {min_images}")

    for r in records:
        src_chain = r["source"]
        if any(tok in src_chain for tok in FORBIDDEN_TOKENS):
            errs.append(f"禁入来源：{r['file']} ← {src_chain}")
        img = os.path.join(out_dir, r["file"])
        if not os.path.exists(img):
            errs.append(f"缺图片：{r['file']}")
            continue
        if os.path.getsize(img) != r["bytes"] or file_sha(img) != r["sha256"]:
            errs.append(f"图片与源文件字节不一致：{r['file']}")
        src = os.path.join(char_dir, r["source"])
        if not os.path.exists(src):
            errs.append(f"源文件不存在：{r['source']}")
        elif os.path.getsize(src) != r["bytes"]:
            errs.append(f"副本与源大小不一致：{r['file']}")
        cap_a = img[:-4] + ".txt"
        cap_b = os.path.join(out_dir, "cap_kohya", r["file"].split("img/", 1)[1][:-4] + ".txt")
        if not os.path.exists(cap_a):
            errs.append(f"缺 profile-A caption：{os.path.basename(cap_a)}")
        if not os.path.exists(cap_b):
            errs.append(f"缺 profile-B caption：{os.path.basename(cap_b)}")

    for split, expect in (("val.txt", len(cfg["val_slugs"])), ):
        p = os.path.join(out_dir, split)
        if not os.path.exists(p):
            errs.append(f"缺 {split}")
        else:
            lines = [l for l in open(p, encoding="utf-8").read().splitlines() if l.strip()]
            if len(lines) != expect:
                errs.append(f"{split} 应为 {expect} 张，实际 {len(lines)}")
    for fn in ("train.txt", "default_caption.txt", "smoke_test_prompts.txt", "dataset.json"):
        if not os.path.exists(os.path.join(out_dir, fn)):
            errs.append(f"缺 {fn}")

    # train/val 与 manifest 一致
    tr = {l for l in open(os.path.join(out_dir, "train.txt"), encoding="utf-8").read().splitlines() if l}
    va = {l for l in open(os.path.join(out_dir, "val.txt"), encoding="utf-8").read().splitlines() if l}
    allf = {r["file"] for r in records}
    if tr | va != allf or tr & va:
        errs.append("train/val 清单与 manifest 不一致或有交叠")

    # 近重复：母版与多视图正面不得同时在集
    if any("多视图-正面" in r["source"] for r in records):
        errs.append("多视图-正面与母版近重复，必须排除")

    framing = {f: sum(1 for r in records if r["framing"] == f) for f in FRAMING_DIR}
    if framing["full"] > framing["face"]:
        warns.append(f"全身 {framing['full']} 多于头肩 {framing['face']}，注意 repeats 分组剂量")
    return errs, warns


def check(root, pkg=None):
    pkg_dirs = [resolve_pkg(root, pkg)] if pkg else discover_pkgs(root)
    rc = 0
    if not pkg_dirs:
        print("没有找到含 11_训练素材/trainset.config.json 的角色包。")
    for char_dir in pkg_dirs:
        cfg = load_config(char_dir)
        errs, warns = check_char(char_dir)
        print(f"[check] {cfg['code']}: ERROR {len(errs)}，WARN {len(warns)}")
        for e in errs:
            print("   ✗ " + e)
        for w in warns:
            print("   ! " + w)
        if errs:
            rc = 1
    return rc


def main():
    ap = argparse.ArgumentParser(description="G14 训练素材数据集构建与校验")
    ap.add_argument("--root", default=os.getcwd(), help="库根（默认当前目录）")
    ap.add_argument("--char", default=None, help="角色包目录名或路径；不传则处理库内全部带 config 的包")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(os.path.expanduser(args.root))
    if not (args.build or args.check):
        ap.error("指定 --build 或 --check")
    if args.build:
        build(root, args.char)
    if args.check:
        sys.exit(check(root, args.char))


if __name__ == "__main__":
    main()
