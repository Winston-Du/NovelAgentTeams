"""
Layer 3: Tool System - ToolSpec, ToolRegistry, ToolExecutor

Declarative tool definitions and registry following agent-harness patterns.
"""
from dataclasses import dataclass, field
from typing import Protocol, Optional, Callable, Any, runtime_checkable


@dataclass
class ToolSpec:
    """Declarative tool definition."""
    name: str
    description: str
    input_schema: dict  # JSON Schema dict
    handler: Optional[Callable] = None  # The actual function to call (None for agent tools)


@runtime_checkable
class ToolExecutor(Protocol):
    def execute(self, tool_name: str, tool_input: str) -> tuple[str, bool]:
        """Execute a tool. Returns (output, is_error)."""
        ...  # pragma: no cover


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self):
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec):
        self._specs[spec.name] = spec

    def get_spec(self, name: str) -> Optional[ToolSpec]:
        return self._specs.get(name)

    def all_specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def has(self, name: str) -> bool:
        return name in self._specs

    def to_openai_tools(self) -> list[dict]:
        """Convert all specs to OpenAI API tools format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema,
                }
            }
            for spec in self._specs.values()
        ]


def build_builtin_tool_registry() -> ToolRegistry:
    """Build a registry with all built-in tools (not including agent tools)."""
    registry = ToolRegistry()

    # === Sample Retriever ===
    from .tools.sample_retriever import retrieve_writing_samples
    registry.register(ToolSpec(
        name="retrieve_writing_samples",
        description="检索相似的写作样例，用于参考。输入场景描述，返回匹配的样例内容。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "描述你想写的场景或类型，如：'权谋听证、多角色对话、逻辑碾压'"
                },
                "chapter_type": {
                    "type": "string",
                    "description": "章节类型筛选",
                    "enum": ["战斗章", "情感章", "权谋章", "经营章", "节奏章"]
                },
                "num_samples": {
                    "type": "integer",
                    "description": "返回样例数(1-5)",
                    "default": 3
                }
            },
            "required": ["query"]
        },
        handler=retrieve_writing_samples,
    ))

    # === Character Voice Checker ===
    from .tools.character_voice_checker import check_character_voice, get_character_voice_guide
    registry.register(ToolSpec(
        name="check_character_voice",
        description="检查章节内容中的人物对话是否符合人物卡库设定，返回检查报告和修改建议。",
        input_schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "章节内容或包含对话的文本"
                },
                "focus_characters": {
                    "type": "string",
                    "description": "指定要检查的人物（逗号分隔），如：'陆商曜,黑商周桓'"
                }
            },
            "required": ["content"]
        },
        handler=check_character_voice,
    ))

    registry.register(ToolSpec(
        name="get_character_voice_guide",
        description="获取指定人物的对话风格指南，包含语气、特征、示例台词、避免事项。",
        input_schema={
            "type": "object",
            "properties": {
                "character_name": {
                    "type": "string",
                    "description": "人物名称，如：陆商曜、黑商周桓、木九公"
                }
            },
            "required": ["character_name"]
        },
        handler=get_character_voice_guide,
    ))

    # === Feedback Tools ===
    from .tools.feedback_tools import (
        retrieve_feedback, get_common_mistakes,
        record_feedback, record_batch_feedback,
    )

    registry.register(ToolSpec(
        name="retrieve_feedback",
        description="检索历史校对反馈，用于避免重复犯错。可按问题类型或人物筛选。",
        input_schema={
            "type": "object",
            "properties": {
                "issue_type": {
                    "type": "string",
                    "description": "问题类型筛选，如：'对话风格偏离', 'Tell而非Show', '节奏问题'"
                },
                "character": {
                    "type": "string",
                    "description": "按人物筛选，如：'陆商曜'"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量(1-10)",
                    "default": 5
                }
            }
        },
        handler=retrieve_feedback,
    ))

    registry.register(ToolSpec(
        name="get_common_mistakes",
        description="获取最常见的创作问题类型，用于预防性检查。",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回数量(1-10)",
                    "default": 5
                }
            }
        },
        handler=get_common_mistakes,
    ))

    registry.register(ToolSpec(
        name="record_feedback",
        description="记录一条校对反馈到反馈库。",
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章节ID"},
                "issue_type": {"type": "string", "description": "问题类型"},
                "character": {"type": "string", "description": "相关人物（可选）"},
                "original_text": {"type": "string", "description": "原始有问题的文本"},
                "problem": {"type": "string", "description": "问题描述"},
                "fix_applied": {"type": "string", "description": "应用的修正方案"},
                "severity": {
                    "type": "string",
                    "description": "严重程度",
                    "enum": ["high", "medium", "low"],
                    "default": "medium"
                }
            },
            "required": ["chapter_id", "issue_type", "original_text", "problem", "fix_applied"]
        },
        handler=record_feedback,
    ))

    registry.register(ToolSpec(
        name="record_batch_feedback",
        description="批量记录校对反馈。",
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章节ID"},
                "issues_json": {
                    "type": "string",
                    "description": "JSON格式的问题列表"
                }
            },
            "required": ["chapter_id", "issues_json"]
        },
        handler=record_batch_feedback,
    ))

    # === Iteration Tools ===
    from .tools.iteration_tools import (
        check_iteration_status, should_continue_iteration,
        get_revision_feedback, record_iteration,
    )

    registry.register(ToolSpec(
        name="check_iteration_status",
        description="检查当前章节的迭代状态，包含当前迭代次数、最佳分数等。",
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章节ID"}
            },
            "required": ["chapter_id"]
        },
        handler=check_iteration_status,
    ))

    registry.register(ToolSpec(
        name="should_continue_iteration",
        description="判断是否需要继续迭代。",
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章节ID"},
                "quality_score": {"type": "integer", "description": "当前质量评分(1-10)"}
            },
            "required": ["chapter_id", "quality_score"]
        },
        handler=should_continue_iteration,
    ))

    registry.register(ToolSpec(
        name="get_revision_feedback",
        description="获取上一轮校对的反馈，用于指导修改。",
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章节ID"}
            },
            "required": ["chapter_id"]
        },
        handler=get_revision_feedback,
    ))

    registry.register(ToolSpec(
        name="record_iteration",
        description="记录一次迭代结果。",
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章节ID"},
                "draft": {"type": "string", "description": "草稿内容"},
                "review_issues": {"type": "string", "description": "校对问题(JSON)"},
                "quality_score": {"type": "integer", "description": "质量评分(1-10)"}
            },
            "required": ["chapter_id", "draft", "review_issues", "quality_score"]
        },
        handler=record_iteration,
    ))

    # === Character Card Tools ===
    from .tools.character_card_tools import (
        update_character_card,
        add_character_dialogue_example,
        get_character_card,
        list_all_characters,
    )

    registry.register(ToolSpec(
        name="update_character_card",
        description="更新人物卡的指定字段。支持嵌套字段（如 unique_speaking_style.tone）。",
        input_schema={
            "type": "object",
            "properties": {
                "character_name": {"type": "string", "description": "人物名称，如：陆商曜、黑商周桓"},
                "field": {"type": "string", "description": "要更新的字段，支持点号嵌套，如：unique_speaking_style.tone"},
                "value": {"type": "string", "description": "新的值（JSON格式）"}
            },
            "required": ["character_name", "field", "value"]
        },
        handler=update_character_card,
    ))

    registry.register(ToolSpec(
        name="add_character_dialogue_example",
        description="为人物添加新的对话示例。",
        input_schema={
            "type": "object",
            "properties": {
                "character_name": {"type": "string", "description": "人物名称"},
                "dialogue": {"type": "string", "description": "新的对话示例"}
            },
            "required": ["character_name", "dialogue"]
        },
        handler=add_character_dialogue_example,
    ))

    registry.register(ToolSpec(
        name="get_character_card",
        description="获取人物的完整设定卡。",
        input_schema={
            "type": "object",
            "properties": {
                "character_name": {"type": "string", "description": "人物名称"}
            },
            "required": ["character_name"]
        },
        handler=get_character_card,
    ))

    registry.register(ToolSpec(
        name="list_all_characters",
        description="列出所有可用的人物。",
        input_schema={
            "type": "object",
            "properties": {}
        },
        handler=list_all_characters,
    ))

    # === Chapter Fix Tools ===
    from .tools.chapter_fix_tools import (
        fix_chapter_issue,
        get_chapter_content,
        list_generated_chapters,
    )

    registry.register(ToolSpec(
        name="fix_chapter_issue",
        description="记录章节问题并提供修正指导。自动记录到反馈库，防止同类错误再次发生。",
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章节ID"},
                "issue_description": {"type": "string", "description": "问题描述（用户发现的具体问题）"},
                "original_text": {"type": "string", "description": "有问题的原文片段（可选）"},
                "fix_instruction": {"type": "string", "description": "修正指导（用户希望的修改方向）"},
                "severity": {
                    "type": "string",
                    "description": "严重程度",
                    "enum": ["high", "medium", "low"],
                    "default": "medium"
                }
            },
            "required": ["chapter_id", "issue_description"]
        },
        handler=fix_chapter_issue,
    ))

    registry.register(ToolSpec(
        name="get_chapter_content",
        description="获取已生成的章节内容，用于查看和修改。",
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章节ID"}
            },
            "required": ["chapter_id"]
        },
        handler=get_chapter_content,
    ))

    registry.register(ToolSpec(
        name="list_generated_chapters",
        description="列出所有已生成的章节。",
        input_schema={
            "type": "object",
            "properties": {}
        },
        handler=list_generated_chapters,
    ))

    # === Graph Memory Tools ===
    from .memory.graph_memory_tool import (
        query_character_network,
        query_relation_between,
        search_graph,
        trace_foreshadowing,
        get_graph_context,
        build_knowledge_graph,
        get_graph_stats,
    )

    registry.register(ToolSpec(
        name="query_character_network",
        description="查询人物的关系网络，包括直接关系和间接关系、相关事件、所属组织、关联暗线等。",
        input_schema={
            "type": "object",
            "properties": {
                "character_name": {
                    "type": "string",
                    "description": "要查询的人物名称"
                },
                "max_depth": {
                    "type": "integer",
                    "description": "查询深度 (1-3)",
                    "default": 2
                }
            },
            "required": ["character_name"]
        },
        handler=query_character_network,
    ))

    registry.register(ToolSpec(
        name="query_relation_between",
        description="查询两个实体之间是否存在关联关系，支持查找直接关系和间接关联路径。",
        input_schema={
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "源实体名称"
                },
                "target": {
                    "type": "string",
                    "description": "目标实体名称"
                }
            },
            "required": ["source", "target"]
        },
        handler=query_relation_between,
    ))

    registry.register(ToolSpec(
        name="search_graph",
        description="在知识图谱中搜索实体，支持按名称或类型查找人物、事件、地点、概念等。",
        input_schema={
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "entity_type": {
                    "type": "string",
                    "description": "实体类型过滤: all/character/event/location/organization/concept",
                    "default": "all"
                }
            },
            "required": ["keyword"]
        },
        handler=search_graph,
    ))

    registry.register(ToolSpec(
        name="trace_foreshadowing",
        description="追踪暗线或伏笔的关联脉络，查看哪些事件被预示、哪些概念引用了它、关联人物等信息。",
        input_schema={
            "type": "object",
            "properties": {
                "concept_name": {
                    "type": "string",
                    "description": "概念/伏笔名称，如：神秘玉简、陆家隐秘"
                }
            },
            "required": ["concept_name"]
        },
        handler=trace_foreshadowing,
    ))

    registry.register(ToolSpec(
        name="get_graph_context",
        description="获取指定实体在图谱中的上下文信息（可用于注入写作 Prompt），支持写作上下文和校对上下文两种模式。",
        input_schema={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "实体名称"
                },
                "context_type": {
                    "type": "string",
                    "description": "上下文类型: writing (写作上下文) 或 review (校对上下文)",
                    "enum": ["writing", "review"],
                    "default": "writing"
                }
            },
            "required": ["entity_name"]
        },
        handler=get_graph_context,
    ))

    registry.register(ToolSpec(
        name="build_knowledge_graph",
        description="构建或重建知识图谱，从人物卡和已生成章节中提取实体和关系。",
        input_schema={
            "type": "object",
            "properties": {
                "character_cards_path": {
                    "type": "string",
                    "description": "人物卡 YAML 文件路径（空字符串使用默认）",
                    "default": ""
                },
                "full_sync": {
                    "type": "boolean",
                    "description": "是否全量重建（默认增量同步）",
                    "default": False
                }
            },
            "required": []
        },
        handler=build_knowledge_graph,
    ))

    registry.register(ToolSpec(
        name="get_graph_stats",
        description="获取知识图谱的统计信息，包括节点数、关系数、类型分布、核心人物等。",
        input_schema={
            "type": "object",
            "properties": {}
        },
        handler=get_graph_stats,
    ))

    return registry
