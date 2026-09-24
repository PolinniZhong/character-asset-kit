---
name: character-asset-kit
description: 千面工坊·角色资产生产线（character-asset-kit）。当用户要用千面工坊/角色生产线建新角色、做角色资产或角色库，或提到 character sheet、角色设定图板、多视图/三视图、表情板、动作库、角色道具/商卡、角色一致性资产、按门径生产角色，以及真人写实角色、真人男主、都市/韩剧男主、真人照片质感时使用。把新角色按 G0–G14 门径（立项到封存：白底母版、多视图、表情、细节、胸像、动作、道具、拼板商卡，含微表情/机位视线/场景/风格变体/训练素材）做成可复用、可对账、可训练备料的 AIGC 角色资产库。内置 3D 卡通盲盒风与真人写实摄影风两套 profile；确定性脚本（Pillow＋Vision 抠图）负责落格、拼板、台账与训练集导出，生图由运行时调图像模型完成（默认豆包 seedream_5.0_pro，兼容多家网关）。不用于写文章配图，不承诺库内训练 LoRA。
license: MIT
---

# 千面工坊 · 角色资产生产线（character-asset-kit）

> 千面如一：一个身份锚点，千张资产不漂移。

把"一个新角色"做成**可复用、可对账、可训练备料**的整套资产：身份签名先冻结，再逐单元生成、逐门验收，确定性脚本负责一切像素排版与台账。方法论来自一条真实跑通的生产线（两个角色走完 G0–G14、第三个角色 G0–G12 自用验证）与 210 张受控复现实验；门径、插槽、风格全部 **profile 化**，本 skill 不绑定任何具体角色或具体画风。

**版本 v1.3.1（2026-09-24）**：
- **v1.2**：生图运行时层解耦——默认仍走豆包 `seedream_5.0_pro`，新增 `kit_generate.py`（纯标准库）支持 OpenRouter 统一网关 / Google Gemini / OpenAI gpt-image / 火山方舟 / 任意兼容网关，含模型解析优先级、参考图上限预检、`--dry-run`、限流重试、非 PNG 归一；新增 `references/runtime-portability.md`（提供商矩阵与最小再验证）。
- **v1.2.1（方舟真机验证修复）**：持密钥打通 `--provider ark` 后修掉四条**静态检查抓不到**的缺陷——图生图端点（方舟无 `/images/edits`，改走 `/images/generations` + JSON `image`）、**零水印**（方舟不传 `watermark` 默认 `true`，现始终显式 `false`）、错误分类（`BrokenPipeError` 不再被写成"网络不可达"）、密钥候选（`key_env` 支持候选表）。
- **v1.2.2（参考图配置：新增一个维度）**：`prompt-rewrite-rules.md` **新增 §7**——**构图锚必须与目标构图同景别、且一次只给一个**；混景别双锚（如全身母版＋胸像锚）时模型**两张都不跟、把主体撑满整幅**；成品资产不能当构图锚。坏例 **BC-34**。
- **v1.3（双 profile）**：新增**真人写实第二 profile** `profiles/gates-realhuman-v1.json`（7.3 头身、真实皮肤方法论、现实都市 world、G13 改为造型变体、训练集 min_images=30）＋ `references/profile-realhuman.md`；脚本向后兼容（dataset_slot／真人手持命名／可配 min_images）。**一个 Skill 多 profile、不拆分**；真人线目前仅豆包 seedream_5.0_pro 完成真机验证。
- **v1.3.1（真人线修复＋L1 评测闭环）**：修真人 profile 端到端问题——G14 训练集 slot 按 config 解析（原硬编码 S slot 误报 E5）、道具板手持动态多行、变体插槽支持 R 前缀、裁剪门跳过；L1 触发边界按**任务形态**重定义（S12/S13 带角色语境触发、新增 N11/N12 裸话术合理不触发；堆词证伪），26 case 三轮 Precision/Specificity 100%、Recall 均值 97.6%，release 门禁通过；皮肤 v2.1 失败、胸像正面柔光、右肩留白回灌。43 单测全绿。
- v1.1：第三个角色自用验证（dogfooding）8 条缺口回灌（清单模板内置 character_sheet、色键兜底脚本、方格口径 2364、CLI 假绿灯防护、空族跳过等，详见 CHANGELOG.md）。

## 硬约束（任何门都适用）

1. **门径驱动，用户过门才推进**：每门结束给验收清单，用户明确说"过 / 确认 / ok / 通过"才进下一门；不得自行连跳。返工只改本门单元，不回改已定稿资产，除非用户明确要求。
2. **身份签名是最高优先级**：规格卡（`00_角色规格卡_*.md`）冻结的发型签名/脸型/服装/头身比/材质，高于一切参考图。参考图与签名冲突时，停下问用户，不得自行改掉关键特征。
3. **生图模型按运行时路由（默认豆包）**：豆包运行时用 `seedream_5.0_pro`，以图生图/参考绑定走 `image_edit`、从零起图走 `image_gen`，**每次 `request_list` 只放 1 个请求**，要多张就多次并行调用。其他运行时用 `scripts/bin/kit_generate.py` 直连：`openrouter`（统一网关，一把 key 触达 Gemini/Seedream/GPT-Image 等，推荐入口）/`google`（Gemini 图像）/`openai`（gpt-image 族）/`ark`（火山方舟）/`custom`（任意 OpenAI Images 兼容网关）；本地 CUDA（ComfyUI 等）按 `references/runtime-portability.md` §7 的 CLI 契约自包。**门径与验收不变**；换模型前必须读该文 §4 跑 G1/G2/G3/G7 最小再验证——服从度实验结论是 seedream 特定的，不得跨模型照搬。
4. **资产本体零文字**：角色图上绝不出现文字、字母、数字、logo、水印、标注线；标签只允许出现在拼板/商卡的**排版层（画面外）**。服装自带签名印花是唯一例外且必须在规格卡登记。客户端预览上的"AI 生成"角标是平台叠加层、不在像素里；**入库以保存到本地的 PNG 为准**并重新打开放大核对。
5. **单元直出，禁止整板直出**：多视图/表情/动作/道具一律**逐单元生成单图** → 确定性脚本抠图落标准格 → 脚本拼板。模型一次性直出多格板必然崩（脸不一致、镜像、手崩），这是实测铁律。
6. **每张定稿立即沉淀提示词**：按六段式（用途 / 参考图喂料 / 提示词原文 / 尺寸口径 / 验收结论 / bad case）追加到该包 `08_提示词库/` 对应文档。这是生产线最有复用价值的资产，不能事后补记忆。
7. **一次只给 1 张候选**，除非用户要求对比；候选之间必须有可肉眼区分的变量（发型/光效/表情幅度），不出肉眼无差异的凑数图。
8. **脚本只做确定性工序**（抠图、落格、拼板、台账、训练集导出），不做审美判断；脚本跑不通先读报错修通道，不把工序退回手工。
9. **诚实原则**：没生成就说没生成、没搜到就说没搜到；做不到的工序（如库内训练 LoRA、非 macOS 抠图）直接说明边界。

## 标准插槽（blindbox3d profile 默认；其他 profile 见 profiles/）

```
<CODE>-<slug>/
├── 00_角色规格卡_<CODE>_v1.0.md   # G0 产物，身份最高权威
├── 资产清单.json                   # 拼板/商卡的计划（模板生成）
├── 资产档案.json                   # 台账（脚本 scaffold/check，稳定 asset_id）
├── subjectmask (+.swift)          # macOS 抠图二进制（init 自动带）
├── 01_母版/                        # G1 白底母版（竖3:4）＋透明版
├── 02_多视图/单图 拼板 俯仰视线/    # G2 五视图＋视线；G11 俯仰
├── 03_表情/单图 拼板 微表情矩阵/    # G3 基础表情；G10 微表情
├── 04_细节特写/单图 拼板            # G4 六个签名细节
├── 05_营销胸像/                    # G5 头肩胸像
├── 06_动作姿态/单图 拼板            # G6 A/B/C 组
├── 07_道具/单体独立图 手持关系 配饰变体 拼板   # G7
├── 08_提示词库/                    # 六段式沉淀（每门一份）
├── 09_风格变体/<插槽>/风格母版 单图 拼板   # G13
├── 10_商卡成品/                    # G8 角色设定板＋商卡
├── 11_训练素材/                    # G14 派生物（不进台账扫描）
├── 12_场景包/场景母版 单图 拼板      # G12
└── 99_过程稿/                      # raw、候选、版本留档（不进成品）
```

## 门径地图（先读哪篇）

| 门 | 产物 | 关键脚本 | 必读 reference |
|---|---|---|---|
| G0 立项 | 规格卡＋资产清单＋目录树 | `kit_init_character.py` | gates-g0-g9.md §G0 |
| G1 母版 | 白底母版＋透明版 | `kit_standard_cell.py`、subjectmask | gates-g0-g9.md §G1 |
| G2 多视图 | 五视图单图＋拼板（含验收版） | standard_cell、`kit_build_board.py --type multiview` | gates-g0-g9.md §G2 |
| G3 表情 | 6 基础表情（头肩）＋板 | standard_cell `--bust`、build_board expression | gates-g0-g9.md §G3 |
| G4 细节特写 | 6 签名细节方格＋板 | standard_cell `--square`、build_board detail | gates-g0-g9.md §G4 |
| G5 营销胸像 | 前 3/4 胸像 | standard_cell `--bust` | gates-g0-g9.md §G5 |
| G6 动作姿态 | A 手势/B 身势/C 职业动作＋板 | standard_cell（坐姿 `--scale-factor 0.58`）、build_board pose | gates-g0-g9.md §G6 |
| G7 道具 | 单体图→比例对照→手持关系＋板 | standard_cell `--square`、build_board prop | gates-g0-g9.md §G7 |
| G8 拼板/商卡 | 角色设定板＋商卡 | build_board character_sheet / card | gates-g0-g9.md §G8 |
| G9 封存 | 台账全绿、提示词齐、版本留档 | `kit_asset_index.py --all --check` | gates-g0-g9.md §G9 |
| G10 微表情矩阵 | 4 情绪族×L1/L2/L3＋中性＝13 格 | build_board micro_expression | gates-g10-g14.md |
| G11 机位/视线 | 俯仰 ±15°＋视线四向 | build_board gaze | gates-g10-g14.md |
| G12 场景包 | 场景母版＋5 场景竖/横＋总览板 | `kit_scene_board.py` | gates-g10-g14.md |
| G13 风格变体 | 风格母版＋五视图＋表情（如黏土风） | `kit_style_board.py` | gates-g10-g14.md |
| G14 训练素材 | 47 张级数据集＋双 caption＋val | `kit_trainset.py --build/--check` | gates-g10-g14.md |

扩展门 G10–G14 **按需做**，不阻塞 G9 封存；新角色立项时默认只承诺 G0–G9。

## 按需加载（不要一次读完）

1. 新对话/新角色开工：**先确认风格 profile（3D 盲盒＝gates-blindbox3d-v1 / 真人写实＝gates-realhuman-v1）**；读本文件 + `references/gates-g0-g9.md §0、§G0、§G1` + `references/style-profiles.md`；真人线加读 `references/profile-realhuman.md`。
2. 到哪一门读 `gates-g0-g9.md` 对应一节；写提示词前读 `references/prompt-framework.md` 对应单元模板。
3. 提示词被模型"不听"、出崩图：读 `references/prompt-rewrite-rules.md`（210 张实验总结的改写配方 A/B/C）与 `references/bad-cases.md`。
4. 每门验收前：读 `references/acceptance-checklists.md` 对应清单；台账 E/W 码含义查 `references/registry-rules.md`。
5. 用户要扩展门：读 `references/gates-g10-g14.md` 对应章节。
6. 换画风/换门径/换插槽：读 `references/style-profiles.md` 与对应内置 profile（`profiles/gates-blindbox3d-v1.json` 或 `profiles/gates-realhuman-v1.json`，真人增量见 `references/profile-realhuman.md`），另存 profile 副本、不改内置文件；门裁剪副本放库根 `profiles/`，命名见 style-profiles §5。
7. 换生图模型/运行时（OpenAI、方舟、兼容网关、本地 CUDA）：读 `references/runtime-portability.md`，按 profile 的 `runtime` 块配置，并跑该文 §4 的最小再验证后再批量生产。

## 脚本速查（库根＝存放角色包的目录；脚本路径相对本 skill）

```bash
SK=path/to/character-asset-kit
# G0 建包（macOS 会自动编译并随包放 subjectmask）
python3 "$SK/scripts/bin/kit_init_character.py" --dir CHAR-01-slug --root /path/to/library
# 非豆包运行时出 raw（provider：openrouter 推荐 / google / openai / ark / custom；先 --dry-run 核对）
export OPENROUTER_API_KEY=...
python3 "$SK/scripts/bin/kit_generate.py" --provider openrouter --mode edit \
  --ref 01_母版/CHAR-01_母版_v1.0_白.png --prompt-file 99_过程稿/p.txt \
  --size 1773x2364 --out 99_过程稿/raw_G2左侧_v1.png
# G1–G7 raw → 标准格（白底接触阴影版＋透明版）；包内单角色把 /path/to/library/CHAR 换成 . 并用 --char .
python3 "$SK/scripts/bin/kit_standard_cell.py" --char /path/to/library/CHAR-01-slug \
  --in 99_过程稿/raw_xxx.jpg --white 06_动作姿态/单图/CHAR-01_动作-A1挥手_v1.0_白.png \
  --transparent 06_动作姿态/单图/CHAR-01_动作-A1挥手_v1.0_透明.png
# G2–G8 拼板（先干净版，需要时加 --review 出验收版）
python3 "$SK/scripts/bin/kit_build_board.py" --char /path/to/library/CHAR-01-slug --type multiview
# Vision 抠图失败兜底：深色道具走色键（边缘泛洪近白），面部微距让皮肤满幅后直接 --already-cutout
python3 "$SK/scripts/bin/kit_colorkey_cutout.py" --in 99_过程稿/raw_道具.jpg --out 99_过程稿/cut_道具.png
# G9 台账：重扫 → 对账（0 ERROR 才能封存）；包内单角色用 --char .，库级用 --root+--all（二者不可同传）
python3 "$SK/scripts/bin/kit_asset_index.py" --root /path/to/library --all --scaffold
python3 "$SK/scripts/bin/kit_asset_index.py" --root /path/to/library --all --check
# G12/G13/G14
python3 "$SK/scripts/bin/kit_scene_board.py" --char CHAR-01-slug --root /path/to/library
python3 "$SK/scripts/bin/kit_style_board.py" --char CHAR-01-slug --slot S2-黏土 --root /path/to/library
python3 "$SK/scripts/bin/kit_trainset.py" --root /path/to/library --char CHAR-01-slug --build
```

环境：Python 3.10+、Pillow（`pip install pillow`，纯 Python 侧无其他必需依赖）；抠图与白底落格依赖 macOS Vision（仅 macOS；非 macOS 用第三方抠图后传 `--already-cutout`）。

## 输出口径

- 规划阶段：给门级计划（当前门、单元清单、参考图喂料表、画幅/命名），不一次规划全部 15 门的细节。
- 生成阶段：先给完整可复核提示词（含参考图顺序与逐字文字约束），再调工具；每请求单图。
- 过门阶段：给该门验收清单的逐项核对结果＋落盘路径＋台账/拼板结果；状态只能是"内部通过、待用户确认"，用户说过才算过门。
- 每次发现新 bad case：先修当图，再把规则回灌 `references/` 或该包 `08_提示词库/` 并升版本。
