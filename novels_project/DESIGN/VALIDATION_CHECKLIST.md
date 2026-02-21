# 初始化验证清单

> 在执行创作流程前，必须通过所有检查项

---

## ✅ 检查项目

### 1. 设计文档完整性
```yaml
check_design_documents:
  required_files:
    - DESIGN/BRAINSTORM_SUMMARY.md
    - DESIGN/WORKFLOW.md
    - DESIGN/AGENTS_DEFINITION.md
    - DESIGN/DATA_STRUCTURES.md
    - DESIGN/PROMPTS/chief_editor_prompt.md
    - DESIGN/PROMPTS/character_designer_prompt.md
    - DESIGN/PROMPTS/plot_writer_prompt.md
    - DESIGN/PROMPTS/proofreader_prompt.md

  validation:
    - 文件存在
    - 文件非空（>100字节）
```

### 2. 配置文件完整性
```yaml
check_config_files:
  required_files:
    - src/novels_project/config/agents.yaml
    - src/novels_project/config/tasks.yaml
    - src/novels_project/config/character_base_cards.yaml

  validation:
    - 文件存在
    - YAML 格式正确
    - 必填字段非空
```

### 3. 人物卡库检查
```yaml
check_character_base_cards:
  file: src/novels_project/config/character_base_cards.yaml

  required_tiers:
    s_tier:
      minimum_count: 4
      required_fields:
        - name
        - role
        - core_personality
        - unique_speaking_style
        - example_dialogues  # 至少2条

    a_tier:
      minimum_count: 10
      required_fields:
        - name
        - role
        - core_personality
        - unique_speaking_style

  validation:
    - S级人物至少4个
    - A级人物至少10个
    - 每个人物的必填字段非空
    - example_dialogues 至少有2条对话示例
```

### 4. 样例库检查
```yaml
check_samples:
  directory: samples/

  required_categories:
    - 权谋章
    - 战斗章
    - 情感章
    - 经营章

  minimum_samples: 2

  validation:
    - samples/ 目录存在
    - 至少有2个 .md 样例文件
    - 每个样例文件>500字
```

### 5. 环境变量检查
```yaml
check_environment_variables:
  required_vars:
    COMPANY_API_KEY:
      description: "API密钥（格式：APP_ID:APP_KEY）"
      validation: "非空且包含冒号"
      example: "abc123:xyz789"

  optional_vars:
    MODEL_NAME:
      default: "gemini-3-pro"
    API_BASE_URL:
      default: "http://ai-service.tal.com/openai-compatible/v1"
    EMBEDDING_MODEL:
      default: "text-embedding-v4"
```

### 6. Python 依赖检查
```yaml
check_dependencies:
  required_packages:
    - crewai>=1.9.3
    - chromadb
    - langchain
    - pyyaml
    - python-dotenv

  validation:
    - pip list 包含所有必需包
```

---

## 🚨 错误处理

### 错误报告格式
```
❌ 验证失败：人物卡库检查

问题：
  1. S级人物只有 2 个，需要至少 4 个
     缺失：白璃、方清砚

  2. 陆商曜的 example_dialogues 只有 1 条，需要至少 2 条

修复建议：
  - 用 qwen3-max 生成缺失的 S 级人物卡
  - 为陆商曜补充至少 1 条对话示例

相关文档：DESIGN/GUIDES/CHARACTER_GENERATION.md
```

### 警告（非致命）
```
⚠️  警告：样例库较少

当前状态：
  - 只有 2 个样例文件
  - 建议至少 5 个样例以提高质量

建议：
  - 从试读样例中提取更多片段
  - 参考：DESIGN/GUIDES/SAMPLE_MANAGEMENT.md
```

---

## 🔧 验证脚本使用

```bash
# 运行完整验证
python initialize.py

# 只验证特定项
python initialize.py --check character_cards
python initialize.py --check samples
python initialize.py --check env

# 详细模式（显示所有检查细节）
python initialize.py --verbose
```

---

## ✅ 通过标准

所有检查项必须通过（✅）或警告（⚠️），不能有错误（❌）

```
验证报告：
✅ 设计文档完整性
✅ 配置文件完整性
✅ 人物卡库检查
⚠️  样例库检查（只有2个样例，建议5个）
✅ 环境变量检查
✅ Python 依赖检查

总结：6/6 通过（1个警告）
状态：✅ 可以开始执行
```
