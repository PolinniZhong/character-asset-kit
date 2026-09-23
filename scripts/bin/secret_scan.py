#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""密钥扫描（最简安全检查，差距 4 第一阶段）：扫文本文件中的常见 API key/token/私钥，
命中即退出码 1（供 CI）。纯标准库；只显示掩码、不回显完整密钥。

用法:
  python3 secret_scan.py [--root PATH]
"""
import argparse
import os
import re
import sys

SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz", ".tar",
            ".pyc", ".ico", ".wav", ".mp3", ".mp4", ".mov", ".ttc", ".ttf", ".otf",
            ".woff", ".woff2"}
SKIP_DIRS = {".git", "__pycache__", "renditions", ".venv", "venv"}
SKIP_FILES = {"secret_scan.py"}

# 强签名（一旦出现基本就是真密钥）
PATTERNS = [
    ("AWS-AccessKey", r"AKIA[0-9A-Z]{16}"),
    ("Google-APIKey", r"AIza[0-9A-Za-z\-_]{35}"),
    ("GitHub-Token", r"gh[pousr]_[A-Za-z0-9]{36}"),
    ("OpenAI-APIKey", r"sk-(?:proj-)?[A-Za-z0-9]{20,}"),
    ("Slack-Token", r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    ("Stripe-LiveKey", r"[sr]k_live_[A-Za-z0-9]{16,}"),
    ("Private-Key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
]
GENERIC = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|access[_-]?key)\s*[:=]\s*[\"']?([A-Za-z0-9\-_/.+]{12,})")
# 占位/示例不算泄密
PLACE = re.compile(r"(?i)(your[-_]|example|xxxx|changeme|placeholder|replace|<|\.\.\.|null|none|sample|demo)")


def mask(s):
    return (s[:4] + "****" + s[-2:]) if len(s) > 8 else "****"


def scan(root):
    findings = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if fn in SKIP_FILES:
                continue
            if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                continue
            p = os.path.join(dp, fn)
            try:
                lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                for name, pat in PATTERNS:
                    m = re.search(pat, line)
                    if m and not PLACE.search(m.group(0)):
                        findings.append((p, i, name, mask(m.group(0))))
                m = GENERIC.search(line)
                if m and not PLACE.search(m.group(2)):
                    findings.append((p, i, "Generic-Secret-Assignment", mask(m.group(2))))
    return findings


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--root", default=os.path.normpath(os.path.join(here, "..", "..")))
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    findings = scan(root)
    for p, i, name, ms in findings:
        print(f"  POSSIBLE SECRET  {name}  {os.path.relpath(p, root)}:{i}  {ms}")
    if findings:
        print(f"密钥扫描：发现 {len(findings)} 处疑似密钥（已掩码）。请移除或改用环境变量；"
              "占位示例请用 your-/example/<> 标注。")
        sys.exit(1)
    print("密钥扫描：未发现疑似密钥。")


if __name__ == "__main__":
    main()
