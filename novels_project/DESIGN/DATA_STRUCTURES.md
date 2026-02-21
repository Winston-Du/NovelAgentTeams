# 数据结构规范

> 定义所有 Agent 间传递的数据格式

---

## 📋 核心数据结构

### 1. 章大纲（Chapter Outline）

**生产者**：总编 Agent
**消费者**：人物设计师、剧情撰写员、资深校对

```yaml
chapter_outline:
  chapter_id: 1
  chapter_title: "市集开局，落魄货栈遭围堵"

  # 核心故事框架
  story_structure:
    act_1: "陆商曜在市集摆摊，被黑商周桓逼签霸王条款——展现主角的契约精神和谋略"
    act_2: "主角反以合同漏洞脱身——展现灵活应对和底线原则"
    act_3: "木九公出手重构账目，暗示背后有高手——为后续铺垫"

  # 人物出场清单
  characters_appearance:
    - name: "陆商曜"
      role: "主角"
      key_actions: ["拨动算盘", "提出合同条款", "展现沉着"]
    - name: "黑商周桓"
      role: "小反派"
      key_actions: ["逼签霸王条款", "冷笑", "被智取"]
    - name: "木九公"
      role: "配角/导师"
      key_actions: ["咳嗽", "整理账本", "出手相助"]

  # 爽点规划
  climax_plan:
    - type: "打脸"
      description: "合同漏洞智取黑商"
      emotional_impact: "爽快感"
    - type: "经营"
      description: "账目重构展现专业"
      emotional_impact: "信任感"

  # 环境和氛围
  atmosphere: "市集的混乱与压抑，灯火摇晃，巷口风声紧迫"

  # 伏笔埋设清单
  foreshadowing:
    - content: "古印微微发热"
      recovery_plan: "卷七中神印影借试点"

  # 节奏指导
  pacing_notes: "快节奏，信息密集，但保留细节空间供描写"
```

---

### 2. 人物状态卡（Character State Card）

**生产者**：人物设计师 Agent
**消费者**：剧情撰写员、资深校对

```yaml
chapter_character_states:
  chapter_id: 1

  # 每个人物的本章状态
  陆商曜:
    chapter_arc: "初次展现合约精神"
    current_mood: "沉着、压抑着野心"

    relationship_with_others:
      黑商周桓: "刚认识，尚未信任，评估对手强度"
      木九公: "第一次深度合作，建立信任基础"

    behavior_this_chapter:
      - "面对威胁时不慌张，反而拨动算盘来冷静思考"
      - "用冷静的逻辑和条款来对抗暴力威胁"

    dialogue_style_this_chapter:
      tone: "冷静、精确、带着隐藏的自信"
      examples:
        - "可以签，但按城里常用的合同样式来。"
        - "不是。是拿清楚的字句当尺子。"
      speaking_frequency: "言少意多，每句话都有目的"
      avoid: "不要显得紧张，也不要太张狂"

    internal_state:
      conscious_thought: "必须用规则的武器来对付这个贪婪的商人"
      subconscious_fear: "如果规则不管用呢？"

  # 人物间的张力
  character_tensions:
    陆商曜_vs_黑商周桓:
      type: "对抗型张力"
      surface_conflict: "利益冲突"
      deeper_tension: "规则 vs 暴力"
      tension_peak: "陆商曜成功用合同条款反制"

  # 本章冲突点与转折点
  story_conflicts_and_turning_points:
    - conflict_id: "C1"
      name: "霸王条款的威胁"
      characters_involved: ["陆商曜", "黑商周桓"]
      turning_point:
        trigger: "陆商曜提出合同样式"
        action: "反以契约漏洞脱身"
        consequence: "周桓失去掌控权"

  # Callback内容
  callbacks:
    from_volume_outline:
      - source: "卷一目标：立信立威"
        callback_in_chapter: "陆商曜通过与周桓的对抗立信"
```

---

### 3. 章节初稿（Chapter Draft）

**生产者**：剧情撰写员 Agent
**消费者**：资深校对 Agent

```yaml
chapter_draft:
  chapter_id: 1
  chapter_title: "市集开局，落魄货栈遭围堵"

  # 实际的章节内容
  content: |
    [完整的章节文本，3000-5000 字]

  # 创作过程的自我反思
  creation_notes:
    writing_challenges:
      - challenge: "如何在不显得过度武力的情况下表现护航的威力？"
        solution: "通过器傀的无言压制而非直接战斗"

    samples_referenced:
      - "权谋章样例：参考了'逻辑碾压'的对话节奏"

    estimated_word_count: 4200

  # 自我检查清单
  self_check:
    - "✓ 是否避免了'然后...接着...'的叙述？"
    - "✓ 人物对话是否符合各自的口吻？"
    - "✓ 环境描写是否有具体的感官细节？"
```

---

### 4. 最终版章节（Chapter Final）

**生产者**：资深校对 Agent
**消费者**：输出系统

```yaml
chapter_final:
  chapter_id: 1
  chapter_title: "市集开局，落魄货栈遭围堵"

  # 最终版本的完整内容
  final_content: |
    [经过校对优化后的章节文本]

  # 校对过程的记录
  proofreading_log:
    issues_found_and_fixed:
      - id: "ISSUE_1"
        location: "第3段"
        original_text: "然后陆商曜拨动算盘..."
        issue_type: "重复叙述结构"
        severity: "medium"
        fix_applied: "优化为：陆商曜拨动算盘，珠声在掌心里轻轻滚。"

    positive_aspects:
      - "陆商曜和周桓的对话张力很好，维持不变"

    pacing_analysis:
      overall_assessment: "节奏良好，张力递进清晰"

    character_voice_check:
      陆商曜: "✓ 言简意赅的特点充分体现"
```

---

### 5. 章节摘要卡（Chapter Summary Card）

**生产者**：资深校对 Agent
**消费者**：下一章的总编、剧情撰写员

```yaml
chapter_summary_card:
  chapter_id: 1
  chapter_title: "市集开局，落魄货栈遭围堵"

  # 故事进展
  story_progress:
    key_events:
      - "陆商曜在市集摊位被黑商周桓逼迫签署霸王条款"
      - "陆商曜以合同漏洞反制周桓"
      - "木九公出手重构账目"
    story_arc_completed: "建立初代班底"
    forward_momentum: "下章将面对关税司的审查"

  # 人物状态更新
  character_status_updates:
    陆商曜:
      status_change: "从'孤立的商人' → '有班底支撑的商人'"
      relationship_updates:
        黑商周桓: "对立，已展现逻辑优势"
        木九公: "信任度从0提升到60%"
      key_insight: "规则可以成为武器"

  # 伏笔状态
  foreshadowing_status:
    buried_foreshadowing:
      - content: "古印微微发热"
        expected_recovery_volume: "卷七"
    resolved_foreshadowing: []

  # 规则世界更新
  world_rules_updates:
    new_concepts_introduced:
      - "合同制度作为'保护权'的依据"

  # 未解之谜
  open_questions:
    - "黑商周桓背后是否有靠山？"
    - "木九公是从哪里来的？"

  # 供下章使用的关键信息
  info_for_next_chapter:
    character_status_snapshot: "陆商曜：信心增强，班底初具"
    plot_continuity: "黑商周桓的失利将激怒他的支持者"
    unresolved_tensions: "周桓是否会再次报复？"
```

---

## 📁 人物卡库结构

### 全局人物基础卡（Character Base Cards）

**存储位置**：`src/novels_project/config/character_base_cards.yaml`

```yaml
metadata:
  version: "1.0"
  last_updated: "2026-02-21"
  total_characters: 14

# S级核心主线人物
s_tier:
  count: 4
  characters:
    陆商曜:
      name: "陆商曜"
      role: "主角"
      tier: "S_TIER"
      core_personality: ["腹黑果决", "能屈能伸", "守底线", "重承诺"]
      character_flaw: ["过于沉着显得冷漠", "对规则依赖"]
      core_motivation: "从混乱中生存，建立商业帝国"
      bottom_line: ["不卖人命", "不灭根本", "不负承诺"]
      unique_speaking_style:
        tone: "言简意赅，逻辑清晰"
        characteristics: ["很少重复", "喜欢用数字和比喻"]
        example_dialogues:
          - "可以签，但按城里常用的合同样式来。"
          - "不是。是拿清楚的字句当尺子。"
        speaking_frequency: "言少意多"
        avoid_patterns: ["不要显得紧张", "不要大段独白"]
      signature_habits: ["拨动算盘思考", "平视对手"]

# A级重要支线人物
a_tier:
  count: 10
  characters:
    木九公:
      name: "木九公"
      role: "导师/助手"
      tier: "A_TIER"
      core_personality: ["沉着", "精于算计", "有侠义心肠"]
      core_motivation: "找到明主，建立事业"
      unique_speaking_style:
        tone: "低调、带着方言韵味、词汇古雅"
        example_dialogues:
          - "虽是粗陋货栈，规矩却要清楚。"
```

---

## 🔧 辅助数据结构

### 写作风格指南
```yaml
writing_style_guide:
  core_principles:
    - "Show, don't tell"
    - "环境渲染"
    - "拒绝平铺直叙"

  reference_sample:
    title: "试读样例"
    content: "..."
    techniques:
      - "环境开场"
      - "内心细节"
      - "对话张力"
```

### 校对标准
```yaml
proofreading_criteria:
  logic_consistency:
    check_points:
      - "人物的动机与行为是否一致？"
      - "因果链条是否清晰？"

  pacing:
    check_points:
      - "铺垫、冲突、高潮、收束的时间分配是否合理？"

  writing_quality:
    check_points:
      - "是否有重复的表述或词汇？"
      - "长短句是否交替？"
```

---

## ✅ 数据验证规则

### 必填字段检查
```python
required_fields = {
    'chapter_outline': ['chapter_id', 'story_structure', 'characters_appearance'],
    'character_state_card': ['chapter_id', '至少1个人物状态'],
    'chapter_draft': ['chapter_id', 'content'],
    'chapter_final': ['chapter_id', 'final_content'],
    'chapter_summary': ['chapter_id', 'story_progress', 'character_status_updates']
}
```

### 字数范围检查
```python
word_count_ranges = {
    'chapter_draft': (3000, 5000),
    'chapter_final': (3000, 5000),
    'chapter_outline': (200, 1000),
    'character_state_card': (500, 2000)
}
```
