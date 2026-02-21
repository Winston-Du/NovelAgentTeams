# 大纲与样例库说明（outline_and_samples）

本文件说明：整书大纲与章节 outline 应该放哪里、推荐格式是什么；以及样例库 samples 的 front matter 字段如何维护。

## 1. 整书大纲（全局）

### 1.1 当前大纲文件位置

仓库里已存在整书大纲：[`../../First/大纲.md`](../../First/大纲.md)

该文件包含：
- 世界观、规则设定、经济体系
- 人物与势力
- 卷纲与爆点排程
- 第一卷详细章纲

### 1.2 整书大纲的作用

- 为总编 Agent 提供“卷目标/主题/冲突/爽点矩阵/伏笔回收计划”的权威来源。
- 作为后续章节 outline 的“上位约束”，避免设定漂移。

> 当前 runner [`../run.py`](../run.py) 的 `load_chapter_outline()` 仍使用硬编码测试数据（见 [`load_chapter_outline()`](../run.py:16)），尚未从大纲文件自动解析。

## 2. 章节 outline（每章输入）

### 2.1 现状

- 目前：章节信息在 [`load_chapter_outline()`](../run.py:16) 中用 Python dict 写死。
- 未来建议：为每章维护独立 outline 文件，便于：
  - 人工审阅
  - 版本管理
  - 支持临时人物定义

### 2.2 推荐目录结构（建议）

> 该结构是建议，当前仓库尚未强制。

- 在项目根目录下新增：`outlines/`
- 文件命名：`outlines/chapter_001_outline.md`、`outlines/chapter_002_outline.md` ...

对应关系示例：
- 第 1 章 outline -> `outlines/chapter_001_outline.md`

### 2.3 推荐 outline 内容结构（建议）

- 章节元信息（chapter_id、chapter_title、节奏标签）
- 故事大纲（三幕/关键节点）
- 本章涉及人物
  - base_cards 人物
  - 临时人物（本章一次性）

临时人物写法可参考：[`../CHARACTER_MANAGEMENT_GUIDE.md`](../CHARACTER_MANAGEMENT_GUIDE.md)

## 3. 样例库 samples（写作参考素材）

### 3.1 目录位置

样例库目录：[`../samples/`](../samples/)

示例文件：[`../samples/权谋章/opening_scene.md`](../samples/权谋章/opening_scene.md)

初始化检查会检查 samples 是否存在与数量：[`DesignValidator._check_samples()`](../src/novels_project/initialize.py:171)

### 3.2 样例的两部分结构

样例文件建议由两部分组成：

1. **YAML front matter 元数据**（文件开头的 `---` 区块）
2. **正文内容**（可包含技巧总结、拆解）

### 3.3 front matter 字段说明（以现有样例为准）

以 [`opening_scene.md`](../samples/权谋章/opening_scene.md) 为例：

| 字段 | 类型 | 含义 | 维护建议 |
|---|---|---|---|
| `chapter_id` | string | 样例来自哪一章/哪段 | 可用 `试读_第1章`、`chapter_12_scene_3` |
| `chapter_title` | string | 章节/片段标题 | 便于检索与展示 |
| `type` | string | 章类型 | 建议统一枚举：权谋章/战斗章/经营章/情感章/节奏章 |
| `tags` | list[string] | 标签 | 越具体越好：场景、手法、冲突类型 |
| `focus` | string | 训练目标 | 例如 环境渲染+对话张力+Show not tell |
| `scene_type` | string | 场景类型 | 例如 权谋对话/听证/夜袭/拍卖 |
| `word_count` | number | 样例字数 | 便于筛选短/长样例 |
| `quality_score` | number | 主观评分 | 用于优先返回高质量样例 |
| `author_notes` | string | 备注 | 写明为什么这段值得学 |

### 3.4 样例如何被使用

剧情撰写员与资深校对可调用工具：[`retrieve_writing_samples()`](../src/novels_project/tools/sample_retriever.py:19)

底层向量库构建逻辑：[`SampleRetrievalEngine`](../src/novels_project/retrieval_engine.py:29)

注意：
- Embedding 模型当前写死为 `text-embedding-v4`（见 [`SampleRetrievalEngine.__init__()`](../src/novels_project/retrieval_engine.py:32)）。
- 若 Embedding API 配额不足，会自动重试并最终降级（见 [`SampleRetrievalEngine._build_vectorstore()`](../src/novels_project/retrieval_engine.py:84) 与 [`RateLimitHandler`](../src/novels_project/retry_handler.py:12)）。

### 3.5 样例维护规则（推荐）

1. 每新增一个高质量章节，至少抽取 1-2 个“可复用片段”放入 samples。
2. tags 要包含：场景 + 手法 + 冲突类型（例如 市集/合同博弈/逻辑碾压）。
3. 在正文末尾写 3-10 条技巧总结（便于人类复盘，也利于向量检索）。
4. 避免大段重复的模板句式，否则会拉低检索质量。

## 4. 与人物系统的衔接点

- base_cards（长期人物）：[`../src/novels_project/config/character_base_cards.yaml`](../src/novels_project/config/character_base_cards.yaml)
- 临时人物（一次性）：推荐在章节 outline 中定义

混合模式规则详见：
- [`../CHARACTER_MANAGEMENT_GUIDE.md`](../CHARACTER_MANAGEMENT_GUIDE.md)
- [`../HYBRID_CHARACTER_SYSTEM.md`](../HYBRID_CHARACTER_SYSTEM.md)
