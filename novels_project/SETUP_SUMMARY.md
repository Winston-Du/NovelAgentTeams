# 自定义模型提供商集成 - 配置总结

## 概述

已成功为 CrewAI 项目配置了自定义 OpenAI 兼容的模型提供商。

**配置信息：**
- API 端点：`http://ai-service.tal.com/openai-compatible/v1`
- 支持模型：`gemini-3-pro` (默认)、`gpt-5.2`
- API 认证：使用 `COMPANY_API_KEY` 环境变量

## 文件修改清单

### 1. `.env` - 环境变量配置
**改动：** 更新模型配置信息
```env
MODEL_PROVIDER=custom_openai
MODEL_NAME=gemini-3-pro
API_BASE_URL=http://ai-service.tal.com/openai-compatible/v1
API_KEY=${COMPANY_API_KEY}
```

### 2. `src/novels_project/crew.py` - 核心 Crew 类
**改动：**
- 导入 `LLM` 类
- 添加 `__init__()` 方法，支持动态模型选择
- 添加 `_create_llm()` 方法，初始化自定义 LLM
- 在 `researcher` 和 `reporting_analyst` Agent 中配置 `llm` 参数

**关键方法：**
```python
def __init__(self, model_name: str = None):
    """初始化 Crew，支持指定模型名称"""
    self.model_name = model_name or os.getenv('MODEL_NAME', 'gemini-3-pro')
    self.llm = self._create_llm()

def _create_llm(self) -> LLM:
    """创建自定义 LLM 实例"""
    # 从环境变量读取配置并创建 LLM
```

### 3. `src/novels_project/main.py` - 主程序入口
**改动：**
- 添加 `SUPPORTED_MODELS` 列表
- 更新所有命令行函数以支持 `--model` 参数：
  - `run()` - 基础运行
  - `train()` - 模型训练
  - `replay()` - 任务回放
  - `test()` - Crew 测试
  - `run_with_trigger()` - 触发器运行

**新增支持：**
```bash
# 使用默认模型（gemini-3-pro）
python -m novels_project.main run

# 使用特定模型
python -m novels_project.main run --model gpt-5.2

# 训练、测试等命令也支持 --model 参数
python -m novels_project.main train 3 output.pkl --model gpt-5.2
```

## 新增文件

### `MODEL_CONFIG.md` - 配置指南
完整的使用文档，包含：
- 环境变量说明
- 命令行使用示例
- 架构说明
- 故障排除指南

### `test_model_config.py` - 配置验证脚本
验证脚本，检查：
- 环境变量设置
- 依赖包安装
- LLM 初始化
- 模型列表

## 使用步骤

### 1. 设置环境变量
```bash
export COMPANY_API_KEY=your_api_key_here
```

### 2. 验证配置（可选）
```bash
python test_model_config.py
```

### 3. 运行 Crew

**使用默认模型 (gemini-3-pro)：**
```bash
crewai run
```
或
```bash
python -m novels_project.main run
```

**使用特定模型 (gpt-5.2)：**
```bash
python -m novels_project.main run --model gpt-5.2
```

## 架构设计

### 模型选择优先级（从高到低）
1. 运行时命令行参数 `--model`
2. 环境变量 `MODEL_NAME`
3. 默认值 `gemini-3-pro`

### LLM 配置流程
```
NovelsProject(model_name=?)
    ↓
读取优先级最高的模型名称
    ↓
调用 _create_llm()
    ↓
读取环境变量：COMPANY_API_KEY、API_BASE_URL
    ↓
创建 LLM 实例 (model, base_url, api_key)
    ↓
所有 Agent 共享同一个 LLM 实例
```

## 添加新模型

要支持新的模型，只需在 `main.py` 中修改：

```python
SUPPORTED_MODELS = [
    'gemini-3-pro',
    'gpt-5.2',
    'your-new-model'  # 添加新模型
]
```

## 验证步骤

### 1. 快速验证配置
```bash
python test_model_config.py
```

### 2. 测试运行
```bash
# 测试默认模型
crewai run

# 测试指定模型
python -m novels_project.main run --model gpt-5.2
```

### 3. 检查输出文件
- 默认输出文件：`report.md`（由 `reporting_task` 生成）

## 技术细节

### CrewAI LLM 集成
- 使用 CrewAI 的 `LLM` 类来支持自定义提供商
- OpenAI 兼容 API 接口
- 支持自定义 `base_url` 和 `api_key`

### 环境隔离
- 每个 Crew 实例有独立的 LLM 配置
- 支持多进程运行不同模型的 Crew

## 故障排除

| 问题 | 原因 | 解决方案 |
|------|------|--------|
| `COMPANY_API_KEY` 环境变量未设置 | 未配置 API 密钥 | `export COMPANY_API_KEY=your_key` |
| 连接到 API 端点失败 | 端点不可达 | 检查 `API_BASE_URL`，确保服务运行 |
| 不支持的模型错误 | 模型未在列表中 | 在 `main.py` 的 `SUPPORTED_MODELS` 中添加 |
| LLM 初始化失败 | 环境变量或导入问题 | 运行 `python test_model_config.py` 诊断 |

## 后续改进建议

1. **支持多个 API 密钥**：为不同模型配置不同的密钥
2. **模型配置文件**：使用 YAML/JSON 管理模型列表
3. **缓存机制**：缓存 LLM 响应以提升性能
4. **错误重试**：添加指数退避重试逻辑
5. **模型性能监控**：记录调用统计和性能指标

## 参考资源

- CrewAI 文档：https://docs.crewai.com
- LLM 配置：https://docs.crewai.com/concepts/llm
- OpenAI API 兼容格式：https://platform.openai.com/docs/api-reference
