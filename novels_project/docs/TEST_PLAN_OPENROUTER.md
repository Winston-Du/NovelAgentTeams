# OpenRouter (owl-alpha) 模型集成测试计划

**项目**: NovelAgentTeams 小说创作系统
**测试模型**: OpenRouter - owl-alpha
**测试日期**: 2026-06-04
**版本**: v0.3.0

---

## 1. 测试范围定义

### 1.1 测试对象

| 模块 | Agent/功能 | API 前缀 | 说明 |
|------|-----------|----------|------|
| **Agent配置** | master | `/api/agents/master` | 主控 Agent |
| | character_designer | `/api/agents/character_designer` | 人物设计师 |
| | plot_writer | `/api/agents/plot_writer` | 剧情撰写员 |
| | proofreader | `/api/agents/proofreader` | 资深校对 |
| **内容管理** | 人物卡 | `/api/content/characters/*` | 人物卡 CRUD |
| | 章节 | `/api/content/chapters/*` | 章节管理 |
| | 暗线 | `/api/content/plotlines/*` | 暗线管理 |
| | 搜索 | `/api/content/search` | 全局搜索 |
| | AI优化 | `/api/content/characters/optimize` | AI内容优化 |
| **记忆管理** | 实体 | `/api/memory/entities/*` | 实体管理 |
| | 关系 | `/api/memory/relations/*` | 关系管理 |
| | 同步 | `/api/memory/sync` | 记忆同步 |
| | 统计 | `/api/memory/stats` | 记忆统计 |

### 1.2 测试前置条件

- [ ] OpenRouter 供应商已配置，模型 ID: `owl-alpha`
- [ ] API 密钥已设置且有效
- [ ] 后端服务已启动 (`http://localhost:8000`)
- [ ] 前端页面可访问 (`http://localhost:8000`)
- [ ] 测试环境数据已备份

### 1.3 测试环境信息

```yaml
模型供应商:
  名称: OpenRouter
  标识: openrouter
  协议: OpenAI 兼容 (Chat Completions)
  Base URL: https://openrouter.ai/api/v1
  模型: owl-alpha

后端服务:
  地址: http://localhost:8000
  API 前缀: /api
```

---

## 2. 测试用例设计

### 2.1 Agent 配置模块

#### TC-AGENT-001: 获取所有 Agent 配置
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/agents/` |
| **前置条件** | 服务正常启动 |
| **测试步骤** | 1. 发送 GET 请求到 `/api/agents/` |
| **预期结果** | 返回包含 master, character_designer, plot_writer, proofreader 的配置列表 |
| **验证点** | - 返回状态码 200<br>- 包含 4 个 Agent 配置<br>- 每个配置包含 model, temperature, enabled 字段 |
| **使用模型** | owl-alpha |

#### TC-AGENT-002: 更新 Agent 模型配置
| 属性 | 内容 |
|------|------|
| **接口** | `PUT /api/agents/{name}` |
| **前置条件** | Agent 配置存在 |
| **测试步骤** | 1. 发送 PUT 请求更新 plot_writer 的 model 为 `owl-alpha`<br>2. 验证更新成功 |
| **预期结果** | 返回更新后的配置，model 字段为 `owl-alpha` |
| **验证点** | - 返回状态码 200<br>- model 字段已更新 |
| **使用模型** | owl-alpha |

#### TC-AGENT-003: 启用/禁用 Agent
| 属性 | 内容 |
|------|------|
| **接口** | `PUT /api/agents/{name}/toggle` |
| **前置条件** | Agent 配置存在 |
| **测试步骤** | 1. 发送 PUT 请求禁用 proofreader<br>2. 验证禁用成功<br>3. 重新启用 |
| **预期结果** | proofreader 状态切换 |
| **验证点** | - 返回 enabled=false<br>- 再次请求返回 enabled=true |
| **使用模型** | owl-alpha |

#### TC-AGENT-004: 获取 Agent 运行状态
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/agents/{name}/status` |
| **前置条件** | Agent 配置存在 |
| **测试步骤** | 1. 发送 GET 请求获取 master 状态 |
| **预期结果** | 返回 Agent 当前状态信息 |
| **验证点** | - 返回 enabled, model, temperature, status 字段 |
| **使用模型** | owl-alpha |

---

### 2.2 内容管理模块

#### TC-CONTENT-001: 获取人物卡列表
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/content/characters` |
| **前置条件** | 存在人物卡数据 |
| **测试步骤** | 1. 发送 GET 请求<br>2. 验证返回数据格式 |
| **预期结果** | 返回扁平化的人物卡列表 |
| **验证点** | - 返回数组<br>- 每个元素包含 name, tier 字段 |
| **使用模型** | owl-alpha (通过 AI 优化功能) |

#### TC-CONTENT-002: 创建人物卡
| 属性 | 内容 |
|------|------|
| **接口** | `POST /api/content/characters` |
| **前置条件** | 无 |
| **测试步骤** | 1. 发送 POST 请求创建测试人物<br>2. 验证创建成功 |
| **预期结果** | 人物卡创建成功 |
| **验证点** | - 返回 status: "created"<br>- 人物名称正确 |
| **使用模型** | owl-alpha |

#### TC-CONTENT-003: 获取单个人物卡详情
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/content/characters/{name}` |
| **前置条件** | 人物卡已存在 |
| **测试步骤** | 1. 获取创建的人物卡详情 |
| **预期结果** | 返回完整的人物卡信息 |
| **验证点** | - 返回所有字段<br>- 包含 tier, name, role 等 |
| **使用模型** | owl-alpha |

#### TC-CONTENT-004: 更新人物卡
| 属性 | 内容 |
|------|------|
| **接口** | `PUT /api/content/characters/{name}` |
| **前置条件** | 人物卡已存在 |
| **测试步骤** | 1. 更新人物的性格描述<br>2. 验证更新成功 |
| **预期结果** | 人物卡更新成功 |
| **验证点** | - 返回 status: "updated"<br>- 数据已保存 |
| **使用模型** | owl-alpha |

#### TC-CONTENT-005: 删除人物卡
| 属性 | 内容 |
|------|------|
| **接口** | `DELETE /api/content/characters/{name}` |
| **前置条件** | 人物卡已存在 |
| **测试步骤** | 1. 删除测试人物<br>2. 验证删除成功 |
| **预期结果** | 人物卡删除成功 |
| **验证点** | - 返回 status: "deleted"<br>- 再次查询返回 404 |
| **使用模型** | owl-alpha |

#### TC-CONTENT-006: AI 优化人物内容
| 属性 | 内容 |
|------|------|
| **接口** | `POST /api/content/characters/optimize` |
| **前置条件** | OpenRouter 模型已配置 |
| **测试步骤** | 1. 发送优化请求，字段为 `brief`<br>2. 验证优化结果 |
| **预期结果** | 返回优化后的内容 |
| **验证点** | - 返回 optimized_value 字段<br>- 内容已优化<br>- 通过 owl-alpha 模型生成 |
| **使用模型** | owl-alpha |

**优化请求示例**:
```json
{
  "field": "brief",
  "current_value": "一个普通的商人",
  "character_name": "测试人物",
  "context": {
    "role": "商人",
    "personality": "精明、狡猾"
  }
}
```

#### TC-CONTENT-007: 获取章节列表
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/content/chapters` |
| **前置条件** | 存在章节数据 |
| **测试步骤** | 1. 发送 GET 请求<br>2. 验证返回数据 |
| **预期结果** | 返回章节列表（含摘要） |
| **验证点** | - 返回数组<br>- 每个章节包含 chapter_id, title, summary |
| **使用模型** | owl-alpha |

#### TC-CONTENT-008: 获取章节详情
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/content/chapters/{chapter_id}` |
| **前置条件** | 章节已存在 |
| **测试步骤** | 1. 获取第1章详情 |
| **预期结果** | 返回完整章节内容 |
| **验证点** | - 包含 content, title, summary<br>- 内容完整 |
| **使用模型** | owl-alpha |

#### TC-CONTENT-009: 创建暗线
| 属性 | 内容 |
|------|------|
| **接口** | `POST /api/content/plotlines` |
| **前置条件** | 无 |
| **测试步骤** | 1. 创建测试暗线<br>2. 验证创建成功 |
| **预期结果** | 暗线创建成功 |
| **验证点** | - 返回包含 id<br>- status: 隐式成功 |
| **使用模型** | owl-alpha |

#### TC-CONTENT-010: 全局搜索
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/content/search?q={keyword}` |
| **前置条件** | 存在数据 |
| **测试步骤** | 1. 搜索关键词<br>2. 验证搜索结果 |
| **预期结果** | 返回匹配的搜索结果 |
| **验证点** | - 返回 results 数组<br>- 包含 type, id, title, snippet |
| **使用模型** | owl-alpha |

---

### 2.3 记忆管理模块

#### TC-MEMORY-001: 获取实体列表
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/memory/entities` |
| **前置条件** | 图谱已初始化 |
| **测试步骤** | 1. 发送 GET 请求<br>2. 验证返回数据 |
| **预期结果** | 返回实体列表（分页） |
| **验证点** | - 返回 total, entities 字段<br>- 支持分页参数 |
| **使用模型** | owl-alpha |

#### TC-MEMORY-002: 获取实体详情
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/memory/entities/{entity_id}` |
| **前置条件** | 实体已存在 |
| **测试步骤** | 1. 获取实体详情<br>2. 验证关联关系 |
| **预期结果** | 返回实体及关联关系 |
| **验证点** | - 包含 entity 和 relations |
| **使用模型** | owl-alpha |

#### TC-MEMORY-003: 更新实体
| 属性 | 内容 |
|------|------|
| **接口** | `PUT /api/memory/entities/{entity_id}` |
| **前置条件** | 实体已存在 |
| **测试步骤** | 1. 更新实体属性<br>2. 验证更新成功 |
| **预期结果** | 实体更新成功 |
| **验证点** | - 返回 status: "updated"<br>- 数据已保存 |
| **使用模型** | owl-alpha |

#### TC-MEMORY-004: 删除实体
| 属性 | 内容 |
|------|------|
| **接口** | `DELETE /api/memory/entities/{entity_id}` |
| **前置条件** | 实体已存在 |
| **测试步骤** | 1. 删除实体<br>2. 验证删除成功 |
| **预期结果** | 实体删除成功 |
| **验证点** | - 返回 status: "deleted"<br>- 再次查询返回 404 |
| **使用模型** | owl-alpha |

#### TC-MEMORY-005: 创建关系
| 属性 | 内容 |
|------|------|
| **接口** | `POST /api/memory/relations` |
| **前置条件** | 两个实体已存在 |
| **测试步骤** | 1. 创建人物间关系<br>2. 验证创建成功 |
| **预期结果** | 关系创建成功 |
| **验证点** | - 返回 source, target, type |
| **使用模型** | owl-alpha |

#### TC-MEMORY-006: 获取关系列表
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/memory/relations` |
| **前置条件** | 存在关系数据 |
| **测试步骤** | 1. 获取关系列表<br>2. 验证数据格式 |
| **预期结果** | 返回关系列表 |
| **验证点** | - 返回 total, relations |
| **使用模型** | owl-alpha |

#### TC-MEMORY-007: 删除关系
| 属性 | 内容 |
|------|------|
| **接口** | `DELETE /api/memory/relations?source={}&target={}` |
| **前置条件** | 关系已存在 |
| **测试步骤** | 1. 删除关系<br>2. 验证删除成功 |
| **预期结果** | 关系删除成功 |
| **验证点** | - 返回 status: "deleted" |
| **使用模型** | owl-alpha |

#### TC-MEMORY-008: 获取人物关系网络
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/memory/network/{name}?depth=2` |
| **前置条件** | 人物实体已存在 |
| **测试步骤** | 1. 获取人物关系网络<br>2. 验证可视化数据 |
| **预期结果** | 返回人物网络图数据 |
| **验证点** | - 返回 nodes 和 edges<br>- 支持 depth 参数 |
| **使用模型** | owl-alpha |

#### TC-MEMORY-009: 获取未回收伏笔
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/memory/foreshadow` |
| **前置条件** | 图谱已初始化 |
| **测试步骤** | 1. 获取伏笔列表<br>2. 验证数据 |
| **预期结果** | 返回未回收伏笔 |
| **验证点** | - 返回 unresolved 数组 |
| **使用模型** | owl-alpha |

#### TC-MEMORY-010: 获取记忆统计
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/memory/stats` |
| **前置条件** | 图谱已初始化 |
| **测试步骤** | 1. 获取统计信息<br>2. 验证数据 |
| **预期结果** | 返回统计信息 |
| **验证点** | - 包含实体数量、关系数量等 |
| **使用模型** | owl-alpha |

#### TC-MEMORY-011: 搜索记忆内容
| 属性 | 内容 |
|------|------|
| **接口** | `GET /api/memory/search?q={keyword}` |
| **前置条件** | 图谱已初始化 |
| **测试步骤** | 1. 搜索关键词<br>2. 验证搜索结果 |
| **预期结果** | 返回搜索结果 |
| **验证点** | - 返回 results 数组 |
| **使用模型** | owl-alpha |

#### TC-MEMORY-012: 手动触发记忆同步
| 属性 | 内容 |
|------|------|
| **接口** | `POST /api/memory/sync` |
| **前置条件** | 同步模块可用 |
| **测试步骤** | 1. 触发同步<br>2. 验证同步结果 |
| **预期结果** | 同步成功完成 |
| **验证点** | - 返回 status: "synced" |
| **使用模型** | owl-alpha |

#### TC-MEMORY-013: 从工作空间初始化图谱
| 属性 | 内容 |
|------|------|
| **接口** | `POST /api/memory/init` |
| **前置条件** | 人物卡数据存在 |
| **测试步骤** | 1. 触发初始化<br>2. 验证导入数量 |
| **预期结果** | 从人物卡导入到图谱 |
| **验证点** | - 返回 imported 数量 |
| **使用模型** | owl-alpha |

---

## 3. 测试执行流程

### 3.1 执行顺序

```
阶段1: 基础设施验证 (5分钟)
├── TC-SETUP-001: 服务健康检查
├── TC-SETUP-002: 模型配置验证
└── TC-SETUP-003: 数据备份

阶段2: Agent 配置测试 (10分钟)
├── TC-AGENT-001: 获取所有配置
├── TC-AGENT-002: 更新模型配置
├── TC-AGENT-003: 启用/禁用
└── TC-AGENT-004: 获取状态

阶段3: 内容管理测试 (20分钟)
├── TC-CONTENT-001 ~ 005: 人物卡 CRUD
├── TC-CONTENT-006: AI 优化功能 ⭐
├── TC-CONTENT-007 ~ 008: 章节管理
├── TC-CONTENT-009: 暗线管理
└── TC-CONTENT-010: 全局搜索

阶段4: 记忆管理测试 (15分钟)
├── TC-MEMORY-001 ~ 004: 实体管理
├── TC-MEMORY-005 ~ 007: 关系管理
├── TC-MEMORY-008: 关系网络
├── TC-MEMORY-009 ~ 011: 查询功能
└── TC-MEMORY-012 ~ 013: 同步功能

阶段5: 压力测试 (5分钟)
└── 并发请求测试
```

### 3.2 测试命令示例

```bash
# 1. 健康检查
curl -X GET http://localhost:8000/api/health

# 2. 获取 Agent 列表
curl -X GET http://localhost:8000/api/agents/

# 3. 更新 Agent 模型
curl -X PUT http://localhost:8000/api/agents/master \
  -H "Content-Type: application/json" \
  -d '{"model": "owl-alpha"}'

# 4. 创建测试人物
curl -X POST http://localhost:8000/api/content/characters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试人物",
    "tier": "b_tier",
    "role": "商人",
    "brief": "一个普通的商人"
  }'

# 5. AI 优化内容
curl -X POST http://localhost:8000/api/content/characters/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "field": "brief",
    "current_value": "一个普通的商人",
    "character_name": "测试人物"
  }'

# 6. 获取实体列表
curl -X GET http://localhost:8000/api/memory/entities

# 7. 触发记忆同步
curl -X POST http://localhost:8000/api/memory/sync
```

---

## 4. 测试结果记录模板

### 4.1 测试执行记录

| 项目 | 内容 |
|------|------|
| **测试日期** | 2026-06-04 |
| **测试人员** | |
| **测试模型** | OpenRouter - owl-alpha |
| **开始时间** | |
| **结束时间** | |
| **总耗时** | |

### 4.2 测试结果汇总

| 用例编号 | 用例名称 | 执行结果 | 实际耗时 | 问题编号 | 备注 |
|----------|----------|----------|----------|----------|------|
| TC-AGENT-001 | 获取所有配置 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-AGENT-002 | 更新模型配置 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-AGENT-003 | 启用/禁用 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-AGENT-004 | 获取状态 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-CONTENT-001 | 获取人物列表 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-CONTENT-002 | 创建人物 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-CONTENT-003 | 获取详情 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-CONTENT-004 | 更新人物 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-CONTENT-005 | 删除人物 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-CONTENT-006 | AI优化内容 ⭐ | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-CONTENT-007 | 获取章节列表 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-CONTENT-008 | 获取章节详情 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-CONTENT-009 | 创建暗线 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-CONTENT-010 | 全局搜索 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-001 | 获取实体列表 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-002 | 获取实体详情 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-003 | 更新实体 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-004 | 删除实体 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-005 | 创建关系 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-006 | 获取关系列表 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-007 | 删除关系 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-008 | 关系网络 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-009 | 伏笔追踪 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-010 | 记忆统计 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-011 | 搜索记忆 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-012 | 同步记忆 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |
| TC-MEMORY-013 | 初始化图谱 | ⬜ 通过 ⬜ 失败 ⬜ 阻塞 | | | |

### 4.3 详细结果记录

#### 用例编号: TC-CONTENT-006 (AI 优化功能 - 核心测试)

| 属性 | 内容 |
|------|------|
| **执行时间** | |
| **请求 Payload** | ```json<br>{<br>  "field": "brief",<br>  "current_value": "一个普通的商人",<br>  "character_name": "测试人物",<br>  "context": {...}<br>}<br>``` |
| **预期输出** | 优化后的文本，内容更加生动具体 |
| **实际输出** | |
| **响应时间** | ms |
| **HTTP 状态码** | |
| **结果判定** | ⬜ 通过 ⬜ 失败 |
| **问题描述** | |

### 4.4 问题记录

| 问题编号 | 用例编号 | 严重级别 | 问题描述 | 发现时间 | 状态 | 修复记录 |
|----------|----------|----------|----------|----------|------|----------|
| | | ⬜ 致命 ⬜ 严重 ⬜ 一般 ⬜ 建议 | | | ⬜ 待解决 ⬜ 已解决 ⬜ 延期 | |

---

## 5. 异常处理机制

### 5.1 问题等级划分

| 等级 | 定义 | 处理方式 | 响应时间 |
|------|------|----------|----------|
| **P0 - 致命** | 系统崩溃、API 完全不可用、数据丢失 | 立即停止测试，记录详细日志 | 即时 |
| **P1 - 严重** | 核心功能不可用、模型调用失败 | 记录问题，分析原因 | 2小时内 |
| **P2 - 一般** | 功能部分异常、响应时间过长 | 记录问题，继续测试 | 24小时内 |
| **P3 - 建议** | UI 问题、文档问题、性能优化建议 | 记录在案 | 下一版本 |

### 5.2 问题报告流程

```
发现问题
    ↓
判定等级 (P0/P1/P2/P3)
    ↓
记录问题详情
    ├── 问题编号
    ├── 用例编号
    ├── 严重级别
    ├── 问题描述
    ├── 复现步骤
    ├── 预期 vs 实际
    └── 相关日志/截图
    ↓
报告给负责人
    ↓
修复验证
    ↓
关闭问题
```

### 5.3 常见问题及处理

| 问题类型 | 可能原因 | 排查步骤 | 解决方案 |
|----------|----------|----------|----------|
| API 超时 | 网络延迟、模型响应慢 | 检查网络、查看日志 | 增加超时配置 |
| 认证失败 | API Key 无效/过期 | 验证密钥配置 | 更新 API Key |
| 模型不支持 | 模型 ID 错误 | 核对模型列表 | 使用正确的模型 ID |
| 数据格式错误 | 请求/响应格式不匹配 | 检查 schema | 调整数据格式 |
| 服务不可用 | 后端未启动 | 检查服务状态 | 重启后端服务 |

### 5.4 报告模板

```markdown
## 问题报告

**问题编号**: ISSUE-001
**报告时间**: 2026-06-04 HH:MM
**报告人**:
**用例编号**: TC-XXXX
**严重级别**: P1 - 严重

### 问题描述
[详细描述问题]

### 复现步骤
1. [步骤1]
2. [步骤2]
3. [步骤3]

### 预期行为
[期望的结果]

### 实际行为
[实际发生的情况]

### 相关日志
```
[粘贴相关日志]
```

### 截图/附件
[如有]

### 根因分析
[分析问题原因]

### 修复建议
[建议的解决方案]
```

---

## 6. 测试通过标准

### 6.1 成功标准

| 模块 | 通过条件 | 目标通过率 |
|------|----------|------------|
| **Agent 配置** | 所有用例通过 | 100% |
| **内容管理** | 所有用例通过，AI 优化正常工作 | 100% |
| **记忆管理** | 所有用例通过 | 100% |
| **整体** | 无 P0/P1 问题 | - |

### 6.2 验收检查清单

- [ ] 所有 Agent 可正常配置 owl-alpha 模型
- [ ] 人物卡 CRUD 功能正常
- [ ] AI 优化功能通过 owl-alpha 模型返回正确结果
- [ ] 章节管理功能正常
- [ ] 暗线管理功能正常
- [ ] 全局搜索功能正常
- [ ] 实体管理功能正常
- [ ] 关系管理功能正常
- [ ] 记忆同步功能正常
- [ ] 无致命或严重问题遗留

---

## 7. 附录

### 7.1 API 端点汇总

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | /api/agents/ | 获取所有 Agent 配置 |
| GET | /api/agents/{name} | 获取单个 Agent |
| PUT | /api/agents/{name} | 更新 Agent |
| PUT | /api/agents/{name}/toggle | 启用/禁用 |
| GET | /api/agents/{name}/status | 获取状态 |
| GET | /api/content/characters | 获取人物列表 |
| POST | /api/content/characters | 创建人物 |
| GET | /api/content/characters/{name} | 获取人物详情 |
| PUT | /api/content/characters/{name} | 更新人物 |
| DELETE | /api/content/characters/{name} | 删除人物 |
| POST | /api/content/characters/optimize | AI 优化 |
| GET | /api/content/chapters | 获取章节列表 |
| GET | /api/content/chapters/{id} | 获取章节详情 |
| GET | /api/content/plotlines | 获取暗线列表 |
| POST | /api/content/plotlines | 创建暗线 |
| GET | /api/content/search?q= | 全局搜索 |
| GET | /api/memory/entities | 获取实体列表 |
| GET | /api/memory/entities/{id} | 获取实体详情 |
| PUT | /api/memory/entities/{id} | 更新实体 |
| DELETE | /api/memory/entities/{id} | 删除实体 |
| GET | /api/memory/relations | 获取关系列表 |
| POST | /api/memory/relations | 创建关系 |
| DELETE | /api/memory/relations | 删除关系 |
| GET | /api/memory/network/{name} | 获取关系网络 |
| GET | /api/memory/foreshadow | 获取伏笔 |
| GET | /api/memory/stats | 记忆统计 |
| GET | /api/memory/search?q= | 搜索记忆 |
| POST | /api/memory/sync | 同步记忆 |
| POST | /api/memory/init | 初始化图谱 |

### 7.2 参考文档

- OpenRouter API 文档: https://openrouter.ai/docs
- 模型 ID: owl-alpha
- 支持的协议: OpenAI 兼容

---

**文档版本**: 1.0
**创建日期**: 2026-06-04
**最后更新**: 2026-06-04
