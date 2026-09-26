# 跨运行时 / 跨模型移植指南

> skill 的生产线（门径、提示词框架、落格、拼板、台账、训练备料）与**谁来出图**解耦。
> 本文说明：在非豆包运行时里怎么换生图模型、换之前要验证什么、哪些结论不能跨模型照搬。
> 能力表核对日期 **2026-09-22**（来源：各厂商公开文档与两个高星开源 skill：baoyu-image-gen、k-dense/generate-image）；模型迭代快，以 `--dry-run` 与厂商当时文档为准。

## 1. 两层结构，先分清

| 层 | 内容 | 是否与模型相关 |
|---|---|---|
| 生产线层（本 skill 主体） | G0–G14 门径、单元拆分、六段式提示词、标准格/拼板/台账脚本、BC 目录 | **无关**，任何模型都照跑 |
| 生图运行时层 | 文生图、参考图编辑、出 raw 像素 | **强相关**，由宿主工具或 API 适配器承担 |

**换模型不换流程**：替换的只是每门"生成 raw"这一步，后续抠图、落标准格、拼板、验收、台账完全不变。

## 2. 运行时接法与提供商矩阵

| 运行时 | 出图方式 | 参考图编辑 |
|---|---|---|
| 豆包（默认） | 宿主工具 `image_gen` / `image_edit`，模型 `seedream_5.0_pro`，每请求单图 | 原生多参考，参考图必须实际传入 |
| OpenRouter 统一网关（推荐的非豆包入口） | `kit_generate.py --provider openrouter`，一把 key 触达 Gemini / Seedream / GPT-Image / Recraft / Flux 等约 30 个模型 | 取决于具体模型（选多模态图像模型） |
| Google Gemini | `--provider google`（`generateContent`，默认 `gemini-2.5-flash-image`） | 强；2.5-flash 参考图上限 3，gemini-3 族 14 |
| OpenAI 官方 | `--provider openai`（`/images/generations`、`/images/edits`，默认 `gpt-image-2.5-flare`） | multipart，单图字段 `image`、多图重复 `image[]`，上限 16 |
| 火山方舟（豆包自家 API） | `--provider ark`（`/images/generations`；默认 `doubao-seedream-5-0-pro-260628`，可 `--model` 换 lite/4.5 等） | **JSON `image` 字段**（data URI），单图字符串、多图数组；**没有 `/images/edits`** |
| 自建 / 兼容网关 | `--provider custom --base-url …`（OpenAI Images 兼容） | 多为 multipart `/images/edits`，看网关实现 |
| 本地 CUDA（ComfyUI / Flux / SD） | 自包命令行，契约见 §7 | 取决于工作流（IP-Adapter / Flux Kontext 等） |

> OpenAI 的图像模型权重不开放，**不能在本地 CUDA 上跑**；本地 CUDA 是开源权重路线，走 §7 自包。

> ★ **方舟（ark）已做真机验证（2026-09-22，`doubao-seedream-5-0-lite-260128`）** —— 此前是"照文档写、未持密钥验证"，
> 一跑就掉出四条静态检查抓不到的问题，都已在 `kit_generate.py` 修掉并补了证伪用例：
> ① **只收 JSON**：multipart（字段名 `image` 或 `image[0]` 都试过）一律回 `we could not parse the JSON body`；
> 图生图必须走 `/images/generations` + `image` 字段（data URI，单图字符串／多图数组）。
> ② **端点只有 `/images/generations`**：`/images/edits` 实测 **404**；打错端点时服务端在收完请求体前关连接，
> 表现为 `BrokenPipeError`（脚本现已把它与"网络不可达"**分开报**，否则会被引去查网络）。
> ③ **不传 `watermark` 时服务端默认 `true`，水印会烧进像素**（同提示词对照：`true` 右下角 5,614 个痕迹像素 / `false` 163 个，
> 增强后 `true` 可读出「AI生成」）。与"资产本体零水印"红线直接冲突 ⇒ 脚本对 JSON 类提供商**始终显式发 `watermark: false`**。
> ⚠️ **兼容网关不保证认这个字段**，接入新网关时按 §4 第 5 条做一次零文字目检。
> ④ **key 名按模型可换**：`ARK_API_KEY` 与由模型 id 推导的 `DOUBAO_SEEDREAM_5_0_PRO_260628_API_KEY` 都认
> （脚本按候选表取第一个有值的，换模型不改脚本）。
> ⑤ **尺寸 `passthrough`（原样发）**：实测该模型族下限 **3,686,400 px**、上限 **16,777,216 px**；
> 本线标准格 `1773x2364`＝4,191,372 px **在区间内可直接用**，无需降采样。
> ⑥ `--model` 收**模型 id**（如 `doubao-seedream-5-0-lite-260128`），不是推理端点 id。
> 模型名是配置项：`--model` ＞ 环境变量 `<PROVIDER>_IMAGE_MODEL` ＞ 内置默认。2026-09 时 OpenAI 线上为
> `gpt-image-2.5-flare`（默认向，快）/ `gpt-image-2.5-sunburst`（编辑优先），另有 gpt-image-2 / 1.5 / 1；
> OpenRouter 用完整 id（如 `bytedance-seed/seedream-4.5`、`openai/gpt-image-2`）。

### 选型建议（按本生产线需求）

1. **多参考图编辑是命门**（G2 之后全部依赖）：首选 Gemini 系或 OpenRouter 上的 Gemini/Seedream；
2. 透明底：gpt-image-1 族支持 `background=transparent`（2.5 族以厂商文档为准）；本 skill 另有抠图链路，不依赖模型产透明；
3. 图内文字/签名印花：Recraft v4.1、Riverflow 等文字服从更好（参考社区评测）；本生产线默认零文字，影响小；
4. 画幅：Gemini/OpenRouter 吃**宽高比枚举**（3:4、16:9 直接支持）；gpt-image 族只有固定档位（竖版 1024×1536 是 2:3，
   与本线 3:4 的比例差由 standard_cell 落格吸收）；方舟/网关多为像素透传（`--keep-size`）。

## 3. kit_generate.py 用法

```bash
# key 只走环境变量，绝不写进规格卡/清单/档案/git
export OPENROUTER_API_KEY=...        # 或 GOOGLE_API_KEY / OPENAI_API_KEY / ARK_API_KEY

# 先 dry-run 核对请求形状（不调用、不花钱、不需要 key）
python3 scripts/bin/kit_generate.py --provider google --mode edit \
  --ref 01_母版/CHAR-01_母版_v1.0_白.png --prompt-file p.txt \
  --size 1773x2364 --dry-run

# 文生图（G1 母版等从零起图）
python3 scripts/bin/kit_generate.py --provider openrouter \
  --model google/gemini-3.1-flash-image \
  --mode gen --prompt-file 99_过程稿/p_G1.txt --size 1773x2364 \
  --out 99_过程稿/raw_G1_v1.png

# 参考编辑（G2 之后；--ref 可重复，数量上限随提供商/模型）
python3 scripts/bin/kit_generate.py --provider google --mode edit \
  --ref 01_母版/CHAR-01_母版_v1.0_白.png --ref 99_过程稿/构图参考.png \
  --prompt-file 99_过程稿/p_G2侧面.txt --size 1773x2364 \
  --out 99_过程稿/raw_G2左侧_v1.png

# OpenAI 官方（多图 multipart）
python3 scripts/bin/kit_generate.py --provider openai --mode edit \
  --ref 母版.png --ref 参考.png --prompt "……" --size 1773x2364 --out raw.png

# 火山方舟（--model 传推理端点 id）/ 自建网关
python3 scripts/bin/kit_generate.py --provider ark --model doubao-seedream-... \
  --mode gen --prompt "……" --size 1773x2364 --out raw.png
OPENAI_BASE_URL=https://your-gw/v1 python3 scripts/bin/kit_generate.py \
  --provider custom --model <id> --keep-size --mode gen --prompt "……" --out raw.png
```

行为约定：

- **一次调用只出 1 张**（`n=1` 固定），多张多次调用——与豆包运行时纪律一致；
- raw 一律先进 `99_过程稿/`，再走 `kit_standard_cell.py`；本脚本不拼板、不做审美判断；
- 不传 `--provider` 时按已存在的 key 自动选择（openrouter → google → openai → ark），并打印实际 provider/model；
- 返回 JPEG/WebP 时自动转成 PNG 落盘（生产线落格只收 PNG），日志打印源格式；
- 429/5xx 自动重试 2 次（指数退避），4xx 不重试（请求本身要改）；
- 退出码：`0` 成功；`1` 服务商/网络失败；`2` 用法/配置错误（缺 key、参考图超限、文件不存在）。
- **真机验证状态（诚实声明）**：豆包宿主工具路径已在生产中验证；openai/google/openrouter/ark/custom
  五个适配器的请求形状按公开文档实现、由离线 mock 测试覆盖（34 个 unittest），**尚未持密钥真机回归**；
  首次接入新提供商时请先用 G1 单张冒烟，再跑 §4。

## 4. 换新模型前的最小再验证（必做）

`prompt-rewrite-rules.md` 的服从度数据（85.0/83.3/75.0、配方 A/B/C、"屏幕合上 0/15"等）是 **seedream_5.0_pro 的模型特定结论**，不得跨模型照搬。新模型上线前跑最小 dogfood：

1. **G1 母版 ×3**：纯文生图，检查身份签名可复现性、白底纯净度、默认画幅占比；
2. **G2 五视图**：重点验证**多图参考编辑**（命门）——侧脸镜像率、背面是否变脸、五视图等高；
3. **G4 表情 2 格**：头肩取景是否听话（配方 A 在该模型上是否成立）；
4. **G7 道具手持 1 格**：手部数量、握持接触、道具比例；
5. 文字/印花禁止句对抗测试 5 张（给一张带印花的参考，看零文字禁止句守不守得住）。

结果记进该 profile 的验证小结：哪些 BC 条目仍成立、哪些失效、新模型特有崩点（编号从 BC-34 起顺延，标注适用模型/提供商）。

## 5. 选模型的能力清单（按重要性）

1. **多参考图图生图编辑**（最重要）：能同时吃母版＋构图参考并保持身份；做不到只能跑 G1；
2. 参考图数量上限（Gemini 2.5 flash 为 3、gemini-3 为 14、OpenAI 为 16，OpenRouter 随模型）；
3. 手与手部交互稳定性；
4. 文字服从度（零文字禁止句、签名印花）；
5. 画幅/分辨率档位（决定落格放大倍率与比例裁剪）；
6. 透明底能力（没有也没关系，本 skill 有抠图三路径）；
7. 生成内容商用授权条款（随提供商而变）。

## 6. 密钥与成本纪律

- key 只走环境变量（`OPENROUTER_API_KEY` / `GOOGLE_API_KEY` / `OPENAI_API_KEY` / `ARK_API_KEY`），
  或宿主的凭据服务（如 DSH 的 `ctx.credentials`）；不进任何文件、不进 git；
- 先用便宜模型/低分辨率迭代文案，定稿后再用目标模型出正式 raw；
- 上传参考图前确认版权与服务商数据政策；开源 profile 只写模型名与能力位，不写密钥与内部端点。

## 7. 本地 CUDA（ComfyUI 等）适配器契约

本 skill 不内置 ComfyUI 调用，但你包的命令行只要满足下面契约，就能无缝替换 kit_generate 的位置：

- 输入：`--mode gen|edit`、`--prompt-file`、若干 `--ref`、`--size WxH`、`--out`、`--dry-run`；
- 输出：退出码 0 且 `--out` 是可被 Pillow 打开的 PNG；失败退出码非零并向 stderr 打印原因；
- 一次只出一张；429/5xx 可重试、4xx/参数错不重试；
- 不依赖交互界面（可被 Agent 以子进程方式调用）。

## 8. 参考实现（调研来源）

- **baoyu-image-gen**（JimLiu/baoyu-skills，多提供商生图 skill）：提供商/模型解析优先级、
  能力位路由（有参考图时自动选支持编辑的提供商）、批量任务、质量预设映射；
- **k-dense/generate-image**（OpenRouter Images 的纯标准库 skill）：统一网关思路、
  发请求前按模型目录做参数预检（不支持的参数在计费前本地失败）、`--dry-run`、
  按 `media_type` 决定落盘格式、4xx 终态/限流重试。
