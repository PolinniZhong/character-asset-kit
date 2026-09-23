#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1 触发评测统计：读 trigger_tests.json（期望）与 trigger_results.json（3 次实测），
算 Precision/Recall/Specificity、分 profile 触发率与逐 case 触发率，并判定门禁。

平台是否加载 skill 由路由层决定，本脚本只做"结果→指标"的确定性统计，不替你执行触发。
用法：
  python3 run_trigger_check.py                         # 默认读同目录 tests/results
  python3 run_trigger_check.py --results my.json --json
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def pct(x, d):
    return 100.0 * x / d if d else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default=os.path.join(HERE, "trigger_tests.json"))
    ap.add_argument("--results", default=os.path.join(HERE, "trigger_results.json"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    tests = json.load(open(args.tests, encoding="utf-8"))
    if not os.path.exists(args.results):
        raise SystemExit(f"找不到结果文件：{args.results}\n可复制 trigger_results.example.json 为 "
                         "trigger_results.json 并填写实测结果。")
    results = json.load(open(args.results, encoding="utf-8"))["results"]

    cases = {c["id"]: c for c in tests["cases"]}
    # 按每次 run 累计混淆矩阵
    tp = fp = tn = fn = skipped = 0
    per_case = []
    prof = {"blindbox3d": [0, 0], "realhuman": [0, 0]}  # fired, valid

    for cid, c in cases.items():
        runs = results.get(cid, [])
        fired = sum(1 for r in runs if r is True)
        valid = sum(1 for r in runs if r is not None)
        expect_trigger = c["expect"] == "trigger"
        for r in runs:
            if r is None:
                skipped += 1
            elif r is True:
                if expect_trigger:
                    tp += 1
                else:
                    fp += 1
            else:
                if expect_trigger:
                    fn += 1
                else:
                    tn += 1
        per_case.append({"id": cid, "expect": c["expect"], "profile": c["profile"],
                         "fired": fired, "valid": valid,
                         "rate": pct(fired, valid)})
        if expect_trigger and valid:
            key = "realhuman" if c["profile"] == "realhuman" else "blindbox3d"
            prof[key][0] += fired
            prof[key][1] += valid

    precision = pct(tp, tp + fp)
    recall = pct(tp, tp + fn)
    specificity = pct(tn, tn + fp)
    should_rate = recall                      # 应触发组的实际触发率
    shouldnot_rate = pct(fp, fp + tn)         # 不应触发组的误触发率
    p3 = pct(prof["blindbox3d"][0], prof["blindbox3d"][1])
    pr = pct(prof["realhuman"][0], prof["realhuman"][1])

    g_init = tests["method"]["pass_gate_initial"]
    g_rel = tests["method"]["pass_gate_release"]
    init_pass = (should_rate / 100 >= g_init["should_trigger_rate_min"]
                 and shouldnot_rate / 100 <= g_init["should_not_trigger_rate_max"])
    rel_pass = (precision / 100 >= g_rel["precision_min"]
                and recall / 100 >= g_rel["recall_min"])

    out = {
        "results_file": os.path.basename(args.results),
        "observations": {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "skipped": skipped},
        "metrics_percent": {"precision": round(precision, 1), "recall": round(recall, 1),
                            "specificity": round(specificity, 1),
                            "should_trigger_rate": round(should_rate, 1),
                            "should_not_trigger_rate": round(shouldnot_rate, 1)},
        "profile_trigger_rate_percent": {
            "blindbox3d(含通用)": round(p3, 1),
            "realhuman": round(pr, 1)},
        "per_case": per_case,
        "gate": {"initial": "PASS" if init_pass else "FAIL/PENDING",
                 "release": "PASS" if rel_pass else "FAIL/PENDING"},
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print(f"== L1 触发评测 · {out['results_file']} ==")
    o = out["observations"]
    print(f"混淆矩阵(按run) TP {o['tp']} · FP {o['fp']} · TN {o['tn']} · FN {o['fn']} · 未跑 {o['skipped']}")
    m = out["metrics_percent"]
    print(f"Precision {m['precision']}% · Recall {m['recall']}% · Specificity {m['specificity']}%")
    print(f"应触发组触发率 {m['should_trigger_rate']}% · 不应触发组误触发率 {m['should_not_trigger_rate']}%")
    pp = out["profile_trigger_rate_percent"]
    print(f"分 profile 触发率：3D {pp['blindbox3d(含通用)']}% · 真人 {pp['realhuman']}%")
    print("逐 case：")
    for r in per_case:
        print(f"  {r['id']} [{r['expect']:<10} {r['profile']:<10}] {r['fired']}/{r['valid']}  {r['rate']:.0f}%")
    print(f"门禁：第一层宽松 {out['gate']['initial']} · 发版 {out['gate']['release']}")


if __name__ == "__main__":
    main()
