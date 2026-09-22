#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新角色立项脚手架：按标准目录树建角色包，灌入规格卡/资产清单/提示词库骨架。

用法：
  python3 kit_init_character.py --dir CHAR-01-slug --root /path/to/library
  [--code CHAR-01]
不传 --root 时以当前工作目录为库根。
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
TEMPLATE_DIR = os.path.join(SKILL_ROOT, "templates")
MASK_SWIFT = os.path.join(HERE, "subjectmask.swift")
MASK_BIN = os.path.join(HERE, "subjectmask")

# 标准插槽目录树（编号即生产顺序；扩展门目录在用到时再建）
TREE = [
    "01_母版",
    "02_多视图/单图", "02_多视图/拼板",
    "03_表情/单图", "03_表情/拼板",
    "04_细节特写/单图", "04_细节特写/拼板",
    "05_营销胸像",
    "06_动作姿态/单图", "06_动作姿态/拼板",
    "07_道具/单体独立图", "07_道具/手持关系", "07_道具/配饰变体", "07_道具/拼板",
    "08_提示词库",
    "09_风格变体",
    "10_商卡成品",
    "11_训练素材",
    "12_场景包/场景母版", "12_场景包/单图", "12_场景包/拼板",
    "99_过程稿",
]

PROMPT_DOCS = [
    "{code}_母版提示词_v1.0.md",
    "{code}_多视图设定图板提示词_v1.0.md",
    "{code}_表情提示词_v1.0.md",
    "{code}_细节特写提示词_v1.0.md",
    "{code}_动作姿态提示词_v1.0.md",
    "{code}_单体道具提示词_v1.0.md",
]


def ensure_mask_binary():
    """抠图依赖 macOS Vision（subjectmask.swift）。缺二进制时尝试本机编译。"""
    if os.path.exists(MASK_BIN):
        return True
    if not os.path.exists(MASK_SWIFT) or sys.platform != "darwin":
        return False
    try:
        subprocess.run(["swiftc", MASK_SWIFT, "-o", MASK_BIN], check=True,
                       capture_output=True)
        return os.path.exists(MASK_BIN)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="角色包目录名，如 CHAR-01-slug")
    ap.add_argument("--root", default=os.getcwd(), help="库根（默认当前目录）")
    ap.add_argument("--code", default=None, help="角色代号，默认取目录名 '-' 前两段")
    args = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(args.root))
    char_dir = os.path.join(root, args.dir)
    code = args.code or "-".join(args.dir.split("-")[:2])
    if os.path.exists(char_dir):
        raise SystemExit(f"目录已存在，避免覆盖：{char_dir}")

    for sub in TREE:
        os.makedirs(os.path.join(char_dir, sub), exist_ok=True)

    # 规格卡
    spec_tpl = os.path.join(TEMPLATE_DIR, "角色规格卡_模板.md")
    with open(spec_tpl, encoding="utf-8") as fp:
        spec = fp.read().replace("{CODE}", code)
    with open(os.path.join(char_dir, f"00_角色规格卡_{code}_v1.0.md"), "w", encoding="utf-8") as fp:
        fp.write(spec)

    # 资产清单
    mf_tpl = os.path.join(TEMPLATE_DIR, "资产清单_模板.json")
    with open(mf_tpl, encoding="utf-8") as fp:
        mf = fp.read().replace("{CODE}", code)
    with open(os.path.join(char_dir, "资产清单.json"), "w", encoding="utf-8") as fp:
        fp.write(mf)

    # 提示词库骨架
    for name in PROMPT_DOCS:
        p = os.path.join(char_dir, "08_提示词库", name.format(code=code))
        with open(p, "w", encoding="utf-8") as fp:
            fp.write(f"# {code} 提示词文档\n\n> 每个定稿提示词按「用途 / 参考图喂料 / 提示词原文 / 尺寸口径 / 验收结论 / bad case」六段追加沉淀。\n\n")

    # 抠图工具随角色放一份（部分流程要求在角色目录下调用）
    if ensure_mask_binary():
        shutil.copy(MASK_BIN, os.path.join(char_dir, "subjectmask"))
        if os.path.exists(MASK_SWIFT):
            shutil.copy(MASK_SWIFT, os.path.join(char_dir, "subjectmask.swift"))
        print("subjectmask（macOS Vision 抠图）已随包复制。")
    else:
        print("提示：未生成 subjectmask 二进制（非 macOS 或缺少 swiftc）；")
        print("      抠图/标准格流程在 macOS 上执行，或先 `swiftc scripts/bin/subjectmask.swift -o subjectmask`。")

    print("角色包已创建：", char_dir)
    print("下一步：填写规格卡身份签名 → G1 母版 → 逐单元生产（见 Skill 的 references/gates-g0-g9.md）")


if __name__ == "__main__":
    main()
