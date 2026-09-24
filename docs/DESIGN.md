# DESIGN · 千面工坊·角色资产生产线（character-asset-kit，软件设计说明）

## 1. 硬约束（设计前提）

1. **生图能力在运行时，不在仓内**：Skill 不内置模型权重，只规定 Agent 何时生图、喂什么参考、怎么验收。豆包运行时走宿主工具；其他运行时由可选的零依赖 HTTP 适配器 `kit_generate.py`（v1.2）承担，模型名是配置项，门径不认识任何厂商。
2. **确定性与审美分离**：凡是几何、排版、落格、拼板、台账，必须由 Python 脚本确定性完成；凡是长相、表情、构图好坏，由人＋Agent 判断。
3. **单元直出，禁止整板直出**：模型一次只生成一个单元（一张正面、一个表情、一个道具），多格板由脚本拼。整板直出的手指/五官/镜像错误无法单格返工。
4. **标签永远在画面之外**：所有拼板标签渲染在独立图框区，不压资产像素。
5. **profile 化**：画风、头身比、门集合、插槽、画幅全部来自 profile JSON；默认盲盒 3D profile 只是示例。
6. **零必需重依赖**：Python 3.10+ 与 Pillow 即可跑全部确定性工序；macOS Vision 抠图是可选增强。
7. **不绑定私有资产**：仓内不出现任何私有角色名、内部路径；模板用 `{CODE}` 占位。

## 2. 总体架构

```
SKILL.md                 # Agent 入口：硬约束、门径地图、按需加载表
references/              # 方法论大脑（Markdown，Agent 按需读）
  gates-g0-g9.md         #   核心九门作业手册（每门：目标/输入/生图单元/脚本/验收）
  gates-g10-g14.md       #   扩展门：微表情矩阵/机位视线/场景/风格变体/训练备料
  prompt-framework.md    #   六段式提示词模板
  prompt-rewrite-rules.md#   实证改写规则（210 张受控实验）
  bad-cases.md           #   崩图目录 BC-01…33：现象/根因/修法
  acceptance-checklists.md # 逐门验收清单
  registry-rules.md      # 台账 E/W 规则码
  runtime-portability.md # 多运行时生图（v1.2）：提供商矩阵/最小再验证
  style-profiles.md      # 换画风/裁剪门/副本约定
profiles/                # 门径 profile（示例：gates-blindbox3d-v1）
templates/               # 规格卡 / 资产清单 / trainset config 模板
scripts/
  charkit/               # 库：assets（抠图/落格）· board（画布/字体）· boards（九种板）· fonts
  bin/                   # CLI：init / standard_cell / colorkey_cutout / build_board /
                         #      asset_index / scene_board / style_board / trainset / generate
  bin/subjectmask.swift  # macOS Vision 抠图源码（init 时 swiftc 现编译，不发二进制）
examples/                # 走通门径的脱敏示例说明
tests/                   # 纯标准库 unittest（不依赖网络、不依赖 macOS Vision）
```

## 3. 门径模型（G0–G14）

核心门 G0–G9：立项 → 母版 → 五视图 → 基础表情 → 细节特写 → 营销胸像 → 动作姿态 → 道具 → 拼板/商卡（含角色设定板）→ 封存。
扩展门 G10–G14：微表情矩阵（情绪族×L1/L2/L3）、机位与视线、场景包、风格变体、训练素材备料。

门的定义在 profile 的 `gates[]`（id/name/enabled），资产插槽在 `slots`，单元词表在 `units`。裁剪一个项目 = 复制 profile 副本把 `enabled` 置 false（命名约定见 style-profiles §5）。

**确认粒度**：门级。门内 Agent 自检、崩图单格返工；整门干净版＋验收版一次交用户过门。

## 4. 关键数据流

### 4.1 角色包结构（init 生成）

```
<CODE>-<slug>/
├── 00_角色规格卡_<CODE>_v1.0.md   # 身份签名最高权威（G0 与人共写）
├── 资产清单.json                   # 计划：九种板的输入配置（脚本读）
├── 资产档案.json                   # 账：扫描登记的 media 与派生交付物（脚本写）
├── 01_母版/ 02_多视图/ 03_表情/ 04_细节特写/ 05_营销胸像/
├── 06_动作姿态/ 07_道具/ 08_提示词库/ 09_风格变体/ 10_商卡成品/
├── 11_训练素材/ 12_场景包/
└── 99_过程稿/                      # raw、废稿、版本留档（不进成品）
```

每个成品插槽内固定三件套：`单图/`（落格 PNG）、`raw/`（模型原图）、`拼板/`（干净版＋验收版）。

### 4.2 从 raw 到拼板

1. Agent 生图 → raw 存 `raw/`（保存后必须转真 PNG 并放大目检，聊天缩略图不算验收）。
2. `kit_standard_cell.py`：subjectmask（macOS Vision）或 `--already-cutout` / `kit_colorkey_cutout.py`（近白色键兜底）抠图 → 按 profile 画幅落标准格（竖版 1773×2364、角色高 0.80、足底锚定、接触阴影；胸像无阴影；道具/细节方格 2364²）。
3. `kit_build_board.py --type <板型>`：读 `资产清单.json` 的该板配置，从 `单图/` 取格，charkit.boards 确定性拼板；`--review` 出带对齐线/边界的验收版。
4. `kit_asset_index.py --scaffold` 登记新文件、`--check` 对账（E/W 规则码见 registry-rules.md）。

### 4.3 台账（资产档案.json）

`kit_asset_index.py` 按目录约定扫描磁盘，绝不靠 Agent 手工记账：
- media 行：路径/插槽单元/标签/版本/完成度/角色/门/宽高；
- derived_deliverables 行：拼板与商卡；
- 规则码：E1 路径不存在 · E2 规格卡指向缺失 · E3 多份规格卡未指现行 · E4 版权声明空 · E5 done 门缺最小产物 · E6 版本无对应变体 · E7 缺必填字段；W1 磁盘 PNG 未登记 · W2 清单产物未生成 · W3 目录未登记 · W4 门状态与产物矛盾 · W5 同键多版本 · W6 旧规格卡仍 draft · W7 编号冲突。
- 封存门槛：0 ERROR（WARN 需逐条说明，如有意裁剪的 W2）。

## 5. 九种确定性板（charkit.boards）

| 板 | 输入 | 关键确定性约束 |
|---|---|---|
| multiview 多视图 | 正/左右侧/背/3/4 侧 | 格高对齐、标签画面外 |
| expression 基础表情 | 6 表情（含中性） | 只许头肩、按清单顺序 |
| detail 细节特写 | 发型/面部/鞋/配饰/帽前/帽后 | 方格 2364²，bbox 0.86 |
| pose 动作姿态 | A/B/C 组动作 | 全身、足底锚定 |
| prop 道具 | 单体＋手持关系 | 单体 `--square --no-shadow`；比例对照固定 |
| micro_expression 微表情矩阵 | 情绪族×L1/L2/L3＋中性 | **空 levels 族自动跳过**（#008）；只许头肩 |
| gaze 机位视线 | 俯仰×视线 | 头肩 |
| character_sheet 角色设定板 | 胸像＋2×2 全身＋8 字段＋色板＋表情＋细节 | 2430×3240；字段自动收进列宽禁止压字；`meta` 是成品文字 |
| card 商卡 | 清单配置 | 由清单 height 收口 |

场景总览板与风格五视图板分别由 `kit_scene_board.py`、`kit_style_board.py` 构建。

## 6. 抠图三条路径（平台边界）

1. **subjectmask（macOS，默认）**：Swift 调 `VNGenerateForegroundInstanceMaskRequest`；init 时 `swiftc` 现编译，二进制不入库。
2. **色键兜底 `kit_colorkey_cutout.py`**：仅适用纯白无缝底——四边泛洪近白背景转透明，MinFilter 收缩 1px＋高斯羽化，输出背景占比自检 WARN。针对 Vision 对深色小道具确定性 `no subject found`（BC-28）。
3. **第三方抠图＋`--already-cutout`**：非 macOS，或面部微距（皮肤满幅、Vision 会过度语义分割剥皮）时，外部工具抠好直接落格。

## 7. 提示词方法论（references，脚本之外的另一半）

- **六段式沉淀**：每张定稿图记录 用途 / 参考图喂料 / 提示词原文 / 尺寸口径 / 验收结论 / bad case，存 `08_提示词库/`。
- **实证改写规则**来自 210 张受控复现实验（**180 张三组主实验**：带净面母版 / 带缺陷废稿 / 纯文本各 60，**＋30 张 P1 提示词改进验证**；身份统计基于 180；另有 15 张 G1 探路批不计入）：参考图通道强于文字通道；模型听定性词、数量词、禁止词，不听数值词与状态词；信息缺失改提示词即可，人体几何必须提示词＋参考图组合。
- **bad-cases.md** 是失败知识库：每条含现象、根因、修法；新失败在门内回灌并升 Skill 版本。

## 8. 决策记录（被否选项与代价）

| 决策 | 被否选项 | 代价/理由 |
|---|---|---|
| Skill 形态 | pip CLI / 自主 Agent / 纯模板 | 见 docs/PRD.md §4 |
| 脚本落格拼板 | 让模型整板直出 | 整板崩图无法单格返工，实测必崩 |
| 标签画面外 | 标签压在图上 | 压字污染像素、干扰后续模型识别 |
| 只发 Swift 源码 | 发编译好的二进制 | 二进制不可审计、跨架构失效；现编译一次即可 |
| Pillow 为唯一重依赖 | 引入 OpenCV/rembg | 开箱成本与平台兼容；抠图交给系统 Vision/色键/外部工具三选一 |
| 不做 pyproject 打包 | 发 pip 包 | 调用方是 Agent 不是 shell 用户；复制目录即用，版本随 Skill 走 |
| 方格边长服从实现（2364） | 改代码凑文档的 2048 | 2364 是标准格长边、几何自洽；要 2048 显式 `--cell`（#004） |
| G14 只备料不训练 | 内置训练 | 训练环境/模型许可在库外，库内只保证数据集规格 |
| 生产线与生图解耦（v1.2） | 把模型名写死进脚本/提示词 | 模型会换代、运行时不同；门径/提示词/落格/台账与厂商无关，出图只占一个可替换插槽 |
| 非豆包默认推荐 OpenRouter 网关（v1.2） | 只对接 OpenAI 官方 / 每家各写一套 | 一把 key 触达约 30 个图像模型（含 Seedream/Gemini/GPT-Image），用户换模型不改代码；官方端点与 Gemini 仍单独支持 |
| 适配器纯标准库 + 离线 mock 测试（v1.2） | 引官方 SDK / 真机测试入仓 | 零依赖原则；密钥不进仓，真机回归**不写进测试套件**（跑一次即弃、结论回灌文档），请求形状用 mock 锁定；v1.2.1 起方舟已由维护者持密钥真机回归一次，结论落 `runtime-portability.md` |

## 9. 测试策略

`tests/` 为纯标准库 unittest，不联网、不依赖 macOS Vision：

- **端到端冒烟**：临时目录 init 新库 → scaffold → check 断言 0 ERROR、模板含全部九种板配置；
- **板构建**：缺配置段 exit 2；`--all` 缺核心板 WARN；空 levels 族不产生空白行（板高正确）；
- **落格几何**：高主体在错误参数组合下抛 ValueError；`--square` 输出 2364²；
- **色键**：合成近白底图泛洪抠除、深色主体保留、背景占比在合理区间；
- **CLI 守卫**：`--all --char` 互斥 exit 2；空枚举 exit 2；库根不存在 exit 2 且无 traceback；
- **生图适配器（v1.2，test_generation）**：monkeypatch 唯一网络出口，锁定五提供商请求形状（OpenAI generations/edits multipart 单图与多图、Gemini generateContent 的 inline_data 与 aspectRatio、OpenRouter /images 的 input_references）、模型解析优先级、自动探测、429 重试/4xx 终态、dry-run 不联网、JPEG→PNG 归一、参考图上限与缺 key 退出码。

三层验证各有盲区：unittest 查不出审美问题与模型侧崩图；目检查得出崩图但查不出台账漂移；台账 0 ERROR 不代表图好看。三层都过才封存。

## 10. 已知边界与未来项

- 生图模型相关的画幅回退（如横版返回等比不同分辨率）由拼板 contain 吸收，不做强制。
- 非 macOS 的自动抠图未内置（三选一里路径 2 色键可跨平台，路径 3 依赖外部工具）。
- 中文字体：默认冬青黑体（macOS 自带）；其他平台需在板构建时指定可用 CJK 字体路径。
- 训练在库外；G14 产物面向 kohya/ai-toolkit 目录约定。
- 生图适配器（v1.2）的**方舟（ark）通路已于 v1.2.1 持密钥真机回归**（顺手修掉四条静态检查抓不到的缺陷：JSON-only 图生图端点、显式 `watermark:false`、错误分类、密钥候选——见 CHANGELOG v1.2.1 与 `runtime-portability.md` 的方舟实测段）；**其余四家（openai / google / openrouter / custom）仍仅离线 mock 验证、未持密钥真机回归**。DashScope/即梦/Replicate 与 ComfyUI 本地 CUDA 暂只留契约（runtime-portability §7/§8），需要时按同一适配器模式扩展。
