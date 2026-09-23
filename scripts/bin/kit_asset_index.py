#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资产档案索引与对账（AIGC 角色资产库）。

`资产清单.json` 是拼板构建的输入（计划）；本工具维护的 `资产档案.json` 是资产状态的记录（账）。
两者职责不同，本工具只读清单、只新增档案，绝不改写任何既有文件或用户资产。

用法：
  # 生成/刷新档案草稿（扫描目录 + 读清单标签 + 读规格卡版本；保留人工已填字段）
  python3 kit_asset_index.py --char CHAR-01-demo --scaffold

  # 对账（严格只读，不写任何文件）；有 ERROR 时退出码 1
  python3 kit_asset_index.py --char CHAR-01-demo --check
  python3 kit_asset_index.py --all --check

  # 库级总览
  python3 kit_asset_index.py --all --report

字段、状态枚举与 E1-E7 / W1-W6 规则随 Skill 分发在 references/registry-rules.md。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.getcwd()  # 库根默认当前目录；脚本随 Skill 分发，不再假设内置库结构
REGISTRY_NAME = "资产档案.json"
MANIFEST_NAME = "资产清单.json"

# 目录名（去掉数字前缀后）→ (unit_type, gate)
STAGE_MAP = {
    "母版": ("master", "G1"),
    "多视图": ("multiview", "G2"),
    "表情": ("expression", "G3"),
    "细节特写": ("detail", "G4"),
    "营销胸像": ("bust", "G5"),
    "动作姿态": ("pose", "G6"),
    "道具": ("prop", "G7"),
    "风格变体": ("style", "G13"),
    "商卡成品": ("card", "G8"),
    "训练素材": ("training", "G14"),
    "场景包": ("scene", "G12"),
}
ROLE_DIRS = {"单体独立图": "solo", "手持关系": "held", "配饰变体": "accessory"}
BOARD_DIR = "拼板"
NON_MEDIA_DIRS = ("提示词库", "过程稿", "训练素材")

BOARD_TYPES = {
    "multiview": "board_multiview",
    "expression": "board_expression",
    "detail": "board_detail",
    "pose": "board_pose",
    "prop": "board_prop",
    "micro_expression": "board_micro_expression",
    "gaze": "board_gaze",
    "scene": "board_scene",
    "style": "board_style",
}

# 封存后表演扩展包（G10/G11）：挂在 02/03 下的三级子目录，键为 strip_num 后的目录名
EXT_SUBDIRS = {
    "微表情矩阵": ("micro_expression", "G10", "board_micro_expression"),
    "俯仰视线": ("gaze", "G11", "board_gaze"),
}
BASE_GATES = [f"G{i}" for i in range(10)]
EXT_GATES = ["G10", "G11", "G12", "G13", "G14"]
ALL_GATES = BASE_GATES + EXT_GATES

# 结构规范 v0.3 的 kit_init_character TREE 已登记的二级子目录（用于 W3）
KNOWN_SUBDIRS = {"单图", "拼板", "单体独立图", "手持关系", "配饰变体", "微表情矩阵", "俯仰视线", "场景母版", "风格母版"}

REQ_PKG_FIELDS = ("registry_version", "library_type", "asset_object_type",
                  "code", "character_asset_key", "spec_card_current")

# 命名有两种顺序：`..._v1.1_白.png`（多数）与 `..._白底_v1.0.png`（母版），故不锚定行尾
FINISH_TOKEN_RE = re.compile(r"_(白底|透明|白)(?=_|$)")
VER_RE = re.compile(r"_(v\d+\.\d+(?:-[^_]+)?)")
SPECCARD_RE = re.compile(r"^00_.*规格卡.*_(v\d+\.\d+)\.md$")
BOARD_VARIANT = {"干净版": "clean", "验收版": "review"}
VARIANT_ORDER = {"base": 0, "signature": 1, "clean": 2}


# ---------------------------------------------------------------- 基础工具

def strip_num(name):
    """去掉目录/文件名前的数字编号前缀：07_道具 → 道具。"""
    return re.sub(r"^\d+_", "", name)


def vkey(v):
    """版本排序键：'v1.1' → (1, 1)。"""
    m = re.match(r"v(\d+)\.(\d+)", v or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def rel(char_dir, path):
    return os.path.relpath(path, char_dir).replace(os.sep, "/")


def load_json(path):
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def find_char_dirs(root):
    out = []
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, MANIFEST_NAME)):
            out.append(d)
    return out


def resolve_char(arg, root):
    """--char 先按 cwd 解析，再按库根解析（README 示例从库根调用）。"""
    for cand in (os.path.abspath(os.path.expanduser(arg)),
                 os.path.join(root, os.path.expanduser(arg))):
        if os.path.isdir(cand):
            return cand
    raise SystemExit(f"找不到角色目录：{arg}")


# ------------------------------------------------- 从清单收集权威标签

def norm_key(rel_path, code):
    """把文件路径归一为"单元键"，使同一单元的白底/透明两版共享同一标签。

    `02_多视图/单图/CHAR-01_多视图-正面_v1.1_白.png`
      → `02_多视图/单图/CHAR-01_多视图-正面`
    """
    d, name = os.path.split(rel_path)
    stem = re.sub(r"\.png$", "", name)
    stem = re.sub(r"^" + re.escape(code) + r"_", "", stem)
    stem = VER_RE.sub("", stem)
    stem = FINISH_TOKEN_RE.sub("", stem).strip("_")
    return f"{d}/{stem}" if d else stem


def manifest_labels(mf, code):
    """从 资产清单.json 收集 单元键 → label（清单标签权威，优先于文件名推导）。"""
    labels = {}

    def take(path, label):
        if isinstance(path, str) and isinstance(label, str):
            labels[norm_key(path, code)] = label

    master = mf.get("master") or {}
    take(master.get("white"), "母版")
    take(master.get("transparent"), "母版")
    take(master.get("bust"), "营销胸像")

    for b in (mf.get("boards") or {}).values():
        if not isinstance(b, dict):
            continue
        for it in b.get("items") or []:
            take(it.get("white"), it.get("label"))
        for key in ("solo", "held"):
            for it in b.get(key) or []:
                take(it.get("white"), it.get("label"))
    return labels


def manifest_outputs(mf, sections=None):
    """清单声明的产物路径。

    清单是**计划**，可以合法包含尚未生成的产物，故此处只做投影；
    由调用方决定按哪个门去要求（G8 只看基础板，G10/G11 看各自的扩展板）。
    `sections` 给定时只取这些 board 段。
    """
    boards = mf.get("boards") or {}
    outs = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("out", "out_clean", "out_review") and isinstance(v, str):
                    outs.append(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)

    if sections is None:
        walk(boards)
    else:
        for key in sections:
            if isinstance(boards.get(key), dict):
                walk(boards[key])
    return outs


def base_board_sections(mf):
    """基础流水线板段（G8）；排除封存后扩展板（G10/G11 各管各的）。"""
    ext = {v[2].replace("board_", "") for v in EXT_SUBDIRS.values()}
    return [k for k in (mf.get("boards") or {}) if k not in ext]


# ------------------------------------------------------------ 扫描与分类

def derive_label(code, filename):
    """从文件名推导中文标签：CHAR-01_多视图-正面_v1.0_白.png → 正面。"""
    stem = re.sub(r"\.png$", "", filename)
    stem = re.sub(r"^" + re.escape(code) + r"_", "", stem)
    stem = VER_RE.sub("", stem)
    stem = FINISH_TOKEN_RE.sub("", stem)
    stem = strip_num(stem).strip("_")
    if "-" in stem:
        stem = stem.split("-", 1)[1]
    return stem


def classify(char_dir, path, code, labels):
    """把一个 PNG 分类为 media 或 derived_deliverable；返回 dict 或 None。"""
    r = rel(char_dir, path)
    parts = r.split("/")
    stage = strip_num(parts[0])

    if any(x in parts[0] for x in NON_MEDIA_DIRS):
        return None
    if not r.endswith(".png"):
        return None

    name = parts[-1]
    # 表演扩展包三级目录优先分类（03_表情/微表情矩阵、02_多视图/俯仰视线）
    for sub in parts[1:-1]:
        if strip_num(sub) in EXT_SUBDIRS:
            ext_type, ext_gate, ext_board = EXT_SUBDIRS[strip_num(sub)]
            vm0 = VER_RE.search(name)
            if BOARD_DIR in parts:
                return {"kind": "deliverable", "path": r,
                        "deliverable_type": ext_board,
                        "variant": BOARD_VARIANT.get(strip_num(name).split("_")[-1].replace(".png", ""), "clean"),
                        "unit_version": vm0.group(1) if vm0 else "v1.0",
                        "gate": ext_gate}
            fm0 = FINISH_TOKEN_RE.search(re.sub(r"\.png$", "", name))
            finish0 = {"白": "white", "白底": "white", "透明": "transparent"}.get(fm0.group(1)) if fm0 else "flat"
            return {"kind": "media", "path": r, "unit_type": ext_type,
                    "label": labels.get(norm_key(r, code)) or derive_label(code, name),
                    "unit_version": vm0.group(1) if vm0 else "v1.0",
                    "finish": finish0, "role": "single", "gate": ext_gate}
    fm = FINISH_TOKEN_RE.search(re.sub(r"\.png$", "", name))
    finish = {"白": "white", "白底": "white", "透明": "transparent"}.get(fm.group(1)) if fm else "flat"
    vm = VER_RE.search(name)
    unit_version = vm.group(1) if vm else "v1.0"
    variant = "clean" if "-净面" in unit_version else None
    if variant:
        unit_version = unit_version.split("-")[0]

    # 拼板 / 商卡 → L3 派生交付物
    if BOARD_DIR in parts:
        return {
            "kind": "deliverable",
            "path": r,
            "deliverable_type": BOARD_TYPES.get(STAGE_MAP.get(stage, ("", ""))[0], "board_other"),
            "variant": BOARD_VARIANT.get(strip_num(name).split("_")[-1].replace(".png", ""), "clean"),
            "unit_version": unit_version,
            "gate": {"场景包": "G12", "风格变体": "G13"}.get(stage, "G8"),
        }

    unit_type, gate = STAGE_MAP.get(stage, (None, None))
    # 角色设定板与商卡同放 10_商卡成品/，但它是**另一种交付物**：
    # 若不单独分类，两者会得到同一个 (deliverable_type, unit_version, variant) 键，
    # 分配 asset_id 时互相覆盖（实测：同键三行触发 --assign-ids 零漂移中止）。
    if unit_type == "card" and "设定板" in name:
        return {"kind": "deliverable", "path": r,
                "deliverable_type": "board_character_sheet",
                "variant": BOARD_VARIANT.get(
                    strip_num(name).split("_")[-1].replace(".png", ""), "final"),
                "unit_version": unit_version, "gate": "G8"}
    if unit_type == "card":
        return {"kind": "deliverable", "path": r, "deliverable_type": "card",
                "variant": "final", "unit_version": unit_version, "gate": "G8"}
    if unit_type is None:
        return {"kind": "media", "path": r, "unit_type": "unclassified", "label": name,
                "unit_version": unit_version, "finish": finish, "role": "single", "gate": "G9"}

    role = "single"
    for p in parts[:-1]:
        if strip_num(p) in ROLE_DIRS:
            role = ROLE_DIRS[strip_num(p)]
    if unit_type == "accessory":
        role = "accessory"

    label = labels.get(norm_key(r, code)) or derive_label(code, name)
    rec = {"kind": "media", "path": r, "unit_type": unit_type, "label": label,
           "unit_version": unit_version, "finish": finish, "role": role, "gate": gate}
    if variant:
        rec["variant"] = variant
    return rec


def scan_structure_issues(char_dir):
    """W7：顶层目录编号冲突或未登记的阶段目录（名称匹配，不写死编号）。"""
    issues = []
    known_names = set(STAGE_MAP) | {"提示词库", "过程稿"}
    by_prefix = {}
    for n in sorted(os.listdir(char_dir)):
        d = os.path.join(char_dir, n)
        if not os.path.isdir(d) or n.startswith("."):
            continue
        m = re.match(r"^(\d+)_(.*)$", n)
        if not m:
            continue
        num, name = m.group(1), m.group(2)
        by_prefix.setdefault(num, []).append(n)
        if name not in known_names:
            issues.append(f"顶层目录未登记的阶段名：{n}")
    for num, names in sorted(by_prefix.items()):
        if len(names) > 1:
            issues.append(f"顶层目录编号冲突（前缀 {num}_ 被 {len(names)} 个目录占用）：{'、'.join(names)}")
    return issues


def scan_unknown_dirs(char_dir):
    """W3：结构规范 v0.3 未登记的二级子目录（check 与 scaffold 共用，不依赖生成字段）。"""
    out = set()
    for root, dirs, files in os.walk(char_dir):
        relroot = rel(char_dir, root)
        if relroot == ".":
            continue
        top = relroot.split("/")[0]
        if any(x in top for x in NON_MEDIA_DIRS):
            dirs[:] = []
            continue
        parts = relroot.split("/")
        if len(parts) >= 2:
            second = parts[1]
            if re.match(r"^S\d+[-_]", second):
                # 风格变体插槽层（如 S2-黏土），其下再挂 风格母版/单图/拼板
                if len(parts) >= 3 and parts[2] not in KNOWN_SUBDIRS and parts[2] != BOARD_DIR:
                    out.add(f"{parts[0]}/{second}/{parts[2]}")
            elif second not in KNOWN_SUBDIRS and second != BOARD_DIR:
                out.add(f"{parts[0]}/{parts[1]}")
    return sorted(out)


def scan_char(char_dir, mf):
    code = mf.get("code") or os.path.basename(char_dir).split("-")[0]
    labels = manifest_labels(mf, code)
    media, deliv = [], []

    for root, dirs, files in os.walk(char_dir):
        relroot = rel(char_dir, root)
        top = relroot.split("/")[0] if relroot != "." else ""
        if top and any(x in top for x in NON_MEDIA_DIRS):
            dirs[:] = []
            continue
        for n in sorted(files):
            if n.startswith(".") or not n.endswith(".png"):
                continue
            rec = classify(char_dir, os.path.join(root, n), code, labels)
            if rec is None:
                continue
            (media if rec["kind"] == "media" else deliv).append(rec)

    media.sort(key=lambda m: (m["gate"], m["unit_type"], m["label"], m["finish"]))
    deliv.sort(key=lambda d: (d["deliverable_type"], d["unit_version"], d["variant"]))
    return media, deliv


def scan_spec_cards(char_dir):
    out = {}
    for n in sorted(os.listdir(char_dir)):
        m = SPECCARD_RE.match(n)
        if m:
            out[m.group(1)] = n
    return out


def g14_dataset_ok(char_dir, code):
    """G14：S1 训练数据集最小要求（完整校验由 kit_trainset.py --check 负责）。"""
    import glob
    base = os.path.join(char_dir, "11_训练素材", "datasets")
    slots = glob.glob(os.path.join(base, "S1-*")) if os.path.isdir(base) else []
    if not slots:
        return False
    for d in slots:
        man = os.path.join(d, "manifest.jsonl")
        if not os.path.exists(man):
            return False
        rows = [l for l in open(man, encoding="utf-8") if l.strip()]
        cfg_p = os.path.join(char_dir, "11_训练素材", "trainset.config.json")
        min_images = (json.load(open(cfg_p, encoding="utf-8")).get("min_images", 40)
                      if os.path.exists(cfg_p) else 40)
        if len(rows) < min_images:
            return False
        for fn in ("train.txt", "val.txt", "default_caption.txt",
                   "smoke_test_prompts.txt", "dataset.json"):
            if not os.path.exists(os.path.join(d, fn)):
                return False
        val = [l for l in open(os.path.join(d, "val.txt"), encoding="utf-8") if l.strip()]
        if len(val) != 5:
            return False
        img_root = os.path.join(d, "img")
        for root, _, files in os.walk(img_root):
            for n in files:
                if n.endswith(".png") and not os.path.exists(os.path.join(root, n[:-4] + ".txt")):
                    return False
    return True


# ------------------------------------------------------------------ scaffold

def build_registry(char_dir, mf, old=None, today=None):
    today = today or __import__("datetime").date.today().isoformat()
    code = mf.get("code") or os.path.basename(char_dir).split("-")[0]
    media, deliv = scan_char(char_dir, mf)
    cards = scan_spec_cards(char_dir)
    is_new_registry = not old
    old = old or {}

    cur = old.get("spec_card_current")
    if not cur or not os.path.exists(os.path.join(char_dir, cur)):
        cur = cards[max(cards, key=vkey)] if cards else ""

    # L1：人工已写的条目原样保留（同一 asset_version 可有 signature/clean 多条）；
    # 仅为"规格卡存在但 L1 尚未覆盖"的版本补一条 draft，绝不自动改状态。
    old_list = old.get("asset_versions") or []
    versions = [dict(v) for v in old_list]
    covered = {v.get("asset_version") for v in versions}
    for ver in sorted(cards, key=vkey):
        if ver not in covered:
            versions.append({
                "asset_version": ver,
                "variant": "base",
                "costume_state_spec": "",
                "asset_validity_status": "draft",
                "formal_confirmation": {"date": "", "evidence": ""},
            })
    if not versions:
        versions = [{"asset_version": "v1.0", "variant": "base", "costume_state_spec": "",
                     "asset_validity_status": "draft",
                     "formal_confirmation": {"date": "", "evidence": ""}}]
    versions.sort(key=lambda v: (vkey(v.get("asset_version")),
                                 VARIANT_ORDER.get(v.get("variant"), 9)))

    for m in media:
        m.setdefault("variant", None)
    media = [{k: v for k, v in m.items() if not (k == "variant" and v is None)}
             for m in media]
    deliv = [{k: v for k, v in d.items() if k != "kind"} for d in deliv]
    media = [{k: v for k, v in m.items() if k != "kind"} for m in media]

    # v3 守卫：旧档案若已是契约 v3，按路径把 asset_id/content_id/kind/tier 原样带回，
    # 绝不因 scaffold 重扫而丢失稳定 ID（丢了会断 renditions/<asset_id>/ 链接）。
    # 路径匹配不上的新增行不伪造 ID，留给上层资产中心工具链的 assign-ids 流程补打。
    is_v3 = old.get("contract") == "v3"
    unstamped = []
    if is_v3:
        stamps = {}
        for r in (old.get("media") or []) + (old.get("derived_deliverables") or []):
            p = r.get("path")
            if p and r.get("asset_id"):
                stamps[p] = {k: r.get(k) for k in ("asset_id", "content_id", "kind", "tier")}

        def restamp(r):
            s = stamps.get(r.get("path"))
            if s:
                r.update({k: v for k, v in s.items() if v is not None})
            else:
                unstamped.append(r.get("path"))
            return r
        media = [restamp(m) for m in media]
        deliv = [restamp(d) for d in deliv]

    reg = {
        "registry_version": "v1.0",
        "library_type": old.get("library_type", "character"),
        "asset_object_type": old.get("asset_object_type", "character"),
        "code": code,
        "character_asset_key": old.get("character_asset_key", code),
        "display_name": old.get("display_name", ""),
        "spec_card_current": cur,
        "spec_cards_present": [cards[k] for k in sorted(cards, key=vkey)],
        "appearance_spec_ref": old.get("appearance_spec_ref", f"{cur} §1 身份签名" if cur else ""),
        "applicable_scope": old.get("applicable_scope", ""),
        "sharing_scope": old.get("sharing_scope", ""),
        "authorization_refs": (
            old.get("authorization_refs")
            if old.get("authorization_refs") is not None
            else ([{"type": "自有版权", "note": "库内自建资产，无外部素材/肖像授权依赖；若使用外部参考或肖像请人工改写"}]
                  if is_new_registry else [])
        ),
        "asset_versions": versions,
        "media": media,
        "derived_deliverables": deliv,
        "gates": (lambda og: {**{g: og.get(g, "pending") for g in ALL_GATES},
                               **{g: v for g, v in og.items() if g not in ALL_GATES}})(old.get("gates", {})),
        "notes": old.get("notes", ""),
    }
    if is_v3:
        reg["contract"] = "v3"
        if old.get("_migrated_by"):
            reg["_migrated_by"] = old["_migrated_by"]
    todos = todo_list(reg)
    if todos:
        reg["_todo_human"] = todos
    reg["_unstamped_new"] = unstamped  # 临时字段，main 写盘前弹出
    return reg


def todo_list(reg):
    """按当前档案的实际空缺点生成待办；填完即自动消失（不写死清单）。"""
    t = []
    for f in ("display_name", "applicable_scope", "sharing_scope"):
        if not reg.get(f):
            t.append(f)
    if not reg.get("authorization_refs"):
        t.append("authorization_refs（自有版权也须显式声明）")
    for v in reg.get("asset_versions") or []:
        tag = f"{v.get('asset_version')}/{v.get('variant')}"
        if not v.get("costume_state_spec"):
            t.append(f"asset_versions[{tag}].costume_state_spec：服装与状态一句摘要")
        if v.get("asset_validity_status") == "draft":
            t.append(f"asset_versions[{tag}].asset_validity_status 仍为 draft（需人工判定，脚本不代写）")
        if not (v.get("formal_confirmation") or {}).get("date"):
            t.append(f"asset_versions[{tag}].formal_confirmation：日期 + 可回查证据位置")
    if all(v == "pending" for v in (reg.get("gates") or {}).values()):
        t.append("gates：按实际进度标注 done/partial/pending")
    return t


# --------------------------------------------------------------------- check

def check_registry(char_dir, reg, mf):
    errs, warns = [], []

    def E(c, m):
        errs.append((c, m))

    def W(c, m):
        warns.append((c, m))

    for f in REQ_PKG_FIELDS:
        if not reg.get(f):
            E("E7", f"缺必填包级字段 {f}")

    # E2 / E3：规格卡现行指针
    cards = scan_spec_cards(char_dir)
    cur = reg.get("spec_card_current")
    if cur and not os.path.exists(os.path.join(char_dir, cur)):
        E("E2", f"spec_card_current 指向不存在的文件：{cur}")
    if len(cards) > 1 and not cur:
        E("E3", f"存在多份规格卡 {sorted(cards)} 但未指明现行版本")

    # E4：授权
    if not reg.get("authorization_refs"):
        E("E4", "authorization_refs 为空（自有版权也须显式声明）")

    media = reg.get("media") or []
    deliv = reg.get("derived_deliverables") or []

    # E1：登记的文件必须存在
    for rec in media + deliv:
        p = rec.get("path")
        if not p or not os.path.exists(os.path.join(char_dir, p)):
            E("E1", f"登记路径不存在：{p}")

    # E6：media.variant 必须有对应 L1 版本
    have_variants = {v.get("variant") for v in reg.get("asset_versions") or []}
    for m in media:
        if m.get("variant") and m["variant"] not in have_variants:
            E("E6", f"media variant={m['variant']} 在 asset_versions 中无对应版本：{m['path']}")

    # E5 / W4：阶段门与产物一致性
    def has(unit, finish=None, pred=None):
        for m in media:
            if m.get("unit_type") != unit:
                continue
            if finish and m.get("finish") != finish:
                continue
            if pred and not pred(m):
                continue
            return True
        return False

    def outs_exist(sections=None):
        return all(os.path.exists(os.path.join(char_dir, p))
                   for p in manifest_outputs(mf, sections))

    base_secs = base_board_sections(mf)
    reqs = {
        "G1": (lambda: has("master", "white") and has("master", "transparent"),
               "master 白底+透明"),
        "G2": (lambda: len({m["label"] for m in media if m.get("unit_type") == "multiview"
                            and m.get("finish") == "white"}) >= 5, "multiview ≥5 视角"),
        "G3": (lambda: has("expression", None,
                           lambda m: str(m.get("label", "")).startswith(("0", "中性"))),
               "expression 第0格中性"),
        "G4": (lambda: has("detail"), "detail ≥1"),
        "G5": (lambda: has("bust"), "bust ≥1"),
        "G6": (lambda: has("pose"), "pose ≥1"),
        "G7": (lambda: has("prop", None, lambda m: m.get("role") == "solo"), "prop solo ≥1"),
        # G8 只对**基础流水线**板段负责；封存后扩展板（G10/G11）各由自己的门校验，
        # 否则给已封存角色追加扩展板会让 G8 由 done 翻成错误（清单是计划，会持续增长）。
        "G8": (lambda: bool(deliv)
               and all(os.path.exists(os.path.join(char_dir, d["path"])) for d in deliv)
               and outs_exist(base_secs),
               "全部派生交付物与基础板段清单产物存在"),
        "G10": (lambda: sum(1 for m in media if m.get("unit_type") == "micro_expression"
                            and m.get("finish") == "white") >= 9
                and outs_exist(["micro_expression"]),
                "micro_expression 白 ≥9（≥3 族 × L1–L3）且扩展板产物存在"),
        "G11": (lambda: sum(1 for m in media if m.get("unit_type") == "gaze"
                            and "机位" in m.get("path", "")) >= 2
                and sum(1 for m in media if m.get("unit_type") == "gaze"
                        and "视线" in m.get("path", "")) >= 4
                and outs_exist(["gaze"]),
                "gaze：机位俯仰 ≥2 且视线方向 ≥4 且扩展板产物存在"),
        "G12": (lambda: any(m.get("unit_type") == "scene" and "场景母版" in m.get("path", "")
                            for m in media)
                and sum(1 for m in media if m.get("unit_type") == "scene"
                        and "竖3x4" in m.get("path", "")) >= 5
                and sum(1 for m in media if m.get("unit_type") == "scene"
                        and "横16x9" in m.get("path", "")) >= 5
                and any(d.get("deliverable_type") == "board_scene" for d in deliv),
                "scene：场景母版 1 + 竖版/横版各 ≥5 + 场景总览板"),
        "G13": (lambda: any(m.get("unit_type") == "style" and "风格母版" in m.get("path", "")
                            for m in media),
                "style：至少 1 张已过门的风格母版（派生包按需增量）"),
        "G14": (lambda: g14_dataset_ok(char_dir, reg.get("code")),
                "training：S1 数据集 ≥min_images（默认40、真人线30）、sidecar 全覆盖、val=5（详见 kit_trainset.py --check）"),
    }
    gates = reg.get("gates") or {}
    for g, (fn, desc) in reqs.items():
        st = gates.get(g)
        ok = fn()
        if st == "done" and not ok:
            E("E5", f"{g} 标为 done 但最小产物要求不满足（{desc}）")
        elif st in ("pending", "partial") and ok:
            W("W4", f"{g} 标为 {st} 但产物已满足要求（{desc}），可能已可过门")

    # W1：磁盘未登记
    disk = []
    for root, dirs, files in os.walk(char_dir):
        r = rel(char_dir, root)
        top = r.split("/")[0] if r != "." else ""
        if top and any(x in top for x in NON_MEDIA_DIRS):
            dirs[:] = []
            continue
        for n in files:
            if n.endswith(".png") and not n.startswith("."):
                disk.append(rel(char_dir, os.path.join(root, n)))
    registered = {m["path"] for m in media} | {d["path"] for d in deliv}
    for p in sorted(set(disk) - registered):
        W("W1", f"磁盘 PNG 未登记：{p}")

    # W2：清单声明的产物未生成（计划，属正常）
    for p in manifest_outputs(mf):
        if not os.path.exists(os.path.join(char_dir, p)):
            W("W2", f"清单声明的产物尚未生成：{p}")

    # W3：结构规范未登记的目录
    for d in scan_unknown_dirs(char_dir):
        W("W3", f"目录未登记进结构规范 v0.3：{d}")

    # W7：顶层目录编号冲突 / 阶段名未登记
    for msg in scan_structure_issues(char_dir):
        W("W7", msg)

    # W5：同 unit_type+label 多版本并存
    seen = {}
    for m in media:
        if m.get("finish") != "white":
            continue
        seen.setdefault((m.get("unit_type"), m.get("label")), set()).add(m.get("unit_version"))
    for (ut, lb), vs in sorted(seen.items(), key=lambda x: str(x[0])):
        if len(vs) > 1:
            W("W5", f"{ut}/{lb} 存在多版本并存 {sorted(vs)}（需确认哪版现行）")

    # W6：非现行规格卡版本仍为 draft
    ver_status = {v.get("asset_version"): v.get("asset_validity_status")
                  for v in reg.get("asset_versions") or []}
    for ver, fname in sorted(cards.items(), key=lambda x: vkey(x[0])):
        if fname == cur:
            continue
        if ver_status.get(ver) == "draft":
            W("W6", f"非现行规格卡 {ver}（{fname}）的 asset_version 仍为 draft，需人工判为 superseded 或保留")

    return errs, warns


# -------------------------------------------------------------------- report

def report(root):
    print(f"库根：{root}")
    print(f"{'角色':<18}{'阶段门':<28}{'媒体':>6}{'白/透':>9}{'交付物':>7}  错误/提示")
    print("-" * 92)
    tot_e = tot_w = 0
    for cd in find_char_dirs(root):
        mf = load_json(os.path.join(cd, MANIFEST_NAME))
        rp = os.path.join(cd, REGISTRY_NAME)
        if not os.path.exists(rp):
            print(f"{os.path.basename(cd):<18}{'（无资产档案，先跑 --scaffold）':<28}")
            continue
        reg = load_json(rp)
        media = reg.get("media") or []
        deliv = reg.get("derived_deliverables") or []
        errs, warns = check_registry(cd, reg, mf)
        tot_e += len(errs)
        tot_w += len(warns)
        gates = reg.get("gates") or {}
        gate_keys = BASE_GATES + [g for g in sorted(gates) if g not in BASE_GATES]
        marked = {g: v for g, v in sorted(gates.items()) if v not in ("pending", None)}
        if marked:
            done = [g for g, v in marked.items() if v == "done"]
            gs = f"已过 {len(done)}/{len(gate_keys)}" + (
                f"（至 {max(done, key=lambda x: int(x[1:]))}）" if done else "")
        else:
            gs = "未记录（全部 pending）"
        white = sum(1 for m in media if m.get("finish") == "white")
        trans = sum(1 for m in media if m.get("finish") == "transparent")
        print(f"{reg.get('code', os.path.basename(cd)):<18}{gs:<28}{len(media):>6}"
              f"{f'{white}/{trans}':>9}{len(deliv):>7}  {len(errs)}/{len(warns)}")
    print("-" * 92)
    print(f"合计：ERROR {tot_e}，WARN {tot_w}")
    return 0


# ------------------------------------------------------------------- gallery

UNIT_ORDER = ["master", "multiview", "expression", "micro_expression", "gaze", "scene",
              "detail", "bust", "pose", "prop", "accessory", "style", "training", "card"]
UNIT_LABELS = {
    "master": "母版", "multiview": "多视图", "expression": "表情",
    "micro_expression": "微表情矩阵", "gaze": "机位与视线", "scene": "场景包",
    "detail": "细节特写", "bust": "营销胸像", "pose": "动作姿态",
    "prop": "道具", "accessory": "配饰", "style": "风格变体",
    "training": "训练素材", "card": "商卡", "unclassified": "未分类",
}
ROLE_LABELS = {"single": "", "solo": "单体", "held": "手持", "accessory": "配饰"}
DELIV_LABELS = {
    "board_multiview": "多视图板", "board_expression": "表情板",
    "board_detail": "细节板", "board_pose": "动作姿态板",
    "board_prop": "道具手持板", "board_accessory": "配饰板",
    "board_micro_expression": "微表情板", "board_gaze": "机位视线板", "board_scene": "场景总览板", "board_style": "风格总览板",
    "board_character_sheet": "角色设定板",
    "card": "商卡成品", "board_other": "其他板",
}
DELIV_VARIANT = {"clean": "干净版", "review": "验收版", "final": "成品"}
FINISH_LABELS = {"white": "白底", "transparent": "透明", "flat": "平底"}
GATE_LABELS = {
    "G0": "立项", "G1": "母版", "G2": "五视图", "G3": "表情", "G4": "细节",
    "G5": "胸像", "G6": "动作", "G7": "道具", "G8": "拼板/商卡", "G9": "封存",
    "G10": "微表情矩阵", "G11": "机位与视线", "G12": "场景包", "G13": "风格变体",
    "G14": "训练素材备料",
}

GALLERY_CSS = """
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:#F5F5F6;color:#18181B;
 font:14px/1.6 system-ui,-apple-system,"PingFang SC","Hiragino Sans GB",sans-serif}
a{color:#2563EB;text-decoration:none}
a:hover{text-decoration:underline}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
header{position:sticky;top:0;z-index:10;background:rgba(255,255,255,.92);
 backdrop-filter:saturate(1.6) blur(8px);border-bottom:1px solid #E4E4E7;padding:16px 28px}
.hrow{display:flex;flex-wrap:wrap;align-items:baseline;gap:12px}
h1{margin:0;font-size:19px;font-weight:650;letter-spacing:.01em}
.sub{color:#71717A;font-size:12.5px;margin:4px 0 0}
.seg{display:inline-flex;border:1px solid #D4D4D8;border-radius:7px;overflow:hidden;background:#fff}
.seg button{border:0;background:transparent;padding:5px 12px;font:inherit;font-size:12.5px;
 color:#52525B;cursor:pointer}
.seg button+button{border-left:1px solid #E4E4E7}
.seg button.on{background:#4F9DFF;color:#fff}
main{padding:22px 28px 60px;max-width:1560px;margin:0 auto}
.char{background:#fff;border:1px solid #E4E4E7;border-radius:12px;padding:20px 22px;margin-bottom:22px}
.chead{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-start;justify-content:space-between}
h2{margin:0;font-size:17px;font-weight:650}
h2 .name{color:#71717A;font-weight:400;margin-left:7px}
.meta{color:#71717A;font-size:12.5px;margin-top:5px;max-width:760px}
.meta b{color:#3F3F46;font-weight:550}
.gates{display:flex;gap:3px;flex:0 0 auto}
.gate{width:26px;height:24px;border-radius:5px;display:flex;align-items:center;
 justify-content:center;font-size:10.5px;font-weight:600;background:#F4F4F5;
 color:#A1A1AA;border:1px solid #E4E4E7;cursor:help}
.gate.done{background:#DCFCE7;color:#15803D;border-color:#BBF7D0}
.gate.partial{background:#FEF9C3;color:#A16207;border-color:#FEF08A}
.stats{display:flex;gap:16px;flex-wrap:wrap;margin-top:12px;font-size:12.5px;color:#52525B}
.stats b{font-weight:600;color:#18181B}
.pal{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.sw{display:flex;align-items:center;gap:6px;border:1px solid #E4E4E7;border-radius:6px;
 padding:3px 8px 3px 4px;background:#FAFAFA;font-size:11.5px;color:#52525B}
.sw i{width:15px;height:15px;border-radius:3px;border:1px solid rgba(0,0,0,.14);display:block}
.vers{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.ver{border:1px solid #E4E4E7;border-left:3px solid #A1A1AA;border-radius:6px;
 padding:7px 11px;background:#FAFAFA;font-size:12.5px;max-width:560px}
.ver.formal{border-left-color:#15803D}
.ver.superseded{border-left-color:#A1A1AA;opacity:.72}
.ver.void{border-left-color:#DC2626}
.ver .vh{font-weight:600}
.ver .vs{color:#71717A;font-size:12px;margin-top:2px}
h3{font-size:13.5px;font-weight:650;margin:20px 0 10px;color:#3F3F46;
 display:flex;align-items:baseline;gap:9px}
h3 .n{color:#A1A1AA;font-weight:400;font-size:12px}
h3 em{font-style:normal;font-weight:400;color:#A1A1AA;font-size:11.5px}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(132px,1fr))}
.grid.wide{grid-template-columns:repeat(auto-fill,minmax(320px,1fr))}
figure{margin:0}
.frame{display:block;border:1px solid #E4E4E7;border-radius:8px;overflow:hidden;
 background:#fff;height:132px;position:relative}
.grid.wide .frame{height:240px}
.frame img{width:100%;height:100%;object-fit:contain;display:block}
body.ck .frame{background-color:#fff;
 background-image:linear-gradient(45deg,#EDEDEE 25%,transparent 25%),
  linear-gradient(-45deg,#EDEDEE 25%,transparent 25%),
  linear-gradient(45deg,transparent 75%,#EDEDEE 75%),
  linear-gradient(-45deg,transparent 75%,#EDEDEE 75%);
 background-size:16px 16px;background-position:0 0,0 8px,8px -8px,-8px 0}
figcaption{padding:5px 2px 0;font-size:11.5px;line-height:1.45}
.lb{color:#27272A;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bd{color:#A1A1AA;font-size:10.5px;display:block;white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis}
details{margin-top:14px;font-size:12.5px}
summary{cursor:pointer;color:#52525B}
.diag{margin:8px 0 0;padding:10px 12px;background:#FAFAFA;border:1px solid #E4E4E7;
 border-radius:7px;font-family:ui-monospace,Menlo,monospace;font-size:11.5px;white-space:pre-wrap}
.diag .err{color:#B91C1C}.diag .warn{color:#A16207}.diag .ok{color:#15803D}
footer{color:#A1A1AA;font-size:11.5px;padding:0 28px 40px;max-width:1560px;margin:0 auto}
"""

GALLERY_JS = """
(function(){
  var finish='white';
  function apply(){
    var imgs=document.querySelectorAll('img[data-white]');
    for(var i=0;i<imgs.length;i++){
      var im=imgs[i],t=im.getAttribute('data-trans');
      im.src=(finish==='transparent'&&t)?t:im.getAttribute('data-white');
    }
    var bs=document.querySelectorAll('[data-fin]');
    for(var j=0;j<bs.length;j++){
      var b=bs[j],t2=b.getAttribute('data-trans');
      b.textContent=(finish==='transparent'&&t2)?'透明':'白底';
    }
    var btns=document.querySelectorAll('.seg button[data-finish]');
    for(var k=0;k<btns.length;k++){
      btns[k].className=(btns[k].getAttribute('data-finish')===finish)?'on':'';
    }
  }
  var seg=document.querySelectorAll('.seg button[data-finish]');
  for(var i=0;i<seg.length;i++){
    seg[i].onclick=function(){finish=this.getAttribute('data-finish');apply();};
  }
  var ck=document.getElementById('ck');
  if(ck){ck.onclick=function(){document.body.classList.toggle('ck');
    ck.className=document.body.classList.contains('ck')?'on':'';};}
  apply();
})();
"""


def build_gallery(root, out_path):
    from collections import OrderedDict
    from html import escape

    def e(s):
        return escape(str(s if s is not None else ""), quote=True)

    chars = []
    tot_media = tot_deliv = tot_err = tot_warn = 0
    for cd in find_char_dirs(root):
        rp = os.path.join(cd, REGISTRY_NAME)
        if not os.path.exists(rp):
            continue
        reg = load_json(rp)
        mf = load_json(os.path.join(cd, MANIFEST_NAME))
        errs, warns = check_registry(cd, reg, mf)
        tot_err += len(errs)
        tot_warn += len(warns)
        chars.append({
            "dir": os.path.basename(cd), "reg": reg, "mf": mf,
            "errs": errs, "warns": warns,
            "media": reg.get("media") or [],
            "deliv": reg.get("derived_deliverables") or [],
        })
        tot_media += len(chars[-1]["media"])
        tot_deliv += len(chars[-1]["deliv"])

    h = []
    h.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    h.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
    h.append('<title>AIGC 角色资产库 · 总览</title>')
    h.append(f"<style>{GALLERY_CSS}</style></head><body>")

    stamp = __import__("time").strftime("%Y-%m-%d %H:%M")
    h.append('<header><div class="hrow">')
    h.append(f'<h1>AIGC 角色资产库</h1><span class="sub">生成 {e(stamp)} · '
             f'{len(chars)} 个角色 · {tot_media} 张媒体 · {tot_deliv} 个派生交付物 · '
             f'对账 {tot_err} ERROR / {tot_warn} WARN</span>')
    h.append('</div><div class="hrow" style="margin-top:10px">')
    h.append('<span class="sub">缩略图：</span>')
    h.append('<span class="seg"><button data-finish="white" class="on">白底</button>'
             '<button data-finish="transparent">透明</button></span>')
    h.append('<span class="seg"><button id="ck">棋盘格底</button></span>')
    h.append('<span class="sub">页面只读，不改动任何资产文件</span>')
    h.append('</div></header><main>')

    for c in chars:
        reg, dirn = c["reg"], c["dir"]
        h.append('<section class="char">')
        h.append('<div class="chead"><div>')
        h.append(f'<h2>{e(reg.get("code"))}<span class="name">{e(reg.get("display_name") or "—")}</span></h2>')
        h.append('<div class="meta">'
                 f'规格卡 <b>{e(reg.get("spec_card_current") or "未指定")}</b> · '
                 f'asset_key <code>{e(reg.get("character_asset_key"))}</code> · '
                 f'适用 <b>{e(reg.get("applicable_scope") or "—")}</b> · '
                 f'共享 <b>{e(reg.get("sharing_scope") or "—")}</b></div>')
        auth = reg.get("authorization_refs") or []
        astr = "、".join(str(a.get("type", "")) for a in auth if isinstance(a, dict)) or "未声明"
        h.append(f'<div class="meta">授权依据 <b>{e(astr)}</b></div>')
        h.append('</div>')

        gates = reg.get("gates") or {}
        gate_keys = BASE_GATES + [g for g in sorted(gates) if g not in BASE_GATES]
        h.append('<div class="gates">')
        for g in gate_keys:
            st = gates.get(g, "pending")
            h.append(f'<span class="gate {e(st)}" title="{e(g)}：{e(st)}">{e(g)}</span>')
        h.append('</div></div>')

        media, deliv = c["media"], c["deliv"]
        white = sum(1 for m in media if m.get("finish") == "white")
        trans = sum(1 for m in media if m.get("finish") == "transparent")
        done = sum(1 for g in gate_keys if gates.get(g) == "done")
        h.append('<div class="stats">'
                 f'<span>阶段门 <b>{done}/{len(gate_keys)} done</b></span>'
                 f'<span>媒体 <b>{len(media)}</b>（白底 {white} · 透明 {trans}）</span>'
                 f'<span>派生交付物 <b>{len(deliv)}</b></span>'
                 f'<span>对账 <b>{len(c["errs"])} ERROR / {len(c["warns"])} WARN</b></span>'
                 '</div>')

        pal = c["mf"].get("palette") or []
        if pal:
            h.append('<div class="pal">')
            for p in pal:
                if not isinstance(p, dict):
                    continue
                h.append(f'<span class="sw"><i style="background:{e(p.get("hex"))}"></i>'
                         f'{e(p.get("name"))} <code>{e(p.get("hex"))}</code></span>')
            h.append('</div>')

        vers = reg.get("asset_versions") or []
        if vers:
            h.append('<div class="vers">')
            for v in vers:
                st = v.get("asset_validity_status", "draft")
                fc = v.get("formal_confirmation") or {}
                h.append(f'<div class="ver {e(st)}">'
                         f'<div class="vh">L1 {e(v.get("asset_version"))} · '
                         f'{e(v.get("variant"))} · {e(st)}</div>'
                         f'<div class="vs">{e(v.get("costume_state_spec") or "（未填服装状态摘要）")}</div>'
                         + (f'<div class="vs">确认 {e(fc.get("date"))} · {e(fc.get("evidence"))}</div>'
                            if fc.get("date") else "")
                         + '</div>')
            h.append('</div>')

        # L2 资产媒体：按 unit_type → label/version/role 归并白底+透明
        groups = OrderedDict()
        for m in media:
            key = (m.get("unit_type"), m.get("label"), m.get("unit_version"),
                   m.get("role", "single"))
            groups.setdefault(key, {})[m.get("finish")] = m.get("path")
        order = {u: i for i, u in enumerate(UNIT_ORDER)}
        keys = sorted(groups, key=lambda k: (order.get(k[0], 99), str(k[1]), vkey(k[2])))

        by_unit = OrderedDict()
        for k in keys:
            by_unit.setdefault(k[0], []).append(k)

        for ut, ks in by_unit.items():
            h.append(f'<h3>{e(UNIT_LABELS.get(ut, ut))}<span class="n">{len(ks)} 单元 · '
                     f'{sum(len(groups[k]) for k in ks)} 张</span></h3>')
            h.append('<div class="grid">')
            for k in ks:
                _, label, uver, role = k
                fins = groups[k]
                # 缩略图优先白底；无白底则退回透明/平底，并如实标注初始底色
                wfin = "white" if fins.get("white") else (
                    "flat" if fins.get("flat") else "transparent")
                w = fins.get(wfin)
                t = fins.get("transparent")
                h.append('<figure>')
                h.append(f'<a class="frame" href="{e(dirn)}/{e(w)}" target="_blank" '
                         f'title="打开原图：{e(w)}">')
                h.append(f'<img src="{e(dirn)}/{e(w)}" data-white="{e(dirn)}/{e(w)}"'
                         + (f' data-trans="{e(dirn)}/{e(t)}"' if t else "")
                         + f' loading="lazy" decoding="async" alt="{e(label)}">')
                h.append('</a>')
                h.append(f'<figcaption><span class="lb" title="{e(label)}">{e(label)}</span>'
                         f'<span class="bd">{e(uver)}'
                         + (f' · {e(ROLE_LABELS.get(role))}' if ROLE_LABELS.get(role) else "")
                         + f' · <span data-fin data-trans="{e(t or "")}">'
                         f'{e(FINISH_LABELS.get(wfin))}</span></span>'
                         '</figcaption></figure>')
            h.append('</div>')

        # L3 派生交付物
        if deliv:
            h.append('<h3>派生交付物<span class="n">%d 个</span>'
                     '<em>04 中暂无对应对象（本地扩展）</em></h3>' % len(deliv))
            h.append('<div class="grid wide">')
            dk = sorted(deliv, key=lambda d: (str(d.get("deliverable_type")),
                                              vkey(d.get("unit_version")), str(d.get("variant"))))
            for d in dk:
                p = d.get("path")
                lb = f'{DELIV_LABELS.get(d.get("deliverable_type"), d.get("deliverable_type"))} · ' \
                     f'{DELIV_VARIANT.get(d.get("variant"), d.get("variant"))}'
                h.append('<figure>')
                h.append(f'<a class="frame" href="{e(dirn)}/{e(p)}" target="_blank" '
                         f'title="打开原图：{e(p)}">')
                h.append(f'<img src="{e(dirn)}/{e(p)}" loading="lazy" decoding="async" '
                         f'alt="{e(lb)}">')
                h.append('</a>')
                h.append(f'<figcaption><span class="lb">{e(lb)}</span>'
                         f'<span class="bd">{e(d.get("unit_version"))} · {e(d.get("gate"))}</span>'
                         '</figcaption></figure>')
            h.append('</div>')

        if c["errs"] or c["warns"]:
            h.append(f'<details><summary>对账明细（{len(c["errs"])} ERROR / '
                     f'{len(c["warns"])} WARN）</summary><div class="diag">')
            for code, msg in c["errs"]:
                h.append(f'<span class="err">✗ {e(code)} {e(msg)}</span>')
            for code, msg in c["warns"]:
                h.append(f'<span class="warn">! {e(code)} {e(msg)}</span>')
            h.append('</div></details>')
        todo = reg.get("_todo_human") or []
        if todo:
            h.append('<details><summary>待人工补充（%d 项）</summary><div class="diag">' % len(todo))
            for t in todo:
                h.append(f'<span class="warn">· {e(t)}</span>')
            h.append('</div></details>')

        h.append('</section>')

    h.append('</main><footer>本页由 <code>kit_asset_index.py --gallery</code> 从各角色 '
             '<code>资产档案.json</code> 生成，可随时重跑；标签一律置于资产画面之外，'
             '不覆盖任何像素。资产本体未被复制或修改。</footer>')
    h.append(f"<script>{GALLERY_JS}</script></body></html>")

    doc = "\n".join(h)
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write(doc)
    return out_path, len(chars), tot_media, tot_deliv


# ---------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="资产档案索引与对账")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="库根（默认当前工作目录）")
    ap.add_argument("--char", default=None, help="角色目录名，如 CHAR-01-demo")
    ap.add_argument("--all", action="store_true", help="对库内全部角色执行")
    ap.add_argument("--scaffold", action="store_true", help="生成/刷新 资产档案.json")
    ap.add_argument("--check", action="store_true", help="对账（只读，不写任何文件）")
    ap.add_argument("--report", action="store_true", help="库级总览")
    ap.add_argument("--gallery", action="store_true",
                    help="生成自包含静态总览页（只读资产，仅在库根写 1 个 html）")
    ap.add_argument("--out", default=None, help="--gallery 输出路径（默认 <库根>/资产总览.html）")
    args = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(args.root))
    if not (args.char or args.all or args.report or args.gallery):
        ap.error("至少指定 --char、--all、--report 或 --gallery")
    if args.all and args.char:
        ap.error("--all（按库根枚举全部角色）与 --char（指定单个角色）不能同时使用；"
                 "包内单角色用 --char .，库级操作用 --root <库根> --all")

    if args.gallery:
        out = os.path.abspath(os.path.expanduser(args.out)) if args.out \
            else os.path.join(root, "资产总览.html")
        path, n, nm, nd = build_gallery(root, out)
        print(f"[gallery] {path}（{n} 个角色，{nm} 张媒体，{nd} 个派生交付物）")
        print("          双击即可打开；页面只读，未改动任何资产文件")
        return 0

    if args.report or args.all:
        if args.all and not os.path.isdir(root):
            print(f"[error] 库根不存在：{root}（请用 --root 指定已存在的库根）", file=sys.stderr)
            return 2
        chars = find_char_dirs(root) if args.all or args.report else []
        if not chars:
            print(f"[error] 在库根 {root} 下未找到任何角色目录（含 {MANIFEST_NAME} 的目录）。"
                  "若你在角色包内操作，请改用 --char .", file=sys.stderr)
            return 2
    else:
        chars = [resolve_char(args.char, root)]

    if args.scaffold and args.check:
        ap.error("--scaffold 与 --check 不能同时使用（一个写、一个只读）")

    rc = 0
    if args.report and not (args.scaffold or args.check):
        return report(root)

    for cd in chars:
        name = os.path.basename(cd)
        mf = load_json(os.path.join(cd, MANIFEST_NAME))
        rp = os.path.join(cd, REGISTRY_NAME)

        if args.scaffold:
            old = load_json(rp) if os.path.exists(rp) else None
            reg = build_registry(cd, mf, old)
            unstamped = reg.pop("_unstamped_new", [])
            with open(rp, "w", encoding="utf-8") as fp:
                json.dump(reg, fp, ensure_ascii=False, indent=2)
                fp.write("\n")
            print(f"[scaffold] {name} → {REGISTRY_NAME}"
                  f"（media {len(reg['media'])}，交付物 {len(reg['derived_deliverables'])}，"
                  f"规格卡 {reg['spec_card_current'] or '未找到'}）")
            if reg.get("contract") == "v3":
                if unstamped:
                    print(f"          ⚠ v3 档案：{len(unstamped)} 个新增文件尚无 asset_id：")
                    for p in unstamped[:8]:
                        print(f"            · {p}")
                    if len(unstamped) > 8:
                        print(f"            · …另有 {len(unstamped) - 8} 个")
                    print("          请随后用上层资产中心工具链的 --assign-ids 增量补 ID"
                          "（本 Skill 的 G0-G14 流程使用 v1 档案，不含该工具）")
                else:
                    print("          v3 守卫：全部行的 asset_id/content_id 已按路径保留 ✓")
            continue

        if args.check or args.all:
            if not os.path.exists(rp):
                print(f"[check] {name}: 缺 {REGISTRY_NAME}，先跑 --scaffold")
                rc = 1
                continue
            reg = load_json(rp)
            errs, warns = check_registry(cd, reg, mf)
            print(f"[check] {name}: ERROR {len(errs)}，WARN {len(warns)}")
            for code, msg in errs:
                print(f"   ✗ {code} {msg}")
            for code, msg in warns:
                print(f"   ! {code} {msg}")
            if errs:
                rc = 1

    return rc


if __name__ == "__main__":
    sys.exit(main())
