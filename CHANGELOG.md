# Changelog

本文件记录 character-asset-kit 的变更；方法论/提示词层的变化同时回灌 references/ 并在门径文档标注。

## v1.1（2026-09-22）— 第三个角色自用验证（dogfooding）补丁回灌

第三个角色在全新对话中只依赖本 Skill 跑完 G0–G12（media 106 / 交付物 17 / 0 ERROR），暴露并修复 8 条缺口：

- **#001（阻塞级）** `templates/资产清单_模板.json` 缺 `boards.character_sheet` 段，G8 必 KeyError、`--type all` 静默跳过 → 模板内置该段（8 字段占位＋height 3240＋out_clean/out_review）；`kit_build_board.py` 缺段时明确报错、`--type all` 缺核心板打 WARN。
- **#005（真实卡点）** macOS Vision 对深色道具确定性 `no subject found`、对面部微距过度分割 → 新增 `kit_colorkey_cutout.py`（边缘泛洪近白色键＋收缩羽化）；cutout() 失败信息带 returncode 与两条兜底路径；G4/G7 文档写入"满幅微距免抠图 / 色键兜底"双路径（BC-28）。
- **#006** `kit_standard_cell.py` docstring 的道具参数组合几何上必然裁顶 → 修正为 `--square --no-shadow`；standard_cell 对顶部越界直接报错（BC-29）。
- **#007** `--all --char .` 静默空跑造成假绿灯 → 参数互斥校验、枚举为空非零退出（BC-30）。
- **#008** 微表情板为空 levels 可选族渲染空白行 → 构建器自动跳过空族（BC-32）。
- **#004** `--square` 实际输出 2364×2364（标准格长边）而文档写 2048 → 文档/help 统一为 2364，需要 2048 显式 `--cell 2048x2048`。
- **#002** 门裁剪 profile 副本无存放约定 → style-profiles §5 规定库根 `profiles/profile_<id>_<代号>_<门范围>.json` 命名与扩展留痕。
- **#003** 台账脚本注释引用未随 Skill 分发的文档/上层工具 → 新增 `references/registry-rules.md`（E1–E7/W1–W7 随仓分发），注释与 v3 提示改为仓内自洽表述。
- 另：清单 `boards.*.meta` 是会上板的对外文字（BC-31），模板加 `_comment` 说明。
- 开源包装：新增 `tests/`（14 个 unittest：端到端冒烟、CLI 守卫、落格几何、色键、空族跳过）、`docs/PRD.md`、`docs/DESIGN.md`（SDD）、`docs/DOGFOODING.md`（覆盖率报告）、双语 README、CONTRIBUTING、examples 端到端走查。
- BC-33：正面复用母版时若字节拷贝，上层资产中心按内容指纹去重会串号 → 必须重新落格产出独立文件（见 bad-cases）。

## v1.0（2026-09-21）— 首版封装

G0–G14 门径、blindbox3d profile、六段式提示词框架、210 样本改写规则、BC-01–27、确定性脚本（init/standard_cell/build_board/scene_board/style_board/asset_index/trainset＋subjectmask.swift）。
