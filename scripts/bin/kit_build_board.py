#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按资产清单构建角色拼板。

用法：
  python3 kit_build_board.py --char <角色目录> --type <板型> [--review]
  python3 kit_build_board.py --char /path/to/library/CHAR-01-demo --type all
板型：multiview / expression / detail / pose / prop / micro_expression / gaze / card /
      character_sheet / all
--review：multiview/expression/detail/pose 同时（或仅）出验收版（对齐线/格框）。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from charkit.boards import BUILDERS  # noqa: E402


def load_manifest(char_dir):
    p = os.path.join(char_dir, "资产清单.json")
    with open(p, encoding="utf-8") as fp:
        return json.load(fp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True, help="角色目录（含 资产清单.json）")
    ap.add_argument("--type", required=True, choices=list(BUILDERS.keys()) + ["all"])
    ap.add_argument("--review", action="store_true", help="出验收版（仅四类技术板）")
    args = ap.parse_args()

    char_dir = os.path.abspath(os.path.expanduser(args.char))
    mf = load_manifest(char_dir)
    base_kinds = ["multiview", "expression", "detail", "pose", "prop",
                  "micro_expression", "gaze", "card", "character_sheet"]
    core_kinds = {"multiview", "expression", "detail", "pose", "prop",
                  "card", "character_sheet"}  # G0-G9 核心门；micro_expression/gaze 为扩展门
    if args.type == "all":
        boards = mf.get("boards", {})
        kinds = [k for k in base_kinds if k == "card" or k in boards]
        skipped_core = [k for k in core_kinds if k != "card" and k not in boards]
        for k in skipped_core:
            print(f"[warn] 核心板型 {k} 在资产清单 boards 中缺配置段，已跳过（模板已内置该段；"
                  f"若是裁剪掉的门请忽略）")
    else:
        kinds = [args.type]
        if args.type != "card" and args.type not in mf.get("boards", {}):
            print(f"[error] 资产清单 boards.{args.type} 配置段缺失。"
                  f"请对照 templates/资产清单_模板.json 中同名段补齐（含 out/out_clean 等键）后再构建。",
                  file=sys.stderr)
            return 2
    for k in kinds:
        technical = k in ("multiview", "expression", "detail", "pose",
                          "micro_expression", "gaze", "character_sheet")
        if technical and args.review and args.type != "all":
            print("saved", BUILDERS[k](char_dir, mf, guides=True))
            continue
        print("saved", BUILDERS[k](char_dir, mf, guides=False))
        if technical and (args.review or args.type == "all"):
            print("saved", BUILDERS[k](char_dir, mf, guides=True))


if __name__ == "__main__":
    sys.exit(main())
