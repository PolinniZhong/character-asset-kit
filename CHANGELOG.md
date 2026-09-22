# Changelog

本文件记录 character-asset-kit 的变更；方法论/提示词层的变化同时回灌 references/ 并在门径文档标注。

## v1.2.2（2026-09-22）— 参考图配置：新增一个维度（六轮真机实测）

追加密一个表情格时连出六张构图漂移的图，**前五轮全部失败，且没有一次是模型能力问题**——全是**参考图配置问题**。
此前 `prompt-rewrite-rules.md` §1 已写"参考图通道 ＞ 文字通道"，但只讲了"提示词怎么写"，**没讲"该喂哪张参考图"**；本版补上这一维度。

- **新增 `prompt-rewrite-rules.md` §7「参考图配置」**：
  - 构图锚**一次只给一个**，且其取景必须**就是目标的取景**；
  - **不要混景别喂双锚**——实测"全身母版（占高 65.4%）＋胸像锚（90.9%）"是**最差**组合：模型两张都不跟，把主体撑到 **100% 占高、头顶贴边**；
  - **不要拿成品资产当构图锚**（成品头已放大/裁切对位，等于照抄放大构图）；
  - 换模型时**先怀疑参考图，再怀疑模型**：同一个"构图错"在 Pro 与 Lite 上都出现，锚配对时两者都听话；
  - 纠正后的单锚配置：输出 **95.3%**、落格后 **90.4%**，与既有基准格（90.9% / 91.0%）一致。
- **新增坏例 `bad-cases.md` BC-34**（编号按 registry 顺延）：完整记录六轮迭代的模型×参考图×结果对照表。
- **再次复现既有口径**：把取景写成明文百分比（"头顶留白约 4.5%""下巴在 55%""宽度不超 70%"）**仍被 100% 忽略** —— 取景靠锚与确定性后处理，不靠数值（§2 表"数值服从度低"第 4 次复现）。
- **落格的边界写清**：`kit_standard_cell --bust` 只归一"整体大小/位置"，**修正不了"景别不对"** ⇒ 锚仍要选对。
- 验证：全仓 **43 个测试全绿**；本轮改动为纯文档（`references/` 两份），无代码变更。

## v1.2.1（2026-09-22）— 方舟（ark）真机验证修复：图生图、零水印、错误分类、密钥候选

v1.2 的五个 HTTP 适配器只有离线 mock 测试。这一版**第一次持密钥把 `ark` 打通**（`doubao-seedream-5-0-lite-260128`，标准格 `1773x2364`），
一跑就掉出**四条静态检查抓不到的缺陷**。逐条修复并补了**证伪过的**用例（把 bug 放回去会红）：

- **① 图生图端点错（阻塞级）**：`ark` 原先和 OpenAI 共用 multipart `/images/edits`。实测方舟**没有这个端点**（curl 404），
  且该端点**只收 JSON**——multipart（字段名 `image`、`image[0]` 都试过）一律回 `we could not parse the JSON body`。
  新增 `edit_as_json` 开关：方舟图生图改走 `/images/generations` + JSON `image` 字段（data URI，单图字符串／多图数组）。
  ⇒ **不修则门径里所有"以参考图生成"的步骤（G2 之后几乎每一步）在方舟上全废。**
- **② 零水印红线被破（阻塞级）**：`ark` 原负载不含 `watermark`，而方舟**默认 `true`** ⇒「AI生成」水印**烧进像素**，
  直接违反硬约束 4。同提示词对照实测：`true` 右下角 5,614 个痕迹像素 / `false` 163 个（增强后 `true` 可读出「AI生成」）。
  JSON 类提供商现在**始终显式发 `watermark: false`**。
- **③ 错误分类误导**：服务端提前关连接（如打了不存在的端点）会以 `BrokenPipeError` 落进 `except URLError`，
  旧文案一律写「网络不可达」⇒ 拿着 404 的病因去查网络。现按异常类型分流，`BrokenPipeError/ConnectionResetError`
  明确报「连接被服务端提前关闭……先核对请求地址/负载格式，不要按网络问题排查」。
- **④ 密钥名硬编码**：`key_env` 原为单字符串 `ARK_API_KEY`，而 DSH/豆包侧按模型 id 推导的名字是
  `DOUBAO_SEEDREAM_5_0_PRO_260628_API_KEY` ⇒ 用户配了 key 仍报"缺少环境变量"。
  改为**候选表**（字符串或 list 均支持），按序取第一个有值的。
- **顺带两处口径修正**：`ark` 的 `default_model` 由 `None`（必须显式传）改为 `doubao-seedream-5-0-pro-260628`（与 Skill 默认一致）；
  docstring 里"`--model` 传推理端点 id"更正为**传模型 id**（实测模型名可用，旧注释误导）。
- **文档**：`references/runtime-portability.md` 提供商矩阵拆分"方舟"与"自建/兼容网关"两行，并补一段方舟实测事实
  （JSON-only、无 `/images/edits`、水印默认 true、密钥候选、尺寸区间 3,686,400–16,777,216 px、标准格 1773×2364 可直接用）。
- **测试**：`tests/test_generation.py` 20 → **28 个用例**（新增 ark 图生图 JSON 形状、多图数组、dry-run 不发请求、
  密钥候选回落、gen/edit 两处 watermark 断言、BrokenPipe 文案回归）；全仓 **43 个测试全绿**。
- **验证边界（如实声明）**：本轮真机只覆盖 **ark**；`openai`/`google`/`openrouter`/`custom` **仍未持密钥验证**。
  另注：本轮实测**未重现**取景漂移是否与模型相关——同一条提示词在 lite 上仍是"头部占满画幅"，
  说明**取景由提示词决定、与 ark 通路无关**（该现象在 seedream_5.0_pro 上同样存在，见 prompt-rewrite-rules §配方 A）。

## v1.2（2026-09-22）— 多运行时生图支持（生产线与出图解耦）

- **定名「千面工坊 · 角色资产生产线」**（slogan：千面如一）；技术名/仓库名/frontmatter `name` 仍为 `character-asset-kit`（标识符不改，避免破坏 Skill 发现与引用），中文名进 SKILL.md 标题与 description 触发词、双语 README。
- **新增跨运行时适配器 `scripts/bin/kit_generate.py`（纯标准库）**，支持五家提供商：
  - `openrouter`（OpenRouter Images 统一网关，一把 key 触达 Gemini/Seedream/GPT-Image/Recraft/Flux 等约 30 个模型，推荐的非豆包入口）；
  - `google`（Gemini 图像 generateContent，默认 `gemini-2.5-flash-image`，多参考编辑，参考图上限预检 3）；
  - `openai`（Images generations/edits multipart，默认 `gpt-image-2.5-flare`，参考图上限 16）；
  - `ark`（火山方舟 OpenAI 兼容网关，`--model` 传推理端点）；
  - `custom`（任意 OpenAI Images 兼容端点，`OPENAI_BASE_URL` + `--keep-size`）。
- 模型解析优先级：`--model` ＞ 环境变量 `<PROVIDER>_IMAGE_MODEL` ＞ 内置默认；`--provider` 省略时按已存在的 key 自动探测（openrouter→google→openai→ark）。
- 工程行为：一次调用只出 1 张；429/5xx 指数退避重试 2 次、4xx 直接失败；`--dry-run` 离线打印请求形状（不调用不花钱）；非 PNG 返回（JPEG/WebP）自动归一为 PNG 落盘；竖版 3:4 在 gpt-image 族映射为 1024×1536（2:3，比例差由 standard_cell 落格吸收），Gemini/OpenRouter 走宽高比枚举。
- profile `runtime` 块扩为五提供商（含能力位、密钥环境变量、选型注释）；新增 `references/runtime-portability.md`（提供商矩阵、能力清单、选型建议、最小再验证 G1/G2/G3/G7、密钥纪律、本地 CUDA CLI 契约、调研来源）。
- SKILL.md 硬约束第 3 条由"模型绑定"改为"运行时路由"；README/README.en 增"非豆包运行时"章节。
- 测试：新增 `tests/test_generation.py` 20 个离线用例（五提供商请求形状、multipart 单/多图、Gemini inline_data 与 3:4、OpenRouter input_references、自动探测、env 模型覆盖、429 重试/4xx 终态、dry-run 不联网、JPEG→PNG 归一、参考图超限、缺 key/缺 model 退出码），全仓 34 个测试全绿。
- **诚实更正**：v1.2 讨论初期我曾断言"OpenAI 只有 gpt-image-1、没有 Image 2.x"。该说法错误：OpenAI 已于 2026-09-08 在 API 发布 `gpt-image-2.5-flare` 与 `gpt-image-2.5-sunburst`（另有 gpt-image-2、gpt-image-1.5）。默认模型已按此修正。
- **验证边界（如实声明）**：豆包宿主工具路径已在生产与 DSH 实测跑通；五个 HTTP 适配器的请求形状依据公开文档与两个对标开源 skill（baoyu-image-gen、k-dense/generate-image）实现，仅经离线 mock 测试，**未持密钥真机回归**；首次接入需按 runtime-portability §4 跑最小再验证。

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
- **自查纠错**：v1.0 的 CHANGELOG 声称"BC-01–27"随首版分发，但 `bad-cases.md` 实际只在门径文档中引用了编号、目录文件缺失；v1.1 据框架 bad case 表、210 样本复现实验与 dogfooding 记录整理为完整 BC-01–33（每条四段：现象/根因/修法/首现门）。

## v1.0（2026-09-21）— 首版封装

G0–G14 门径、blindbox3d profile、六段式提示词框架、210 样本改写规则、BC-01–27、确定性脚本（init/standard_cell/build_board/scene_board/style_board/asset_index/trainset＋subjectmask.swift）。
