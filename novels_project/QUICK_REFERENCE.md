# 快速参考卡 - 混合模式人物管理

## 三类人物速查表

### 主线人物
**定义位置**：`character_base_cards.yaml` → S_TIER
```yaml
character_type: "main"
```
**何时使用**：贯穿多章的关键角色（如主角、主反派）
**处理方式**：每章生成详细状态卡
**例子**：陆商曜、黑商周桓、木九公

---

### 支线人物
**定义位置**：`character_base_cards.yaml` → A/B/C_TIER
```yaml
character_type: "supporting"
```
**何时使用**：多章出现、需要连贯性的配角
**处理方式**：本章出现时生成中等状态卡
**例子**：铁阙（护卫）、市集店主甲

---

### 临时人物
**定义位置**：`outline.md` 中的"临时人物"部分
```markdown
**临时人物**（仅本章）：
- 赤眉匪头
  - 身份：...
  - 动机：...
```
**何时使用**：一次性或极少重复的角色
**处理方式**：根据outline临时创建简化卡
**例子**：盗匪头目、路人甲

---

## 人物类型决策

```
新人物出现？
  ↓
  多章出现？
  ├─ YES → 有复杂背景和动机？
  │        ├─ YES → main (S_TIER)
  │        └─ NO → supporting (A_TIER)
  └─ NO → 临时人物 (outline指定)
```

---

## 各章创建清单

### 编写章节outline时
- [ ] 明确本章主故事线
- [ ] 列出涉及的base_cards人物（只写涉及的）
- [ ] 定义本章临时人物（名称、身份、动机、说话风格）

### 人物设计师处理时
- [ ] 加载base_cards所有人物
- [ ] 对涉及的人物按type生成状态卡
- [ ] 根据outline创建临时人物简化卡
- [ ] 输出完整的chapter_character_states.yaml

---

## 文件位置速查

```
定义位置：
├── 主线/支线人物 → src/novels_project/config/character_base_cards.yaml
├── 临时人物 → outlines/chapter_X_outline.md
└── 当章状态卡 → output/chapter_summaries/chapter_X_summary.yaml
```

---

## 示例代码片段

### base_cards中添加支线人物
```yaml
a_tier:
  characters:
    铁阙:
      name: "铁阙"
      character_type: "supporting"  # 关键
      role: "陆商曜的护卫"
      core_personality: ["忠诚", "沉默"]
      # ... 其他字段
```

### outline中添加临时人物
```markdown
## 第2章 - 市集风波

### 本章临时人物

**赤眉匪头**
- 身份：盗匪头目
- 动机：抢劫试探
- 说话风格：粗野、蛮横
- 出场：第三幕攻击货栈
```

---

## 关键术语

| 术语 | 说明 |
|------|------|
| character_type | 人物类型标记（main/supporting） |
| base_cards | 人物库，存储长期人物定义 |
| outline | 章节大纲，指定临时人物 |
| 状态卡 | 人物在某章的行为、情绪、目标快照 |
| 支线人物 | supporting类，可跨章出现 |
| 临时人物 | 仅在outline中指定，一次性或极少重复 |

---

## 💡 记住这一点

```
主线人物 → base_cards, character_type="main", 详细, 追踪
支线人物 → base_cards, character_type="supporting", 中等, 需要时追踪
临时人物 → outline中, 简化, 无追踪
```

