# evals/ · Skill 层评测

> 本目录是 character-asset-kit 的**评测框架与数据**（Skill 资产，随仓公开）。
> 评测**结果报告**（暴露短板与 roadmap）回内部目录 `06_企业化_千面工坊/`，不进公开仓。

评测回答三个问题，从易到难分三层：**该不该用（触发）→ 用了好不好（质量）→ 每次稳不稳（一致性）**。

## 文件清单

| 文件 | 层 | 作用 |
|---|---|---|
| `trigger_tests.json` | L1 | 触发测试集（24 case：14 应触发[含 4 真人话术] ＋ 10 不应触发） |
| `trigger_results.example.json` | L1 | 结果记录模板（复制为 `trigger_results.json` 使用） |
| `run_trigger_check.py` | L1 | 读结果算 Precision/Recall/Specificity、分 profile 触发率、门禁判定 |
| `task_quality.json` | L2 | 质量任务集（4 个真实任务，3D/真人 × 简单/标准/复杂，A/B） |
| `rubric.md` | L2 | 五维度 0–5 评分标准、critical 项、A/B 归因与判线 |
| `quality_report_v1.md` | L2 | A/B 评分结果（**跑后产出，结果回内部目录**） |
| `consistency_report.md` | L3 | 同任务 5 次波动记录（第二阶段） |

## 怎么跑

### L1 触发评测
```bash
cp evals/trigger_results.example.json evals/trigger_results.json
# 在目标平台：每个 case 用「干净新会话」单独发送 3 次，
# 观测是否加载 character-asset-kit，把 true/false 填入 trigger_results.json
python3 evals/run_trigger_check.py
```
- 第一层宽松线：应触发组触发率 > 50%、不应触发组误触发率 < 50%；
- 发版门禁线：Precision/Recall ≥ 90%（分 profile 各看 3D、真人）。

### L2 任务质量评测
1. 从 `task_quality.json` 选任务，准备**相同**的需求/参考/模型/画幅；
2. A 组裸模型、B 组加载 Skill，分别生产；
3. 按 `rubric.md` 人工打分，算 B 百分制与 **B−A（Skill 净价值）**；
4. 结果写入 `quality_report_v1.md`（对外不公开，副本回 `06_企业化_千面工坊/`）。
- 单任务通过：B ≥ 80 且无 critical；任务完成率目标 ≥ 85%；
- LLM-as-judge 须先验证与人评一致性 ≥ 80% 才可使用。

### L3 一致性评测（第二阶段）
同任务跑 5 次，记录门数/返工/资产数/身份一致性，关键指标波动 ≤ 15%（分 profile）。

## 诚实边界

- 触发与质量评测的**执行**必须在目标平台的真实会话里完成（平台是否加载 Skill 由路由层决定）；
- 本目录脚本只做"结果 → 指标"的确定性统计，**不能**在脚本内模拟或替代平台的 Skill 路由；
- 评测集应从真实失败"长"出来：每跑一个角色，新问题即新用例（自进化闭环雏形）。
