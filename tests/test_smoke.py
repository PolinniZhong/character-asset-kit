#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端冒烟与 CLI 守卫测试（纯标准库 + Pillow，不联网、不依赖 macOS Vision）。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BIN = os.path.join(SKILL, "scripts", "bin")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

PY = sys.executable
CODE = "CHAR-01-demo"
DIR = CODE


def run(*args):
    return subprocess.run([PY] + list(args), capture_output=True, text=True)


class SmokeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = self.tmp.name
        self.char = os.path.join(self.lib, DIR)
        r = run(os.path.join(BIN, "kit_init_character.py"),
                "--dir", DIR, "--root", self.lib, "--code", CODE)
        self.assertEqual(r.returncode, 0, r.stderr)

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_creates_full_skeleton(self):
        # 规格卡、清单、档案插槽齐全
        self.assertTrue(os.path.exists(
            os.path.join(self.char, f"00_角色规格卡_{CODE}_v1.0.md")))
        with open(os.path.join(self.char, "资产清单.json"), encoding="utf-8") as fp:
            mf = json.load(fp)
        # #001 回归：模板必须内置全部九种板配置（含 character_sheet）
        for k in ("multiview", "expression", "detail", "pose", "prop",
                  "micro_expression", "gaze", "character_sheet", "card"):
            self.assertIn(k, mf["boards"], f"模板缺 boards.{k}（#001 回归）")
        for slot in ("01_母版", "02_多视图", "03_表情", "04_细节特写", "05_营销胸像",
                     "06_动作姿态", "07_道具", "08_提示词库", "12_场景包"):
            self.assertTrue(os.path.isdir(os.path.join(self.char, slot)), slot)

    def test_empty_package_scaffold_and_check(self):
        r = run(os.path.join(BIN, "kit_asset_index.py"),
                "--root", self.lib, "--char", DIR, "--scaffold")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.char, "资产档案.json")))
        r = run(os.path.join(BIN, "kit_asset_index.py"),
                "--root", self.lib, "--char", DIR, "--check")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("ERROR 0", r.stdout + r.stderr)

    def test_all_and_char_are_mutually_exclusive(self):
        # #007 回归：argparse 互斥 → exit 2，不允许静默空跑
        r = run(os.path.join(BIN, "kit_asset_index.py"),
                "--root", self.lib, "--all", "--char", ".", "--check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("不能同时使用", r.stderr)

    def test_all_on_empty_library_errors(self):
        # #007 回归：库根下没有任何角色 → exit 2，不是假绿灯
        empty = tempfile.mkdtemp(dir=self.tmp.name)
        r = run(os.path.join(BIN, "kit_asset_index.py"),
                "--root", empty, "--all", "--check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("未找到任何角色目录", r.stderr)

    def test_nonexistent_library_root_errors(self):
        r = run(os.path.join(BIN, "kit_asset_index.py"),
                "--root", os.path.join(self.lib, "nope"), "--all", "--check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("库根不存在", r.stderr)

    def test_scaffold_and_check_mutex(self):
        r = run(os.path.join(BIN, "kit_asset_index.py"),
                "--root", self.lib, "--char", DIR, "--scaffold", "--check")
        self.assertEqual(r.returncode, 2)

    def test_build_board_missing_section_exits_2(self):
        # #001 回归：缺 boards.character_sheet 必须明确报错，不许 KeyError/静默跳过
        other = os.path.join(self.lib, "CHAR-02-bare")
        os.makedirs(other)
        with open(os.path.join(other, "资产清单.json"), "w", encoding="utf-8") as fp:
            json.dump({"boards": {"multiview": {}}}, fp)
        r = run(os.path.join(BIN, "kit_build_board.py"),
                "--char", other, "--type", "character_sheet")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("配置段缺失", r.stderr)

    def test_build_board_all_warns_missing_core(self):
        # #001 回归：--type all 对缺失的核心板打 WARN（用假构建器隔离像素工序）
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "kit_build_board", os.path.join(BIN, "kit_build_board.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        other = os.path.join(self.lib, "CHAR-03-partial")
        os.makedirs(other)
        with open(os.path.join(other, "资产清单.json"), "w", encoding="utf-8") as fp:
            json.dump({"boards": {k: {} for k in
                      ("multiview", "expression", "detail", "pose", "prop")}}, fp)
        called = []

        def fake(char_dir, mf, guides=False):
            called.append(True)
            return "fake.png"

        mod.BUILDERS = {k: fake for k in
                        ("multiview", "expression", "detail", "pose", "prop", "card")}
        oldargv = sys.argv
        sys.argv = ["kit_build_board.py", "--char", other, "--type", "all"]
        try:
            from io import StringIO
            from contextlib import redirect_stdout, redirect_stderr
            out, err = StringIO(), StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = mod.main()
        finally:
            sys.argv = oldargv
        self.assertEqual(rc, None)  # 已配置的板照常构建
        # 五个存在的板：四块技术板各出干净版+验收版(8)，prop 与 card 各 1 → 10
        self.assertEqual(len(called), 10)
        self.assertIn("核心板型 character_sheet", out.getvalue() + err.getvalue())


if __name__ == "__main__":
    unittest.main()
