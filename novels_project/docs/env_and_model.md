# 环境变量与模型配置（env_and_model）

本文件说明：如何通过环境变量配置模型与 API，以及这些字段在代码中如何被读取。

## 1. 你需要编辑哪些地方

### 1.1 本地文件（可选）：[`../.env`](../.env)

当前示例（注意：不要提交真实密钥）：

```env
# 自定义模型配置
MODEL_PROVIDER=custom_openai
MODEL_NAME=gemini-3-pro
API_BASE_URL=http://ai-service.tal.com/openai-compatible/v1
API_KEY=${COMPANY_API_KEY}
```

### 1.2 终端环境变量（必需）：`COMPANY_API_KEY`

- **用途**：作为 OpenAI-compatible API 的认证密钥。
- **格式**：通常为 `APP_ID:APP_KEY`（初始化检查里会做格式提示）。
- **设置方式**：

```bash
export COMPANY_API_KEY=your_app_id:your_app_key
```

> 说明：项目中多个组件都会读取 `COMPANY_API_KEY`（Crew LLM + Embedding）。

## 2. 字段说明（.env 与环境变量）

### 2.1 `MODEL_NAME`

- **含义**：默认模型名；也可能作为“全局覆盖模型”。
- **读取位置**：
  - 在 [`NovelsCrewAI.__init__()`](../src/novels_project/crew.py:21) 中，如果 CLI 传入 `model_name` 或环境变量 `MODEL_NAME` 存在，则 **4 个 Agent 统一用同一模型**。
  - 否则进入“默认分组双模型模式”：总编+校对用 `gemini-3-pro`，人物+剧情用 `qwen3-max`（见 [`NovelsCrewAI.__init__()`](../src/novels_project/crew.py:21)）。

### 2.2 `API_BASE_URL`

- **含义**：LLM ChatCompletion 的 OpenAI-compatible base_url。
- **读取位置**：[`NovelsCrewAI._create_llm()`](../src/novels_project/crew.py:54)
- **默认值**：`http://ai-service.tal.com/openai-compatible/v1`

### 2.3 `MODEL_PROVIDER` / `API_KEY`

- **现状**：出现在 [`../.env`](../.env) 的示例中，但在核心运行路径中：
  - Crew LLM 初始化实际读取的是 `COMPANY_API_KEY` + `API_BASE_URL`（见 [`NovelsCrewAI._create_llm()`](../src/novels_project/crew.py:54)）。
- **建议**：保留这些字段作为“人类可读的配置说明”，但以代码实际读取的环境变量为准。

### 2.4 `EMBEDDING_API_BASE_URL`（可选）

- **含义**：Embedding API 的 base_url（与 ChatCompletion 可相同也可不同）。
- **读取位置**：[`SampleRetrievalEngine.__init__()`](../src/novels_project/retrieval_engine.py:32)
- **默认值**：`http://ai-service.tal.com/openai-compatible/v1`

## 3. 模型选择与路由规则

### 3.1 默认分组双模型（不设置 MODEL_NAME，且 CLI 不传 --model）

- 总编 + 资深校对：`gemini-3-pro`
- 人物设计师 + 剧情撰写员：`qwen3-max`

实现依据：[`NovelsCrewAI.__init__()`](../src/novels_project/crew.py:21)

### 3.2 全局覆盖单模型

满足任一条件：
- CLI 传入 `--model`（runner 里注入到 `NovelsCrewAI(model_name=...)`）
- 或设置环境变量 `MODEL_NAME`

则：4 个 Agent 统一使用该模型。

实现依据：[`NovelsCrewAI.__init__()`](../src/novels_project/crew.py:21)

## 4. 与初始化检查相关的约束

- 初始化脚本会检查 `COMPANY_API_KEY` 是否存在，以及是否包含 `:`（格式提示）。
- 位置：[`DesignValidator._check_environment_variables()`](../src/novels_project/initialize.py:188)

## 5. 敏感信息与最佳实践

- `.env` 已被 git 忽略（见 [`../.gitignore`](../.gitignore)）。
- 推荐：
  - 只在本地机器设置 `COMPANY_API_KEY` 环境变量。
  - 不要把真实密钥写进任何 Markdown/代码/commit。
