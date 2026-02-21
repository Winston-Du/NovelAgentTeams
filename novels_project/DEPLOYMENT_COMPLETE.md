# 完整部署指南

> MVP 版本 - 从零到运行第 1 章

---

## ✅ 当前状态

**代码实现：100% 完成**
- ✅ 所有设计文档
- ✅ 4 个 Agent（总编、人物设计师、撰写员、校对）
- ✅ 完整的日志和指标系统
- ✅ 向量库样例检索
- ✅ 初始化检查脚本
- ✅ 运行脚本
- ✅ 自动测试用例

**你需要准备：**
- ⏳ 最小人物卡库（3 个人物）
- ⏳ 1 个样例文件
- ⏳ 环境变量配置

---

## 🚀 快速开始（30-60 分钟）

### Step 1: 安装依赖（5 分钟）

```bash
cd /Users/tal/Documents/personal/workspace/novels/novels_project

# 安装所有依赖
pip install crewai[tools]==1.9.3
pip install chromadb langchain langchain-community python-dotenv pyyaml unstructured
```

### Step 2: 设置环境变量（1 分钟）

```bash
# 设置 API 密钥
export COMPANY_API_KEY=your_app_id:your_app_key

# 验证
echo $COMPANY_API_KEY
```

### Step 3: 准备最小人物卡库（20-30 分钟）

创建文件：`src/novels_project/config/character_base_cards.yaml`

```yaml
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
      tier: "S_TIER"
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
      tier: "S_TIER"
      core_personality: ["沉着", "精于算计", "有侠义心肠"]
      core_motivation: "找到明主，建立事业"
      unique_speaking_style:
        tone: "低调、带着方言韵味、词汇古雅"
        example_dialogues:
          - "虽是粗陋货栈，规矩却要清楚。"
```

### Step 4: 准备一个样例（5-10 分钟）

```bash
mkdir -p samples/权谋章
```

创建文件：`samples/权谋章/opening_scene.md`

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

### Step 5: 运行自动测试（2 分钟）

```bash
# 运行完整测试
./test.sh

# 或者手动运行各项测试
python src/novels_project/initialize.py
python tests/test_system.py
python run.py --chapter 1 --dry-run
```

**预期输出：**
```
✅ 所有检查通过（有警告），可以继续。
✅ 所有测试通过！
🔍 模拟运行模式（不调用 LLM）
   输入数据已准备完毕
```

---

## 🎯 运行第 1 章创作

### 完整运行

```bash
python run.py --chapter 1
```

**预期执行流程：**
```
🚀 CrewAI 小说创作系统
📖 加载章节信息...
   章节: 第 1 章 - 市集开局，落魄货栈遭围堵
👥 加载人物卡库...
   人物数: 3
🤖 初始化 CrewAI（模型: gemini-3-pro）...
   ✅ Crew 已初始化
📝 开始执行第 1 章创作流程...

[09:15:23] 🚀 第1章开始执行
[09:15:24] 📝 总编 Agent 启动 - 生成章大纲
[09:15:45] ✅ 总编完成
[09:15:46] 👥 人物设计师 Agent 启动
[09:16:12] ✅ 人物设计师完成
[09:16:13] ✏️  剧情撰写员 Agent 启动
[09:18:45] ✅ 剧情撰写员完成
[09:18:46] 🔍 资深校对 Agent 启动
[09:20:15] ✅ 资深校对完成

✅ 章节创作完成！
✅ 输出已保存：output/chapters/chapter_1_final.md
📊 性能指标:
   总耗时: 288.0 秒
   总 Token: 32870
```

### 指定模型运行

```bash
# 使用 gpt-5.2 模型
python run.py --chapter 1 --model gpt-5.2
```

---

## 📂 输出文件

成功运行后，你将得到：

```
output/
├── chapters/
│   └── chapter_1_final.md          # 最终版章节（3000-5000字）
└── chapter_summaries/
    └── chapter_1_summary.yaml      # 章节摘要卡（供第2章使用）

logs/
├── execution_logs/
│   └── chapter_1_execution.md      # 执行轨迹和决策链路
└── performance_metrics/
    └── chapter_1_metrics.json      # 性能指标（Token、耗时）
```

---

## 🧪 测试命令速查

```bash
# 1. 初始化检查
python src/novels_project/initialize.py

# 2. 单元测试
python tests/test_system.py

# 3. 模拟运行（不调用 LLM）
python run.py --chapter 1 --dry-run

# 4. 完整测试
./test.sh

# 5. 运行第 1 章
python run.py --chapter 1

# 6. 运行第 1 章（指定模型）
python run.py --chapter 1 --model gpt-5.2
```

---

## 🔍 故障排除

### 问题 1：环境变量未设置
```
ValueError: COMPANY_API_KEY 环境变量未设置
```
**解决方案：**
```bash
export COMPANY_API_KEY=your_app_id:your_app_key
```

### 问题 2：人物卡库文件不存在
```
FileNotFoundError: 人物卡库文件不存在
```
**解决方案：** 按 Step 3 创建 `character_base_cards.yaml`

### 问题 3：依赖包未安装
```
ImportError: No module named 'crewai'
```
**解决方案：**
```bash
pip install crewai[tools]==1.9.3
pip install chromadb langchain langchain-community python-dotenv pyyaml unstructured
```

### 问题 4：LLM API 调用失败
```
Error: API call failed
```
**解决方案：**
- 检查 API 密钥是否正确
- 检查 API 端点是否可访问：`http://ai-service.tal.com/openai-compatible/v1`
- 检查模型名称是否正确：`gemini-3-pro` 或 `gpt-5.2`

---

## 📊 下一步

### 完善系统（可选）
1. 补充更多人物卡（A 级 10 个）
2. 增加更多样例（5-10 个）
3. 调整 Prompt 模板以优化输出质量

### 规模化生产
1. 运行第 2-60 章
2. 收集优秀章节作为新样例
3. 根据反馈持续优化

### 升级到方案 C
1. 添加 Agent 间反馈机制
2. 支持校对将问题发回撰写员重写
3. 支持撰写员主动询问人物设计师

---

## ✅ 检查清单

完成准备后，确认以下清单：

- [ ] 已安装所有依赖包
- [ ] 已设置 `COMPANY_API_KEY` 环境变量
- [ ] 已创建人物卡库文件（至少 3 个人物）
- [ ] 已创建至少 1 个样例文件
- [ ] 运行 `./test.sh` 所有测试通过
- [ ] 准备好运行第 1 章

**全部完成后，运行：**
```bash
python run.py --chapter 1
```

---

## 🎯 预期结果

- **执行时间**：3-5 分钟
- **Token 消耗**：约 30,000-40,000 tokens
- **输出质量**：3000-5000 字的章节初稿
- **日志完整**：包含执行轨迹和性能指标

祝创作顺利！🎉
