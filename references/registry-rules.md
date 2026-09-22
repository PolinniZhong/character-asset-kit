# 台账规则速查（E1–E7 / W1–W7）

`kit_asset_index.py --check` 的判级规则。**ERROR 必须清零才能过门；WARN 要逐条确认并在封存小结写明处置。**
规则实现以 `scripts/bin/kit_asset_index.py` 为准（本表随 v1.1 分发，解决早期版本注释引用未随 Skill 分发文档的问题）。

## ERROR（阻断过门，退出码 1）

| 码 | 含义 | 处置 |
|---|---|---|
| E1 | 档案登记的媒体路径在磁盘不存在 | 账实不符：补文件或重新 scaffold |
| E2 | `spec_card_current` 指向不存在的规格卡 | 改指现行规格卡 |
| E3 | 存在多份规格卡但未指明现行版本 | 在档案里指明 current，旧版归 `99_过程稿/版本留档/` |
| E4 | `authorization_refs` 为空 | **自有版权也必须显式声明**（init 模板已预填，勿删） |
| E5 | 门状态标为 done，但该门最小产物要求不满足 | 补产物，或把门状态改回未完成 |
| E6 | 某 media 的 variant 在 asset_versions 中没有对应版本 | 补版本登记 |
| E7 | 缺必填包级字段 | 按报错字段补齐 |

## WARN（不阻断，须人工确认）

| 码 | 含义 | 处置 |
|---|---|---|
| W1 | 磁盘有 PNG 但未登记进档案 | 跑 `--scaffold` 重扫（注意：包内操作用 `--char .`，不要加 `--all`） |
| W2 | 资产清单声明的产物尚未生成 | 未做的门属正常；**有意裁剪的门**（profile enabled=false）在规格卡 §0 与封存小结声明后接受 |
| W3 | 出现未登记进插槽规范的目录 | 确认是否新插槽；是则补规范，否则归 `99_过程稿/` |
| W4 | 门未标 done 但产物已满足最小要求 | 通常是已可过门，补门状态 |
| W5 | 同 unit_type+label 多版本并存 | 确认现行版，旧版标 superseded 或归版本留档 |
| W6 | 非现行规格卡的 asset_version 仍为 draft | 判为 superseded 或保留并说明 |
| W7 | 顶层目录编号冲突 / 阶段名未登记 | 按插槽编号规范整改 |

## 命令口径（避免假绿灯）

- 角色包目录内：`kit_asset_index.py --char . --scaffold|--check`（**不要带 `--all`**，v1.1 起同传直接报错）。
- 库级：`kit_asset_index.py --root <库根> --all --scaffold|--check`。
- `--scaffold`（写）与 `--check`（只读）不能同传。
- v1 档案是本 Skill G0–G14 的默认形态；契约 v3 的 `asset_id` 分配属于上层资产中心工具链，不在本 Skill 内。
