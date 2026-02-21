# 人物卡库说明（character_cards）

本文件说明：人物基础卡库（base_cards）的文件位置、整体结构、以及各字段的意义与填写建议。

## 1. 文件位置

人物基础卡库（永久人物设定）位于：
- [`../src/novels_project/config/character_base_cards.yaml`](../src/novels_project/config/character_base_cards.yaml)

初始化检查会要求该文件存在：[`DesignValidator._check_config_files()`](../src/novels_project/initialize.py:107)

## 2. 核心概念

### 2.1 base_cards 是什么

- **base_cards**：人物的“长期设定”，跨章保持稳定。
- **chapter_character_states**：人物在某一章的“当前状态卡”（由人物设计师 Agent 生成，随剧情变化）。

> 人物设计师会把 base_cards + 本章章大纲 + 前章状态（如有）综合生成状态卡（见 [`character_designer_prompt.md`](../DESIGN/PROMPTS/character_designer_prompt.md)）。

### 2.2 混合模式的三类人物

在 [`character_base_cards.yaml`](../src/novels_project/config/character_base_cards.yaml) 的 `metadata.character_types` 已定义三类：

- `main`：主线人物（需要详细状态卡追踪）
- `supporting`：支线人物（需要中等详度状态卡；本章不出场则不生成）
- `temporary`：临时人物（通常不写入 base_cards；在章节大纲里定义）

规则被写进人物设计师 Prompt：[`character_designer_prompt.md`](../DESIGN/PROMPTS/character_designer_prompt.md)

## 3. 文件结构总览

```yaml
metadata:
  version: ...
  last_updated: ...
  total_characters: ...
  character_types:
    main: ...
    supporting: ...
    temporary: ...
  note: ...

s_tier:
  count: ...
  characters:
    人物名:
      name: ...
      role: ...
      tier: S_TIER
      character_type: main
      core_personality: [...]
      ...

a_tier:
  count: ...
  characters:
    人物名:
      tier: A_TIER
      character_type: supporting
      ...
```

> 目前项目用到 `s_tier` 与 `a_tier`（初始化检查也会遍历这两个 tier）。

## 4. 字段逐项说明（建议稳定）

### 4.1 顶层 `metadata`

| 字段 | 类型 | 含义 |
|---|---|---|
| `version` | string | 人物卡格式版本/阶段标识 |
| `last_updated` | string | 最近更新时间（建议 YYYY-MM-DD） |
| `total_characters` | number | 人物数量统计（可人工维护） |
| `character_types` | map | 对 `main/supporting/temporary` 的文字解释 |
| `note` | string | 补充说明（例如临时人物写在 outline） |

### 4.2 `s_tier` / `a_tier`

| 字段 | 类型 | 含义 |
|---|---|---|
| `count` | number | 该 tier 人物数（可人工维护） |
| `characters` | map | key 为人物名，value 为人物卡 |

### 4.3 单个人物卡（建议字段）

> 初始化检查要求（至少）：`name`、`role`、`core_personality`、`unique_speaking_style`（见 [`DesignValidator._check_character_base_cards()`](../src/novels_project/initialize.py:132)）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 人物名（建议与键一致） |
| `role` | string | 叙事功能定位（主角/反派/导师/盟友等） |
| `tier` | string | `S_TIER` / `A_TIER` 等，用于区分重要度 |
| `character_type` | string | `main` 或 `supporting`（临时人物通常不写入 base_cards） |
| `core_personality` | list[string] | 核心性格标签（用于生成一致口吻与行为） |
| `character_flaw` | list[string] | 缺点/弱点（可选但很有用） |
| `core_motivation` | string | 核心动机（推动行为一致性） |
| `bottom_line` | list[string] | 底线（用于限制行为，避免 OOC） |
| `unique_speaking_style` | map | 说话风格对象（强烈建议完整填写） |
| `signature_habits` | list[string] | 标志性动作/习惯（用于 Show not tell） |

### 4.4 `unique_speaking_style`（强烈建议结构化）

当前样例结构见：[`character_base_cards.yaml`](../src/novels_project/config/character_base_cards.yaml)

| 字段 | 类型 | 说明 |
|---|---|---|
| `tone` | string | 总体语气（冷静/粗鲁/古雅等） |
| `characteristics` | list[string] | 口癖、句式倾向、语言习惯 |
| `example_dialogues` | list[string] | 示例台词（初始化检查建议 ≥2 条） |
| `speaking_frequency` | string | 话痨/话少等（帮助控制对白密度） |
| `avoid_patterns` | list[string] | 需要避免的表达方式（防止跑偏） |

初始化检查会提示对话示例过少：[`DesignValidator._check_character_base_cards()`](../src/novels_project/initialize.py:132)

## 5. 人物新增/维护流程（推荐）

1. 判断人物类型：
   - 多章贯穿且需要持续追踪 -> `character_type: main`
   - 多章出现但非核心 -> `character_type: supporting`
   - 一次性/极少复用 -> 不写 base_cards，在章节 outline 里定义
2. 先写“口吻与底线”：`unique_speaking_style` + `bottom_line`
3. 再写“动机与缺陷”：`core_motivation` + `character_flaw`
4. 最后补“标志性动作”：`signature_habits`

更完整的实践与决策树可参考：
- [`../CHARACTER_MANAGEMENT_GUIDE.md`](../CHARACTER_MANAGEMENT_GUIDE.md)
- [`../QUICK_REFERENCE.md`](../QUICK_REFERENCE.md)

## 6. 常见问题

### 6.1 人物键名 vs name 不一致

建议保持一致（例如键 `陆商曜` 与字段 `name: 陆商曜`），以便未来做解析与检索。

### 6.2 是否需要维护 `count` 与 `total_characters`

不是硬性要求，但建议维护：
- 人类更易审阅
- 未来做校验脚本更方便

### 6.3 支线人物不出场怎么办

按混合模式规则：支线人物本章不出场可以不生成状态卡（Prompt 已说明）。

> 关键在于：章节 outline 要能明确“本章涉及人物”。
