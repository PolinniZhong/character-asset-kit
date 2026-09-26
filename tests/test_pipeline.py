#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""确定性像素工序测试：落格几何、色键兜底、微表情空族跳过。"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BIN = os.path.join(SKILL, "scripts", "bin")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

from charkit.assets import standard_cell, square_cell  # noqa: E402
from charkit import boards  # noqa: E402


def load_module(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(BIN, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


colorkey = load_module("kit_colorkey_cutout", "kit_colorkey_cutout.py")


def opaque(w, h, color=(60, 72, 92, 255)):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([w // 4, 0, w * 3 // 4, h], fill=color)
    return im


class GeometryTest(unittest.TestCase):
    def test_tall_subject_bad_params_raises(self):
        # #006 回归：fig_ratio=0.72 + sole_ratio=0.5 对高主体必然裁顶，必须显式报错
        cut = opaque(400, 1000)
        with self.assertRaises(ValueError) as cx:
            standard_cell(cut, cell_w=2048, cell_h=2048,
                          fig_ratio=0.72, sole_ratio=0.5)
        self.assertIn("越界", str(cx.exception))

    def test_square_cell_default_is_2364(self):
        # #004 回归：方格默认边长服从实现 = 标准格长边 2364
        cut = opaque(300, 500)
        white, transparent = square_cell(cut)
        self.assertEqual(white.size, (2364, 2364))
        self.assertEqual(transparent.size, (2364, 2364))

    def test_square_cell_keeps_subject_inside(self):
        cut = opaque(300, 500)
        _, transparent = square_cell(cut, cell=1024)
        bbox = transparent.getbbox()
        self.assertIsNotNone(bbox)
        self.assertGreaterEqual(bbox[0], 0)
        self.assertLessEqual(bbox[2], 1024)
        self.assertGreaterEqual(bbox[1], 0)
        self.assertLessEqual(bbox[3], 1024)


class ColorkeyTest(unittest.TestCase):
    def test_white_border_removed_dark_subject_kept(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "raw.png")
            dst = os.path.join(td, "cut.png")
            im = Image.new("RGB", (512, 512), (255, 255, 255))
            d = ImageDraw.Draw(im)
            d.rectangle([180, 120, 330, 400], fill=(45, 50, 60))
            im.save(src)
            ratio = colorkey.colorkey_cutout(src, dst)
            out = Image.open(dst).convert("RGBA")
            self.assertEqual(out.size, (512, 512))
            # 四角背景透明
            for xy in ((0, 0), (511, 0), (0, 511), (511, 511)):
                self.assertEqual(out.getpixel(xy)[3], 0)
            # 深色主体中心保留
            self.assertEqual(out.getpixel((256, 260))[3], 255)
            # 背景占比合理（主体约占 1/4 画面）
            self.assertGreater(ratio, 0.3)
            self.assertLess(ratio, 0.95)

    def test_enclosed_white_is_not_removed(self):
        # 泛洪只从四边进入：被主体围住的白色（白 T/白板鞋语义）必须保留
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "raw.png")
            dst = os.path.join(td, "cut.png")
            im = Image.new("RGB", (400, 400), (255, 255, 255))
            d = ImageDraw.Draw(im)
            d.rectangle([100, 100, 300, 300], fill=(40, 40, 50))   # 深色主体
            d.rectangle([170, 170, 230, 230], fill=(255, 255, 255))  # 围住的白
            im.save(src)
            colorkey.colorkey_cutout(src, dst, feather=0)
            out = Image.open(dst).convert("RGBA")
            self.assertEqual(out.getpixel((200, 200))[3], 255)


class MicroExpressionTest(unittest.TestCase):
    def test_empty_level_families_skipped(self):
        # #008 回归：levels 为空的可选族不得渲染空白行
        with tempfile.TemporaryDirectory() as td:
            cell_dir = os.path.join(td, "04_表情", "单图")
            os.makedirs(cell_dir)
            for name in ("neutral.png", "e1l1.png"):
                im = Image.new("RGB", (1773, 2364), (238, 238, 238))
                ImageDraw.Draw(im).ellipse([500, 300, 1273, 1900], fill=(180, 150, 120))
                im.save(os.path.join(cell_dir, name))
            out_clean = "04_表情/拼板/micro_clean.png"
            os.makedirs(os.path.join(td, "04_表情", "拼板"))
            mf = {
                "palette": [],
                "boards": {
                    "micro_expression": {
                        "version": "v1.0",
                        "meta": "",
                        "neutral_ref": "04_表情/单图/neutral.png",
                        "out_clean": out_clean,
                        "out_review": "04_表情/拼板/micro_review.png",
                        "families": [
                            {"label": "喜悦", "levels": [
                                {"label": "喜悦 L1", "white": "04_表情/单图/e1l1.png"}]},
                            {"label": "难过", "levels": [], "optional": True},
                            {"label": "生气", "levels": [], "optional": True},
                        ],
                    }
                },
            }
            path = boards.build_micro_expression(td, mf)
            self.assertTrue(os.path.exists(path))
            with Image.open(path) as im:
                self.assertEqual(im.size[0], 4320)
                # 基准轴 1 行 + 1 个有级族 = 2 行：H = 120 + 2*(1080+150) + 120
                self.assertEqual(im.size[1], 2700)


if __name__ == "__main__":
    unittest.main()
