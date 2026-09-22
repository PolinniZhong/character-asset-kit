#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kit_generate 适配器测试：全部离线，monkeypatch 唯一网络出口，不发真实请求。"""
import base64
import importlib.util
import io
import json
import os
import tempfile
import unittest
import urllib.error

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "scripts", "bin")


def load_gen():
    spec = importlib.util.spec_from_file_location(
        "kit_generate", os.path.join(BIN, "kit_generate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = load_gen()


def tiny_b64(fmt="PNG", color=(200, 200, 200)):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


class FakeResp:
    def __init__(self, raw):
        self._raw = raw

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def json_resp(obj):
    return FakeResp(json.dumps(obj).encode())


class SizeMapTest(unittest.TestCase):
    def test_classify_and_aspect(self):
        kind, w, h = gen.classify_size("1773x2364")
        self.assertEqual(kind, "portrait")
        self.assertEqual(gen.nearest_aspect(w, h), "3:4")
        kind, w, h = gen.classify_size("2560x1440")
        self.assertEqual(kind, "landscape")
        self.assertEqual(gen.nearest_aspect(w, h), "16:9")
        kind, _, _ = gen.classify_size("2048x2048")
        self.assertEqual(kind, "square")

    def test_gpt_map(self):
        self.assertEqual(gen.GPT_IMAGE_SIZES["portrait"], "1024x1536")

    def test_bad_size(self):
        for bad in ("abc", "0x100", "100"):
            with self.assertRaises(ValueError):
                gen.classify_size(bad)


class GenerateCLITest(unittest.TestCase):
    def setUp(self):
        for k in ("OPENAI_API_KEY", "ARK_API_KEY", "GOOGLE_API_KEY",
                  "OPENROUTER_API_KEY", "OPENAI_BASE_URL",
                  "OPENAI_IMAGE_MODEL", "GOOGLE_IMAGE_MODEL", "OPENROUTER_IMAGE_MODEL"):
            os.environ.pop(k, None)
        os.environ["OPENAI_API_KEY"] = "test-key"
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "raw.png")
        self.refs = []
        for i, color in enumerate([(240, 240, 240), (210, 210, 210), (180, 180, 180), (150, 150, 150)]):
            p = os.path.join(self.tmp.name, f"ref{i}.png")
            Image.new("RGB", (16, 16), color).save(p)
            self.refs.append(p)
        self.calls = []
        self._orig_urlopen, self._orig_sleep = gen._urlopen, gen._sleep
        gen._sleep = lambda sec: None

    def tearDown(self):
        gen._urlopen, gen._sleep = self._orig_urlopen, self._orig_sleep
        self.tmp.cleanup()

    def fake(self, obj=None, exc_seq=()):
        """exc_seq: 前 N 次调用抛异常，之后返回 obj。"""
        state = {"i": 0}
        exc_seq = list(exc_seq)

        def _fake(req, timeout=600):
            self.calls.append(req)
            if state["i"] < len(exc_seq):
                e = exc_seq[state["i"]]
                state["i"] += 1
                raise e
            state["i"] += 1
            return json_resp(obj if obj is not None else
                             {"data": [{"b64_json": tiny_b64(), "media_type": "image/png"}]})
        gen._urlopen = _fake

    # ---------- OpenAI ----------
    def test_openai_gen_payload(self):
        self.fake()
        rc = gen.main(["--provider", "openai", "--mode", "gen",
                       "--prompt", "blindbox 3d character, white background",
                       "--size", "1773x2364", "--out", self.out])
        self.assertEqual(rc, 0)
        req = self.calls[0]
        self.assertTrue(req.full_url.endswith("/images/generations"))
        self.assertEqual(req.headers["Authorization"], "Bearer test-key")
        payload = json.loads(req.data.decode())
        self.assertEqual(payload["model"], "gpt-image-2.5-flare")
        self.assertEqual(payload["size"], "1024x1536")
        self.assertEqual(payload["n"], 1)
        self.assertEqual(payload["quality"], "high")
        with Image.open(self.out) as im:
            self.assertEqual(im.format, "PNG")

    def test_env_model_override(self):
        self.fake()
        os.environ["OPENAI_IMAGE_MODEL"] = "gpt-image-1"
        rc = gen.main(["--provider", "openai", "--prompt", "x", "--out", self.out])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(self.calls[0].data.decode())["model"], "gpt-image-1")

    def test_openai_edit_multipart_multi_refs(self):
        self.fake()
        rc = gen.main(["--provider", "openai", "--mode", "edit",
                       "--prompt", "side view, same character",
                       "--ref", self.refs[0], "--ref", self.refs[1],
                       "--size", "2048x2048", "--out", self.out])
        self.assertEqual(rc, 0)
        req = self.calls[0]
        self.assertTrue(req.full_url.endswith("/images/edits"))
        body = req.data.decode("latin-1")
        self.assertEqual(body.count('name="image[]"'), 2)
        self.assertIn("ref0.png", body)
        self.assertIn("1024x1024", body)

    def test_openai_edit_single_ref_field(self):
        self.fake()
        rc = gen.main(["--provider", "openai", "--mode", "edit",
                       "--prompt", "x", "--ref", self.refs[0], "--out", self.out])
        self.assertEqual(rc, 0)
        body = self.calls[0].data.decode("latin-1")
        self.assertIn('name="image"', body)
        self.assertNotIn('name="image[]"', body)

    # ---------- Google Gemini ----------
    def test_google_gen_uses_aspect_and_inline_refs(self):
        obj = {"candidates": [{"content": {"parts": [
            {"inlineData": {"mimeType": "image/jpeg", "data": tiny_b64("JPEG")}}]}}]}
        self.fake(obj)
        os.environ["GOOGLE_API_KEY"] = "g-key"
        rc = gen.main(["--provider", "google", "--mode", "edit",
                       "--prompt", "same character, back view",
                       "--ref", self.refs[0], "--ref", self.refs[1],
                       "--size", "1773x2364", "--out", self.out])
        self.assertEqual(rc, 0)
        req = self.calls[0]
        self.assertIn("gemini-2.5-flash-image:generateContent", req.full_url)
        self.assertEqual(req.headers["X-goog-api-key"], "g-key")
        payload = json.loads(req.data.decode())
        self.assertEqual(payload["generationConfig"]["imageConfig"]["aspectRatio"], "3:4")
        inline = [p for p in payload["contents"][0]["parts"] if "inline_data" in p]
        self.assertEqual(len(inline), 2)
        with Image.open(self.out) as im:       # JPEG 返回被归一为 PNG
            self.assertEqual(im.format, "PNG")

    def test_google_ref_limit(self):
        self.fake()
        os.environ["GOOGLE_API_KEY"] = "g-key"
        argv = ["--provider", "google", "--mode", "edit", "--prompt", "x"]
        for r in self.refs[:4]:
            argv += ["--ref", r]
        argv += ["--out", self.out]
        rc = gen.main(argv)
        self.assertEqual(rc, 2)
        self.assertEqual(self.calls, [])

    # ---------- OpenRouter ----------
    def test_openrouter_unified_images_endpoint(self):
        self.fake()
        os.environ["OPENROUTER_API_KEY"] = "or-key"
        rc = gen.main(["--provider", "openrouter", "--mode", "edit",
                       "--model", "bytedance-seed/seedream-4.5",
                       "--prompt", "x", "--ref", self.refs[0],
                       "--size", "2560x1440", "--out", self.out])
        self.assertEqual(rc, 0)
        req = self.calls[0]
        self.assertTrue(req.full_url.endswith("/images"))
        payload = json.loads(req.data.decode())
        self.assertEqual(payload["model"], "bytedance-seed/seedream-4.5")
        self.assertEqual(payload["aspect_ratio"], "16:9")
        self.assertEqual(len(payload["input_references"]), 1)
        self.assertEqual(payload["input_references"][0]["media_type"], "image/png")

    def test_autodetect_prefers_openrouter(self):
        self.fake()
        os.environ["OPENROUTER_API_KEY"] = "or-key"
        rc = gen.main(["--prompt", "x", "--out", self.out])
        self.assertEqual(rc, 0)
        self.assertIn("openrouter.ai", self.calls[0].full_url)

    # ---------- 重试 / 错误 ----------
    def test_retries_on_429_then_succeeds(self):
        err = urllib.error.HTTPError(
            "u", 429, "Too Many", {}, io.BytesIO(b"{}"))
        self.fake(exc_seq=(err, err))
        rc = gen.main(["--provider", "openai", "--prompt", "x", "--out", self.out])
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 3)

    def test_4xx_is_final(self):
        err = urllib.error.HTTPError(
            "u", 400, "Bad Request", {}, io.BytesIO(b'{"error":"bad"}'))
        self.fake(exc_seq=(err,))
        rc = gen.main(["--provider", "openai", "--prompt", "x", "--out", self.out])
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.calls), 1)

    def test_missing_key_exits_2(self):
        del os.environ["OPENAI_API_KEY"]
        rc = gen.main(["--provider", "openai", "--prompt", "x", "--out", self.out])
        self.assertEqual(rc, 2)

    def test_ark_requires_model(self):
        os.environ["ARK_API_KEY"] = "ark-key"
        rc = gen.main(["--provider", "ark", "--prompt", "x", "--out", self.out])
        self.assertEqual(rc, 2)

    def test_doubao_guides_to_host_tools(self):
        rc = gen.main(["--provider", "doubao", "--prompt", "x", "--out", self.out])
        self.assertEqual(rc, 2)
        self.assertEqual(self.calls, [])

    def test_edit_without_ref_exits_2(self):
        rc = gen.main(["--provider", "openai", "--mode", "edit",
                       "--prompt", "x", "--out", self.out])
        self.assertEqual(rc, 2)

    def test_no_prompt_exits_2(self):
        rc = gen.main(["--provider", "openai", "--out", self.out])
        self.assertEqual(rc, 2)

    def test_dry_run_makes_no_call_and_no_key(self):
        def must_not_call(*a, **k):
            raise AssertionError("dry-run 不得发请求")
        gen._urlopen = must_not_call
        del os.environ["OPENAI_API_KEY"]
        rc = gen.main(["--provider", "openai", "--mode", "edit",
                       "--prompt", "x", "--ref", self.refs[0],
                       "--size", "1773x2364", "--dry-run"])
        self.assertEqual(rc, 0)

    def test_custom_base_url_keep_size(self):
        self.fake()
        rc = gen.main(["--provider", "custom", "--base-url", "https://gw.example.com/v1",
                       "--model", "some-image-model", "--prompt", "x",
                       "--size", "1773x2364", "--keep-size", "--out", self.out])
        self.assertEqual(rc, 0)
        req = self.calls[0]
        self.assertEqual(req.full_url, "https://gw.example.com/v1/images/generations")
        self.assertEqual(json.loads(req.data.decode())["size"], "1773x2364")


if __name__ == "__main__":
    unittest.main()
