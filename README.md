# NovelsProject - AI 小说创作系统

基于 Agent Runtime 架构的 AI 小说创作系统，支持交互式对话创作和多项目管理。

## 特性

- **对话式创作**: 通过 CLI 与 AI Agent 自然对话，协作完成小说创作
- **多项目支持**: 在不同目录下运行，每个故事独立管理配置和输出
- **专业分工**: 4 个专业 Agent 协作（总编、人物设计师、剧情撰写员、校对）
- **全局命令**: 安装后可在任意目录直接运行 `novels` 命令
- **记忆系统**: 自动记录校对反馈，避免重复错误
- **向量检索**: 基于样例库的写作风格检索

## 快速开始

### 1. 环境要求

- Python >= 3.10, < 3.14
- pip 或 uv

### 2. 安装

```bash
# 克隆仓库
git clone https://github.com/only891/novels.git
cd novels/novels_project

# 安装为全局命令
pip install -e .
```

安装完成后，`novels` 命令将在全局可用。

### 3. 配置环境变量

在 `~/.zshrc` 或 `~/.bashrc` 中添加：

```bash
# LLM API 配置
export API_KEY="your_api_key_here"
export API_BASE_URL="http://ai-service.tal.com/openai-compatible/v1"  # 可选，有默认值
export MODEL_NAME="gemini-3-pro"  # 可选，默认 gemini-3-pro

# 向量检索 API（可选，用于样例检索）
export siliconflow_api="your_siliconflow_key"
```

重新加载配置：
```bash
source ~/.zshrc  # 或 source ~/.bashrc
```

### 4. 创建新故事项目

```bash
# 创建故事目录结构
mkdir -p ~/novels/我的故事/{config,DESIGN/PROMPTS,samples,output}

# 创建人物卡（必需）
cat > ~/novels/我的故事/config/character_base_cards.yaml << 'EOF'
metadata:
  world_name: 我的故事世界
  genre: 玄幻

characters:
  主角:
    name: 李明
    description: 一个普通的少年
    personality: 坚韧、善良
    background: 出身贫寒，但心怀大志
EOF

# 切换到故事目录并启动
cd ~/novels/我的故事
novels
```

## 使用方法

### 交互模式（推荐）

```bash
cd ~/novels/我的故事
novels
```

进入交互式 REPL，与 Agent 对话创作：
```
novels> 请创作第1章
novels> 修改第1章的结尾，让主角更果断
novels> 查看人物卡
```

### 命令行参数

```bash
# 快速创作指定章节
novels --chapter 1

# 单次对话模式
novels --prompt "帮我构思第1章的大纲"

# 使用指定模型
novels --model glm-5

# 恢复之前的会话
novels --resume <session_id>

# 初始化向量库
novels --init-vectordb
```

### REPL 内置命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/status` | 显示当前项目状态 |
| `/chapter <N>` | 快速创作第N章 |
| `/cost` | 显示 Token 使用统计 |
| `/session` | 显示当前会话信息 |
| `/sessions` | 列出所有保存的会话 |
| `/resume <id>` | 恢复已保存的会话 |
| `/compact` | 手动压缩上下文 |
| `/clear` | 清空当前对话 |
| `/quit` | 退出 |

## 项目结构

每个故事项目目录结构：
```
我的故事/
├── config/
│   └── character_base_cards.yaml  # 人物卡（必需）
├── DESIGN/
│   └── PROMPTS/                   # 自定义提示模板（可选）
├── samples/                       # 写作样例（可选）
├── output/
│   ├── chapters/                  # 生成的章节
│   └── chapter_summaries/         # 章节摘要
├── sessions/                      # 会话记录
├── feedback/                      # 校对反馈
└── vector_db/                     # 向量库
```

## Agent 架构

系统采用 5 层架构：

```
用户 <-> CLI/REPL
         │
    ConversationRuntime (主 Agent)
         │
         ├── chief_editor (总编) - gemini-3-pro
         ├── character_designer (人物设计师) - glm-5
         ├── plot_writer (剧情撰写员) - glm-5
         └── proofreader (校对) - gemini-3-pro
```

- **主 Agent**: 负责理解用户意图，协调子 Agent 工作
- **子 Agent**: 各司其职，完成专业任务

## 工具列表

主 Agent 可用的核心工具：

| 工具 | 说明 |
|------|------|
| `chief_editor` | 制定章节规划和大纲 |
| `character_designer` | 设计人物细节和对话风格 |
| `plot_writer` | 撰写章节正文 |
| `proofreader` | 校对并记录问题 |
| `update_character_card` | 修改人物卡 |
| `fix_chapter_issue` | 记录章节问题并获取修正指导 |
| `save_chapter` | 保存章节到文件 |
| `load_chapter_data` | 加载章节数据 |

## 测试

```bash
cd novels/novels_project
PYTHONPATH=src pytest tests/ -v
```

## License

MIT
