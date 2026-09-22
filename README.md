# character-asset-kit

> 把一个新角色按企业级门径（G0–G14）做成**跨角度、跨表情、跨动作、跨场景、可训练备料、可对账**的 AIGC 角色资产库的 Agent Skill。
> Agent 负责生图与编排，本 Skill 提供门径 SOP、实证提示词方法论与确定性脚本。

English: [README.en.md](README.en.md)

## 它解决什么问题

"能生成一个好看的角色"和"拥有一个稳定可复用的角色资产"是两件事。后者需要：

1. **身份先冻结再量产**：规格卡 → 白底母版，之后一切单元回指母版；
2. **单元直出、确定性拼板**：多视图/表情/动作逐张生成，脚本抠图落标准格并拼板，杜绝"整板直出必崩"；
3. **门径与验收**：每门有验收清单，用户过门才推进，台账对账 0 ERROR 才封存；
4. **提示词资产化**：每张定稿图六段式沉淀（用途/喂料/原文/尺寸/验收/bad case）；
5. **实证的改写规则**：210 张受控复现实验的结论——参考图通道强于文字通道；模型听定性/数量/禁止词，不听数值/状态词；信息缺失改提示词即可，人体几何必须提示词＋参考图组合。

## 现状

- 方法论在两个完整角色（G0–G14 全门）上跑通；第三个角色由**全新对话只靠本 Skill** 完成 dogfooding（G0–G12，106 件媒体、17 件派生交付物、封存 0 ERROR/0 WARN），暴露的 8 条缺口已全部修复，见 [`docs/DOGFOODING.md`](docs/DOGFOODING.md)。
- 画风、门集合、插槽、画幅全部 **profile 化**；默认 profile 是皮克斯/盲盒手办感 3D（`gates-blindbox3d-v1`），**只是一个示例**，不绑定任何具体角色。

## 目录

```
character-asset-kit/
├── SKILL.md                     # Agent 入口：硬约束、门径地图、按需加载表
├── references/                  # 方法论大脑（Agent 按需读取）
│   ├── gates-g0-g9.md           #   核心九门作业手册
│   ├── gates-g10-g14.md         #   微表情/机位视线/场景/风格变体/训练备料
│   ├── prompt-framework.md      #   六段式提示词模板
│   ├── prompt-rewrite-rules.md  #   实证改写规则（210 张实验）
│   ├── bad-cases.md             #   崩图目录 BC-01…33
│   ├── acceptance-checklists.md #   逐门验收清单
│   ├── registry-rules.md        #   台账 E/W 规则码
│   └── style-profiles.md        #   怎么换画风/裁剪门
├── profiles/gates-blindbox3d-v1.json  # 示例 profile（门/插槽/画幅/单元）
├── templates/                   # 规格卡、资产清单、训练配置模板
├── scripts/                     # 确定性工序（Python 3.10+ / Pillow）
│   ├── charkit/                 #   抠图、标准格、九种拼板、字体
│   └── bin/                     #   init / standard_cell / colorkey_cutout /
│                                #   build_board / asset_index / scene_board /
│                                #   style_board / trainset（+ subjectmask.swift）
├── tests/                       # 纯标准库 unittest（不联网、不依赖 macOS Vision）
├── examples/                    # 脱敏的端到端走查
└── docs/                        # PRD / DESIGN（SDD）/ DOGFOODING
```

## 快速开始

1. 把本目录放进 Agent 的 skill 发现路径（豆包：`~/.doubao/agent_mode/workspace/.user_skills/`，软链即可；其他 Agent 按其 Skill 约定放置）。
2. 用户说"建一个新角色"，Agent 读 `SKILL.md` 并初始化角色包：
   ```bash
   python3 scripts/bin/kit_init_character.py --dir CHAR-01-demo --root /path/to/library
   ```
3. 与用户共写规格卡（G0）→ 母版（G1）→ 逐门推进到封存（G9）；扩展门 G10–G14 按需启用。
4. 每门的喂料、脚本命令、验收项在 `references/` 按需读取。

典型脚本用法：

```bash
# raw 落标准格（macOS 自动抠图；非 macOS 先自行抠图再 --already-cutout）
python3 scripts/bin/kit_standard_cell.py --char CHAR-01-demo --unit master --in raw.png --variant white
# 深色道具 Vision 失败时的纯白底色键兜底
python3 scripts/bin/kit_colorkey_cutout.py raw.png cut.png
# 拼板（干净版 / 验收版）
python3 scripts/bin/kit_build_board.py --char CHAR-01-demo --type multiview
python3 scripts/bin/kit_build_board.py --char CHAR-01-demo --type all --review
# 台账登记与对账（封存要求 0 ERROR）
python3 scripts/bin/kit_asset_index.py --char CHAR-01-demo --scaffold
python3 scripts/bin/kit_asset_index.py --char CHAR-01-demo --check
```

## 环境

- Python 3.10+、Pillow（`pip install pillow`），纯 Python 侧无其他必需依赖。
- 自动抠图（subjectmask）依赖 **macOS Vision**：Swift 源码随仓，首次 init 自动 `swiftc` 编译（只发源码不发二进制）。非 macOS 用任意抠图工具后传 `--already-cutout`，或对纯白底素材用跨平台色键脚本 `kit_colorkey_cutout.py`。
- 生图模型与工具由运行时提供；方法论以 `seedream_5.0_pro` 为默认绑定写成，其他运行时按 `references/gates-g0-g9.md §0` 替换等价能力。
- 中文字体默认冬青黑体（macOS 自带）；其他平台需为拼板指定可用 CJK 字体。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 边界

- **不做 LoRA 训练本身**：G14 只产出数据集（双 caption profile、分层 val、哈希校验）与训练外执行指南，训练在库外（kohya / ai-toolkit）。
- 不做文章配图型插画、不做真人写实照片、不模仿在世艺术家。
- 脚本只做确定性像素工序与台账，不做审美判断；过门决策在人。
- 不发 pip 包：调用方是 Agent，复制 Skill 目录即用。

## 文档

- [docs/PRD.md](docs/PRD.md)：产品需求与形态决策
- [docs/DESIGN.md](docs/DESIGN.md)：软件设计说明（架构、数据流、板型、抠图三路径、决策记录、测试策略）
- [docs/DOGFOODING.md](docs/DOGFOODING.md)：第三个角色的自用验证报告（缺口分布、返工统计、结论）
- [CONTRIBUTING.md](CONTRIBUTING.md)：贡献规则
- [CHANGELOG.md](CHANGELOG.md)：版本记录

## License

MIT，见 [LICENSE](LICENSE)。
