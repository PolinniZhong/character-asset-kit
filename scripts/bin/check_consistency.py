#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""character-asset-kit · 跨文件一致性自检（五条断言）。

用途：把"版本号 / 门序门名 / profile 声明 / evals 口径 / 触发结果覆盖"这五类
**本应只有一份事实、却散落在多个文件**的口径，机械地对齐检查，避免"改了一处、
其余文件静默滞后"（典型：G3/G4 门序对调只落地一半；新增 profile / case 后
skill.yaml、trigger_results 没同步）。

纯标准库（json / re），不依赖 PyYAML：skill.yaml 只做针对性字段抽取。
退出码：全部 PASS → 0；任一 FAIL → 1。
"""
import json
import os
import re
import sys

# 仓库根：本脚本在 <root>/scripts/bin/ 下，上两级即根。
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", ".."))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fp:
        return fp.read()


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fp:
        return json.load(fp)


# ------------------------------------------------------------ skill.yaml 抽取

def parse_skill_yaml(text):
    """只抽取本检查需要的字段，不实现完整 YAML。"""
    version = re.search(r'^version:\s*["\']?([^"\'\s#]+)', text, re.M)
    # profiles 段：从行首 `profiles:` 到下一个行首非空白顶层键。
    seg = re.search(r'(?m)^profiles:\s*\n(.*?)(?=^\S)', text, re.S)
    body = seg.group(1) if seg else ""
    profiles = []
    for item in re.finditer(r'(?m)^\s*-\s*id:\s*(\S+)\s*\n(.*?)(?=^\s*-\s*id:|\Z)',
                            body, re.S):
        pid = item.group(1)
        pf = re.search(r'profile_file:\s*(\S+)', item.group(2))
        profiles.append({"id": pid,
                         "profile_file": pf.group(1) if pf else None})
    total_cases = re.search(r'(?m)^\s*total_cases:\s*(\d+)', text)
    return {
        "version": version.group(1) if version else None,
        "profiles": profiles,
        "total_cases": int(total_cases.group(1)) if total_cases else None,
    }


def gate_num(gid):
    m = re.match(r'G(\d+)', str(gid))
    return int(m.group(1)) if m else 999


# ------------------------------------------------------------ 五条断言

def check_versions(yaml_d):
    """① 版本号多处一致：skill.yaml == package.json，且 README「现状」、SKILL.md「版本」行同步。"""
    detail = []
    pkg = load_json("package.json")
    pv = str(pkg.get("version"))
    yv = str(yaml_d.get("version"))
    ok = yv == pv
    detail.append(f"skill.yaml version={yv} · package.json version={pv}")
    rm = re.search(r'现状[（(]最新\s*v?([0-9.]+)', read("README.md"))
    if rm:
        rv = rm.group(1)
        detail.append(f"README「现状」v{rv}")
        if rv != pv:
            ok = False
    sm = re.search(r'版本\s*v?([0-9.]+)', read("SKILL.md"))
    if sm:
        sv = sm.group(1)
        detail.append(f"SKILL.md「版本」v{sv}")
        if sv != pv:
            ok = False
    return ok, detail


def _md_gate_titles():
    """合并 gates-g0-g9.md（## §Gx）与 gates-g10-g14.md（## Gx）的章节标题。"""
    titles = {}
    for rel in ("references/gates-g0-g9.md", "references/gates-g10-g14.md"):
        for m in re.finditer(r'(?m)^##\s*§?\s*(G\d+)\s+(.+?)\s*$', read(rel)):
            titles[m.group(1)] = m.group(2)
    return titles


def _tool_gate_maps():
    src = read("scripts/bin/kit_asset_index.py")
    # GATE_LABELS = { ... }
    blk = re.search(r'GATE_LABELS\s*=\s*\{(.*?)\}', src, re.S)
    labels = dict(re.findall(r'"(G\d+)":\s*"([^"]+)"', blk.group(1) if blk else ""))
    # STAGE_MAP 里 表情/细节 映射到的 gate
    expr_g = re.search(r'"表情":\s*\(\s*"expression"\s*,\s*"(G\d+)"', src)
    detail_g = re.search(r'"细节特写":\s*\(\s*"detail"\s*,\s*"(G\d+)"', src)
    return labels, (expr_g.group(1) if expr_g else None), \
        (detail_g.group(1) if detail_g else None)


def check_gates(yaml_d):
    """② 门 id / 门序在 profile、SKILL.md 门表、工具映射、门径手册四处一致；
    G3=细节特写、G4=基础表情的核心词在四处对齐。"""
    detail, ok = [], True

    profile_files = sorted(f for f in os.listdir(os.path.join(ROOT, "profiles"))
                           if f.endswith(".json"))
    prof_gates = {}
    base_ids = None
    for f in profile_files:
        d = load_json(os.path.join("profiles", f))
        ids = [g["id"] for g in d.get("gates", [])]
        names = {g["id"]: g["name"] for g in d.get("gates", [])}
        prof_gates[f] = (ids, names)
        if d.get("default") is True or base_ids is None:
            base_ids = ids
    expect = [f"G{i}" for i in range(len(base_ids))]

    # 所有 profile 门 id 序列必须等于基准（门序，含 G3/G4 位置）
    for f, (ids, _) in prof_gates.items():
        if ids != expect:
            ok = False
            detail.append(f"{f} 门序≠基准：{ids}")

    # SKILL.md 门径地图表格
    skill_ids = re.findall(r'(?m)^\|\s*(G\d+)\s', read("SKILL.md"))
    # 工具 GATE_LABELS
    tool_labels, expr_g, detail_g = _tool_gate_maps()
    # 手册章节
    md_titles = _md_gate_titles()

    sources = {"SKILL.md门表": skill_ids,
               "工具GATE_LABELS": sorted(tool_labels, key=gate_num),
               "门径手册章节": sorted(md_titles, key=gate_num)}
    for name, ids in sources.items():
        if ids != expect:
            ok = False
            detail.append(f"{name} 门集合≠G0..G{len(expect)-1}：{ids}")

    # G3/G4 核心词对齐（本次门序对调的硬口径）；基准 profile = 门序等于 expect 者。
    base_file = next(f for f in prof_gates if prof_gates[f][0] == expect)
    g3, g4 = prof_gates[base_file][1].get("G3", ""), prof_gates[base_file][1].get("G4", "")
    pairs = [
        ("基准profile", g3, g4),
        ("门径手册", md_titles.get("G3", ""), md_titles.get("G4", "")),
        ("工具GATE_LABELS", tool_labels.get("G3", ""), tool_labels.get("G4", "")),
    ]
    for where, t3, t4 in pairs:
        if "细节" not in t3 or "表情" not in t4:
            ok = False
            detail.append(f"{where} G3/G4 核心词错位：G3={t3!r} G4={t4!r}")
    if detail_g != "G3" or expr_g != "G4":
        ok = False
        detail.append(f"工具 STAGE_MAP：detail→{detail_g}（期望G3）· expression→{expr_g}（期望G4）")

    if not detail:
        detail.append(f"门 G0–G{len(expect)-1} 四处同序；G3=细节特写、G4=基础表情 核心词全对齐")
    return ok, detail


def check_profile_decl(yaml_d):
    """③ skill.yaml 声明的 profiles 与 profiles/ 目录实际文件一致，且 profile_file 存在。"""
    detail, ok = [], True
    disk = {f[:-5] for f in os.listdir(os.path.join(ROOT, "profiles"))
            if f.endswith(".json")}
    declared = {p["id"] for p in yaml_d.get("profiles", [])}
    detail.append(f"skill.yaml 声明 {sorted(declared)} · profiles/ 实际 {sorted(disk)}")
    if declared != disk:
        ok = False
        for x in sorted(disk - declared):
            detail.append(f"  未在 skill.yaml 声明：{x}")
        for x in sorted(declared - disk):
            detail.append(f"  skill.yaml 声明但 profiles/ 无文件：{x}")
    for p in yaml_d.get("profiles", []):
        pf = p.get("profile_file")
        if not pf or not os.path.exists(os.path.join(ROOT, pf)):
            ok = False
            detail.append(f"  profile_file 不存在：{p.get('id')} → {pf}")
    return ok, detail


def check_eval_cases(yaml_d):
    """④ evals/trigger_tests.json 的 case 数与 skill.yaml 声称的 total_cases 一致。"""
    tests = load_json("evals/trigger_tests.json")
    n = len(tests.get("cases", []))
    claimed = yaml_d.get("total_cases")
    ok = claimed == n
    return ok, [f"skill.yaml total_cases={claimed} · trigger_tests.json cases={n}"]


def check_results_coverage():
    """⑤ evals/trigger_results.json 覆盖的 case 与 trigger_tests.json 的 case 集合一致。

    注意 trigger_results.json 是**实测结果、被 .gitignore 排除**（不进公开仓）：
    CI 全新 checkout 时该文件不存在 → 判 SKIP（发版前在本地手动跑），不阻断 CI。
    """
    rel = "evals/trigger_results.json"
    if not os.path.exists(os.path.join(ROOT, rel)):
        return "SKIP", [f"{rel} 不在公开仓（实测结果被 .gitignore 排除）",
                        "CI 上跳过；发版前在本地运行本检查作为手动门禁"]
    tests = load_json("evals/trigger_tests.json")
    want = {c.get("id") for c in tests.get("cases", [])}
    res = load_json(rel).get("results", {})
    got = set(res.keys()) if isinstance(res, dict) else \
        {c.get("id") for c in res}
    missing, extra = sorted(want - got), sorted(got - want)
    detail = [f"trigger_tests case={len(want)} · trigger_results 覆盖={len(got)}"]
    if missing:
        detail.append(f"  缺结果：{missing}")
    if extra:
        detail.append(f"  多余结果：{extra}")
    return ("PASS" if not missing and not extra else "FAIL"), detail


# ------------------------------------------------------------------ main

CHECKS = [
    ("①版本号多处一致", lambda y: check_versions(y)),
    ("②门 id/门序·G3G4 四处一致", lambda y: check_gates(y)),
    ("③skill.yaml profiles 与目录一致", lambda y: check_profile_decl(y)),
    ("④evals case 数与声称一致", lambda y: check_eval_cases(y)),
    ("⑤trigger_results 覆盖全部 case", lambda y: check_results_coverage()),
]


def main():
    yaml_d = parse_skill_yaml(read("skill.yaml"))
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    print("[check_consistency] character-asset-kit 跨文件一致性自检")
    for title, fn in CHECKS:
        st, detail = fn(yaml_d)
        if st is True:
            st = "PASS"
        if st is False:
            st = "FAIL"
        counts[st] += 1
        print(f"\n{st}  {title}")
        for line in detail:
            print(f"      {line}")
    suffix = f" · {counts['SKIP']} 跳过" if counts["SKIP"] else ""
    print(f"\n结论：{counts['PASS']}/{len(CHECKS)} 通过{suffix}"
          + ("（全部一致）" if counts["FAIL"] == 0 else f"（{counts['FAIL']} 条不一致）"))
    return 0 if counts["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
