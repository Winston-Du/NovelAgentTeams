# Brainstorming 设计总结

> **创建时间**：2026-02-21
> **项目名称**：东方玄幻权谋经营流长篇小说创作系统
> **框架**：CrewAI 多 Agent 协作

---

## 📖 核心目标

创作一部**东方玄幻权谋经营流长篇小说**，规模：
- **12 卷**
- **约 930 章**
- **每章 3000-5000 字**

**设定背景**：
- 大千世界，神/巫/妖/佛四系并存
- 主角通过契约和商道对抗强权
- 核心主题：权谋、经营、智斗、越级翻盘

---

## 🔄 工作流设计

### 基本模式
**串联模式（方案 A）** - 按顺序执行

```
总编 → 人物设计师 → 剧情撰写员 → 资深校对
  ↓       ↓            ↓            ↓
章大纲  人物状态卡    初稿      最终版+摘要卡
```

### 执行粒度
- **按章推进**：每章完整走一遍 4-Agent 流程
- **顺序执行**：Agent 间严格串联，无并行
- **后续升级**：预留升级到方案 C（Agent 间反馈机制）

### 上下文管理
- **摘要模式**：每章生成摘要卡，后续章节参考前章摘要（不保留全文历史）
- **动态人物卡**：基础卡（不变）+ 当前状态卡（每章更新）

---

## 🤖 Agent 角色定义

### 1️⃣ 总编（Chief Editor）
- **职责**：制定本章故事大纲
- **输入**：卷目标 + 前章摘要
- **输出**：章大纲（故事结构、人物出场、爽点规划、伏笔埋设）

### 2️⃣ 人物设计师（Character Designer）
- **职责**：生成本章人物状态卡
- **输入**：章大纲 + 全局人物卡库
- **输出**：人物状态卡（行为指导、对话风格、人物张力、冲突点、Callback）

### 3️⃣ 剧情撰写员（Plot Writer）
- **职责**：创作章节初稿
- **输入**：章大纲 + 人物卡 + 前章摘要 + 样例库检索
- **输出**：章节初稿（3000-5000 字）
- **工具**：`retrieve_writing_samples`（查询相似样例）

### 4️⃣ 资深校对（Senior Proofreader）
- **职责**：优化文笔 + 生成摘要卡
- **输入**：初稿 + 章大纲 + 人物卡
- **输出**：最终版章节 + 章节摘要卡
- **工具**：`retrieve_writing_samples`（查询相似样例）

---

## 📊 数据结构

### 章大纲（Chapter Outline）
```yaml
chapter_outline:
  chapter_id: 1
  chapter_title: "..."
  story_structure:
    act_1: "..."
    act_2: "..."
    act_3: "..."
  characters_appearance: [...]
  climax_plan: [...]
  atmosphere: "..."
  foreshadowing: [...]
  pacing_notes: "..."
```

### 人物状态卡（Character State Card）
```yaml
chapter_character_states:
  人物名:
    chapter_arc: "..."
    current_mood: "..."
    behavior_this_chapter: [...]
    dialogue_style_this_chapter: {...}
    internal_state: {...}
  character_tensions: {...}
  story_conflicts_and_turning_points: [...]
  callbacks: {...}
```

### 章节摘要卡（Chapter Summary Card）
```yaml
chapter_summary_card:
  chapter_id: 1
  story_progress: {...}
  character_status_updates: {...}
  foreshadowing_status: {...}
  world_rules_updates: {...}
  open_questions: [...]
  info_for_next_chapter: {...}
```

---

## 🗃️ 人物卡系统

### 分层管理
| 等级 | 定义 | 数量 | 字段数 | 示例 |
|------|------|------|--------|------|
| **S_TIER** | 核心主线人物 | 4 | 完整卡（500-800字） | 陆商曜、薛灵槿、白璃、方清砚 |
| **A_TIER** | 重要支线人物 | 10 | 简化卡（250-350字） | 木九公、铁阙、郁衡、慕容瑶光 |
| **B_TIER** | 次要支线人物 | 15 | 骨架卡（80-150字） | 黑商周桓、皇甫青闳 |
| **C_TIER** | 临时配角 | N/A | 不进库，临时生成 | 魏执铗、云舟船长 |

### 生成方式
- **S/A/B 级人物**：用 qwen3-max 批量生成
- **C 级人物**：撰写员创作时临时生成

---

## 🔍 样例库系统

### 技术栈
- **向量库**：Chroma + SQLite（本地）
- **Embedding API**：自定义 OpenAI 兼容服务
  - URL: `http://ai-service.tal.com/openai-compatible/v1/embeddings`
  - Model: `text-embedding-v4`
  - API Key: `COMPANY_API_KEY`（格式：APP_ID:APP_KEY）

### 样例分类
```
samples/
├── 权谋章/
├── 战斗章/
├── 情感章/
├── 经营章/
└── 节奏章/
```

### 检索方式
- **语义搜索**：Agent 查询"权谋听证、逻辑碾压"等描述
- **自动返回**：Top-3 最相似样例
- **动态扩展**：每卷完成后补充优秀章节作为样例

---

## 📈 日志与指标

### Part 1：执行轨迹（Execution Log）
```markdown
[时间] 🚀 第N章开始执行
[时间] 📝 总编 Agent 启动 - 生成章大纲
[时间] ✅ 总编完成 - 输出大纲
[时间] 👥 人物设计师 Agent 启动
       - 决策：发现4个出场角色
       - 查询人物库：陆商曜(S级)✓ ...
[时间] ✅ 人物设计师完成
...
```

### Part 2：性能指标（Performance Metrics）
```json
{
  "chapter_N": {
    "agent_name": {
      "duration_seconds": 21,
      "tokens_used": {"input": 2150, "output": 1320, "total": 3470},
      "status": "success"
    },
    "chapter_summary": {
      "total_duration_seconds": 288,
      "total_tokens": 32870,
      "estimated_cost": "$0.15"
    }
  }
}
```

---

## 🛠️ 技术栈总结

| 组件 | 技术 | 用途 |
|------|------|------|
| Agent 框架 | CrewAI | 多 Agent 协作 |
| LLM | 自定义 OpenAI 兼容 API | gemini-3-pro / gpt-5.2 |
| Embedding | 自定义 OpenAI 兼容 API | text-embedding-v4 |
| 向量库 | Chroma + SQLite | 样例检索 |
| 配置 | YAML + Markdown | 设计文档 + 数据结构 |
| 日志 | Markdown + JSON | 执行轨迹 + 性能指标 |

---

## 🚀 实施路线图

### 阶段 1：数据准备（用户）
- 用 qwen3-max 生成人物卡库（S/A 级共 14 人）
- 从试读样例中提取 2-3 个初始样例

### 阶段 2：环境搭建（协同）
- 创建所有设计文档
- 实现代码框架
- 配置向量库和日志系统

### 阶段 3：第 1 章试运行（共同）
- 完整执行 4-Agent 流程
- 验证输出格式
- 调整 Prompt 和数据结构

### 阶段 4：规模化生产（持续）
- 逐章创作（第 2-60 章）
- 动态补充样例库
- 根据反馈优化 Prompt

---

## ⬆️ 后续升级计划

### 从方案 A → 方案 C
当需要 Agent 间反馈时：
- 校对可以将问题发回给撰写员重写
- 撰写员可以主动询问人物设计师
- 引入"反馈统合"机制

**升级触发条件**：
- 试运行发现需要多轮迭代
- 质量要求进一步提升
- 创作复杂度增加

---

## ✅ 设计锁定确认

- [x] 工作流：串联模式
- [x] 粒度：按章推进
- [x] 上下文：摘要模式 + 动态人物卡
- [x] 样例库：向量检索
- [x] 人物卡：分层管理
- [x] 日志：执行轨迹 + 性能指标
- [x] 文档：混合 MD + YAML

**设计完成时间**：2026-02-21
**设计状态**：✅ 已锁定
