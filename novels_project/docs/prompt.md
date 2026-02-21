# Prompt 模板说明（prompt）

本文件说明：4 个 Agent 的 Prompt 模板放在哪里、各自负责什么、以及你在修改 Prompt 时需要关注哪些输入/输出字段。

## 1. Prompt 文件位置

所有 Prompt 模板位于：[`../DESIGN/PROMPTS/`](../DESIGN/PROMPTS/)

| Agent | Prompt 文件 | 在代码中的加载方式 |
|---|---|---|
| 总编 Chief Editor | [`../DESIGN/PROMPTS/chief_editor_prompt.md`](../DESIGN/PROMPTS/chief_editor_prompt.md) | [`NovelsCrewAI._load_design_docs()`](../src/novels_project/crew.py:71) -> `self.prompts['chief_editor']` |
| 人物设计师 Character Designer | [`../DESIGN/PROMPTS/character_designer_prompt.md`](../DESIGN/PROMPTS/character_designer_prompt.md) | 同上 -> `self.prompts['character_designer']` |
| 剧情撰写员 Plot Writer | [`../DESIGN/PROMPTS/plot_writer_prompt.md`](../DESIGN/PROMPTS/plot_writer_prompt.md) | 同上 -> `self.prompts['plot_writer']` |
| 资深校对 Senior Proofreader | [`../DESIGN/PROMPTS/proofreader_prompt.md`](../DESIGN/PROMPTS/proofreader_prompt.md) | 同上 -> `self.prompts['proofreader']` |

> 运行时：这些 Prompt 会被拼接进各 Task 的 `description` 字段（见 [`NovelsCrewAI.create_chapter_outline_task()`](../src/novels_project/crew.py:163) 等）。

## 2. 4 个 Agent 的职责边界（建议保持稳定）

### 2.1 总编：生成章大纲（YAML）

- Prompt：[`chief_editor_prompt.md`](../DESIGN/PROMPTS/chief_editor_prompt.md)
- Task：[`NovelsCrewAI.create_chapter_outline_task()`](../src/novels_project/crew.py:163)
- 产物：章大纲 YAML（后续人物/剧情/校对都依赖）

**输出字段（核心）**：
- `story_structure`：三幕结构（act_1/2/3）
- `characters_appearance`：本章出场人物清单（name/role/key_actions）
- `climax_plan`：爽点设计（type/description/emotional_impact）
- `atmosphere`：场景氛围
- `foreshadowing`：伏笔与回收计划
- `pacing_notes`：节奏指导

### 2.2 人物设计师：生成本章人物状态卡（YAML）

- Prompt：[`character_designer_prompt.md`](../DESIGN/PROMPTS/character_designer_prompt.md)
- Task：[`NovelsCrewAI.design_character_states_task()`](../src/novels_project/crew.py:181)
- 依赖：总编章大纲（通过 `context` 串联）

**混合模式规则（重要）**：
- 主线人物 `character_type: main`：需要详细状态卡，并跨章追踪
- 支线人物 `character_type: supporting`：本章出现才生成中等状态卡
- 临时人物：不在 base_cards，来自章节大纲（outline）里的描述

字段来源：人物基础卡库 [`../src/novels_project/config/character_base_cards.yaml`](../src/novels_project/config/character_base_cards.yaml)

**输出字段（核心）**：
- 每个出场人物：`chapter_arc`、`current_mood`、`behavior_this_chapter`、`dialogue_style_this_chapter`（tone/examples/avoid）
- `character_tensions`：人物张力
- `story_conflicts_and_turning_points`：冲突与转折点
- `callbacks`：对大纲/世界规则的回应

### 2.3 剧情撰写员：生成章节初稿（YAML）

- Prompt：[`plot_writer_prompt.md`](../DESIGN/PROMPTS/plot_writer_prompt.md)
- Task：[`NovelsCrewAI.write_chapter_draft_task()`](../src/novels_project/crew.py:198)
- 依赖：章大纲 + 人物状态卡
- 可用工具：`retrieve_writing_samples`（样例检索）
  - 工具定义：[`retrieve_writing_samples()`](../src/novels_project/tools/sample_retriever.py:19)

**输出字段（核心）**：
- `content`：正文（建议 3000-5000 字）
- `creation_notes`：创作笔记（挑战、引用样例、字数等）

### 2.4 资深校对：定稿 + 摘要卡（YAML）

- Prompt：[`proofreader_prompt.md`](../DESIGN/PROMPTS/proofreader_prompt.md)
- Task：[`NovelsCrewAI.proofread_and_summarize_task()`](../src/novels_project/crew.py:217)
- 依赖：章大纲 + 人物状态卡 + 初稿

**输出字段（核心）**：
- `chapter_final`：最终正文 + `proofreading_log`（修正记录）
- `chapter_summary_card`：供下一章使用的摘要卡
  - `story_progress`
  - `character_status_updates`
  - `foreshadowing_status`
  - `open_questions`
  - `info_for_next_chapter`

## 3. Prompt 改写建议（易踩坑）

1. **坚持输出必须是 YAML**：否则下游难以解析/复用。
2. **字段名尽量稳定**：一旦你改了字段名，后续如果做解析/自动归档会更难。
3. **不要把“流程说明”当输出**：流程说明写在 Prompt 里可以，但输出应保持纯 YAML。
4. **把风格约束写成可执行的检查项**：
   - 例：禁止使用流水账连接词（然后/接着/最后），或要求每段至少 1 个可见动作。

## 4. 你可能想新增的 Prompt 变量（未来扩展）

> 当前 Task 通过 `inputs` 把数据注入 Crew kickoff，尚未做更严格的变量映射。

常见扩展变量建议：
- `chapter_type`：权谋章/战斗章/经营章/情感章
- `target_word_count`
- `style_rules`：全局风格约束集合
- `forbidden_tropes`：禁用桥段
