#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kit_generate.py — 跨运行时生图适配器（生产线的"手"，可替换）。

skill 的确定性脚本不绑定任何生图厂商：
- 豆包运行时：由宿主 image_gen/image_edit 工具出图（不经过本脚本，--provider doubao 会给出指引）；
- 其他运行时：本脚本直连多家图像 API，把 raw 落到 99_过程稿/，再由 kit_standard_cell 抠图落格。

provider（2026-09-22 依据公开 skill/API 文档实现，未持密钥做真机验证；--dry-run 可离线核对请求）：
  openai      OpenAI Images（/images/generations、/images/edits；默认 gpt-image-2.5-flare）
  google      Gemini 图像（generateContent；默认 gemini-2.5-flash-image，多参考图强）
  openrouter  OpenRouter Images 统一网关（一把 key 触达 Gemini/Seedream/GPT/Recraft/Flux 等）
  ark         火山方舟 OpenAI 兼容网关（--model 传推理端点）
  custom      任意 OpenAI Images 兼容端点（--base-url 或 OPENAI_BASE_URL）

模型解析优先级：--model ＞ 环境变量 <PROVIDER>_IMAGE_MODEL ＞ 内置默认。
纪律：一次调用只出 1 张（要多张多次调用）；raw 先进 99_过程稿/；不拼板、不做审美判断。
退出码：0 成功；1 服务商/网络失败（429/5xx 自动重试 2 次，4xx 不重试）；2 用法/配置错误。
仅依赖标准库；Pillow 用于回读校验与非 PNG 返回归一为 PNG（本生产线落格只收 PNG）。
"""
import argparse
import base64
import io
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

# ---- 提供商表（能力位说明见 references/runtime-portability.md §3；模型迭代快，以 --dry-run/厂商文档为准）----
PROVIDERS = {
    "openai": {
        "kind": "openai-images",
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_IMAGE_MODEL",
        "default_model": "gpt-image-2.5-flare",
        "size_mode": "gpt-map",        # gpt-image 族固定档位
        "ref_limit": 16,
    },
    "google": {
        "kind": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "key_env": "GOOGLE_API_KEY",
        "model_env": "GOOGLE_IMAGE_MODEL",
        "default_model": "gemini-2.5-flash-image",
        "size_mode": "aspect",        # 只吃宽高比枚举
        "ref_limit": 3,               # 2.5 Flash Image 为 3；gemini-3 族为 14（见文档）
    },
    "openrouter": {
        "kind": "openrouter-images",
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "model_env": "OPENROUTER_IMAGE_MODEL",
        "default_model": "google/gemini-3.1-flash-image",
        "size_mode": "aspect",
        "ref_limit": None,            # 随模型而变，不做本地拦截
    },
    "ark": {
        "kind": "openai-images",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "key_env": "ARK_API_KEY",
        "model_env": "ARK_IMAGE_MODEL",
        "default_model": None,        # 推理端点 id，必须显式
        "size_mode": "passthrough",
        "ref_limit": None,
    },
    "custom": {
        "kind": "openai-images",
        "base_url": None,
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_IMAGE_MODEL",
        "default_model": None,
        "size_mode": "passthrough",
        "ref_limit": None,
    },
}

GPT_IMAGE_SIZES = {
    "portrait": "1024x1536",   # 2:3（gpt-image 族无 3:4，比例差由 standard_cell 落格吸收）
    "landscape": "1536x1024",
    "square": "1024x1024",
}
ASPECT_RATIOS = ["1:1", "3:4", "4:3", "9:16", "16:9", "2:3", "3:2"]
RETRIABLE_STATUS = {429, 500, 502, 503, 504}


def die(msg, code=2):
    print(f"kit_generate: {msg}", file=sys.stderr)
    return code


def _sleep(sec):
    time.sleep(sec)


def _urlopen(req, timeout):
    """唯一网络出口，测试 monkeypatch 此函数。"""
    return urllib.request.urlopen(req, timeout=timeout)


def http_open(req, timeout, retries=2):
    """带重试的请求：429/5xx/网络错误指数退避，4xx 直接失败。返回 response。"""
    attempt = 0
    while True:
        try:
            return _urlopen(req, timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in RETRIABLE_STATUS and attempt < retries:
                attempt += 1
                _sleep(2 ** attempt)
                continue
            raise
        except urllib.error.URLError:
            if attempt < retries:
                attempt += 1
                _sleep(2 ** attempt)
                continue
            raise


def classify_size(size_str):
    try:
        w, h = (int(x) for x in size_str.lower().split("x", 1))
    except (ValueError, AttributeError):
        raise ValueError(f"尺寸格式应为 WxH，收到：{size_str!r}")
    if w <= 0 or h <= 0:
        raise ValueError(f"尺寸必须为正：{size_str!r}")
    if abs(w - h) / max(w, h) < 0.08:
        return "square", w, h
    return ("portrait" if h > w else "landscape"), w, h


def nearest_aspect(w, h):
    best, best_diff = None, None
    for ratio in ASPECT_RATIOS:
        rw, rh = (int(x) for x in ratio.split(":"))
        diff = abs(w / h - rw / rh)
        if best_diff is None or diff < best_diff:
            best, best_diff = ratio, diff
    return best


def _multipart(fields, files):
    boundary = "----cak" + uuid.uuid4().hex
    crlf = b"\r\n"
    body = bytearray()
    for name, value in fields:
        body += b"--" + boundary.encode() + crlf
        body += f'Content-Disposition: form-data; name="{name}"'.encode() + crlf + crlf
        body += str(value).encode("utf-8") + crlf
    for field_name, path in files:
        fname = os.path.basename(path)
        ctype = mimetypes.guess_type(fname)[0] or "image/png"
        with open(path, "rb") as fp:
            data = fp.read()
        body += b"--" + boundary.encode() + crlf
        body += (f'Content-Disposition: form-data; name="{field_name}"; '
                 f'filename="{fname}"').encode() + crlf
        body += f"Content-Type: {ctype}".encode() + crlf + crlf
        body += data + crlf
    body += b"--" + boundary.encode() + b"--" + crlf
    return f"multipart/form-data; boundary={boundary}", bytes(body)


def _b64_file(path):
    ctype = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as fp:
        return ctype, base64.b64encode(fp.read()).decode()


def build_request(cfg, provider_name, model, args):
    """返回 (method, url, headers, body_bytes|None, json_payload|None, dry_summary)。"""
    kind, size_str = cfg["kind"], args.size
    kind_, w, h = classify_size(size_str)

    if cfg["size_mode"] == "gpt-map" and not args.keep_size:
        size_send = GPT_IMAGE_SIZES[kind_]
    elif cfg["size_mode"] == "aspect" and not args.keep_size:
        size_send = nearest_aspect(w, h)
    else:
        size_send = size_str

    if kind == "openai-images":
        base = args.base_url or os.environ.get("OPENAI_BASE_URL") or cfg["base_url"]
        if not base:
            raise ValueError("custom 提供商需要 --base-url 或环境变量 OPENAI_BASE_URL")
        headers = {"Authorization": f"Bearer {args.api_key}"}
        if args.mode == "gen":
            url = f"{base.rstrip('/')}/images/generations"
            payload = {"model": model, "prompt": args.prompt, "size": size_send, "n": 1}
            if args.quality:
                payload["quality"] = args.quality
            headers["Content-Type"] = "application/json"
            return url, headers, json.dumps(payload).encode("utf-8"), payload
        field = "image" if len(args.ref) == 1 else "image[]"
        url = f"{base.rstrip('/')}/images/edits"
        ctype, body = _multipart(
            [("model", model), ("prompt", args.prompt), ("size", size_send), ("n", 1)],
            [(field, p) for p in args.ref])
        headers["Content-Type"] = ctype
        summary = {"endpoint": url,
                   "multipart_fields": ["model", "prompt", "size", "n"],
                   "image_field": field, "files": [os.path.basename(p) for p in args.ref]}
        return url, headers, body, summary

    if kind == "gemini":
        url = (f"{cfg['base_url']}/models/{model}:generateContent")
        parts = [{"text": args.prompt}]
        for p in args.ref:
            ctype, b64 = _b64_file(p)
            parts.append({"inline_data": {"mime_type": ctype, "data": b64}})
        payload = {"contents": [{"parts": parts}],
                   "generationConfig": {"responseModalities": ["IMAGE", "TEXT"],
                                        "imageConfig": {"aspectRatio": size_send}}}
        headers = {"Content-Type": "application/json", "x-goog-api-key": args.api_key}
        summary = {"endpoint": url, "aspect_ratio": size_send,
                   "refs": [{"name": os.path.basename(p)} for p in args.ref]}
        return url, headers, json.dumps(payload).encode("utf-8"), summary

    if kind == "openrouter-images":
        url = f"{cfg['base_url']}/images"
        payload = {"model": model, "prompt": args.prompt, "aspect_ratio": size_send}
        if args.ref:
            refs = []
            for p in args.ref:
                ctype, b64 = _b64_file(p)
                refs.append({"type": "image", "media_type": ctype, "data": b64})
            payload["input_references"] = refs
        headers = {"Authorization": f"Bearer {args.api_key}",
                   "Content-Type": "application/json"}
        summary = {"endpoint": url, "model": model, "aspect_ratio": size_send,
                   "ref_count": len(args.ref)}
        return url, headers, json.dumps(payload).encode("utf-8"), summary

    raise ValueError(f"未知提供商类型：{kind}")


def parse_response(cfg, obj):
    """返回 (image_bytes, media_type)。"""
    kind = cfg["kind"]
    if kind == "gemini":
        for part in obj.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"]), inline.get("mimeType", "image/png")
        raise RuntimeError(f"Gemini 响应无图片：{json.dumps(obj, ensure_ascii=False)[:500]}")
    # openai-images / openrouter-images 均为 data[] 形状
    try:
        item = obj["data"][0]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"响应中没有 data[0]：{json.dumps(obj, ensure_ascii=False)[:500]}")
    media = item.get("media_type", "image/png")
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"]), media
    if item.get("url"):
        with http_open(urllib.request.Request(item["url"]), 300) as resp:
            return resp.read(), media
    raise RuntimeError(f"data[0] 既无 b64_json 也无 url：{json.dumps(item, ensure_ascii=False)[:500]}")


def normalize_png(img_bytes, out_path):
    """非 PNG 返回（JPEG/WebP）统一转 PNG，守住生产线落格契约。返回 (格式描述, 尺寸)。"""
    from PIL import Image
    with Image.open(io.BytesIO(img_bytes)) as im:
        src_fmt = im.format
        if im.format != "PNG":
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        im.save(out_path, format="PNG")
        dims = im.size
    return src_fmt, dims


def autodetect_provider():
    for name in ("openrouter", "google", "openai", "ark"):
        if os.environ.get(PROVIDERS[name]["key_env"]):
            return name
    return None


def resolve_model(cfg, provider_name, cli_model):
    if cli_model:
        return cli_model
    env_model = os.environ.get(cfg.get("model_env") or "")
    if env_model:
        return env_model
    if cfg["default_model"]:
        return cfg["default_model"]
    raise ValueError(
        f"{provider_name} 无默认模型：用 --model 指定，或设环境变量 {cfg['model_env']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="跨运行时生图适配器（OpenAI/Gemini/OpenRouter/兼容网关）")
    ap.add_argument("--provider", choices=sorted(PROVIDERS) + ["doubao"], default=None)
    ap.add_argument("--mode", choices=["gen", "edit"], default="gen")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--prompt-file", default=None)
    ap.add_argument("--ref", action="append", default=[], help="参考图路径，可重复")
    ap.add_argument("--size", default="1773x2364", help="本线目标尺寸 WxH（按提供商能力映射）")
    ap.add_argument("--keep-size", action="store_true", help="不做档位/宽高比映射，原样发送")
    ap.add_argument("--out", help="raw 输出路径（建议 99_过程稿/raw_*.png）")
    ap.add_argument("--model", default=None)
    ap.add_argument("--quality", default="high", choices=["high", "medium", "low", "none"])
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true", help="只打印请求形状不调用、不花钱")
    args = ap.parse_args(argv)

    if args.provider is None:
        args.provider = autodetect_provider()
        if args.provider is None:
            return die("未指定 --provider 且未检测到任何 *_API_KEY；支持：" +
                       ", ".join(sorted(PROVIDERS)))
    if args.provider == "doubao":
        return die("豆包运行时不经过本脚本：文生图用宿主 image_gen、参考编辑用 image_edit（模型 seedream_5.0_pro）。")
    cfg = PROVIDERS[args.provider]

    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as fp:
            args.prompt = fp.read().strip()
    if not args.prompt:
        return die("必须给 --prompt 或 --prompt-file")
    if args.quality == "none":
        args.quality = None

    if args.mode == "edit" and not args.ref:
        return die("edit 模式至少需要一张 --ref 参考图")
    missing = [p for p in args.ref if not os.path.isfile(p)]
    if missing:
        return die("参考图不存在：" + ", ".join(missing))
    limit = cfg.get("ref_limit")
    if limit and len(args.ref) > limit:
        return die(f"{args.provider}/{args.model or cfg['default_model']} 参考图上限 {limit} 张，"
                   f"收到 {len(args.ref)} 张（能力表见 runtime-portability.md）")
    try:
        classify_size(args.size.lower())
    except ValueError as exc:
        return die(str(exc))

    args.api_key = os.environ.get(cfg["key_env"])
    if not args.api_key and not args.dry_run:
        return die(f"缺少环境变量 {cfg['key_env']}（key 只从环境读，不写进档案/命令记录）")

    try:
        model = resolve_model(cfg, args.provider, args.model)
        url, headers, body, summary = build_request(cfg, args.provider, model, args)
    except ValueError as exc:
        return die(str(exc))

    if args.dry_run:
        print(json.dumps({"dry_run": True, "provider": args.provider, "model": model,
                          "mode": args.mode, "url": url, "request": summary},
                         ensure_ascii=False, indent=2))
        return 0

    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with http_open(req, args.timeout, retries=args.retries) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
        img_bytes, media = parse_response(cfg, obj)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        return die(f"HTTP {exc.code} {exc.reason}\n{detail}", 1)
    except urllib.error.URLError as exc:
        return die(f"网络不可达：{exc.reason}", 1)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        return die(f"请求/解析失败：{exc}", 1)

    if not args.out:
        return die("非 dry-run 必须给 --out")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    try:
        src_fmt, dims = normalize_png(img_bytes, args.out)
    except Exception as exc:
        return die(f"返回内容无法作为图片打开：{exc}", 1)
    print(f"ok：{args.out}（{dims[0]}x{dims[1]}，源格式 {src_fmt} → PNG）"
          f" via {args.provider}/{model} [{args.mode}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
