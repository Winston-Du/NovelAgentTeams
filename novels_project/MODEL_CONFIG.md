# 自定义模型提供商配置指南

## 项目配置

本项目已配置为支持自定义 OpenAI 兼容的模型提供商。

### 环境变量配置

在 `.env` 文件中设置以下变量：

```env
# 模型提供商类型（目前为 custom_openai）
MODEL_PROVIDER=custom_openai

# 要使用的模型名称（可选，默认为 gemini-3-pro）
MODEL_NAME=gemini-3-pro

# API 基础 URL
API_BASE_URL=http://ai-service.tal.com/openai-compatible/v1

# API 密钥环境变量的引用
API_KEY=${COMPANY_API_KEY}
```

**重要：** 确保系统中设置了 `COMPANY_API_KEY` 环境变量，内容为你的 API 密钥。

### 支持的模型

项目支持以下模型：
- `gemini-3-pro` （默认）
- `gpt-5.2`

## 使用方法

### 1. 使用默认模型运行（gemini-3-pro）

```bash
# 使用 crewai 命令
crewai run

# 或直接运行
python -m novels_project.main
```

### 2. 指定特定模型运行

```bash
# 使用 gpt-5.2 模型
python -m novels_project.main run --model gpt-5.2

# 使用 gemini-3-pro 模型（显式指定）
python -m novels_project.main run --model gemini-3-pro
```

### 3. 训练 Crew

```bash
# 使用默认模型训练
python -m novels_project.main train 3 training_results.pkl

# 指定模型训练
python -m novels_project.main train 3 training_results.pkl --model gpt-5.2
```

### 4. 回放任务

```bash
# 回放任务（使用默认模型）
python -m novels_project.main replay <task_id>

# 指定模型回放
python -m novels_project.main replay <task_id> --model gpt-5.2
```

### 5. 测试 Crew

```bash
# 测试 Crew（使用默认模型）
python -m novels_project.main test 2 gpt-4

# 指定模型测试
python -m novels_project.main test 2 gpt-4 --model gpt-5.2
```

### 6. 带触发器运行

```bash
# 使用默认模型
python -m novels_project.main run_with_trigger '{"key": "value"}'

# 指定模型
python -m novels_project.main run_with_trigger '{"key": "value"}' --model gpt-5.2
```

## 代码架构

### crew.py 中的关键更改

1. **LLM 初始化**：在 `NovelsProject.__init__()` 中创建 LLM 实例
2. **动态模型选择**：支持通过构造函数参数指定模型
3. **Agent 配置**：每个 Agent 都使用配置好的 `self.llm`

```python
from crewai import LLM

def __init__(self, model_name: str = None):
    self.model_name = model_name or os.getenv('MODEL_NAME', 'gemini-3-pro')
    self.llm = self._create_llm()

def _create_llm(self) -> LLM:
    api_key = os.getenv('COMPANY_API_KEY')
    api_base_url = os.getenv('API_BASE_URL', 'http://ai-service.tal.com/openai-compatible/v1')

    return LLM(
        model=self.model_name,
        base_url=api_base_url,
        api_key=api_key
    )
```

## 添加新模型

要添加新的支持模型，请在 `main.py` 中修改 `SUPPORTED_MODELS` 列表：

```python
SUPPORTED_MODELS = ['gemini-3-pro', 'gpt-5.2', 'your-new-model']
```

## 故障排除

### 问题：API 密钥未找到
**解决方案**：确保 `COMPANY_API_KEY` 环境变量已设置
```bash
export COMPANY_API_KEY=your_api_key
```

### 问题：连接到 API 端点失败
**解决方案**：检查 `API_BASE_URL` 是否正确，并确保 API 服务正在运行

### 问题：模型不支持
**解决方案**：检查模型名称是否在 `SUPPORTED_MODELS` 列表中

## Embedding 模型配置（SiliconFlow）

### 概述

本项目使用 SiliconFlow 提供的 Embedding API 进行样例检索的向量化。

- **API 提供商**：[SiliconFlow](https://siliconflow.cn/)
- **默认模型**：`BAAI/bge-large-zh-v1.5`（中文优化，512 tokens，1024 维）
- **API 端点**：`https://api.siliconflow.cn/v1`
- **API 文档**：[SiliconFlow Embeddings API](https://docs.siliconflow.cn/cn/api-reference/embeddings/create-embeddings)

### 环境变量

```bash
# SiliconFlow Embedding API Key（必需）
export SILICONFLOW_API_KEY=your_siliconflow_api_key
```

### 支持的 Embedding 模型

| 简称 | 完整模型名 | 说明 |
|------|-----------|------|
| `bge-large-zh` | `BAAI/bge-large-zh-v1.5` | 中文，512 tokens，1024 维（**默认**） |
| `bge-large-en` | `BAAI/bge-large-en-v1.5` | 英文，512 tokens，1024 维 |
| `bge-m3` | `BAAI/bge-m3` | 多语言，8192 tokens，1024 维 |
| `bge-m3-pro` | `Pro/BAAI/bge-m3` | 多语言增强版，8192 tokens |
| `qwen3-embedding-8b` | `Qwen/Qwen3-Embedding-8B` | 32768 tokens，可调维度 |
| `qwen3-embedding-4b` | `Qwen/Qwen3-Embedding-4B` | 32768 tokens，可调维度 |
| `qwen3-embedding-0.6b` | `Qwen/Qwen3-Embedding-0.6B` | 32768 tokens，可调维度 |

### API 调用示例

```bash
curl --request POST \
  --url https://api.siliconflow.cn/v1/embeddings \
  --header "Authorization: Bearer $SILICONFLOW_API_KEY" \
  --header "Content-Type: application/json" \
  --data '{
    "model": "BAAI/bge-large-zh-v1.5",
    "input": "硅基流动",
    "encoding_format": "float"
  }'
```

### 注意事项

- 更换 Embedding 模型后，需要删除旧的向量库数据并重新构建（不同模型的维度可能不兼容）
- 首次运行或重建向量库时，系统会自动调用 SiliconFlow Embedding API

## 参考资源

- [CrewAI 官方文档](https://docs.crewai.com)
- [OpenAI API 兼容格式](https://platform.openai.com/docs/api-reference)
- [SiliconFlow API 文档](https://docs.siliconflow.cn/cn/api-reference/embeddings/create-embeddings)
