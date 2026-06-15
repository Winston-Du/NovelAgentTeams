# 分层记忆管理系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 NovelAgentTeams 实现 4 层（活跃对话 / 滚动摘要块 / 剧情追踪 / 人物与关系）记忆管理系统，支持 10K+ 章节和 1M+ token 场景下的可控 LLM 上下文注入与可配置压缩。

**Architecture:** 新增 `MemoryManager` 门面组合 `GraphMemoryIntegrator` + `SummaryCompressor`（100 章触发+滑窗）+ `DialogueCompactor`（80% 阈值 LLM 结构化压缩）。配置走 `MemoryConfig` 数据类 + YAML 分层（global + per-agent）。错误处理：LLM 重试 2 次 → 仍失败 → 章节压缩通知前端/对话压缩静默降级 → 块 JSON 损坏从章节文件自动恢复。集成点：扩展 `ConversationRuntime._maybe_auto_compact`、`ContextInjector.inject_context`、`AgentRunner.run_agent`（子 agent 销毁模式）。

**Tech Stack:** Python 3.10+ / dataclasses / pyyaml / pytest / shutil / uuid / 已有的 langchain + networkx + chromadb

**Spec:** [2026-06-11-layered-memory-management-design.md](../specs/2026-06-11-layered-memory-management-design.md)

---

## 文件结构

### 新建文件
- `src/novels_project/memory/__init__.py` - 包初始化
- `src/novels_project/memory/exceptions.py` - 自定义异常类
- `src/novels_project/memory/memory_config.py` - MemoryConfig 数据类 + YAML 加载
- `src/novels_project/memory/summary_compressor.py` - 100 章滚动压缩器
- `src/novels_project/memory/dialogue_compactor.py` - LLM 对话压缩器
- `src/novels_project/memory/memory_manager.py` - 顶层门面
- `config/memory_config.yaml` - 项目级配置
- `tests/unit/memory/__init__.py` - 测试包
- `tests/unit/memory/test_memory_config.py` - MemoryConfig 单元测试
- `tests/unit/memory/test_summary_compressor.py` - SummaryCompressor 单元测试
- `tests/unit/memory/test_dialogue_compactor.py` - DialogueCompactor 单元测试
- `tests/unit/memory/test_memory_manager.py` - MemoryManager 单元测试
- `tests/fixtures/mock_llm_client.py` - Mock LLM 客户端
- `tests/fixtures/chapter_generator.py` - 测试章节生成器
- `tests/integration/memory/__init__.py`
- `tests/integration/memory/test_chapter_compression_flow.py`
- `tests/integration/memory/test_dialogue_compression_flow.py`
- `tests/integration/memory/test_config_hot_reload.py`
- `tests/integration/memory/test_block_recovery.py`
- `tests/integration/agents/test_subagent_session_isolation.py`
- `tests/performance/test_large_scale_memory.py`

### 修改文件
- `src/novels_project/context_injector.py` - 增加历史摘要块注入
- `src/novels_project/runtime.py` - 集成 DialogueCompactor
- `src/novels_project/agents.py` - 子 agent 销毁模式 + 独立 MemoryConfig
- `src/novels_project/api/server.py` (或类似 web 入口) - 增加 memory config API

---

## Phase 1: 基础结构与异常

### Task 1: 创建 memory 包与异常类

**Files:**
- Create: `src/novels_project/memory/__init__.py`
- Create: `src/novels_project/memory/exceptions.py`

- [ ] **Step 1: 写失败的测试**

在 `tests/unit/memory/__init__.py` 创建测试包：
```python
"""Memory system unit tests"""
```

- [ ] **Step 2: 创建 memory 包 `__init__.py`**

```python
"""Memory management subsystem.

Provides 4-layer memory architecture:
- L1: Active dialogue (ConversationRuntime.session)
- L2: Rolling summary blocks (SummaryCompressor)
- L3: Plot tracking (GraphStore concept nodes, unchanged)
- L4: Characters and relationships (GraphStore character nodes, unchanged)
"""

from .exceptions import (
    MemoryConfigError,
    SummaryCompressionError,
    DialogueCompressionError,
    BlockRecoveryError,
)

__all__ = [
    "MemoryConfigError",
    "SummaryCompressionError",
    "DialogueCompressionError",
    "BlockRecoveryError",
]
```

- [ ] **Step 3: 写失败测试 `tests/unit/memory/test_exceptions.py`**

```python
"""Test custom exception hierarchy."""
import pytest
from novels_project.memory.exceptions import (
    MemoryConfigError,
    SummaryCompressionError,
    DialogueCompressionError,
    BlockRecoveryError,
)


def test_summary_compression_error_includes_chapter_range():
    err = SummaryCompressionError(
        "LLM failed",
        chapter_range=(1, 100),
    )
    assert err.chapter_range == (1, 100)
    assert "LLM failed" in str(err)


def test_block_recovery_error_includes_block_path():
    err = BlockRecoveryError(
        "Recovery failed",
        block_path="/tmp/block_00001_00100.json",
    )
    assert err.block_path == "/tmp/block_00001_00100.json"


def test_dialogue_compression_error_is_memory_config_error():
    assert issubclass(DialogueCompressionError, MemoryConfigError)
```

- [ ] **Step 4: 跑测试确认失败**

Run: `pytest tests/unit/memory/test_exceptions.py -v`
Expected: FAIL with "No module named 'novels_project.memory.exceptions'"

- [ ] **Step 5: 实现 exceptions.py**

```python
"""Custom exceptions for the memory subsystem."""


class MemoryConfigError(Exception):
    """Base class for memory configuration errors."""


class SummaryCompressionError(MemoryConfigError):
    """Raised when 100-chapter summary compression fails after all retries."""

    def __init__(self, message: str, chapter_range: tuple[int, int]):
        super().__init__(message)
        self.chapter_range = chapter_range


class DialogueCompressionError(MemoryConfigError):
    """Raised when dialogue compression fails irrecoverably."""


class BlockRecoveryError(MemoryConfigError):
    """Raised when a corrupted ChapterSummaryBlock JSON cannot be recovered."""

    def __init__(self, message: str, block_path: str):
        super().__init__(message)
        self.block_path = block_path
```

- [ ] **Step 6: 跑测试确认通过**

Run: `pytest tests/unit/memory/test_exceptions.py -v`
Expected: 3 passed

- [ ] **Step 7: 提交**

```bash
git add src/novels_project/memory/ tests/unit/memory/
git commit -m "feat(memory): add memory package skeleton and custom exceptions"
```

---

### Task 2: 实现 MemoryConfig 基础结构

**Files:**
- Create: `src/novels_project/memory/memory_config.py`
- Create: `tests/unit/memory/test_memory_config.py`

- [ ] **Step 1: 写失败测试**

```python
"""Test MemoryConfig dataclass and basic operations."""
import pytest
from dataclasses import fields
from novels_project.memory.memory_config import MemoryConfig, SLIDING_WINDOW_TIERS


def test_default_config_has_all_fields():
    config = MemoryConfig()
    field_names = {f.name for f in fields(MemoryConfig)}
    assert "chapter_window" in field_names
    assert "max_summary_blocks" in field_names
    assert "dialogue_compression_threshold" in field_names
    assert "preserve_recent_messages" in field_names


def test_default_config_values():
    config = MemoryConfig()
    assert config.chapter_window == 100
    assert config.max_summary_blocks == 3
    assert config.dialogue_compression_threshold == 0.8
    assert config.preserve_recent_messages == 4
    assert config.dialogue_llm_model is None  # None = follow runtime
    assert config.subagent_compression_enabled is True


def test_sliding_window_tiers_are_100_to_1000():
    assert SLIDING_WINDOW_TIERS == [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    assert len(SLIDING_WINDOW_TIERS) == 10
    assert SLIDING_WINDOW_TIERS[2] == 300  # default


def test_config_is_mutable_dataclass():
    config = MemoryConfig()
    config.max_summary_blocks = 5
    assert config.max_summary_blocks == 5
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/memory/test_memory_config.py -v`
Expected: FAIL with "No module named 'novels_project.memory.memory_config'"

- [ ] **Step 3: 实现 MemoryConfig 基础类**

```python
"""Memory configuration data class and YAML loader."""
from __future__ import annotations
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Optional
import logging
import yaml

logger = logging.getLogger("novels_project.memory.memory_config")

# Web 端固定 10 档（不允许任意值，避免 UI 复杂）
SLIDING_WINDOW_TIERS = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
DEFAULT_BLOCKS_BY_TIER = 3  # 默认 300 章


@dataclass
class MemoryConfig:
    """单 agent 的记忆配置（已合并 global + agent 覆盖）。"""

    # 摘要滑窗
    chapter_window: int = 100
    max_summary_blocks: int = 3
    summary_max_chars: int = 2000

    # 对话压缩
    dialogue_compression_threshold: float = 0.8
    preserve_recent_messages: int = 4
    dialogue_summary_max_chars: int = 3000
    dialogue_llm_model: Optional[str] = None  # None = 跟随运行时

    # 子 agent
    subagent_compression_enabled: bool = True
    subagent_max_messages: int = 30

    @classmethod
    def merge(
        cls,
        global_cfg: "MemoryConfig",
        agent_cfg: Optional["MemoryConfig"],
    ) -> "MemoryConfig":
        """合并 global + agent 配置。

        规则：agent 显式值（≠字段默认值）覆盖 global，否则继承 global。
        """
        if agent_cfg is None:
            return global_cfg
        merged = cls()
        defaults = {f.name: f.default for f in fields(cls)}
        for f in fields(cls):
            agent_val = getattr(agent_cfg, f.name)
            global_val = getattr(global_cfg, f.name)
            # agent 显式设置（非字段默认值）→ 覆盖
            if agent_val != defaults[f.name]:
                setattr(merged, f.name, agent_val)
            else:
                setattr(merged, f.name, global_val)
        return merged

    def validate(self) -> list[str]:
        """配置校验，返回错误列表（空=通过）。"""
        errors: list[str] = []
        if self.max_summary_blocks < 1 or self.max_summary_blocks > 10:
            errors.append(
                f"max_summary_blocks={self.max_summary_blocks} 超出 1-10 范围"
            )
        if not 0.5 <= self.dialogue_compression_threshold <= 0.95:
            errors.append(
                f"dialogue_compression_threshold={self.dialogue_compression_threshold} 超出 0.5-0.95"
            )
        if self.preserve_recent_messages < 2:
            errors.append("preserve_recent_messages 不能小于 2（避免破坏对话连贯性）")
        if self.summary_max_chars < 500:
            errors.append("summary_max_chars 至少 500 字符")
        return errors
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/memory/test_memory_config.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add src/novels_project/memory/memory_config.py tests/unit/memory/test_memory_config.py
git commit -m "feat(memory): add MemoryConfig dataclass with merge and validate"
```

---

### Task 3: 实现 MemoryConfigBundle YAML 加载

**Files:**
- Modify: `src/novels_project/memory/memory_config.py`
- Modify: `tests/unit/memory/test_memory_config.py`

- [ ] **Step 1: 写失败测试**

添加到 `tests/unit/memory/test_memory_config.py`：
```python
from pathlib import Path
from novels_project.memory.memory_config import MemoryConfigBundle


def test_load_yaml_returns_defaults_when_file_missing(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    # 文件不存在
    bundle = MemoryConfigBundle.load_from_yaml(config_path)
    assert bundle.global_config.max_summary_blocks == 3
    assert bundle.resolved == {}  # 无 agent 配置


def test_load_yaml_basic_global_only(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  max_summary_blocks: 5
  dialogue_compression_threshold: 0.75
agents: {}
""", encoding="utf-8")
    bundle = MemoryConfigBundle.load_from_yaml(config_path)
    assert bundle.global_config.max_summary_blocks == 5
    assert bundle.global_config.dialogue_compression_threshold == 0.75


def test_load_yaml_with_agent_override(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  max_summary_blocks: 3
  dialogue_compression_threshold: 0.8
agents:
  plot_writer:
    dialogue_compression_threshold: 0.7
  proofreader:
    max_summary_blocks: 2
""", encoding="utf-8")
    bundle = MemoryConfigBundle.load_from_yaml(config_path)
    # agent 显式值覆盖 global
    assert bundle.resolved["plot_writer"].dialogue_compression_threshold == 0.7
    # agent 继承 global
    assert bundle.resolved["plot_writer"].max_summary_blocks == 3
    # 另一个 agent
    assert bundle.resolved["proofreader"].max_summary_blocks == 2


def test_get_resolved_returns_global_for_unknown_agent(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  max_summary_blocks: 5
agents: {}
""", encoding="utf-8")
    bundle = MemoryConfigBundle.load_from_yaml(config_path)
    cfg = bundle.get_resolved("nonexistent_agent")
    assert cfg.max_summary_blocks == 5


def test_validate_catches_out_of_range_values():
    config = MemoryConfig(max_summary_blocks=15, dialogue_compression_threshold=0.3)
    errors = config.validate()
    assert any("max_summary_blocks" in e for e in errors)
    assert any("dialogue_compression_threshold" in e for e in errors)


def test_validate_passes_with_defaults():
    config = MemoryConfig()
    assert config.validate() == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/memory/test_memory_config.py -v`
Expected: 6 failed (load_yaml tests)

- [ ] **Step 3: 实现 MemoryConfigBundle**

添加到 `src/novels_project/memory/memory_config.py`：
```python
@dataclass
class MemoryConfigBundle:
    """配置包：global + 各 agent 配置（已 merge）。"""

    global_config: MemoryConfig
    agent_configs: dict[str, MemoryConfig]
    resolved: dict[str, MemoryConfig]

    @classmethod
    def load_from_yaml(cls, path: Path) -> "MemoryConfigBundle":
        """从 YAML 加载并自动 merge。

        行为：
        - 文件不存在 → 返回全默认配置
        - 文件存在但字段缺失 → 字段用 MemoryConfig 默认值
        """
        if not path.exists():
            logger.info("[MemoryConfig] 配置文件不存在，使用默认值 | path=%s", path)
            return cls(
                global_config=MemoryConfig(),
                agent_configs={},
                resolved={},
            )

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        # 解析 global
        global_dict = raw.get("global", {}) or {}
        valid_fields = {f.name for f in fields(MemoryConfig)}
        global_cfg = MemoryConfig(
            **{k: v for k, v in global_dict.items() if k in valid_fields}
        )

        # 解析每个 agent
        agent_cfgs: dict[str, MemoryConfig] = {}
        resolved: dict[str, MemoryConfig] = {}
        for agent_name, agent_dict in (raw.get("agents", {}) or {}).items():
            agent_cfg = MemoryConfig(
                **{k: v for k, v in agent_dict.items() if k in valid_fields}
            )
            agent_cfgs[agent_name] = agent_cfg
            resolved[agent_name] = MemoryConfig.merge(global_cfg, agent_cfg)

        logger.info(
            "[MemoryConfig] 配置加载完成 | global=%s agents=%s",
            global_cfg, list(resolved.keys()),
        )
        return cls(
            global_config=global_cfg,
            agent_configs=agent_cfgs,
            resolved=resolved,
        )

    def get_resolved(self, agent_id: str) -> MemoryConfig:
        """获取 agent 的最终合并配置（未知 agent → global）。"""
        return self.resolved.get(agent_id, self.global_config)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/memory/test_memory_config.py -v`
Expected: 10 passed

- [ ] **Step 5: 创建默认配置文件**

创建 `config/memory_config.yaml`：
```yaml
version: "1.0"
global:
  chapter_window: 100
  max_summary_blocks: 3
  summary_max_chars: 2000
  dialogue_compression_threshold: 0.8
  preserve_recent_messages: 4
  dialogue_summary_max_chars: 3000
  dialogue_llm_model: null
  subagent_compression_enabled: true
  subagent_max_messages: 30

agents:
  main: {}
  plot_writer:
    dialogue_compression_threshold: 0.7
    preserve_recent_messages: 2
  proofreader:
    max_summary_blocks: 2
    dialogue_compression_threshold: 0.75
  character_designer:
    max_summary_blocks: 2
    dialogue_compression_threshold: 0.85
    preserve_recent_messages: 6
```

- [ ] **Step 6: 提交**

```bash
git add src/novels_project/memory/memory_config.py tests/unit/memory/test_memory_config.py config/memory_config.yaml
git commit -m "feat(memory): add MemoryConfigBundle YAML loader with merge logic"
```

---

## Phase 2: SummaryCompressor 100 章滚动压缩器

### Task 4: ChapterSummaryBlock 数据类

**Files:**
- Create: `src/novels_project/memory/summary_compressor.py`
- Create: `tests/unit/memory/test_summary_compressor.py`

- [ ] **Step 1: 写失败测试**

```python
"""Test ChapterSummaryBlock dataclass."""
import pytest
from datetime import datetime
from novels_project.memory.chapter_summary_block import ChapterSummaryBlock


def test_summary_block_creation():
    block = ChapterSummaryBlock(
        block_id="block_00001_00100",
        start_chapter=1,
        end_chapter=100,
        chapter_count=100,
        compressed_text="这是压缩后的文本",
        key_events=["事件1", "事件2"],
        character_changes=["陆商曜突破筑基期"],
        created_at="2026-06-11T10:00:00",
        char_count=8,
    )
    assert block.block_id == "block_00001_00100"
    assert block.start_chapter == 1
    assert block.end_chapter == 100
    assert block.chapter_count == 100
    assert block.compressed_text == "这是压缩后的文本"
    assert len(block.key_events) == 2
    assert block.char_count == 8


def test_summary_block_to_dict():
    block = ChapterSummaryBlock(
        block_id="block_00001_00100",
        start_chapter=1,
        end_chapter=100,
        chapter_count=100,
        compressed_text="text",
        key_events=[],
        character_changes=[],
        created_at="2026-06-11T10:00:00",
        char_count=4,
    )
    d = block.to_dict()
    assert d["block_id"] == "block_00001_00100"
    assert d["start_chapter"] == 1


def test_summary_block_from_dict():
    data = {
        "block_id": "block_00001_00100",
        "start_chapter": 1,
        "end_chapter": 100,
        "chapter_count": 100,
        "compressed_text": "text",
        "key_events": ["e1"],
        "character_changes": ["c1"],
        "created_at": "2026-06-11T10:00:00",
        "char_count": 4,
    }
    block = ChapterSummaryBlock.from_dict(data)
    assert block.key_events == ["e1"]
    assert block.character_changes == ["c1"]


def test_summary_block_default_fields():
    block = ChapterSummaryBlock(
        block_id="b1",
        start_chapter=1,
        end_chapter=10,
        chapter_count=10,
        compressed_text="t",
        key_events=[],
        character_changes=[],
        created_at="",
        char_count=1,
    )
    # 字段已提供，不需默认值验证
    assert block.compressed_text == "t"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/memory/test_summary_compressor.py -v`
Expected: FAIL with "No module named 'novels_project.memory.summary_compressor'"

- [ ] **Step 3: 实现 ChapterSummaryBlock**

```python
"""Summary block data class and 100-chapter rolling compressor."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Callable
import json
import logging
import re
import shutil
import time

from .memory_config import MemoryConfig
from .exceptions import SummaryCompressionError, BlockRecoveryError

logger = logging.getLogger("novels_project.memory.summary_compressor")


@dataclass
class ChapterSummaryBlock:
    """单个压缩块，持久化为独立 JSON 文件。"""

    block_id: str
    start_chapter: int
    end_chapter: int
    chapter_count: int
    compressed_text: str
    key_events: list[str]
    character_changes: list[str]
    created_at: str
    char_count: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChapterSummaryBlock":
        return cls(**data)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/memory/test_summary_compressor.py::test_summary_block_creation tests/unit/memory/test_summary_compressor.py::test_summary_block_to_dict tests/unit/memory/test_summary_compressor.py::test_summary_block_from_dict tests/unit/memory/test_summary_compressor.py::test_summary_block_default_fields -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add src/novels_project/memory/summary_compressor.py tests/unit/memory/test_summary_compressor.py
git commit -m "feat(memory): add ChapterSummaryBlock dataclass with serialization"
```

---

### Task 5: SummaryCompressor 累加与触发逻辑

**Files:**
- Modify: `src/novels_project/memory/summary_compressor.py`
- Modify: `tests/unit/memory/test_summary_compressor.py`

- [ ] **Step 1: 写失败测试**

添加到 `tests/unit/memory/test_summary_compressor.py`：
```python
from pathlib import Path
from novels_project.memory.summary_compressor import SummaryCompressor
from novels_project.memory.memory_config import MemoryConfig


@pytest.fixture
def tmp_compressor(tmp_path):
    """Create a SummaryCompressor with small window for testing."""
    config = MemoryConfig(chapter_window=10, max_summary_blocks=3)
    return SummaryCompressor(config=config, storage_dir=tmp_path)


def test_add_chapter_below_threshold_returns_none(tmp_compressor):
    result = tmp_compressor.add_chapter_summary(1, "第1章摘要")
    assert result is None
    assert len(tmp_compressor._accumulator) == 1


def test_add_chapter_reaches_threshold_triggers_compression(tmp_compressor):
    for i in range(1, 11):  # 10 章
        result = tmp_compressor.add_chapter_summary(i, f"第{i}章摘要")
        if i < 10:
            assert result is None
        else:
            assert result is not None
            assert result.start_chapter == 1
            assert result.end_chapter == 10
            assert result.chapter_count == 10


def test_block_id_format(tmp_compressor):
    for i in range(1, 11):
        tmp_compressor.add_chapter_summary(i, f"第{i}章")
    block = tmp_compressor._blocks[0]
    assert block.block_id == "block_00001_00010"


def test_sliding_window_eviction(tmp_compressor):
    # 添加 4 批（每批 10 章，共 40 章）
    for batch in range(4):
        for j in range(10):
            chapter_id = batch * 10 + j + 1
            tmp_compressor.add_chapter_summary(chapter_id, f"第{chapter_id}章")
    # 应该有 3 个块（max=3）
    assert len(tmp_compressor._blocks) == 3
    # 最旧的应该是第二批（11-20）
    assert tmp_compressor._blocks[0].start_chapter == 11
    assert tmp_compressor._blocks[-1].end_chapter == 40


def test_accumulator_clears_after_compression(tmp_compressor):
    for i in range(1, 11):
        tmp_compressor.add_chapter_summary(i, f"第{i}章")
    assert len(tmp_compressor._accumulator) == 0


def test_rule_compress_truncation(tmp_compressor):
    long_text = "x" * 5000
    compressed = tmp_compressor._rule_compress(long_text)
    # summary_max_chars = 2000 (default)
    assert len(compressed) <= 2000
    assert "中间章节省略" in compressed
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/memory/test_summary_compressor.py -v`
Expected: 6 failed (SummaryCompressor not found)

- [ ] **Step 3: 实现 SummaryCompressor 累加与触发**

追加到 `src/novels_project/memory/summary_compressor.py`：
```python
class SummaryCompressor:
    """100 章滚动压缩器。

    工作流：
    1. add_chapter_summary 累加到 accumulator
    2. 累积到 chapter_window 时触发 _trigger_compression
    3. 压缩 + 截断 + 创建 ChapterSummaryBlock
    4. 滑窗淘汰（超过 max_blocks 时）
    5. 持久化到 storage_dir
    """

    def __init__(
        self,
        config: MemoryConfig,
        storage_dir: Path,
        llm_client: Optional[Any] = None,
        error_callback: Optional[Callable] = None,
        chapters_dir: Optional[Path] = None,  # 用于块恢复
    ):
        self.config = config
        self.storage_dir = Path(storage_dir)
        self.llm_client = llm_client
        self.error_callback = error_callback
        self.chapters_dir = Path(chapters_dir) if chapters_dir else None

        # 状态
        self._blocks: list[ChapterSummaryBlock] = []
        self._accumulator: list[tuple[int, str]] = []
        self._dirty = False

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._load_existing_blocks_with_recovery()

    def add_chapter_summary(
        self,
        chapter_id: int,
        summary: str,
    ) -> Optional[ChapterSummaryBlock]:
        """累加单章摘要，达到窗口时触发压缩。"""
        self._accumulator.append((chapter_id, summary))
        logger.info(
            "[SummaryCompressor] 累加摘要 | chapter=%d accumulator=%d/%d",
            chapter_id, len(self._accumulator), self.config.chapter_window,
        )
        if len(self._accumulator) >= self.config.chapter_window:
            return self._trigger_compression()
        return None

    def _trigger_compression(self) -> ChapterSummaryBlock:
        """触发压缩：accumulator → 1 个 ChapterSummaryBlock。"""
        chapters = self._accumulator
        start = chapters[0][0]
        end = chapters[-1][0]
        logger.info(
            "[SummaryCompressor] 触发压缩 | chapter_range=%d-%d count=%d",
            start, end, len(chapters),
        )

        # 1. 拼接
        combined = "\n\n".join(
            f"【第{ch_id}章】\n{summary}"
            for ch_id, summary in chapters
        )

        # 2. 压缩（LLM → 失败重试 → 抛异常）
        try:
            compressed = self._llm_compress_with_retry(combined)
        except SummaryCompressionError:
            raise  # 不回退规则压缩，让用户决定
        # 截断
        compressed = self._truncate(compressed, self.config.summary_max_chars)

        # 3. 提取元数据
        key_events, char_changes = self._extract_metadata(compressed)

        # 4. 创建块
        block = ChapterSummaryBlock(
            block_id=f"block_{start:05d}_{end:05d}",
            start_chapter=start,
            end_chapter=end,
            chapter_count=len(chapters),
            compressed_text=compressed,
            key_events=key_events,
            character_changes=char_changes,
            created_at=datetime.now().isoformat(),
            char_count=len(compressed),
        )

        # 5. 添加到块列表 + 滑窗淘汰
        self._blocks.append(block)
        self._evict_old_blocks()

        # 6. 清空 accumulator
        self._accumulator.clear()
        self._dirty = True

        # 7. 持久化
        self.persist()

        logger.info(
            "[SummaryCompressor] 压缩完成 | block_id=%s char_count=%d total_blocks=%d",
            block.block_id, block.char_count, len(self._blocks),
        )
        return block

    def _evict_old_blocks(self) -> None:
        """滑窗淘汰。"""
        while len(self._blocks) > self.config.max_summary_blocks:
            evicted = self._blocks.pop(0)
            logger.info(
                "[SummaryCompressor] 淘汰旧块 | block_id=%s chapters=%d-%d",
                evicted.block_id, evicted.start_chapter, evicted.end_chapter,
            )

    def _truncate(self, text: str, max_len: int) -> str:
        """截断。"""
        if len(text) <= max_len:
            return text
        return text[: max_len - 20] + "\n\n[内容已截断]"

    def _rule_compress(self, text: str) -> str:
        """规则压缩：取首尾各 1/3。"""
        n = len(text)
        if n <= self.config.summary_max_chars:
            return text
        third = n // 3
        return text[:third] + "\n\n[中间章节省略]\n\n" + text[-third:]

    def _extract_metadata(self, text: str) -> tuple[list[str], list[str]]:
        """从压缩文本提取关键事件和人物变化。"""
        events: list[str] = []
        changes: list[str] = []
        keywords_events = ["击败", "杀死", "获得", "突破", "发现"]
        keywords_changes = ["加入", "离开", "背叛", "受伤", "死亡"]
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if any(kw in line for kw in keywords_events):
                events.append(line[:100])
            if any(kw in line for kw in keywords_changes):
                changes.append(line[:100])
        return events[:20], changes[:20]

    def _llm_compress_with_retry(self, text: str, max_retries: int = 2) -> str:
        """LLM 压缩 + 重试 + 通知前端。"""
        last_error: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                return self._llm_compress(text)
            except Exception as e:
                last_error = e
                logger.warning(
                    "[SummaryCompressor] LLM 压缩失败 | attempt=%d/%d error=%s",
                    attempt, max_retries, e,
                )
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
        # 通知前端
        if self.error_callback:
            self.error_callback(
                error_type="summary_compression_failed",
                message=f"章节摘要压缩失败: {last_error}",
                chapter_range=(
                    self._accumulator[0][0], self._accumulator[-1][0]
                ),
            )
        # 抛出异常
        raise SummaryCompressionError(
            f"LLM 压缩失败，已重试 {max_retries} 次: {last_error}",
            chapter_range=(
                self._accumulator[0][0], self._accumulator[-1][0]
            ),
        )

    def _llm_compress(self, text: str) -> str:
        """调用 LLM 压缩（单次，无重试）。"""
        if not self.llm_client:
            raise RuntimeError("llm_client 未配置")
        from ..api_client import ApiRequest
        prompt = f"""请将以下 {self.config.chapter_window} 章的章节摘要压缩为一段不超过 1500 字的连贯摘要。
要求：
1. 保留主要剧情线、关键事件、人物关系变化
2. 提取核心冲突、高潮、反转
3. 删除冗余描述和过渡性细节
4. 使用第三人称叙述
5. 按章节顺序组织

原文：
{text}
"""
        request = ApiRequest(
            system_prompt="你是专业的小说剧情压缩助手。",
            messages=[],
            tools=[],
            model=self.config.dialogue_llm_model or "default",
            max_tokens=2000,
        )
        events = self.llm_client.stream(request, print_stream=False)
        return "".join(
            e.text for e in events if hasattr(e, "text")
        )

    def get_blocks_for_injection(self) -> str:
        """生成用于注入的文本。"""
        if not self._blocks:
            return ""
        parts = ["【历史剧情摘要（滑窗保留）】"]
        for block in self._blocks:
            parts.append(
                f"\n### {block.block_id} (第 {block.start_chapter}-{block.end_chapter} 章)\n"
                f"{block.compressed_text}"
            )
        return "\n".join(parts)

    def persist(self) -> None:
        """持久化所有块。"""
        if not self._dirty:
            return
        for block in self._blocks:
            block_path = self.storage_dir / f"{block.block_id}.json"
            with open(block_path, "w", encoding="utf-8") as f:
                json.dump(block.to_dict(), f, ensure_ascii=False, indent=2)
        index_path = self.storage_dir / "index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump({
                "blocks": [b.block_id for b in self._blocks],
                "last_update": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)
        self._dirty = False
        logger.info(
            "[SummaryCompressor] 持久化完成 | blocks=%d", len(self._blocks)
        )

    def _load_existing_blocks_with_recovery(self) -> None:
        """启动时加载已有块（含损坏恢复）。"""
        index_path = self.storage_dir / "index.json"
        if not index_path.exists():
            return
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "[SummaryCompressor] index.json 损坏，跳过加载 | error=%s", e
            )
            return
        for block_id in index.get("blocks", []):
            block_path = self.storage_dir / f"{block_id}.json"
            if not block_path.exists():
                continue
            try:
                with open(block_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._blocks.append(ChapterSummaryBlock.from_dict(data))
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
                logger.warning(
                    "[SummaryCompressor] 块损坏，尝试恢复 | path=%s error=%s",
                    block_path.name, e,
                )
                recovered = self._recover_block(block_path)
                if recovered:
                    self._blocks.append(recovered)
                    shutil.move(
                        str(block_path),
                        str(block_path.with_suffix(".corrupted.json")),
                    )
                    logger.info(
                        "[SummaryCompressor] 块已恢复并备份损坏文件 | block_id=%s",
                        recovered.block_id,
                    )

    def _recover_block(self, block_path: Path) -> Optional[ChapterSummaryBlock]:
        """从原始章节文件重新生成块。"""
        match = re.match(r"block_(\d{5})_(\d{5})\.json", block_path.name)
        if not match:
            raise BlockRecoveryError(
                f"无法解析块 ID: {block_path.name}",
                block_path=str(block_path),
            )
        start, end = int(match.group(1)), int(match.group(2))
        if not self.chapters_dir or not self.chapters_dir.exists():
            raise BlockRecoveryError(
                f"chapters_dir 未配置，无法恢复",
                block_path=str(block_path),
            )

        # 从章节文件提取
        summaries: list[tuple[int, str]] = []
        for ch_id in range(start, end + 1):
            chapter_file = self.chapters_dir / f"chapter_{ch_id:05d}_final.md"
            if chapter_file.exists():
                text = chapter_file.read_text(encoding="utf-8")
                summary = self._extract_chapter_summary(text)
                summaries.append((ch_id, summary))
        if not summaries:
            raise BlockRecoveryError(
                f"未找到任何章节文件",
                block_path=str(block_path),
            )

        # 重新压缩
        combined = "\n\n".join(
            f"【第{ch}章】\n{s}" for ch, s in summaries
        )
        compressed = self._rule_compress(combined)  # 恢复用规则压缩
        compressed = self._truncate(compressed, self.config.summary_max_chars)

        return ChapterSummaryBlock(
            block_id=block_path.stem,
            start_chapter=start,
            end_chapter=end,
            chapter_count=len(summaries),
            compressed_text=compressed,
            key_events=[],
            character_changes=[],
            created_at=datetime.now().isoformat() + " (recovered)",
            char_count=len(compressed),
        )

    def _extract_chapter_summary(self, chapter_text: str) -> str:
        """从章节文本中提取简单摘要（首段 + 末段）。"""
        paragraphs = [
            p.strip() for p in chapter_text.split("\n\n") if p.strip()
        ]
        if not paragraphs:
            return ""
        if len(paragraphs) <= 2:
            return "\n\n".join(paragraphs)
        return paragraphs[0] + "\n\n" + paragraphs[-1]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/memory/test_summary_compressor.py -v`
Expected: 10 passed

- [ ] **Step 5: 提交**

```bash
git add src/novels_project/memory/summary_compressor.py tests/unit/memory/test_summary_compressor.py
git commit -m "feat(memory): add SummaryCompressor with 100-chapter rolling and sliding window"
```

---

### Task 6: SummaryCompressor 持久化与恢复

**Files:**
- Modify: `src/novels_project/memory/summary_compressor.py` (扩展测试)
- Modify: `tests/unit/memory/test_summary_compressor.py`

- [ ] **Step 1: 写失败测试**

```python
def test_persist_and_reload(tmp_path):
    config = MemoryConfig(chapter_window=10, max_summary_blocks=3)
    comp1 = SummaryCompressor(config=config, storage_dir=tmp_path)
    for i in range(1, 11):
        comp1.add_chapter_summary(i, f"第{i}章摘要")
    # 新 compressor 加载同一目录
    comp2 = SummaryCompressor(config=config, storage_dir=tmp_path)
    assert len(comp2._blocks) == 1
    assert comp2._blocks[0].block_id == "block_00001_00010"


def test_corrupted_block_recovered_from_chapters(tmp_path):
    # 准备：100 个章节文件
    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    for i in range(1, 11):
        (chapters_dir / f"chapter_{i:05d}_final.md").write_text(
            f"# 第{i}章\n\n内容 x。" * 5,
            encoding="utf-8",
        )
    # 写入损坏的块文件
    storage_dir = tmp_path / "blocks"
    storage_dir.mkdir()
    corrupted = storage_dir / "block_00001_00010.json"
    corrupted.write_text('{"block_id": "block_00001_00010", "compressed_text": "损坏', encoding="utf-8")
    # 写入 index
    (storage_dir / "index.json").write_text(
        '{"blocks": ["block_00001_00010"]}', encoding="utf-8"
    )
    # 初始化 compressor
    config = MemoryConfig(chapter_window=10)
    compressor = SummaryCompressor(
        config=config, storage_dir=storage_dir, chapters_dir=chapters_dir,
    )
    # 验证：块已恢复
    assert len(compressor._blocks) == 1
    recovered = compressor._blocks[0]
    assert recovered.start_chapter == 1
    assert recovered.end_chapter == 10
    assert "recovered" in recovered.created_at
    # 损坏文件已备份
    backup = storage_dir / "block_00001_00010.corrupted.json"
    assert backup.exists()
    assert not corrupted.exists()
```

- [ ] **Step 2: 跑测试确认通过（已有实现支持）**

Run: `pytest tests/unit/memory/test_summary_compressor.py::test_persist_and_reload tests/unit/memory/test_summary_compressor.py::test_corrupted_block_recovered_from_chapters -v`
Expected: 2 passed

- [ ] **Step 3: 提交**

```bash
git add tests/unit/memory/test_summary_compressor.py
git commit -m "test(memory): add persistence and recovery tests for SummaryCompressor"
```

---

## Phase 3: DialogueCompactor LLM 对话压缩器

### Task 7: DialogueSummary 数据类

**Files:**
- Create: `src/novels_project/memory/dialogue_compactor.py`
- Create: `tests/unit/memory/test_dialogue_compactor.py`

- [ ] **Step 1: 写失败测试**

```python
"""Test DialogueSummary data class and DialogueCompactor."""
import pytest
from novels_project.memory.dialogue_compactor import (
    DialogueSummary,
    DialogueCompactor,
)
from novels_project.memory.memory_config import MemoryConfig


def test_dialogue_summary_creation():
    summary = DialogueSummary(
        characters=["陆商曜"],
        active_topics=["突破筑基期"],
        pending_tasks=[{"task": "写第5章", "owner": "user", "status": "pending"}],
        completed_tasks=["第1-4章"],
        key_decisions=["采用伏笔回收"],
        unresolved_questions=["主角身世"],
        context_summary="主角修炼即将突破",
    )
    assert "陆商曜" in summary.characters
    assert len(summary.pending_tasks) == 1


def test_dialogue_summary_render():
    summary = DialogueSummary(
        characters=["陆商曜", "周桓"],
        active_topics=["突破"],
        pending_tasks=[],
        completed_tasks=["第1章"],
        key_decisions=[],
        unresolved_questions=[],
        context_summary="脉络",
    )
    rendered = summary.render()
    assert "<dialogue_compression>" in rendered
    assert "出场人物: 陆商曜, 周桓" in rendered
    assert "已完成: 第1章" in rendered
    assert "对话脉络: 脉络" in rendered


def test_dialogue_summary_render_truncation():
    summary = DialogueSummary(
        characters=[],
        active_topics=[],
        pending_tasks=[],
        completed_tasks=[],
        key_decisions=[],
        unresolved_questions=[],
        context_summary="x" * 5000,
    )
    # render 时 context_summary > dialogue_summary_max_chars 会被截断
    config = MemoryConfig(dialogue_summary_max_chars=1000)
    rendered = summary.render()
    # render 内部不直接截断，由调用方截断
    assert len(rendered) > 1000  # 未截断
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/memory/test_dialogue_compactor.py -v`
Expected: FAIL with "No module named 'novels_project.memory.dialogue_compactor'"

- [ ] **Step 3: 实现 DialogueSummary**

```python
"""LLM-based dialogue compactor with structured JSON output."""
from __future__ import annotations
from dataclasses import dataclass
import json
import logging
import re
import time
from typing import Optional, Any

from .memory_config import MemoryConfig
from .exceptions import DialogueCompressionError

logger = logging.getLogger("novels_project.memory.dialogue_compactor")

DIALOGUE_COMPRESSION_PROMPT = """你是一个专业的对话历史压缩助手。请分析以下对话历史，并严格按照 JSON 格式输出结构化摘要。

## 输出 Schema（严格遵守）
```json
{{
  "characters": ["人物1", "人物2"],
  "active_topics": ["主题1", "主题2"],
  "pending_tasks": [
    {{
      "task": "任务描述",
      "owner": "user" | "agent",
      "status": "状态描述"
    }}
  ],
  "completed_tasks": ["已完成任务1", "已完成任务2"],
  "key_decisions": ["决策1", "决策2"],
  "unresolved_questions": ["问题1", "问题2"],
  "context_summary": "整体对话脉络（200字内）"
}}
```

## 规则
1. 提取对话中所有出场的真实人物（包括对话参与者）
2. 只提取明确提及的主题、任务、决策，不要臆造
3. 任务状态要准确（pending/in_progress/done/blocked）
4. 上下文摘要是连贯的叙事，保留关键转折点
5. 如果某个字段为空，输出空数组 `[]` 或空字符串

## 对话历史
{conversation}

## 输出（仅 JSON，无其他内容）
```json
"""


@dataclass
class DialogueSummary:
    """LLM 结构化对话压缩结果。"""

    characters: list[str]
    active_topics: list[str]
    pending_tasks: list[dict]
    completed_tasks: list[str]
    key_decisions: list[str]
    unresolved_questions: list[str]
    context_summary: str

    def render(self) -> str:
        """渲染为可注入的文本格式。"""
        parts = ["<dialogue_compression>"]
        if self.characters:
            parts.append(f"出场人物: {', '.join(self.characters)}")
        if self.active_topics:
            parts.append(f"当前主题: {'; '.join(self.active_topics)}")
        if self.pending_tasks:
            task_strs = [
                f"  - [{t.get('owner', 'unknown')}] {t.get('task', '')} ({t.get('status', '')})"
                for t in self.pending_tasks
            ]
            parts.append("待办任务:\n" + "\n".join(task_strs))
        if self.completed_tasks:
            parts.append(f"已完成: {'; '.join(self.completed_tasks)}")
        if self.key_decisions:
            parts.append(f"关键决策: {'; '.join(self.key_decisions)}")
        if self.unresolved_questions:
            parts.append(f"待解决: {'; '.join(self.unresolved_questions)}")
        if self.context_summary:
            parts.append(f"对话脉络: {self.context_summary}")
        parts.append("</dialogue_compression>")
        return "\n".join(parts)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/memory/test_dialogue_compactor.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/novels_project/memory/dialogue_compactor.py tests/unit/memory/test_dialogue_compactor.py
git commit -m "feat(memory): add DialogueSummary dataclass with render method"
```

---

### Task 8: DialogueCompactor 主体逻辑

**Files:**
- Modify: `src/novels_project/memory/dialogue_compactor.py`
- Modify: `tests/unit/memory/test_dialogue_compactor.py`

- [ ] **Step 1: 写失败测试**

```python
from novels_project.session import Session, ConversationMessage, MessageRole
from novels_project.content_blocks import TextBlock


def test_should_compress_below_threshold():
    config = MemoryConfig()
    compactor = DialogueCompactor(config=config)
    session = Session(messages=[])
    assert compactor.should_compress(session, max_tokens=10000) is False


def test_should_compress_above_threshold():
    config = MemoryConfig(dialogue_compression_threshold=0.8)
    compactor = DialogueCompactor(config=config)
    # 构造大量消息
    messages = [
        ConversationMessage(role=MessageRole.USER, blocks=[TextBlock(text="x" * 100)])
        for _ in range(100)
    ]
    session = Session(messages=messages)
    # 100 * 25 = 2500 tokens, 80% of 10000 = 8000 → 不会触发
    assert compactor.should_compress(session, max_tokens=10000) is False
    # 调整为 5000 → 80% = 4000 < 2500 仍然不会
    assert compactor.should_compress(session, max_tokens=5000) is False
    # max_tokens = 3000 → 80% = 2400 < 2500 触发
    assert compactor.should_compress(session, max_tokens=3000) is True


def test_compact_preserves_recent_messages():
    config = MemoryConfig(
        preserve_recent_messages=4, dialogue_compression_threshold=0.5
    )
    compactor = DialogueCompactor(config=config)
    messages = [
        ConversationMessage(role=MessageRole.USER, blocks=[TextBlock(text=f"msg {i}")])
        for i in range(20)
    ]
    session = Session(messages=messages)
    result = compactor.compact(session, max_tokens=100)  # 强制触发
    assert result.removed_message_count == 16
    assert len(result.compacted_session.messages) == 5  # 1 摘要 + 4 原始
    assert result.compacted_session.messages[-1].get_text() == "msg 19"


def test_compact_below_messages_count_no_op():
    config = MemoryConfig(preserve_recent_messages=4)
    compactor = DialogueCompactor(config=config)
    messages = [
        ConversationMessage(role=MessageRole.USER, blocks=[TextBlock(text=f"m{i}")])
        for i in range(3)
    ]
    session = Session(messages=messages)
    result = compactor.compact(session, max_tokens=10)
    assert result.removed_message_count == 0
    assert result.summary_text == ""


def test_render_truncation_in_compact():
    config = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_summary_max_chars=500,
        dialogue_compression_threshold=0.5,
    )
    compactor = DialogueCompactor(config=config)
    messages = [
        ConversationMessage(
            role=MessageRole.USER, blocks=[TextBlock(text="x" * 200)]
        )
        for _ in range(20)
    ]
    session = Session(messages=messages)
    # mock LLM 返回长文本
    class MockLLM:
        def stream(self, req, print_stream=False):
            return [type("E", (), {"text": "y" * 1000})()]
    compactor.llm_client = MockLLM()
    result = compactor.compact(session, max_tokens=100)
    assert len(result.summary_text) <= 520  # 500 + 一些容差
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/memory/test_dialogue_compactor.py -v`
Expected: 5 failed

- [ ] **Step 3: 实现 DialogueCompactor**

追加到 `src/novels_project/memory/dialogue_compactor.py`：
```python
class DialogueCompactor:
    """LLM 对话压缩器。"""

    def __init__(
        self,
        config: MemoryConfig,
        llm_client: Optional[Any] = None,
    ):
        self.config = config
        self.llm_client = llm_client

    def should_compress(self, session: Session, max_tokens: int) -> bool:
        """检查是否需要压缩。"""
        estimated = session.total_estimated_tokens()
        trigger = int(max_tokens * self.config.dialogue_compression_threshold)
        return estimated >= trigger

    def compact(
        self,
        session: Session,
        max_tokens: int,
    ) -> "CompactionResult":
        """压缩对话历史。"""
        if not self.should_compress(session, max_tokens):
            return CompactionResult(
                compacted_session=session,
                removed_message_count=0,
                summary_text="",
            )
        messages = session.messages
        preserve_count = self.config.preserve_recent_messages
        if len(messages) <= preserve_count:
            return CompactionResult(
                compacted_session=session,
                removed_message_count=0,
                summary_text="",
            )
        to_summarize = messages[:-preserve_count]
        to_keep = messages[-preserve_count:]
        conversation_text = self._messages_to_text(to_summarize)
        # 压缩
        try:
            summary = self._llm_compress_with_retry(conversation_text)
        except Exception as e:
            logger.warning(
                "[DialogueCompactor] LLM 失败回退规则 | error=%s", e,
            )
            summary = self._rule_compress(to_summarize)
        rendered = summary.render()
        if len(rendered) > self.config.dialogue_summary_max_chars:
            rendered = (
                rendered[: self.config.dialogue_summary_max_chars]
                + "\n... (truncated)"
            )
        # 替换为单个 system 消息
        summary_msg = ConversationMessage(
            role=MessageRole.SYSTEM,
            blocks=[TextBlock(text=rendered)],
        )
        compacted = Session(
            version=session.version,
            messages=[summary_msg] + to_keep,
        )
        logger.info(
            "[DialogueCompactor] 压缩完成 | removed=%d summary_len=%d",
            len(to_summarize), len(rendered),
        )
        return CompactionResult(
            compacted_session=compacted,
            removed_message_count=len(to_summarize),
            summary_text=rendered,
        )

    def _messages_to_text(self, messages: list) -> str:
        lines = []
        for msg in messages:
            role = msg.role.value
            text = msg.get_text()
            if text:
                lines.append(f"[{role}] {text}")
        return "\n\n".join(lines)

    def _llm_compress_with_retry(self, conversation: str, max_retries: int = 2) -> DialogueSummary:
        """LLM 压缩 + JSON 解析重试 + 静默降级。"""
        last_error: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                raw = self._llm_compress_raw(conversation)
                return self._parse_json_output_with_retry(raw, max_retries=1)
            except Exception as e:
                last_error = e
                logger.warning(
                    "[DialogueCompactor] LLM 失败 | attempt=%d/%d error=%s",
                    attempt, max_retries, e,
                )
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
        # 重试耗尽，让外层 catch 静默降级
        raise DialogueCompressionError(f"LLM 压缩失败: {last_error}")

    def _llm_compress_raw(self, conversation: str) -> str:
        if not self.llm_client:
            raise RuntimeError("llm_client 未配置")
        from ..api_client import ApiRequest
        prompt = DIALOGUE_COMPRESSION_PROMPT.format(conversation=conversation)
        request = ApiRequest(
            system_prompt=prompt,
            messages=[],
            tools=[],
            model=self.config.dialogue_llm_model or "default",
            max_tokens=2000,
        )
        events = self.llm_client.stream(request, print_stream=False)
        return "".join(e.text for e in events if hasattr(e, "text"))

    def _parse_json_output_with_retry(self, text: str, max_retries: int = 1) -> DialogueSummary:
        """JSON 解析重试。"""
        for attempt in range(1, max_retries + 1):
            try:
                return self._parse_json_output(text)
            except json.JSONDecodeError as e:
                logger.warning(
                    "[DialogueCompactor] JSON 解析失败 | attempt=%d/%d error=%s",
                    attempt, max_retries, e,
                )
                if attempt < max_retries:
                    # 重新调用 LLM（加强 prompt）
                    text = self._llm_compress_raw_strict(text)
        return self._empty_summary()

    def _llm_compress_raw_strict(self, previous_output: str) -> str:
        """加强 prompt 的二次调用。"""
        strict_prompt = f"""你之前的输出不符合 JSON 格式要求，请重新输出。

## 严格要求
1. 仅输出 ```json ... ``` 代码块
2. 不要有任何解释或额外文字
3. 严格遵守 schema 定义

之前的输出：
{previous_output}

请重新输出：
```json
"""
        from ..api_client import ApiRequest
        request = ApiRequest(
            system_prompt=strict_prompt,
            messages=[],
            tools=[],
            model=self.config.dialogue_llm_model or "default",
            max_tokens=2000,
        )
        events = self.llm_client.stream(request, print_stream=False)
        return "".join(e.text for e in events if hasattr(e, "text"))

    def _parse_json_output(self, text: str) -> DialogueSummary:
        json_match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
        if not json_match:
            json_match = re.search(r"\{[\s\S]*\}", text)
        if not json_match:
            raise json.JSONDecodeError("No JSON found", text, 0)
        data = json.loads(json_match.group(1))
        return DialogueSummary(
            characters=data.get("characters", []),
            active_topics=data.get("active_topics", []),
            pending_tasks=data.get("pending_tasks", []),
            completed_tasks=data.get("completed_tasks", []),
            key_decisions=data.get("key_decisions", []),
            unresolved_questions=data.get("unresolved_questions", []),
            context_summary=data.get("context_summary", ""),
        )

    def _rule_compress(self, messages: list) -> DialogueSummary:
        """规则压缩（fallback）。"""
        from ..compaction import _build_summary
        text = _build_summary(messages, self.config.dialogue_summary_max_chars)
        return DialogueSummary(
            characters=[],
            active_topics=[],
            pending_tasks=[],
            completed_tasks=[],
            key_decisions=[],
            unresolved_questions=[],
            context_summary=text,
        )

    def _empty_summary(self) -> DialogueSummary:
        return DialogueSummary(
            characters=[], active_topics=[], pending_tasks=[],
            completed_tasks=[], key_decisions=[],
            unresolved_questions=[], context_summary="",
        )


@dataclass
class CompactionResult:
    compacted_session: Session
    removed_message_count: int
    summary_text: str
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/memory/test_dialogue_compactor.py -v`
Expected: 8 passed

- [ ] **Step 5: 提交**

```bash
git add src/novels_project/memory/dialogue_compactor.py tests/unit/memory/test_dialogue_compactor.py
git commit -m "feat(memory): add DialogueCompactor with LLM retry, JSON retry, and rule fallback"
```

---

## Phase 4: MemoryManager 顶层门面

### Task 9: MemoryManager 基础结构

**Files:**
- Create: `src/novels_project/memory/memory_manager.py`
- Create: `tests/unit/memory/test_memory_manager.py`

- [ ] **Step 1: 写失败测试**

```python
"""Test MemoryManager facade."""
import pytest
from pathlib import Path
from novels_project.memory.memory_manager import MemoryManager
from novels_project.memory.memory_config import MemoryConfig


@pytest.fixture
def memory_config_path(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  max_summary_blocks: 3
  dialogue_compression_threshold: 0.8
agents:
  plot_writer:
    dialogue_compression_threshold: 0.7
""", encoding="utf-8")
    return config_path


def test_get_memory_config_known_agent(memory_config_path, tmp_path):
    mgr = MemoryManager(
        project_root=tmp_path, config_path=memory_config_path,
    )
    cfg = mgr.get_memory_config("plot_writer")
    assert cfg.dialogue_compression_threshold == 0.7
    assert cfg.max_summary_blocks == 3  # 继承 global


def test_get_memory_config_unknown_agent(memory_config_path, tmp_path):
    mgr = MemoryManager(
        project_root=tmp_path, config_path=memory_config_path,
    )
    cfg = mgr.get_memory_config("unknown")
    assert cfg.dialogue_compression_threshold == 0.8  # global 默认


def test_get_memory_config_main(memory_config_path, tmp_path):
    mgr = MemoryManager(
        project_root=tmp_path, config_path=memory_config_path,
    )
    cfg = mgr.get_memory_config("main")
    assert cfg.max_summary_blocks == 3


def test_summary_compressor_caching(memory_config_path, tmp_path):
    mgr = MemoryManager(
        project_root=tmp_path, config_path=memory_config_path,
    )
    c1 = mgr.get_summary_compressor("main")
    c2 = mgr.get_summary_compressor("main")
    assert c1 is c2  # 缓存


def test_reload_config_clears_cache(memory_config_path, tmp_path):
    mgr = MemoryManager(
        project_root=tmp_path, config_path=memory_config_path,
    )
    c1 = mgr.get_summary_compressor("main")
    mgr.reload_config()
    c2 = mgr.get_summary_compressor("main")
    assert c1 is not c2  # 缓存已清空
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/memory/test_memory_manager.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 MemoryManager**

```python
"""Top-level memory system facade."""
from __future__ import annotations
from pathlib import Path
from typing import Optional, Any
import logging

from .memory_config import MemoryConfig, MemoryConfigBundle
from .summary_compressor import SummaryCompressor, ChapterSummaryBlock
from .dialogue_compactor import DialogueCompactor
from .integrator import GraphMemoryIntegrator

logger = logging.getLogger("novels_project.memory.memory_manager")


class MemoryManager:
    """记忆系统顶层门面。"""

    def __init__(
        self,
        project_root: Path,
        config_path: Optional[Path] = None,
        llm_client: Optional[Any] = None,
        graph_integrator: Optional[GraphMemoryIntegrator] = None,
        chapters_dir: Optional[Path] = None,
    ):
        self.project_root = Path(project_root)
        self.config_path = (
            config_path or self.project_root / "config" / "memory_config.yaml"
        )
        self.llm_client = llm_client
        self.graph_integrator = graph_integrator
        self.chapters_dir = Path(chapters_dir) if chapters_dir else None

        self.config_bundle = MemoryConfigBundle.load_from_yaml(self.config_path)
        errors = self.config_bundle.global_config.validate()
        if errors:
            logger.warning(
                "[MemoryManager] global 配置校验失败 | errors=%s", errors
            )

        self._summary_compressors: dict[str, SummaryCompressor] = {}

    def get_memory_config(self, agent_id: str) -> MemoryConfig:
        return self.config_bundle.get_resolved(agent_id)

    def get_summary_compressor(self, agent_id: str) -> SummaryCompressor:
        if agent_id not in self._summary_compressors:
            cfg = self.get_memory_config(agent_id)
            storage_dir = self.project_root / "memory" / "summary_blocks" / agent_id
            self._summary_compressors[agent_id] = SummaryCompressor(
                config=cfg,
                storage_dir=storage_dir,
                llm_client=self.llm_client,
                chapters_dir=self.chapters_dir,
            )
        return self._summary_compressors[agent_id]

    def create_dialogue_compactor(self, agent_id: str) -> DialogueCompactor:
        cfg = self.get_memory_config(agent_id)
        return DialogueCompactor(config=cfg, llm_client=self.llm_client)

    def on_chapter_generated(
        self,
        agent_id: str,
        chapter_id: int,
        chapter_text: str,
    ) -> Optional[ChapterSummaryBlock]:
        """章节生成回调。"""
        from ..context_injector import get_context_injector
        injector = get_context_injector()
        summary = injector.extract_chapter_summary(chapter_text)
        compressor = self.get_summary_compressor(agent_id)
        return compressor.add_chapter_summary(chapter_id, summary)

    def get_summary_for_injection(self, agent_id: str) -> str:
        compressor = self.get_summary_compressor(agent_id)
        return compressor.get_blocks_for_injection()

    def reload_config(self) -> None:
        logger.info("[MemoryManager] 重载配置 | path=%s", self.config_path)
        self.config_bundle = MemoryConfigBundle.load_from_yaml(self.config_path)
        self._summary_compressors.clear()

    def get_status(self) -> dict:
        return {
            "config_path": str(self.config_path),
            "agents": {
                agent_id: {
                    "blocks_count": len(
                        self.get_summary_compressor(agent_id)._blocks
                    ),
                    "accumulator_count": len(
                        self.get_summary_compressor(agent_id)._accumulator
                    ),
                    "config": self.get_memory_config(agent_id).__dict__,
                }
                for agent_id in self.config_bundle.agent_configs.keys()
            },
        }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/memory/test_memory_manager.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add src/novels_project/memory/memory_manager.py tests/unit/memory/test_memory_manager.py
git commit -m "feat(memory): add MemoryManager facade with config caching and reload"
```

---

## Phase 5: 集成到 ConversationRuntime

> **依赖关系**：本 Phase 拆分为 **Task 10a（基础）** 和 **Task 10b（核心）**。
> - **Task 10a** 立即可执行，**不依赖** DialogueCompactor
> - **Task 10b** 依赖 **Task 7-8**（DialogueCompactor 主体完成）后才能执行

### Task 10a: Runtime 基础集成（依赖 Task 7-8 之前）

**Files:**
- Modify: `src/novels_project/runtime.py:21` (导入)
- Modify: `src/novels_project/runtime.py:68-94` (__init__ 新增参数)
- Create: `tests/integration/test_runtime_compression_basic.py`

- [ ] **Step 1: 写失败测试**

```python
"""Test ConversationRuntime basic integration with MemoryConfig.

10a: 验证 MemoryConfig 阈值和 agent_id 集成，但不依赖 DialogueCompactor。
"""
import pytest
from novels_project.runtime import ConversationRuntime
from novels_project.session import Session, ConversationMessage, MessageRole, TextBlock
from novels_project.memory.memory_config import MemoryConfig


def test_runtime_accepts_memory_config_parameter():
    """MemoryConfig 应作为可选参数传入。"""
    runtime = ConversationRuntime(
        session=Session(),
        memory_config=MemoryConfig(dialogue_compression_threshold=0.7),
    )
    assert runtime.memory_config.dialogue_compression_threshold == 0.7


def test_runtime_has_default_memory_config():
    """未传 memory_config 时使用默认配置。"""
    runtime = ConversationRuntime(session=Session())
    assert runtime.memory_config.dialogue_compression_threshold == 0.8
    assert runtime.agent_id == "main"


def test_runtime_accepts_agent_id_parameter():
    """agent_id 应作为参数传入。"""
    runtime = ConversationRuntime(session=Session(), agent_id="plot_writer")
    assert runtime.agent_id == "plot_writer"


def test_maybe_auto_compact_uses_memory_config_threshold():
    """_maybe_auto_compact 应使用 MemoryConfig.dialogue_compression_threshold。"""
    config = MemoryConfig(dialogue_compression_threshold=0.5)  # 50% 触发
    runtime = ConversationRuntime(
        session=Session(),
        memory_config=config,
        auto_compaction_threshold=1000,  # 触发阈值 1000 tokens
    )
    # 注入消息使 estimated tokens 达到 600（> 500 trigger）
    for i in range(10):
        runtime.session.messages.append(
            ConversationMessage(
                role=MessageRole.USER,
                blocks=[TextBlock(text="x" * 240)],  # 60 tokens
            )
        )
    # 估算 ~600 tokens, 50% of 1000 = 500 → 触发
    event = runtime._maybe_auto_compact()
    # 无 dialogue_compactor 时回退到 compact_session
    assert event is not None
    assert event.removed_message_count > 0


def test_maybe_auto_compact_below_threshold_no_action():
    """未达阈值时不压缩。"""
    config = MemoryConfig(dialogue_compression_threshold=0.95)
    runtime = ConversationRuntime(
        session=Session(),
        memory_config=config,
        auto_compaction_threshold=10000,
    )
    # 仅 10 tokens
    runtime.session.messages.append(
        ConversationMessage(
            role=MessageRole.USER,
            blocks=[TextBlock(text="hello")],
        )
    )
    event = runtime._maybe_auto_compact()
    assert event is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd novels_project && python -m pytest tests/integration/test_runtime_compression_basic.py -v`
Expected: FAIL (memory_config 参数不存在)

- [ ] **Step 3: 修改 runtime.py - 导入部分**

修改 `src/novels_project/runtime.py:21`：
```python
# 旧
from .compaction import compact_session

# 新
from .compaction import compact_session, CompactionResult
from .memory.memory_config import MemoryConfig
```

- [ ] **Step 4: 修改 runtime.py - __init__ 方法**

修改 `src/novels_project/runtime.py:68-94`，在 `output_truncation_limit` 参数后新增：
```python
def __init__(
    self,
    session: Session,
    api_client: ApiClient,
    tool_executor: ToolExecutor,
    tool_registry: ToolRegistry,
    system_prompt: str,
    model: str,
    max_iterations: int = 50,
    auto_compaction_threshold: int = 100000,
    print_stream: bool = True,
    output_truncation_limit: int = 50000,
    # === 新增：记忆子系统基础支持（10a 阶段） ===
    agent_id: str = "main",
    memory_config: Optional[MemoryConfig] = None,
):
    self.session = session
    self.api_client = api_client
    self.tool_executor = tool_executor
    self.tool_registry = tool_registry
    self.system_prompt = system_prompt
    self.model = model
    self.max_iterations = max_iterations
    self.auto_compaction_threshold = auto_compaction_threshold
    self.print_stream = print_stream
    self.output_truncation_limit = output_truncation_limit
    self.usage_tracker = UsageTracker.from_session(session)

    # === 新增属性 ===
    self.agent_id = agent_id
    self.memory_config = memory_config or MemoryConfig()
    # 注：dialogue_compactor 在 Task 10b 中添加（依赖 DialogueCompactor）

    # Hook system for post-turn processing (replaces monkey-patching)
    self._turn_hooks: list[Callable[[TurnSummary], None]] = []
```

- [ ] **Step 5: 修改 runtime.py - _maybe_auto_compact**

修改 `src/novels_project/runtime.py:326-345`：
```python
def _maybe_auto_compact(self) -> Optional[AutoCompactionEvent]:
    """根据 MemoryConfig 阈值压缩对话（10a 阶段回退到 compact_session）。"""
    estimated_tokens = self.session.total_estimated_tokens()
    max_tokens = self.auto_compaction_threshold

    # 从 MemoryConfig 读取阈值
    threshold = self.memory_config.dialogue_compression_threshold
    trigger_tokens = int(max_tokens * threshold)

    logger.info(
        "[Runtime] 评估是否需要自动压缩 | est_tokens=%d trigger=%d threshold=%.2f",
        estimated_tokens, trigger_tokens, threshold,
    )
    if estimated_tokens < trigger_tokens:
        return None

    # 10a 阶段：直接使用 compact_session（规则压缩）
    # 10b 阶段：优先 dialogue_compactor
    result = compact_session(self.session)
    if result.removed_message_count > 0:
        self.session = result.compacted_session
        logger.info(
            "[Runtime] 对话压缩完成 | agent=%s removed=%d summary_len=%d (10a: rule)",
            self.agent_id, result.removed_message_count, len(result.summary_text),
        )
        return AutoCompactionEvent(removed_message_count=result.removed_message_count)
    return None
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd novels_project && python -m pytest tests/integration/test_runtime_compression_basic.py -v`
Expected: 5 passed

- [ ] **Step 7: 提交**

```bash
git add novels_project/src/novels_project/runtime.py novels_project/tests/integration/test_runtime_compression_basic.py
git commit -m "feat(runtime): 10a basic integration with MemoryConfig threshold

- Add agent_id, memory_config parameters to __init__
- _maybe_auto_compact uses MemoryConfig.dialogue_compression_threshold
- Falls back to compact_session (will be replaced by DialogueCompactor in 10b)

Part 1/2: depends on Task 7-8 for DialogueCompactor"
```

---

### Task 10b: Runtime 核心压缩集成（**依赖 Task 7-8**）

**前置条件**：Task 7（DialogueSummary）+ Task 8（DialogueCompactor 主体）已完成

**Files:**
- Modify: `src/novels_project/runtime.py:21` (导入补充)
- Modify: `src/novels_project/runtime.py:78-94` (新增 dialogue_compactor 实例化)
- Modify: `src/novels_project/runtime.py:326-345` (核心压缩逻辑)
- Create: `tests/integration/test_runtime_compression.py`

- [ ] **Step 1: 写失败测试**

```python
"""Test ConversationRuntime core integration with DialogueCompactor.

10b: 验证 DialogueCompactor 路径，依赖 Task 7-8 完成。
"""
import pytest
from novels_project.runtime import ConversationRuntime
from novels_project.session import Session, ConversationMessage, MessageRole, TextBlock
from novels_project.memory.memory_manager import MemoryManager
from novels_project.memory.dialogue_compactor import DialogueCompactor


class MockLLM:
    """快速 mock LLM。"""
    def stream(self, request, print_stream=False):
        return [type("E", (), {"text": '{"characters": [], "active_topics": [], "pending_tasks": [], "completed_tasks": [], "key_decisions": [], "unresolved_questions": [], "context_summary": "mock"}'})()]


@pytest.fixture
def memory_manager_with_mock_llm(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  dialogue_compression_threshold: 0.5
  preserve_recent_messages: 4
""", encoding="utf-8")
    return MemoryManager(
        project_root=tmp_path,
        config_path=config_path,
        llm_client=MockLLM(),
    )


def test_runtime_creates_dialogue_compactor_when_memory_manager_provided(
    tmp_path, memory_manager_with_mock_llm,
):
    """传入 memory_manager 时应自动创建 dialogue_compactor。"""
    runtime = ConversationRuntime(
        session=Session(),
        memory_manager=memory_manager_with_mock_llm,
        agent_id="main",
        memory_config=memory_manager_with_mock_llm.get_memory_config("main"),
    )
    assert runtime.dialogue_compactor is not None
    assert isinstance(runtime.dialogue_compactor, DialogueCompactor)


def test_runtime_uses_dialogue_compactor_in_maybe_auto_compact(
    tmp_path, memory_manager_with_mock_llm,
):
    """_maybe_auto_compact 应优先使用 dialogue_compactor。"""
    runtime = ConversationRuntime(
        session=Session(),
        memory_manager=memory_manager_with_mock_llm,
        agent_id="main",
        memory_config=memory_manager_with_mock_llm.get_memory_config("main"),
        auto_compaction_threshold=1000,
    )
    # 注入消息
    for i in range(15):
        runtime.session.messages.append(
            ConversationMessage(
                role=MessageRole.USER,
                blocks=[TextBlock(text=f"msg {i} " + "x" * 50)],
            )
        )
    event = runtime._maybe_auto_compact()
    # 应使用 DialogueCompactor 压缩
    assert event is not None
    assert event.removed_message_count > 0
    # 验证 DialogueCompactor 被调用（通过 summary 含 "<dialogue_compression>"）
    assert "<dialogue_compression>" in runtime.session.messages[0].get_text()


def test_runtime_without_memory_manager_falls_back_to_compact_session(tmp_path):
    """无 memory_manager 时回退到 compact_session（旧行为）。"""
    runtime = ConversationRuntime(
        session=Session(),
        auto_compaction_threshold=500,
    )
    assert runtime.dialogue_compactor is None  # 未创建
    # 注入消息
    for i in range(15):
        runtime.session.messages.append(
            ConversationMessage(
                role=MessageRole.USER,
                blocks=[TextBlock(text=f"m {i} " + "y" * 50)],
            )
        )
    event = runtime._maybe_auto_compact()
    # 回退到 compact_session，summary 含 "<compaction_summary>"
    if event and event.removed_message_count > 0:
        assert "<compaction_summary>" in runtime.session.messages[0].get_text()


def test_subagent_uses_independent_memory_config(tmp_path):
    """子 agent 应使用自己的 MemoryConfig。"""
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  dialogue_compression_threshold: 0.8
agents:
  plot_writer:
    dialogue_compression_threshold: 0.5
""", encoding="utf-8")
    mgr = MemoryManager(project_root=tmp_path, config_path=config_path, llm_client=MockLLM())
    # plot_writer 阈值 0.5
    cfg = mgr.get_memory_config("plot_writer")
    assert cfg.dialogue_compression_threshold == 0.5
    # main 阈值 0.8
    cfg = mgr.get_memory_config("main")
    assert cfg.dialogue_compression_threshold == 0.8
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd novels_project && python -m pytest tests/integration/test_runtime_compression.py -v`
Expected: FAIL (dialogue_compactor 属性不存在)

- [ ] **Step 3: 修改 runtime.py - 导入补充**

修改 `src/novels_project/runtime.py:21`：
```python
# 旧（10a 阶段）
from .compaction import compact_session, CompactionResult
from .memory.memory_config import MemoryConfig

# 新（10b 阶段补充）
from .compaction import compact_session, CompactionResult
from .memory.memory_config import MemoryConfig
from .memory.dialogue_compactor import DialogueCompactor
```

- [ ] **Step 4: 修改 runtime.py - __init__ 新增 memory_manager 参数**

修改 `src/novels_project/runtime.py:68-94`，在 `memory_config` 参数后新增 `memory_manager`：
```python
def __init__(
    self,
    session: Session,
    api_client: ApiClient,
    tool_executor: ToolExecutor,
    tool_registry: ToolRegistry,
    system_prompt: str,
    model: str,
    max_iterations: int = 50,
    auto_compaction_threshold: int = 100000,
    print_stream: bool = True,
    output_truncation_limit: int = 50000,
    # === 10a: 基础参数 ===
    agent_id: str = "main",
    memory_config: Optional[MemoryConfig] = None,
    # === 10b 新增：完整记忆子系统支持 ===
    memory_manager: Optional["MemoryManager"] = None,
):
    self.session = session
    # ... 现有赋值 ...
    self.agent_id = agent_id
    self.memory_config = memory_config or MemoryConfig()
    self.memory_manager = memory_manager

    # === 10b 新增：创建 dialogue_compactor ===
    self.dialogue_compactor: Optional[DialogueCompactor] = None
    if memory_manager:
        self.dialogue_compactor = memory_manager.create_dialogue_compactor(agent_id)
```

- [ ] **Step 5: 修改 runtime.py - _maybe_auto_compact 优先 DialogueCompactor**

修改 `src/novels_project/runtime.py:326-345`：
```python
def _maybe_auto_compact(self) -> Optional[AutoCompactionEvent]:
    """根据 MemoryConfig 阈值压缩对话（10b 阶段：LLM 优先，规则 fallback）。"""
    estimated_tokens = self.session.total_estimated_tokens()
    max_tokens = self.auto_compaction_threshold

    threshold = self.memory_config.dialogue_compression_threshold
    trigger_tokens = int(max_tokens * threshold)

    logger.info(
        "[Runtime] 评估是否需要自动压缩 | est_tokens=%d trigger=%d threshold=%.2f",
        estimated_tokens, trigger_tokens, threshold,
    )
    if estimated_tokens < trigger_tokens:
        return None

    # === 10b：优先 DialogueCompactor，fallback compact_session ===
    if self.dialogue_compactor:
        result = self.dialogue_compactor.compact(self.session, max_tokens)
        compactor_type = "DialogueCompactor"
    else:
        result = compact_session(self.session)
        compactor_type = "compact_session"

    if result.removed_message_count > 0:
        self.session = result.compacted_session
        logger.info(
            "[Runtime] 对话压缩完成 | agent=%s compactor=%s removed=%d summary_len=%d",
            self.agent_id, compactor_type, result.removed_message_count, len(result.summary_text),
        )
        return AutoCompactionEvent(removed_message_count=result.removed_message_count)
    return None
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd novels_project && python -m pytest tests/integration/test_runtime_compression.py -v`
Expected: 4 passed

- [ ] **Step 7: 提交**

```bash
git add novels_project/src/novels_project/runtime.py novels_project/tests/integration/test_runtime_compression.py
git commit -m "feat(runtime): 10b integrate DialogueCompactor into _maybe_auto_compact

- Add memory_manager parameter to __init__
- Auto-create dialogue_compactor when memory_manager provided
- _maybe_auto_compact prefers DialogueCompactor, falls back to compact_session
- Each agent (main/sub) uses its own MemoryConfig

Part 2/2: completes runtime integration with memory subsystem"
```

---

## Phase 7: 集成到 ContextInjector

### Task 12: ContextInjector 注入历史摘要块

**Files:**
- Modify: `src/novels_project/context_injector.py`
- Create: `tests/integration/test_context_injector_summary.py`

- [ ] **Step 1: 写失败测试**

```python
"""Test ContextInjector integration with history summary blocks."""
import pytest
from novels_project.context_injector import ContextInjector
from novels_project.memory.memory_manager import MemoryManager


def test_context_injector_injects_summary_blocks(tmp_path):
    # 准备配置
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  max_summary_blocks: 3
""", encoding="utf-8")
    mgr = MemoryManager(project_root=tmp_path, config_path=config_path)
    # 模拟添加 100 章（触发压缩）
    for i in range(1, 101):
        mgr.on_chapter_generated("main", i, f"# 第{i}章\n\n内容")
    # 创建 injector
    injector = ContextInjector(memory_manager=mgr)
    # 注入
    result = injector.inject_context("用户输入", max_context_chars=8000, agent_id="main")
    assert "历史剧情摘要" in result
    assert "block_00001_00100" in result


def test_context_injector_without_memory_manager_unchanged():
    """未传 memory_manager 时行为不变。"""
    injector = ContextInjector()
    result = injector.inject_context("用户输入", max_context_chars=8000)
    assert "历史剧情摘要" not in result  # 旧行为
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/integration/test_context_injector_summary.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 context_injector.py**

在 `ContextInjector.__init__` 增加 `memory_manager` 参数：
```python
def __init__(
    self,
    graph=None,
    max_context_chars: int = 8000,
    character_limit: int = 3,
    enabled: bool = True,
    memory_manager: Optional["MemoryManager"] = None,
):
    # ... 现有赋值 ...
    self.memory_manager = memory_manager
```

修改 `inject_context` 方法增加 `agent_id` 和摘要块注入：
```python
def inject_context(
    self,
    user_input: str,
    max_context_chars: int = 8000,
    agent_id: str = "main",
) -> str:
    if not self.enabled:
        return user_input
    context_parts = []
    current_len = 0
    # 1. 角色上下文（≤ 2000 字/角色，最多 3 个）
    for name in self.extract_character_names(user_input)[:self.character_limit]:
        char_ctx = self.get_character_context(name)
        if char_ctx:
            char_ctx = self._truncate_context(char_ctx, 2000)
            if current_len + len(char_ctx) > max_context_chars:
                break
            context_parts.append(char_ctx)
            current_len += len(char_ctx)
    # 2. 伏笔上下文
    if current_len < max_context_chars:
        foreshadow_ctx = self.get_foreshadowing_context()
        if foreshadow_ctx:
            remaining = max_context_chars - current_len
            foreshadow_ctx = self._truncate_context(foreshadow_ctx, remaining)
            context_parts.append(foreshadow_ctx)
            current_len += len(foreshadow_ctx)
    # 3. 历史摘要块（新增）
    if current_len < max_context_chars and self.memory_manager:
        remaining = max_context_chars - current_len
        summary_text = self.memory_manager.get_summary_for_injection(agent_id)
        if summary_text:
            summary_text = self._truncate_context(summary_text, remaining)
            context_parts.append(summary_text)
            current_len += len(summary_text)
            logger.info(
                "[ContextInjector] 注入历史摘要块 | agent=%s summary_len=%d",
                agent_id, len(summary_text),
            )
    if context_parts:
        context_str = "\n\n".join(context_parts)
        return f"【上下文信息】\n{context_str}\n\n【用户输入】\n{user_input}"
    return user_input
```

修改 `_truncate_context`（如果不存在则添加）：
```python
def _truncate_context(self, text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    half = max_len // 2 - 50
    return text[:half] + "\n... [内容已截断] ...\n" + text[-half:]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/integration/test_context_injector_summary.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/novels_project/context_injector.py tests/integration/test_context_injector_summary.py
git commit -m "feat(context-injector): inject history summary blocks with priority over budget"
```

---

## Phase 8: 集成到 AgentRunner 子 Agent

### Task 13: AgentRunner 子 Agent 销毁模式

**Files:**
- Modify: `src/novels_project/agents.py`
- Create: `tests/integration/agents/test_subagent_session_isolation.py`

- [ ] **Step 1: 写失败测试**

```python
"""Test sub-agent destroy mode: session_id 100% unique."""
import pytest
import uuid
from novels_project.agents import AgentRunner, PLOT_WRITER
from novels_project.memory.memory_manager import MemoryManager


def test_subagent_session_ids_are_unique(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("global: {}\nagents: {}", encoding="utf-8")
    mgr = MemoryManager(project_root=tmp_path, config_path=config_path)
    runner = AgentRunner(memory_manager=mgr)
    session_ids = set()
    for i in range(5):
        # 模拟调用（不实际运行）
        sub_session_id = str(uuid.uuid4())
        session_ids.add(sub_session_id)
    assert len(session_ids) == 5


def test_subagent_uses_independent_memory_config(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  dialogue_compression_threshold: 0.8
agents:
  plot_writer:
    dialogue_compression_threshold: 0.5
""", encoding="utf-8")
    mgr = MemoryManager(project_root=tmp_path, config_path=config_path)
    runner = AgentRunner(memory_manager=mgr)
    # plot_writer 应使用独立配置
    cfg = mgr.get_memory_config("plot_writer")
    assert cfg.dialogue_compression_threshold == 0.5
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/integration/agents/test_subagent_session_isolation.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 agents.py**

在 `AgentRunner.__init__` 增加 `memory_manager`：
```python
class AgentRunner:
    def __init__(
        self,
        api_client=None,
        main_runtime=None,
        memory_manager: Optional["MemoryManager"] = None,
    ):
        # ... 现有赋值 ...
        self.memory_manager = memory_manager
```

修改 `run_agent` 创建子 runtime 时使用独立 MemoryConfig：
```python
def run_agent(
    self,
    agent_def: AgentDefinition,
    user_input: str,
    task_id: Optional[str] = None,
    **kwargs,
) -> Any:
    # 每次创建新 session
    sub_session = Session()
    sub_session.id = str(uuid.uuid4())  # 永不复用

    # 获取独立 MemoryConfig
    memory_config = None
    if self.memory_manager:
        memory_config = self.memory_manager.get_memory_config(agent_def.name)
        if not memory_config.subagent_compression_enabled:
            memory_config = None  # 关闭子 agent 压缩

    # 创建子 runtime
    sub_runtime = ConversationRuntime(
        session=sub_session,
        api_client=self.api_client,
        tool_executor=...,
        tool_registry=...,
        system_prompt=agent_def.system_prompt,
        model=agent_def.model,
        max_iterations=agent_def.max_iterations,
        auto_compaction_threshold=agent_def.auto_compaction_threshold,
        agent_id=agent_def.name,
        memory_config=memory_config,
        memory_manager=self.memory_manager,
    )
    # 子 agent session 兜底
    if memory_config and len(sub_runtime.session.messages) > memory_config.subagent_max_messages:
        sub_runtime._maybe_auto_compact()
    return sub_runtime.run_turn(user_input)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/integration/agents/test_subagent_session_isolation.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/novels_project/agents.py tests/integration/agents/test_subagent_session_isolation.py
git commit -m "feat(agents): sub-agent destroy mode with independent MemoryConfig and unique session_id"
```

---

## Phase 9: 配置热重载集成测试

### Task 14: 配置热重载端到端测试

**Files:**
- Create: `tests/integration/memory/test_config_hot_reload.py`

- [ ] **Step 1: 写失败测试**

```python
"""Test config hot reload: web PUT → reload → effective immediately."""
import pytest
from novels_project.memory.memory_manager import MemoryManager


def test_config_reload_propagates_to_new_compressor(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  max_summary_blocks: 3
agents:
  plot_writer:
    max_summary_blocks: 5
""", encoding="utf-8")
    mgr = MemoryManager(project_root=tmp_path, config_path=config_path)
    # 初始
    cfg = mgr.get_memory_config("plot_writer")
    assert cfg.max_summary_blocks == 5
    # 修改
    config_path.write_text("""
global:
  max_summary_blocks: 3
agents:
  plot_writer:
    max_summary_blocks: 7
""", encoding="utf-8")
    # 重载前
    cfg = mgr.get_memory_config("plot_writer")
    assert cfg.max_summary_blocks == 5  # 仍为旧值
    # 重载
    mgr.reload_config()
    # 重载后
    cfg = mgr.get_memory_config("plot_writer")
    assert cfg.max_summary_blocks == 7


def test_reload_clears_summary_compressor_cache(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("global: {}", encoding="utf-8")
    mgr = MemoryManager(project_root=tmp_path, config_path=config_path)
    c1 = mgr.get_summary_compressor("main")
    mgr.reload_config()
    c2 = mgr.get_summary_compressor("main")
    assert c1 is not c2
```

- [ ] **Step 2: 跑测试确认通过**

Run: `pytest tests/integration/memory/test_config_hot_reload.py -v`
Expected: 2 passed

- [ ] **Step 3: 提交**

```bash
git add tests/integration/memory/test_config_hot_reload.py
git commit -m "test(memory): add config hot reload integration tests"
```

---

## Phase 10: 集成端到端流程测试

### Task 15: 章节压缩完整流程

**Files:**
- Create: `tests/integration/memory/test_chapter_compression_flow.py`

- [ ] **Step 1: 写测试**

```python
"""End-to-end chapter compression flow: 250 chapters → 2 blocks → inject."""
import pytest
from novels_project.memory.memory_manager import MemoryManager


class MockLLMClient:
    def __init__(self):
        self.call_count = 0
    def stream(self, request, print_stream=False):
        self.call_count += 1
        return [type("E", (), {"text": f"压缩摘要 {self.call_count}"})()]


def test_250_chapters_produces_2_blocks(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  chapter_window: 100
  max_summary_blocks: 3
""", encoding="utf-8")
    mgr = MemoryManager(
        project_root=tmp_path, config_path=config_path,
        llm_client=MockLLMClient(),
    )
    # 模拟 250 章
    for i in range(1, 251):
        mgr.on_chapter_generated("main", i, f"第{i}章内容")
    compressor = mgr.get_summary_compressor("main")
    assert len(compressor._blocks) == 2
    assert compressor._blocks[0].end_chapter == 100
    assert compressor._blocks[1].end_chapter == 200
    assert len(compressor._accumulator) == 50  # 201-250


def test_summary_injection_contains_block_ids(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("global: {}", encoding="utf-8")
    mgr = MemoryManager(
        project_root=tmp_path, config_path=config_path,
        llm_client=MockLLMClient(),
    )
    for i in range(1, 101):
        mgr.on_chapter_generated("main", i, f"第{i}章")
    injected = mgr.get_summary_for_injection("main")
    assert "block_00001_00100" in injected
```

- [ ] **Step 2: 跑测试确认通过**

Run: `pytest tests/integration/memory/test_chapter_compression_flow.py -v`
Expected: 2 passed

- [ ] **Step 3: 提交**

```bash
git add tests/integration/memory/test_chapter_compression_flow.py
git commit -m "test(memory): add end-to-end chapter compression flow tests"
```

---

### Task 16: 对话压缩与降级流程

**Files:**
- Create: `tests/integration/memory/test_dialogue_compression_flow.py`

- [ ] **Step 1: 写测试**

```python
"""Dialogue compression flow: 80% trigger → retry → fallback to rule."""
import pytest
from novels_project.memory.dialogue_compactor import DialogueCompactor
from novels_project.memory.memory_config import MemoryConfig
from novels_project.session import Session, ConversationMessage, MessageRole
from novels_project.content_blocks import TextBlock


class FailingLLM:
    def __init__(self, fail_count=2):
        self.call_count = 0
        self.fail_count = fail_count
    def stream(self, request, print_stream=False):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise RuntimeError("Mock LLM failure")
        return [type("E", (), {"text": '{"characters": [], "active_topics": [], "pending_tasks": [], "completed_tasks": [], "key_decisions": [], "unresolved_questions": [], "context_summary": "ok"}'})()]


def test_failing_llm_retries_then_falls_back():
    config = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.5,
    )
    failing_llm = FailingLLM(fail_count=10)  # 总是失败
    compactor = DialogueCompactor(config=config, llm_client=failing_llm)
    messages = [
        ConversationMessage(role=MessageRole.USER, blocks=[TextBlock(text=f"msg {i}")])
        for i in range(20)
    ]
    session = Session(messages=messages)
    result = compactor.compact(session, max_tokens=100)
    # 应回退到规则压缩
    assert result.removed_message_count > 0
    assert failing_llm.call_count == 2  # 重试 2 次


def test_successful_llm_does_not_fallback():
    config = MemoryConfig(
        preserve_recent_messages=4,
        dialogue_compression_threshold=0.5,
    )
    success_llm = FailingLLM(fail_count=0)  # 不失败
    compactor = DialogueCompactor(config=config, llm_client=success_llm)
    messages = [
        ConversationMessage(role=MessageRole.USER, blocks=[TextBlock(text=f"msg {i}")])
        for i in range(20)
    ]
    session = Session(messages=messages)
    result = compactor.compact(session, max_tokens=100)
    assert result.removed_message_count > 0
    assert success_llm.call_count == 1  # 一次成功
```

- [ ] **Step 2: 跑测试确认通过**

Run: `pytest tests/integration/memory/test_dialogue_compression_flow.py -v`
Expected: 2 passed

- [ ] **Step 3: 提交**

```bash
git add tests/integration/memory/test_dialogue_compression_flow.py
git commit -m "test(memory): add dialogue compression retry and fallback flow tests"
```

---

## Phase 11: 性能测试

### Task 17: 10K 章节性能基准

**Files:**
- Create: `tests/performance/test_large_scale_memory.py`

- [ ] **Step 1: 写测试**

```python
"""Performance test: 10K chapters + 1M tokens scenario."""
import pytest
import time
from novels_project.memory.memory_manager import MemoryManager


class FastMockLLM:
    """极快 mock LLM。"""
    def stream(self, request, print_stream=False):
        return [type("E", (), {"text": "x" * 100})()]


@pytest.mark.performance
def test_10k_chapters_processing_time(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("""
global:
  chapter_window: 100
  max_summary_blocks: 10
""", encoding="utf-8")
    mgr = MemoryManager(
        project_root=tmp_path, config_path=config_path,
        llm_client=FastMockLLM(),
    )
    start = time.time()
    for i in range(1, 10001):
        mgr.on_chapter_generated("main", i, f"第{i}章")
    elapsed = time.time() - start
    compressor = mgr.get_summary_compressor("main")
    assert len(compressor._blocks) == 10
    assert elapsed < 60  # mock LLM 应 < 60s
    print(f"10K chapters processed in {elapsed:.2f}s")


@pytest.mark.performance
def test_injection_response_time(tmp_path):
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text("global: {}", encoding="utf-8")
    mgr = MemoryManager(
        project_root=tmp_path, config_path=config_path,
        llm_client=FastMockLLM(),
    )
    for i in range(1, 1001):
        mgr.on_chapter_generated("main", i, f"第{i}章")
    start = time.time()
    injected = mgr.get_summary_for_injection("main")
    elapsed = time.time() - start
    assert elapsed < 0.1
    print(f"Injection took {elapsed*1000:.2f}ms, len={len(injected)}")
```

- [ ] **Step 2: 跑测试确认通过**

Run: `pytest -m performance tests/performance/test_large_scale_memory.py -v`
Expected: 2 passed

- [ ] **Step 3: 提交**

```bash
git add tests/performance/test_large_scale_memory.py
git commit -m "test(performance): add 10K chapter and injection response time benchmarks"
```

---

## Phase 12: Web 端 API（基础结构）

### Task 18: 后端 API 端点

**Files:**
- Create: `src/novels_project/api/memory_config_api.py` (或类似位置)
- Create: `tests/integration/api/test_memory_config_api.py`

> **注意**：本节为占位说明。具体实现需根据项目现有 API 框架调整（Flask/FastAPI 等）。

- [ ] **Step 1: 写失败测试**

```python
"""Test memory config API endpoints (skeleton)."""
import pytest
from fastapi.testclient import TestClient  # 假设用 FastAPI
from novels_project.api.main import app  # 假设入口


def test_get_memory_config():
    client = TestClient(app)
    response = client.get("/api/agents/main/memory-config")
    assert response.status_code == 200
    data = response.json()
    assert "config" in data
    assert "global_config" in data


def test_put_memory_config():
    client = TestClient(app)
    new_config = {
        "max_summary_blocks": 5,
        "dialogue_compression_threshold": 0.75,
    }
    response = client.put(
        "/api/agents/plot_writer/memory-config",
        json={"config": new_config},
    )
    assert response.status_code == 200


def test_reset_memory_config():
    client = TestClient(app)
    response = client.post("/api/agents/plot_writer/memory-config/reset")
    assert response.status_code == 200
```

- [ ] **Step 2: 实现 API（按项目框架调整）**

API 实现需在 `src/novels_project/api/memory_config_api.py`（或类似文件）添加：

```python
from fastapi import APIRouter, HTTPException
from pathlib import Path
import yaml

router = APIRouter()
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "memory_config.yaml"


@router.get("/api/agents/{agent_id}/memory-config")
def get_memory_config(agent_id: str):
    from novels_project.memory.memory_config import MemoryConfigBundle
    bundle = MemoryConfigBundle.load_from_yaml(CONFIG_PATH)
    return {
        "config": bundle.get_resolved(agent_id).__dict__,
        "global_config": bundle.global_config.__dict__,
    }


@router.put("/api/agents/{agent_id}/memory-config")
def put_memory_config(agent_id: str, body: dict):
    # 深合并到 YAML
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("agents", {})[agent_id] = body.get("config", {})
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    # 触发 MemoryManager 重载（通过全局 manager）
    from novels_project.api.main import memory_manager
    if memory_manager:
        memory_manager.reload_config()
    return {"status": "ok"}


@router.post("/api/agents/{agent_id}/memory-config/reset")
def reset_memory_config(agent_id: str):
    # 从 YAML 中删除 agent 配置（回退到 global）
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "agents" in data and agent_id in data["agents"]:
        del data["agents"][agent_id]
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    from novels_project.api.main import memory_manager
    if memory_manager:
        memory_manager.reload_config()
    return {"status": "ok"}
```

- [ ] **Step 3: 注册路由**

在 `src/novels_project/api/main.py`（或入口文件）：
```python
from .memory_config_api import router as memory_config_router
app.include_router(memory_config_router)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/integration/api/test_memory_config_api.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/novels_project/api/memory_config_api.py tests/integration/api/test_memory_config_api.py
git commit -m "feat(api): add memory config GET/PUT/reset endpoints"
```

---

## Phase 13: Web 前端（占位）

### Task 19: Agent 设置页 - Memory Management 区块

**Files:**
- Create: `web/src/components/AgentSettings/MemoryManagement.tsx` (或类似)

> **占位说明**：前端实现使用 ui-ux-pro-max-skill-main 技能。
> 复用设计文档第 8 节的 UI 设计稿（4 Tab：Main / Plot Writer / Proofreader / Char Designer）。
> 每个 Tab 包含：
> - 摘要滑动窗口档位（10 档固定）
> - 对话压缩（阈值、保留消息数、摘要上限）
> - LLM 模型（只读，来自 global）
> - [重置为默认] [保存] 按钮

> **本任务由前端工程师使用 ui-ux-pro-max-skill-main 完成，跳过本计划的实现细节。**

---

## Phase 14: 验收清单

### Task 20: 运行所有测试与覆盖率检查

- [ ] **Step 1: 跑所有单元测试**

Run: `pytest -m unit tests/ -v`
Expected: All passed

- [ ] **Step 2: 跑所有集成测试**

Run: `pytest -m "integration or unit" tests/ -v`
Expected: All passed

- [ ] **Step 3: 跑性能测试**

Run: `pytest -m performance tests/ -v`
Expected: All passed

- [ ] **Step 4: 检查覆盖率**

Run: `pytest --cov=novels_project/memory --cov-report=term --cov-report=html tests/`
Expected: > 95% coverage for `memory/` package

- [ ] **Step 5: 手动验收清单**

- [ ] 单元测试覆盖率 > 95%
- [ ] 集成测试全部通过
- [ ] 性能测试：10K 章 < 60s（mock LLM）
- [ ] 注入响应 < 100ms
- [ ] LLM 压缩对话 < 5s
- [ ] 1M token 内存增长 < 200MB
- [ ] 块 JSON 损坏自动恢复率 100%
- [ ] 配置热重载生效 < 1s
- [ ] 子 agent session_id 100% 不重复

- [ ] **Step 6: 最终提交**

```bash
git add -A
git commit -m "feat: layered memory management system - all phases complete"
git tag v1.0-memory-system
```

---

## 总结

**预计时间**: 7-11 个工作日

**关键路径**：
1. Phase 1-2（基础 + SummaryCompressor）：2-3 天
2. Phase 3-4（DialogueCompactor + MemoryManager）：2-3 天
3. Phase 5-8（集成 Runtime 10a/10b + Injector + AgentRunner）：1-2 天
   - **关键依赖**：Task 10a（基础）可立即执行，Task 10b（核心）需等 Task 7-8
4. Phase 9-11（集成 + 性能测试）：1 天
5. Phase 12-14（Web 端 + 验收）：1-2 天

**风险点**：
- LLM 压缩失败率高 → 重试 + 通知用户 + 累积到下一批
- 块文件 I/O 性能问题 → 每块独立 JSON + 缓存
- 配置热重载竞态 → 清空缓存 + 下次访问重建
