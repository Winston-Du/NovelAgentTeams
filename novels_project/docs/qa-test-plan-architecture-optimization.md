# NovelAgentTeams 架构优化 — QA 全面测试方案

> **版本**: v1.0  
> **日期**: 2025-06-05  
> **作者**: gstack-qa-lead  
> **状态**: 待评审  
> **对应优化**: 7 项架构重构 + 3 项性能优化

---

## 1. 测试策略总览

### 1.1 测试金字塔

```
        ┌──────────────┐
        │  E2E (5%)    │  全链路场景验证
        │  12 cases    │  CLI + Web API 双路径
        ├──────────────┤
        │ Integration  │  模块间契约 + 数据流
        │  (20%)       │
        │  48 cases    │  LLM工厂 → 运行时 → 工具
        ├──────────────┤
        │   Unit       │  函数/类级别隔离测试
        │  (75%)       │
        │  185 cases   │  Mock LLM、Mock I/O
        └──────────────┘

总计: ~245 新增/修改测试用例，覆盖 7 个优化模块
现有回归用例: 1364 条（全部保留）
```

### 1.2 各项优化测试重点分布

| 优化项 | 单元 | 集成 | E2E | 性能 | 总权重 |
|--------|------|------|-----|------|--------|
| 1. 配置层重构 | 25 | 8 | 2 | 0 | 15% |
| 2. 工具层去硬编码 | 30 | 6 | 3 | 0 | 17% |
| 3. LLM客户端统一 | 20 | 10 | 3 | 4 | 18% |
| 4. 异常处理分层 | 35 | 4 | 1 | 0 | 16% |
| 5. 迭代逻辑精简 | 25 | 6 | 1 | 1 | 14% |
| 6. 知识图谱分级存储 | 30 | 8 | 1 | 6 | 18% |
| 7. 会话压缩优化 | 20 | 6 | 1 | 5 | 14% |

---

## 2. 单元测试方案

### 2.1 配置层重构 — `project_config.py`

#### 变更要点
- 提取公用人设格式化工具到 `project_config.py`
- 统一 YAML 解析入口（当前多处直接 `yaml.safe_load`）
- 新增 `PersonaFormatter` 类（从各 tools 和 api 模块提取）

#### 新增测试用例

| ID | 用例名称 | 输入 | 预期输出 | Mock 策略 |
|----|---------|------|---------|----------|
| UT-CFG-001 | `PersonaFormatter.format_character()` - 完整字段 | 含所有字段的 character dict | 格式化字符串含 identity/personality/speaking_style | 无 |
| UT-CFG-002 | `PersonaFormatter.format_character()` - 最小字段 | 仅有 name 的 dict | 格式化字符串仅含 name，不报错 | 无 |
| UT-CFG-003 | `PersonaFormatter.format_character()` - 空输入 | `{}` | 不抛异常，返回默认描述 | 无 |
| UT-CFG-004 | `PersonaFormatter.format_all()` - 多层级 | s_tier/a_tier/b_tier 混合 | 返回完整格式化结果 | 无 |
| UT-CFG-005 | `PersonaFormatter.format_all()` - 空层级 | `{}` | 返回空 str | 无 |
| UT-CFG-006 | `PersonaFormatter.from_yaml()` - 正常 YAML | 标准 character_base_cards.yaml | 返回 PersonaFormatter 实例 | Mock 文件 I/O |
| UT-CFG-007 | `PersonaFormatter.from_yaml()` - 损坏 YAML | 语法错误的 YAML | 抛出 `ConfigParseError` | Mock 文件 I/O |
| UT-CFG-008 | `PersonaFormatter.from_yaml()` - YAML 含未知 tier | 含 d_tier 的 YAML | 忽略未知 tier，正常解析其他 | Mock 文件 I/O |
| UT-CFG-009 | `load_yaml_safe()` - 正常加载 | 有效 YAML 路径 | 返回 dict | Mock 文件 I/O |
| UT-CFG-010 | `load_yaml_safe()` - 文件不存在 | 不存在的路径 | 抛出 `FileNotFoundError` | 无 |
| UT-CFG-011 | `load_yaml_safe()` - 编码错误 | 非 UTF-8 文件 | 抛出 `ConfigParseError`，含原始错误信息 | Mock 文件 I/O |
| UT-CFG-012 | `load_yaml_safe()` - 空文件 | 空文件 | 返回 `{}` | Mock 文件 I/O |
| UT-CFG-013 | `get_project_root()` - 环境变量优先 | 设置 `NOVEL_PROJECT_ROOT` | 返回环境变量值 | Mock os.getenv |
| UT-CFG-014 | `get_character_cards_path()` - 新格式优先 | 标准 config/ 路径存在 | 返回标准路径 | tmp_path |
| UT-CFG-015 | `get_character_cards_path()` - legacy 回退 | 仅 legacy 路径存在 | 返回 legacy 路径 | tmp_path |

#### 边界条件覆盖
- YAML 格式兼容：`\t` vs 空格缩进、`---` 多文档
- 空角色列表：无 characters 字段的 tier
- 特殊字符角色名：含 Unicode、emoji、换行符
- 大文件：1000+ 角色的人物卡

---

### 2.2 工具层去硬编码 — `character_voice_checker.py`

#### 变更要点
- 移除 `known_characters` 硬编码列表（第 48 行）
- 改为从 `project_config.PersonaFormatter` 动态加载角色
- `_extract_dialogues()` 支持动态角色名识别

#### 新增测试用例

| ID | 用例名称 | 输入 | 预期输出 | Mock 策略 |
|----|---------|------|---------|----------|
| UT-VCHK-001 | `_extract_dialogues()` - 动态角色加载 | 新角色 + 对话 | 正确识别新角色 | Mock PersonaFormatter |
| UT-VCHK-002 | `_extract_dialogues()` - 空角色列表 | 空 PersonaFormatter | 所有对话标记"未知" | Mock PersonaFormatter |
| UT-VCHK-003 | `_extract_dialogues()` - 角色名含正则特殊字符 | `[测试]角色` 名 | 正确转义，不抛异常 | Mock PersonaFormatter |
| UT-VCHK-004 | `_extract_dialogues()` - 角色名重叠 | `陆商` 和 `陆商曜` | 优先匹配最长名称 | Mock PersonaFormatter |
| UT-VCHK-005 | `_extract_dialogues()` - 中文引号变体 | `「」`、`『』`、`""` | 全部正确提取 | Mock PersonaFormatter |
| UT-VCHK-006 | `_extract_dialogues()` - 无引号对话 | `他说：你好。` | 正确提取 | Mock PersonaFormatter |
| UT-VCHK-007 | `check_character_voice()` - 新角色校验 | 含新增角色的对话 | 能加载该角色卡并校验 | Mock PersonaFormatter |
| UT-VCHK-008 | `_load_character_cards()` - 统一到 PersonaFormatter | N/A | 内部调用 `PersonaFormatter.from_yaml()` | Mock PersonaFormatter |
| UT-VCHK-009 | `refresh_character_cards()` - 清除缓存 + 通知 | 已缓存卡片 | PersonaFormatter 缓存刷新 | Mock PersonaFormatter |
| UT-VCHK-010 | `check_character_voice()` - 超大文本（100KB） | 100KB 章节内容 | 不超时，正常返回报告 | 真实角色卡片 |

#### 回归验证
- 保留全部 41 条现有 `test_character_voice_checker.py` 测试
- 验证 `_is_nervous`、`_is_over_explaining` 等辅助函数行为不变
- 验证 `get_character_voice_guide()` 返回格式不变

---

### 2.3 LLM 客户端统一 — `api_client.py`

#### 变更要点
- 提取 `create_api_client()` 工厂函数，统一 CLI 和 Web API 的创建逻辑
- 支持客户端池化（可选）
- 统一配置读取（环境变量 / providers.yaml / 代码参数）

#### 新增测试用例

| ID | 用例名称 | 输入 | 预期输出 | Mock 策略 |
|----|---------|------|---------|----------|
| UT-LLM-001 | `create_api_client()` - 从环境变量创建 | 设置 `COMPANY_API_KEY`, `API_BASE_URL` | 返回正确配置的 client | Mock os.getenv |
| UT-LLM-002 | `create_api_client()` - 从 providers.yaml 创建 | providers.yaml 含多供应商 | 使用首个可用供应商 | Mock 文件 I/O |
| UT-LLM-003 | `create_api_client()` - 优先级：参数 > env > yaml | 同时设置三处 | 参数优先 | Mock os.getenv + 文件 I/O |
| UT-LLM-004 | `create_api_client()` - 无可用配置 | 无 env、yaml、参数 | 抛出 `ClientConfigError` | Mock |
| UT-LLM-005 | `create_api_client()` - API key 为空字符串 | `api_key=""` | 抛出 `ClientConfigError` | 无 |
| UT-LLM-006 | `create_api_client()` - 自定义 timeout | `timeout=600` | client.timeout == 600 | 无 |
| UT-LLM-007 | `stream()` - 客户端池并发 | 3 并发 stream 请求 | 无交叉污染，各自独立 | Mock API 响应 |
| UT-LLM-008 | `stream()` - 连接超时重试 | 首次调用超时 | 自动重试，最多 3 次 | Mock socket.timeout |
| UT-LLM-009 | `stream()` - API 返回 429 | Rate limit 响应 | 重试并记录 usage 事件 | Mock HTTP 429 |

---

### 2.4 异常处理分层 — `entity_extractor.py`

#### 变更要点
- 区分 LLM 调用错误（网络、超时、Rate Limit）与业务降级（JSON 解析失败、实体缺失）
- 新增异常类型：`LLMError`、`ExtractionFallbackWarning`
- 降级路径显式化：LLM 失败 → 规则模式，规则失败 → 空结果（不抛异常）

#### 新增测试用例

| ID | 用例名称 | 输入 | 预期输出 | Mock 策略 |
|----|---------|------|---------|----------|
| UT-EE-001 | `extract_from_chapter_text()` - LLM 网络超时 | `socket.timeout` | 降级为规则模式，记录 `LLMError` | Mock stream 抛 timeout |
| UT-EE-002 | `extract_from_chapter_text()` - LLM 返回 500 | HTTP 500 错误 | 降级为规则模式 | Mock stream 抛异常 |
| UT-EE-003 | `extract_from_chapter_text()` - LLM 返回空文本 | 空文本流 | 降级为规则模式，记录 `ExtractionFallbackWarning` | Mock 空响应 |
| UT-EE-004 | `extract_from_chapter_text()` - LLM JSON 解析失败 | 非 JSON 响应 | 降级为规则模式 | Mock 非 JSON 响应 |
| UT-EE-005 | `extract_from_chapter_text()` - 规则模式也无匹配 | 文本中无任何已知实体 | 返回 `{"added_entities": 0, "added_relations": 0}` | 空 GraphStore |
| UT-EE-006 | `extract_from_character_cards()` - LLM 异常后规则回退 | LLM 失败 | 规则模式正常提取，不丢数据 | Mock LLM 失败 |
| UT-EE-007 | `_parse_llm_output()` - JSON 包含 markdown code block | ` ```json {...} ``` ` | 正确提取 JSON | 无 |
| UT-EE-008 | `_parse_llm_output()` - JSON 包含 BOM | `\ufeff{...}` | 正确解析 | 无 |
| UT-EE-009 | `build_knowledge_graph()` - 部分章节失败 | 章节 3 LLM 失败 | 章节 1/2/4 正常，errors 列表含章节 3 | Mock 章节 3 失败 |
| UT-EE-010 | `LLMError` 异常类型 | 手动抛出 `LLMError("timeout", retryable=True)` | 可捕获，属性正确 | 无 |
| UT-EE-011 | `ExtractionFallbackWarning` 异常类型 | 手动抛出 | 可捕获，含 fallback_mode 字段 | 无 |

---

### 2.5 迭代逻辑精简 — `iteration_tools.py`

#### 变更要点
- 消除状态映射重复（4 个函数中重复 `IterationStatus` → 中文消息映射）
- 提取 `_format_status_message()` 统一状态映射
- 提取 `_get_session_or_error()` 统一错误处理

#### 新增测试用例

| ID | 用例名称 | 输入 | 预期输出 | Mock 策略 |
|----|---------|------|---------|----------|
| UT-ITER-001 | `_format_status_message()` - ACCEPT | `IterationStatus.ACCEPT, score=8` | `"✅ 质量达标 (8/10)，无需继续迭代"` | 无 |
| UT-ITER-002 | `_format_status_message()` - CONTINUE | `IterationStatus.CONTINUE, score=6, remaining=2` | `"🔄 需要继续迭代 (当前分数: 6/10，剩余迭代次数: 2)"` | 无 |
| UT-ITER-003 | `_format_status_message()` - MAX_ITER | `IterationStatus.MAX_ITER, max=5` | `"⚠️ 已达最大迭代次数 (5)，停止迭代"` | 无 |
| UT-ITER-004 | `_format_status_message()` - 未知状态 | 未知 status | 抛出 `ValueError` | 无 |
| UT-ITER-005 | `_get_session_or_error()` - 会话存在 | valid chapter_id | 返回 session | Mock controller |
| UT-ITER-006 | `_get_session_or_error()` - 会话不存在 | 无会话的 chapter_id | 返回统一格式错误消息 | Mock controller |
| UT-ITER-007 | `record_iteration()` - review_issues 为 None | `review_issues=None` | issues=[]，正常记录 | Mock controller |
| UT-ITER-008 | `record_iteration()` - review_issues 为数组字符串 | `'[{"type":"x"}]'` | 正确解析为 list | Mock controller |

#### 回归验证
- 保留全部 16 条现有 `test_iteration_tools.py` 测试
- 验证 `check_iteration_status()`、`should_continue_iteration()` 等对外接口不变
- 验证 `get_revision_feedback()`、`record_iteration()` 行为不变

---

### 2.6 知识图谱分级存储 — `graph_store.py`

#### 变更要点
- 热数据（最近 5 章涉及的实体）→ 内存 NetworkX
- 冷数据 → JSON 文件按需加载
- 新增 `TieredGraphStore` 类包裹原 `GraphStore`

#### 新增测试用例

| ID | 用例名称 | 输入 | 预期输出 | Mock 策略 |
|----|---------|------|---------|----------|
| UT-GS-001 | `TieredGraphStore.add_entity()` - 新实体默认热存储 | 新增实体 | 在 hot 层，可立即查询 | 空 store |
| UT-GS-002 | `TieredGraphStore.get_entity()` - 热数据命中 | 热层存在的实体 | 直接返回，不读文件 | 预填充 hot |
| UT-GS-003 | `TieredGraphStore.get_entity()` - 冷数据回退 | 仅在冷存储的实体 | 从文件加载到 hot，返回数据 | Mock 冷文件 |
| UT-GS-004 | `TieredGraphStore.get_entity()` - 实体不存在 | 不存在的实体名 | 返回 None | 空 store |
| UT-GS-005 | `TieredGraphStore.promote_to_hot()` - 单实体升级 | chapter_id 变化 | 实体移至 hot 层 | 预填充 cold |
| UT-GS-006 | `TieredGraphStore.demote_to_cold()` - 热数据降级 | 超过 5 章未出现 | 实体移至 cold 文件 | 预填充 hot |
| UT-GS-007 | `TieredGraphStore.save()` - 全量持久化 | hot + cold 均有数据 | hot 序列化 + cold 单独文件 | tmp_path |
| UT-GS-008 | `TieredGraphStore.load()` - 从文件恢复 | 标准 JSON 文件 | hot 加载最近实体，cold 建立文件索引 | tmp_path |
| UT-GS-009 | `TieredGraphStore.entity_count()` - 跨层计数 | hot=3, cold=7 | 返回 10 | 预填充 |
| UT-GS-010 | `TieredGraphStore` - 10000 实体扩展 | 批量插入 10k 实体 | 内存不超 100MB，查询 < 50ms | 无 |

#### 回归验证
- 保留 `GraphStore` 所有原始测试（作为内部引擎）
- `TieredGraphStore` 对外 API 需向后兼容 `GraphStore` 接口

---

### 2.7 会话压缩优化 — `compaction.py`

#### 变更要点
- 增量压缩：上次已压缩的消息不再重复处理
- 分层摘要：short（最近 N 轮） / medium（会话级） / long（跨会话级）
- `CompactionConfig` 新增 `incremental`、`layered` 选项

#### 新增测试用例

| ID | 用例名称 | 输入 | 预期输出 | Mock 策略 |
|----|---------|------|---------|----------|
| UT-CMP-001 | `compact_session()` - incremental 模式：再次压缩 | 已压缩过的 session 追加新消息 | 仅压缩新增部分，保留旧摘要 | 预创建 compressed session |
| UT-CMP-002 | `compact_session()` - layered 模式：short 层 | 10 条消息 | 保留最近 4 条 + short_summary | 标准 session |
| UT-CMP-003 | `compact_session()` - layered 模式：medium 生成 | 50 条消息 | short_summary + medium_summary + 最近 | 大型 session |
| UT-CMP-004 | `compact_session()` - layered 触发阈值 | 100 条消息 | 三层摘要全部生成 | 超大型 session |
| UT-CMP-005 | `compact_session()` - incremental + layered | 200 条消息分段压缩 | 每次增量仅处理新增，摘要分层累积 | 模拟多次 compact |
| UT-CMP-006 | `compact_session()` - 空 session | 0 条消息 | 返回原 session，removed=0 | 空 session |
| UT-CMP-007 | `CompactionConfig` - 新字段默认值 | 不传参数 | `incremental=True`, `layered=True` | 无 |
| UT-CMP-008 | `_build_summary()` - 含已有摘要消息 | 上次压缩的 summary 在消息列表 | 引用旧摘要，不重复分析 | 预构建 |

#### 回归验证
- 保留全部 29 条现有 `test_compaction.py` 测试
- 验证 `estimate_message_tokens()` 行为不变
- 验证 `CompactionResult` 结构向后兼容

---

## 3. 集成测试方案

### 3.1 模块间接口契约测试

| ID | 契约名称 | 参与模块 | 验证点 |
|----|---------|---------|--------|
| IT-CONTRACT-001 | `create_api_client()` → `ConversationRuntime` | api_client + runtime | Runtime 接受工厂创建的 client，正常 run_turn |
| IT-CONTRACT-002 | `PersonaFormatter` → `character_voice_checker` | project_config + tools | voice checker 通过 formatter 加载角色，无需直接读 YAML |
| IT-CONTRACT-003 | `EntityExtractor` → `TieredGraphStore` | entity_extractor + graph_store | LLM 提取的实体正确写入分级 graph |
| IT-CONTRACT-004 | `iteration_tools` → `iteration_controller` | tools + controller | 精简后的工具调用 controller，session 创建/查询正常 |
| IT-CONTRACT-005 | `compact_session()` → `ConversationRuntime.auto_compact` | compaction + runtime | Runtime 触发压缩后，增量摘要正确累积 |
| IT-CONTRACT-006 | `create_api_client()` → CLI `run()` | api_client + cli | CLI 使用工厂创建 client，main agent 正常运行 |
| IT-CONTRACT-007 | `create_api_client()` → Web API `/content/optimize` | api_client + api/content | Web API 使用同一工厂，content optimize 正常 |
| IT-CONTRACT-008 | `PersonaFormatter` → `system_prompt` 构建 | project_config + system_prompt | System prompt 生成使用统一格式化器 |

### 3.2 端到端场景测试

| ID | 场景 | 步骤 | 预期结果 |
|----|------|------|---------|
| E2E-001 | 切换故事项目 → 角色自动识别 → 对话校验 | 1. 切换 `NOVEL_PROJECT_ROOT` 到新项目<br>2. 新项目有不同的人物卡<br>3. 运行 `check_character_voice` | 使用新项目角色列表，正确校验新角色的对话 |
| E2E-002 | CLI + Web API 双路径一致性 | 1. CLI 创建 session 写一章<br>2. Web API 查看 session 继续写<br>3. 同一模型、同一 system_prompt | 两路径产生风格一致的续写 |
| E2E-003 | 知识图谱跨会话持久化 | 1. Session A 提取实体到 graph<br>2. 保存 graph<br>3. Session B 加载 graph，查询 | Session B 能看到 Session A 的实体 |
| E2E-004 | 超长对话增量压缩 | 1. 连续 200 轮对话<br>2. 观察 compaction 触发<br>3. 续写质量不退化 | 增量压缩后上下文字数可控，写作质量稳定 |
| E2E-005 | LLM 故障降级不中断服务 | 1. LLM 实体提取超时<br>2. 自动降级为规则提取<br>3. 写作流程继续 | 降级后规则模式仍能提取已知实体 |
| E2E-006 | 迭代写作-校对-修改闭环 | 1. 写初稿<br>2. 校对识别问题<br>3. 基于反馈修改<br>4. 再次校对直到通过 | 迭代流程正确推进，状态映射正确 |

### 3.3 回归测试套件选择

使用现有 1364 条测试用例，按模块分优先级执行：

| 优先级 | 测试文件 | 条数 | 执行策略 |
|--------|---------|------|---------|
| P0 - 阻塞 | `test_api_client.py`, `test_project_config.py`, `test_session.py`, `test_compaction.py` | ~120 | 每次 commit 必跑 |
| P1 - 核心 | `test_entity_extractor.py`, `test_character_voice_checker.py`, `test_iteration_tools.py`, `test_iteration_controller.py`, `test_runtime.py` | ~200 | 每次 push 必跑 |
| P2 - 关联 | `test_graph_memory.py`, `test_graph_query.py`, `test_integrator.py`, `test_graph_memory_tool.py`, `test_feedback_loop.py` | ~180 | 每日 CI |
| P3 - 全量 | 所有 tests/ 目录 | 1364 | 发布前 / 周 CI |

---

## 4. 性能测试方案

### 4.1 知识图谱大规模实体场景

**目标**: 1000+ 实体、10000+ 关系的读写性能

| ID | 测试名称 | 参数 | 目标指标 | 工具 |
|----|---------|------|---------|------|
| PERF-KG-001 | 批量实体插入 | 1000 实体顺序插入 | < 5 秒 | pytest-benchmark |
| PERF-KG-002 | 批量关系插入 | 10000 关系顺序插入 | < 30 秒 | pytest-benchmark |
| PERF-KG-003 | 热数据查询延迟 | 1000 实体中查 1 个 | < 10ms (P99) | pytest-benchmark |
| PERF-KG-004 | 冷数据加载延迟 | 从文件加载 500 实体 | < 200ms (P99) | pytest-benchmark |
| PERF-KG-005 | 降级操作延迟 | 100 实体从 hot→cold | < 100ms | pytest-benchmark |
| PERF-KG-006 | 内存占用 | 10000 实体在内存中 | < 200MB RSS | memory_profiler |

### 4.2 会话压缩超长对话

**目标**: 500+ 轮对话的压缩性能

| ID | 测试名称 | 参数 | 目标指标 | 工具 |
|----|---------|------|---------|------|
| PERF-CMP-001 | 增量压缩延迟 | 500 轮对话，追加 10 轮后压缩 | < 50ms (仅处理新增) | pytest-benchmark |
| PERF-CMP-002 | 全量压缩延迟（基线） | 500 轮首次压缩 | < 500ms | pytest-benchmark |
| PERF-CMP-003 | 分层摘要内存 | 三层摘要 + 500 轮对话 | < 50MB 摘要开销 | memory_profiler |
| PERF-CMP-004 | 压缩后上下文 token 数 | 500 轮 → 压缩 | < 8000 tokens | estimate_message_tokens |
| PERF-CMP-005 | 连续压缩稳定性 | 1000 轮对话，每 10 轮压缩 | 无内存泄漏，RSS 稳定 | 持续运行监控 |

### 4.3 LLM 客户端并发吞吐量

**目标**: 多 Agent 场景下的并发性能

| ID | 测试名称 | 参数 | 目标指标 | 工具 |
|----|---------|------|---------|------|
| PERF-LLM-001 | 单客户端吞吐 | 连续 stream 请求 | 瓶颈在 API 而非客户端 | locust |
| PERF-LLM-002 | 10 并发 Agent 请求 | 10 个 runtime 同时 run_turn | 无死锁，无交叉响应 | pytest-asyncio |
| PERF-LLM-003 | 客户端创建开销 | 1000 次 create_api_client() | P99 < 1ms（工厂模式避免重复 SSL 握手） | pytest-benchmark |

---

## 5. 兼容性测试方案

### 5.1 CLI 和 Web API 双路径一致性

| ID | 测试内容 | 方法 | 验收标准 |
|----|---------|------|---------|
| COMPAT-001 | 同一 session 双路径写入 | CLI 写一章 → Web API 查看 | session 数据一致 |
| COMPAT-002 | 同一模型双路径配置 | CLI 和 API 用同一 providers.yaml | 连接相同 API endpoint |
| COMPAT-003 | 工具调用结果双路径一致 | 同一工具在 CLI 和 API 分别调用 | 输出格式一致 |
| COMPAT-004 | System prompt 双路径一致 | 同一项目配置 | 生成的 system_prompt 文本相同 |
| COMPAT-005 | 错误处理双路径一致 | LLM 故障时 | 降级行为、错误消息一致 |

### 5.2 旧项目数据迁移兼容性

| ID | 测试内容 | 方法 | 验收标准 |
|----|---------|------|---------|
| MIG-001 | 旧格式 graph.json → TieredGraphStore | 读取旧格式 graph.json | 正确拆分为 hot/cold |
| MIG-002 | 旧格式 character_base_cards.yaml → PersonaFormatter | 旧格式 YAML 加载 | 所有字段正确解析 |
| MIG-003 | 旧格式 session → 新 compacted session | 加载旧 session 文件 | 追加消息后增量压缩正常 |
| MIG-004 | 旧格式 chaptern_final.md → 新提取器 | 旧章节内容实体提取 | 提取结果无退化 |
| MIG-005 | providers.yaml 向后兼容 | 不修改现有 providers.yaml | 新工厂函数仍可正确读取 |

### 5.3 Python 版本兼容性

| Python 版本 | 测试策略 | 重点关注 |
|-------------|---------|---------|
| 3.9 | 基础兼容测试 | `dict | dict` 语法 → `{**a, **b}`，`str.removeprefix` |
| 3.10 | 全量测试（当前生产） | 基准版本 |
| 3.11 | 全量测试 | `tomllib`、异常组 |
| 3.12 | 冒烟测试 | 类型注解变更、`@override` |

在 CI 中使用 `tox` 或 GitHub Actions matrix 并行测试。

---

## 6. 测试工具选型

### 6.1 已具备

| 工具 | 用途 | 版本 | 配置 |
|------|------|------|------|
| **pytest** | 单元 + 集成测试 | ≥7.0 | `pyproject.toml` [tool.pytest.ini_options] |
| **pytest-cov** | 覆盖率 | ≥4.0 | branch=true, fail_under=50（建议提升至 75） |
| **pytest-mock** | Mock 框架 | ≥3.10 | 与 unittest.mock 互补 |
| **pytest-asyncio** | 异步测试 | ≥0.21 | asyncio_mode=auto |
| **pytest-xdist** | 并行测试 | ≥3.0 | 用于加速全量回归 |
| **pytest-benchmark** | 性能微基准 | ≥4.0 | 已配置但未充分使用 |
| **locust** | 负载测试 | ≥2.15 | tests/performance/locustfile.py 已有 |
| **ruff** | Lint | ≥0.1 | [tool.ruff] 配置完整 |
| **mypy** | 静态类型检查 | ≥1.0 | [tool.mypy] 已配置 |
| **bandit** | 安全扫描 | ≥1.7 | [tool.bandit] 已配置 |

### 6.2 建议新增

| 工具 | 用途 | 理由 |
|------|------|------|
| **memory_profiler** | 内存分析 | 知识图谱分级存储的内存监控（PERF-KG-006, PERF-CMP-003） |
| **pytest-timeout** | 测试超时控制 | 防止 LLM mock 测试卡死 |
| **tox** | 多版本测试 | Python 3.9-3.12 兼容性矩阵 |
| **hypothesis** | 属性测试 | 复杂状态机（如 compaction 增量一致性） |
| **coverage-badge** | 覆盖率徽章 | README 可视化 |

### 6.3 CI/CD 集成

```yaml
# .github/workflows/test.yml 建议结构
jobs:
  lint:
    - ruff check
    - mypy src/
    - bandit -c pyproject.toml -r src/

  unit-p0:
    - pytest tests/unit/test_api_client.py tests/unit/test_project_config.py \
            tests/unit/test_session.py tests/unit/test_compaction.py \
      --cov --cov-report=xml -n auto

  unit-p1:
    - pytest tests/unit/ --ignore=tests/unit/test_api_client.py \
            --ignore=tests/unit/test_project_config.py \
      --cov --cov-append -n auto

  integration:
    - pytest tests/integration/ --cov --cov-append

  performance:
    - pytest tests/performance/ --benchmark-only  # 仅在有 --perf flag 时

  compatibility:
    - tox  # Python 3.9, 3.10, 3.11, 3.12

  coverage-gate:
    needs: [unit-p0, unit-p1, integration]
    - coverage report --fail-under=75
```

---

## 7. 覆盖率目标与验收标准

### 7.1 各层覆盖率目标

| 层级 | 行覆盖率 | 分支覆盖率 | 说明 |
|------|---------|-----------|------|
| 配置层 (project_config) | ≥90% | ≥85% | 新增 PersonaFormatter、load_yaml_safe |
| 工具层 (character_voice_checker) | ≥90% | ≥80% | 移除硬编码不降低覆盖率 |
| LLM 客户端 (api_client) | ≥85% | ≥80% | 新增工厂函数和池化 |
| 异常处理 (entity_extractor) | ≥90% | ≥85% | 重点覆盖降级分支 |
| 迭代逻辑 (iteration_tools) | ≥95% | ≥90% | 精简后更容易达到高覆盖 |
| 知识图谱 (graph_store) | ≥85% | ≥80% | 分级存储新增类 |
| 会话压缩 (compaction) | ≥90% | ≥85% | 增量/分层模式 |
| **全局** | **≥80%** | **≥75%** | 从当前 50% fail_under 提升 |

### 7.2 各模块验收条件

| 模块 | 验收条件 |
|------|---------|
| project_config | PersonaFormatter 三个方法 100% 覆盖；新旧格式 YAML 均可解析 |
| character_voice_checker | 移除硬编码后 0 个 Regression；动态加载角色测试 ≥ 10 条 |
| api_client | 工厂函数覆盖 6 种配置优先级组合；并发测试 0 交叉污染 |
| entity_extractor | 5 种 LLM 异常 → 降级路径全覆盖；降级后数据不丢失 |
| iteration_tools | _format_status_message 覆盖所有 IterationStatus 值；旧接口兼容 |
| graph_store | TieredGraphStore 与 GraphStore 接口兼容；热/冷切换无数据丢失 |
| compaction | 增量模式只压缩新增消息；分层摘要三层正确生成 |
| 全局 | 1364 条已有测试全部通过；性能基准无 >10% 退化 |

### 7.3 性能基准与回归阈值

| 指标 | 基线值 | 回归阈值 |
|------|-------|---------|
| 单个单元测试执行时间 | < 1s | > 3s 触发告警 |
| 全量单元测试 (1364 条) | < 60s | > 120s 阻塞发布 |
| 知识图谱 1000 实体查询 | < 10ms | > 50ms 退化 |
| 会话压缩 100 轮 | < 200ms | > 500ms 退化 |
| LLM 客户端创建 | < 1ms | > 5ms 退化 |
| 内存占用（500 轮对话） | < 100MB | > 200MB 阻塞 |

---

## 8. 闭环验证矩阵

将每项架构优化措施映射到具体测试用例，形成完整闭环链路。

### 8.1 配置层重构

| 优化措施 | 测试用例 | 预期结果 | 验收标准 |
|---------|---------|---------|---------|
| 提取 `PersonaFormatter` | UT-CFG-001~008 | 多模块共用同一格式化逻辑 | 3 个调用方（voice_checker, system_prompt, API）使用相同 formatter |
| 统一 `load_yaml_safe()` | UT-CFG-009~012 | 一处 YAML 解析，统一错误处理 | 项目中不再有直接 `yaml.safe_load()` 调用 |
| 向后兼容 get_* 函数 | IT-CONTRACT-008 | 旧调用方无需修改 | 现有 project_config 测试全部通过 |

### 8.2 工具层去硬编码

| 优化措施 | 测试用例 | 预期结果 | 验收标准 |
|---------|---------|---------|---------|
| 移除 hardcoded `known_characters` | UT-VCHK-001~004 | 角色从 PersonaFormatter 动态加载 | 添加新角色无需修改 voice_checker 代码 |
| 动态正则构建 | UT-VCHK-003~004 | 角色名含特殊字符时正确转义 | 角色名 `[测试]` 不导致正则错误 |
| 缓存策略保留 | UT-VCHK-008~009 | 卡片缓存仍有效 | refresh_character_cards 正确刷新 PersonaFormatter 缓存 |
| E2E 切换项目验证 | E2E-001 | 切换后自动识别新角色 | 新项目角色列表在 voice check 中生效 |

### 8.3 LLM 客户端统一

| 优化措施 | 测试用例 | 预期结果 | 验收标准 |
|---------|---------|---------|---------|
| 提取 `create_api_client()` 工厂 | UT-LLM-001~006 | CLI 和 API 使用同一创建路径 | cli.py 和 api/content.py 均调用 create_api_client() |
| 配置优先级 | UT-LLM-003 | 参数 > env > providers.yaml | 三处同时配置时参数生效 |
| 无配置时明确报错 | UT-LLM-004~005 | 抛出 ClientConfigError | 不再 NoneType error |
| 双路径一致性 | E2E-002, COMPAT-001~005 | CLI 和 API 行为一致 | 同一 session 双路径操作结果一致 |
| 并发安全性 | PERF-LLM-001~003 | 10 并发无交叉污染 | locust 压测通过 |

### 8.4 异常处理分层

| 优化措施 | 测试用例 | 预期结果 | 验收标准 |
|---------|---------|---------|---------|
| LLM 网络超时 → 降级 | UT-EE-001 | 规则模式提取，记录 LLMError | 不中断服务 |
| LLM HTTP 500 → 降级 | UT-EE-002 | 规则模式提取 | 不中断服务 |
| LLM JSON 解析失败 → 降级 | UT-EE-004 | 规则模式提取 | 不丢失已知实体 |
| 降级也失败 → 空结果 | UT-EE-005 | 返回空，不抛异常 | 不阻塞写作流程 |
| 新增异常类型 | UT-EE-010~011 | LLMError(retryable=), ExtractionFallbackWarning | 上层可区分处理 |
| E2E 降级不中断 | E2E-005 | 写作流程在 LLM 故障后继续 | 用户感知为轻微延迟 |

### 8.5 迭代逻辑精简

| 优化措施 | 测试用例 | 预期结果 | 验收标准 |
|---------|---------|---------|---------|
| 提取 `_format_status_message()` | UT-ITER-001~004 | 统一状态→消息映射 | 4 个公开函数使用同一 formatter |
| 提取 `_get_session_or_error()` | UT-ITER-005~006 | 统一错误处理 | 错误消息格式一致 |
| 旧接口兼容 | UT-ITER-007~008 | check_iteration_status 等 4 个函数行为不变 | 现有 16 条 iteration_tools 测试全通过 |
| E2E 迭代闭环 | E2E-006 | 写→校→改→验 闭环 | 状态映射在 UI 显示正确 |

### 8.6 知识图谱分级存储

| 优化措施 | 测试用例 | 预期结果 | 验收标准 |
|---------|---------|---------|---------|
| 热数据内存查询 | UT-GS-001~002 | < 10ms 延迟 | 最近 5 章实体即查即得 |
| 冷数据文件按需加载 | UT-GS-003 | < 200ms 冷加载 | 自动升级为热数据 |
| 热冷切换 | UT-GS-005~006 | promote/demote 正确 | 数据无丢失 |
| 持久化/恢复 | UT-GS-007~008 | save/load 往返无损 | graph.json 文件兼容旧格式 |
| 大规模扩展 | UT-GS-010, PERF-KG-001~006 | 10000 实体内存 < 200MB | 性能基准达标 |
| 跨会话持久化 | E2E-003 | Session A 实体在 B 可见 | 冷数据正确加载 |

### 8.7 会话压缩优化

| 优化措施 | 测试用例 | 预期结果 | 验收标准 |
|---------|---------|---------|---------|
| 增量压缩 | UT-CMP-001 | 仅压缩新增消息 | 压缩时间与新增量成正比，非总量 |
| 分层摘要 | UT-CMP-002~005 | short/medium/long 三层正确 | 摘要分层结构正确 |
| 增量+分层组合 | UT-CMP-005 | 200 轮分段 | 每段压缩 < 100ms |
| 旧 session 兼容 | UT-CMP-006 | 空/小 session 不退化 | 现有 compaction 测试全通过 |
| 超长对话性能 | PERF-CMP-001~005 | 500 轮稳定 | 内存无泄漏，token 可控 |
| E2E 超长对话 | E2E-004 | 200 轮后写作质量稳定 | 上下文信息不丢失 |

---

## 附录 A：测试执行时间估算

| 阶段 | 用例数 | 预估耗时 | 执行方式 |
|------|-------|---------|---------|
| 单元测试（P0 阻塞） | ~60 | < 30s | 每次 commit |
| 单元测试（P1 核心） | ~120 | < 2min | 每次 push |
| 单元测试（全量新增） | ~185 | < 5min | 每次 push |
| 集成测试 | ~48 | < 3min | 每日 CI |
| E2E 测试 | ~12 | < 5min | 每日 CI |
| 性能基准 | ~14 | < 10min | 发布前 |
| 兼容性矩阵 | ~20 | < 15min (4 版本并行) | 发布前 |
| 回归（全量 1364） | 1364 | < 3min (xdist) | 发布前 |
| **合计** | **~1703** | **< 45min 全量** | - |

## 附录 B：风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| LLM Mock 不一致 | 中 | 单元测试过但集成挂 | 定期基于真实响应的 snapshot testing |
| 性能测试环境差异 | 高 | CI 与生产不一致 | 在 CI 中设定性能 ratio（CI 值 × 0.5 为上限） |
| 旧项目数据格式未知 | 中 | 迁移失败 | MIG 测试使用真实项目数据 snapshot |
| 并发测试不稳定 (flaky) | 高 | 误报 | 对并发测试使用 `pytest-rerunfailures`（最多重试 3 次） |
| 覆盖率回归 | 低 | 低于 75% 门禁 | 每次 push 跑 `coverage report --fail-under=75` |

## 附录 C：测试文件组织

```
tests/
├── unit/
│   ├── test_project_config.py        # 现有 20 条 + 新增 15 条
│   ├── test_character_voice_checker.py # 现有 41 条 + 新增 10 条
│   ├── test_api_client.py            # 现有 33 条 + 新增 9 条
│   ├── test_entity_extractor.py      # 现有 46 条 + 新增 11 条
│   ├── test_iteration_tools.py       # 现有 16 条 + 新增 8 条
│   ├── test_graph_store.py           # 新增 10 条 (TieredGraphStore)
│   ├── test_compaction.py            # 现有 29 条 + 新增 8 条
│   ├── test_llm_factory.py           # 新增 10 条 (create_api_client)
│   ├── test_persona_formatter.py     # 新增 15 条 (PersonaFormatter)
│   └── ... (existing tests unchanged)
├── integration/
│   ├── test_contract.py              # 新增 8 条契约测试
│   ├── test_e2e_scenarios.py         # 新增 6 条 E2E
│   ├── test_dual_interface.py        # 新增 5 条 双路径
│   ├── test_api_integration.py       # 现有
│   ├── test_sync_manager.py          # 现有
│   └── ...
├── performance/
│   ├── test_knowledge_graph_perf.py  # 新增 6 条
│   ├── test_compaction_perf.py       # 新增 5 条
│   ├── test_llm_concurrency.py       # 新增 3 条
│   └── locustfile.py                 # 现有
├── compatibility/
│   ├── test_migration.py             # 新增 5 条
│   └── test_python_versions.py       # 新增 tox 配置
└── security/
    └── test_security.py              # 现有
```
