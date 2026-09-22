# examples/

本目录不放任何私有角色资产。这里给一份**脱敏的端到端走查**：一个虚构角色 `CHAR-01-demo` 从零到封存的完整命令序列与每门的验收口径。
真实 dogfooding 的统计数据（106 件媒体、17 件派生交付物、8 条缺口与修复）见 [`../docs/DOGFOODING.md`](../docs/DOGFOODING.md)。

## 0. 建库与建包

```bash
mkdir my-character-library && cd my-character-library
python3 /path/to/character-asset-kit/scripts/bin/kit_init_character.py \
  --dir CHAR-01-demo --root .
```

产出：规格卡、资产清单（已含九种板配置）、12 个插槽目录、提示词库骨架；macOS 下还会现编译并随包放一份 subjectmask。

## 1. 门径走查（每门＝用户过门一次）

| 门 | 生图单元（逐张，不整板直出） | 确定性工序 | 过门口径 |
|---|---|---|---|
| G0 立项 | 无 | 与人共写规格卡：身份签名、HEX、版权声明、门裁剪 | 规格卡唯一现行；E2/E3/E4 不触发 |
| G1 母版 | 白底母版（竖 1773×2364） | `kit_standard_cell` 落格（白/透两版） | 身份签名逐项对得上；占格/足底口径正确 |
| G2 五视图 | 正/左右侧/背/3/4 侧 | 落格 → `kit_build_board --type multiview`（＋`--review`） | 五视角等高、镜像错误为 0；正面若复用母版必须重新落格，不得字节拷贝 |
| G3 基础表情 | 6 表情（含中性），只许头肩 | `--type expression` | 五官 AU 叠加、不拧脸；标签画面外 |
| G4 细节特写 | 发型/面部/鞋/配饰等方格 | `kit_standard_cell --square`（2364²）；深色道具 Vision 失败走 `kit_colorkey_cutout` | 微距皮肤满幅＋`--already-cutout`；无白边 |
| G5 营销胸像 | 胸像（`--bust`） | 胸像落格（无阴影） | 顶边距 3.5%、下沿切上胸 |
| G6 动作姿态 | A/B/C 组全身动作 | `--type pose`；复杂人体几何先出几何参考图再二步生成 | 手指数/关节正常；每动作单格返工不扰其他格 |
| G7 道具 | 单体方格＋比例对照＋手持关系 | 单体走 `--square --no-shadow`（**不要**用 `--fig-ratio/--sole-ratio` 组合，必然裁顶） | 单体完整；手持比例经用户确认 |
| G8 拼板/商卡 | character_sheet 胸像与 2×2 全身网格所需单元 | `--type character_sheet`、`--type card`；`--type all --review` 一次出全 | 清单 `meta` 是**成品文字**（不是备注栏）；字段不压字；2430×3240 |
| G9 封存 | 无 | `kit_asset_index --char CHAR-01-demo --scaffold` 后 `--check`；九份提示词入 `08_提示词库/` | **0 ERROR**；WARN 逐条说明（裁剪门的 W2 可接受） |

扩展门（按需）：

| 门 | 要点 |
|---|---|
| G10 微表情矩阵 | 4 情绪族×L1/L2/L3＋中性＝13 格；只许头肩；`levels` 为空的可选族自动跳过，不产生空白行 |
| G11 机位与视线 | 俯仰×视线方向；`--type gaze` |
| G12 场景包 | 竖 3:4＋横 16:9（横版模型可能回等比不同分辨率，拼板 contain 吸收）；`kit_scene_board` |
| G13 风格变体 | 换风格语言时显式重写材质/轮廓规则（如黏土风明示圆润四指）；`kit_style_board` |
| G14 训练备料 | `kit_trainset` 产出数据集（双 caption profile、face/medium/full 分组、val 分层、哈希校验）；训练在库外 |

## 2. 每门的标准循环

1. Agent 读门手册（`references/gates-*.md`）与验收清单；
2. 单请求单图生成 raw → 存 `raw/` → 转真 PNG → 放大目检（聊天缩略图不算验收）；
3. 崩图单格重出，不整板重来；
4. 落格 → 拼板（干净版＋验收版）；
5. 本门提示词按六段式追加进 `08_提示词库/`（用途/喂料/原文/尺寸/验收/bad case）；
6. 整门一次交用户过门。

## 3. 裁剪门范围

复制 `profiles/gates-blindbox3d-v1.json` 到库根 `profiles/profile_<profile-id>_<代号>_<门范围>.json`，
把不做的门 `enabled` 置 false，并在规格卡 §0 声明；中途扩展门范围时新建副本、旧副本留痕。

## 4. 常见失败的第一反应

- Vision 报 `no subject found`（深色小道具）→ `kit_colorkey_cutout.py`（仅限纯白底）；
- Vision 把面部皮肤当背景剥掉 → 微距拍满幅，外部抠图后 `--already-cutout`；
- `--all` 跑完 0 输出 → 你在角色包内却用了 `--all`；包内用 `--char .`（互斥守卫会 exit 2）；
- 构建角色设定板报"配置段缺失"（exit 2）→ 对照 `templates/资产清单_模板.json` 补 `boards.character_sheet`；
- 台账 W1 一片 → 先 `--scaffold` 登记再 `--check`。
