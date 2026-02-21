# MVP 快速开始指南

> 最小可用版本 - 快速测试第 1 章创作流程

---

## 🎯 目标

在 **1-2 小时内** 完成准备，运行第 1 章的完整创作流程，验证系统可行性。

---

## ✅ 前置条件

- [x] Python 3.10-3.13
- [x] 已安装 CrewAI 和相关依赖
- [x] 设置了 `COMPANY_API_KEY` 环境变量

---

## 📋 快速准备清单（约 30-60 分钟）

### Step 1: 安装依赖（5 分钟）

```bash
cd /Users/tal/Documents/personal/workspace/novels/novels_project

# 安装所有依赖
pip install crewai[tools]==1.9.3
pip install chromadb langchain langchain-community python-dotenv pyyaml
pip install unstructured  # 用于 Markdown 解析
```

### Step 2: 生成最小人物卡库（20-30 分钟）

**方式 A：用 qwen3-max 生成（推荐）**

创建一个临时 Python 脚本来生成人物卡：

```python
# generate_characters.py
import os
from openai import OpenAI

# 配置 API
client = OpenAI(
    api_key=os.getenv("COMPANY_API_KEY"),
    base_url="http://ai-service.tal.com/openai-compatible/v1"
)

# Prompt 模板（见 DESIGN/BRAINSTORM_SUMMARY.md）
prompt = """
你是一位资深小说编辑，擅长设计人物。我正在创作一部东方玄幻权谋经营流小说。

请为以下人物生成 YAML 格式的人物卡：

人物名：陆商曜
角色类型：S_TIER（核心主线人物）
身份：主角，落魄商族庶子，掌握契约古印
性格：腹黑果决、能屈能伸、守底线不圣母、重承诺
核心能力：全能术修五系、契约权柄
目标：从混乱中生存，建立商会
底线：不卖人命、不灭根本、不负承诺

输出格式参考：
```yaml
陆商曜:
  name: "陆商曜"
  role: "主角"
  tier: "S_TIER"
  core_personality: ["腹黑果决", "能屈能伸", "守底线", "重承诺"]
  ...
```

只输出 YAML，不要额外解释。
"""

# 调用 API
response = client.chat.completions.create(
    model="qwen3-max",
    messages=[{"role": "user", "content": prompt}]
)

print(response.choices[0].message.content)
```

**方式 B：手工创建（10-15 分钟）**

最小人物卡（只需 3 个核心人物）：

```yaml
# src/novels_project/config/character_base_cards.yaml

metadata:
  version: "0.1-MVP"
  total_characters: 3

s_tier:
  count: 3
  characters:
    陆商曜:
      name: "陆商曜"
      role: "主角"
      tier: "S_TIER"
      core_personality: ["腹黑果决", "能屈能伸", "守底线", "重承诺"]
      character_flaw: ["过于冷漠", "依赖规则"]
      core_motivation: "从混乱中生存，建立商会"
      bottom_line: ["不卖人命", "不负承诺"]
      unique_speaking_style:
        tone: "言简意赅，逻辑清晰"
        characteristics: ["很少重复", "喜欢用数字和比喻"]
        example_dialogues:
          - "可以签，但按城里常用的合同样式来。"
          - "不是。是拿清楚的字句当尺子。"
        speaking_frequency: "言少意多"
        avoid_patterns: ["不要显得紧张", "不要大段独白"]
      signature_habits: ["拨动算盘思考", "平视对手"]

    黑商周桓:
      name: "黑商周桓"
      role: "小反派"
      tier: "S_TIER"  # MVP 简化，暂时放 S 级
      core_personality: ["贪婪", "暴力", "轻敌"]
      core_motivation: "垄断市集利益"
      unique_speaking_style:
        tone: "粗鲁、威胁性"
        example_dialogues:
          - "老规矩，摊位费三成，保护费两成。"
          - "你拿几句漂亮话当盾牌？"

    木九公:
      name: "木九公"
      role: "导师/助手"
      tier: "S_TIER"  # MVP 简化
      core_personality: ["沉着", "精于算计", "有侠义心肠"]
      core_motivation: "找到明主，建立事业"
      unique_speaking_style:
        tone: "低调、带着方言韵味、词汇古雅"
        example_dialogues:
          - "虽是粗陋货栈，规矩却要清楚。"
```

保存到：`src/novels_project/config/character_base_cards.yaml`

### Step 3: 准备一个样例（10 分钟）

创建样例目录和一个参考样例：

```bash
mkdir -p samples/权谋章
```

创建样例文件 `samples/权谋章/opening_scene.md`：

```markdown
---
chapter_id: "试读_第1章"
chapter_title: "市集开局"
type: "权谋章"
tags: ["市集", "对话", "逻辑碾压"]
focus: "环境渲染+对话张力"
---

# 市集开局（试读样例）

落日沉进槐城的雾，市集尽头的货栈挂着一盏裂灯。有人把灯火吹灭，有人把价格抬高；陆商曜拨动算盘，珠声在掌心里轻轻滚。

"老规矩，摊位费三成，保护费两成，过关再收一成。"黑商周桓笑得像掰断脆骨，"签了，明天你还开门。"

木九公抱着破账本咳了一声。陆商曜抬眸，语气平稳："可以签，但按城里常用的合同样式来。你收'保护'，遇到非买卖的打砸抢，要负责。若出现仓毁货损，以当月收取费用十倍赔付；若你的人参与此事，合同当场失效，已收费用全退并公开道歉。"

摊位间有人嘘，有人笑。周桓指节在桌上敲得沉闷："你拿几句漂亮话当盾牌？"

"不是。"陆商曜把纸推过去，"是拿清楚的字句当尺子。"
```

### Step 4: 运行初始化检查（2 分钟）

```bash
python src/novels_project/initialize.py
```

**预期输出：**
```
检查 设计文档完整性... ✅ 通过
检查 配置文件完整性... ⚠️  警告
检查 人物卡库检查... ✅ 通过
检查 样例库检查... ⚠️  警告
检查 环境变量检查... ✅ 通过

⚠️  警告信息：
  • 配置文件 agents.yaml 不存在（可选）
  • S级人物只有 3 个，建议至少 4 个（MVP可以接受）
  • 样例库只有 1 个样例，建议至少 5 个

⚠️  所有检查通过（有警告），可以继续。
```

---

## 🚀 运行第 1 章测试

**目前状态：**
- ✅ 设计文档完成
- ✅ 核心代码完成
- ⏳ CrewAI 集成待完成

**下一步需要：**
1. 更新 `crew.py` 集成所有 Agent
2. 创建运行脚本 `run.py`
3. 测试第 1 章创作流程

---

## 📊 预期结果

成功运行后，你将得到：

```
output/
├── chapters/
│   └── chapter_1_final.md          # 最终版章节（3000-5000字）
├── chapter_summaries/
│   └── chapter_1_summary.yaml      # 章节摘要卡
logs/
├── execution_logs/
│   └── chapter_1_execution.md      # 执行轨迹
└── performance_metrics/
    └── chapter_1_metrics.json      # 性能指标
```

---

## 🔍 下一步行动

**告诉我你的状态：**

1. ✅ "已完成 Step 1-4，准备运行" → 我继续完成 crew.py 集成
2. ⏳ "正在准备数据（Step 2-3）" → 你继续准备，我等待
3. ❓ "遇到问题：[具体问题]" → 我帮你解决

---

## 💡 提示

**MVP 目标**：
- 不追求完美，只验证流程可行
- 3 个人物卡足够测试
- 1 个样例足够启动
- 后续可以逐步完善

**时间分配**：
- 准备数据：30-60 分钟
- 运行测试：10-20 分钟
- 调整优化：30-60 分钟

**总计**：1-2 小时完成 MVP
