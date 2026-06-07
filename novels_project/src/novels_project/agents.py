"""
Layer 5: Sub-Agent System - Agent-as-Tool Pattern

Defines the 4 novel-writing agents as tools that spawn their own
ConversationRuntime instances when invoked by the main agent.

Model names can be overridden via environment variables:
  NOVEL_MODEL_CHIEF_EDITOR, NOVEL_MODEL_CHARACTER_DESIGNER,
  NOVEL_MODEL_PLOT_WRITER, NOVEL_MODEL_PROOFREADER
"""
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from .session import Session, TextBlock
from .tool_spec import ToolSpec, ToolRegistry
from .tool_executor import SubAgentToolExecutor
from .system_prompt import build_sub_agent_system_prompt

if TYPE_CHECKING:
    from .api_client import OpenAICompatibleClient
    from .runtime import ConversationRuntime

logger = logging.getLogger("novels_project.agents")


@dataclass
class AgentDefinition:
    """Declarative definition of a sub-agent."""
    name: str                    # Tool name (e.g., "chief_editor")
    display_name: str            # Human-readable (e.g., "小说总编")
    model: str                   # LLM model to use
    description: str             # Tool description for the orchestrator LLM
    allowed_tools: list[str]     # Tools this sub-agent can use
    input_schema: dict           # JSON Schema for the tool input


# === 4 Agent Definitions ===
# Preserving roles and tool assignments from the original crew.py
# Model names default to hardcoded values but can be overridden via env vars

CHIEF_EDITOR = AgentDefinition(
    name="chief_editor",
    display_name="小说总编",
    model=os.getenv("NOVEL_MODEL_CHIEF_EDITOR", "gemini-3-pro"),
    description=(
        "调用总编Agent生成章节大纲。传入卷大纲、章节信息、人物卡库、前章摘要等完整上下文。"
        "输出YAML格式的章大纲，包含story_structure、characters_appearance、climax_plan、"
        "atmosphere、foreshadowing、pacing_notes。"
    ),
    allowed_tools=[],
    input_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "给总编的完整任务描述，必须包含卷大纲、章节ID、前章摘要等全部上下文"
            }
        },
        "required": ["prompt"]
    },
)

CHARACTER_DESIGNER = AgentDefinition(
    name="character_designer",
    display_name="人物策划设计师",
    model=os.getenv("NOVEL_MODEL_CHARACTER_DESIGNER", "glm-5"),
    description=(
        "调用人物设计师Agent生成人物状态卡。传入章大纲和人物基础卡库。"
        "输出YAML格式的人物状态卡，包含每个人物的chapter_arc、behavior_this_chapter、"
        "dialogue_style_this_chapter、character_tensions、callbacks。"
    ),
    allowed_tools=[],
    input_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "给人物设计师的任务描述，必须包含章大纲和人物基础卡库"
            }
        },
        "required": ["prompt"]
    },
)

PLOT_WRITER = AgentDefinition(
    name="plot_writer",
    display_name="剧情撰写员",
    model=os.getenv("NOVEL_MODEL_PLOT_WRITER", "glm-5"),
    description=(
        "调用剧情撰写员Agent创作章节内容（3000-5000字）。传入章大纲、人物状态卡。"
        "撰写员可使用样例检索(retrieve_writing_samples)和对话风格检查(check_character_voice)等工具。"
        "输出YAML格式的章节内容，包含content、creation_notes、estimated_word_count。"
    ),
    allowed_tools=[
        "retrieve_writing_samples",
        "check_character_voice",
        "get_character_voice_guide",
        "retrieve_feedback",
        "get_common_mistakes",
        "get_revision_feedback",
        "check_iteration_status",
    ],
    input_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "给撰写员的任务描述，包含大纲、人物卡、写作要求"
            }
        },
        "required": ["prompt"]
    },
)

PROOFREADER = AgentDefinition(
    name="proofreader",
    display_name="资深校对",
    model=os.getenv("NOVEL_MODEL_PROOFREADER", "gemini-3-pro"),
    description=(
        "调用校对Agent检查章节质量并生成摘要卡。传入大纲、人物卡、章节初稿。"
        "校对可使用风格检查、反馈记录、迭代控制等工具。"
        "输出YAML格式的最终章节(chapter_final)和摘要卡(chapter_summary_card)。"
    ),
    allowed_tools=[
        "retrieve_writing_samples",
        "check_character_voice",
        "get_character_voice_guide",
        "retrieve_feedback",
        "get_common_mistakes",
        "record_feedback",
        "record_batch_feedback",
        "should_continue_iteration",
        "record_iteration",
        "check_iteration_status",
    ],
    input_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "给校对的任务描述，包含大纲、人物卡、章节初稿"
            }
        },
        "required": ["prompt"]
    },
)

ALL_AGENTS = [CHIEF_EDITOR, CHARACTER_DESIGNER, PLOT_WRITER, PROOFREADER]


class AgentRunner:
    """
    Runs sub-agents as tool calls (Agent-as-Tool pattern).

    Each sub-agent gets its own ConversationRuntime with:
    - Independent Session (empty)
    - Shared ApiClient
    - SubAgentToolExecutor (restricted tools)
    - Sub-agent-specific system prompt
    - Sub-agent-specific model
    """

    def __init__(self, api_client: "OpenAICompatibleClient"):
        self.api_client = api_client
        self._agent_defs = {a.name: a for a in ALL_AGENTS}
        self._builtin_registry: Optional[ToolRegistry] = None

    def set_builtin_registry(self, registry: ToolRegistry):
        """Set the built-in tool registry for sub-agents that need tools."""
        self._builtin_registry = registry

    def is_agent_tool(self, tool_name: str) -> bool:
        return tool_name in self._agent_defs

    def run_agent(self, agent_name: str, tool_input: str) -> str:
        """
        Execute a sub-agent: create a fresh ConversationRuntime,
        run one turn with the provided prompt, return the text output.
        """
        from .runtime import ConversationRuntime

        agent_def = self._agent_defs[agent_name]
        parsed = json.loads(tool_input)
        prompt = parsed["prompt"]

        # Build sub-agent system prompt
        system_prompt = build_sub_agent_system_prompt(agent_name)

        # Build restricted tool registry and executor
        sub_registry = ToolRegistry()
        if agent_def.allowed_tools and self._builtin_registry:
            for tool_name in agent_def.allowed_tools:
                spec = self._builtin_registry.get_spec(tool_name)
                if spec:
                    sub_registry.register(spec)

        sub_executor = SubAgentToolExecutor(
            registry=sub_registry,
            allowed_tools=set(agent_def.allowed_tools),
        )

        # Create independent runtime for this sub-agent
        runtime = ConversationRuntime(
            session=Session(),
            api_client=self.api_client,
            tool_executor=sub_executor,
            tool_registry=sub_registry,
            system_prompt=system_prompt,
            model=agent_def.model,
            max_iterations=20,
            print_stream=True,
        )

        # Run the agent
        logger.info("[%s] 开始执行 | model=%s", agent_def.display_name, agent_def.model)
        if agent_def.allowed_tools:
            logger.debug("[%s] Tools available: %d", agent_def.display_name, len(agent_def.allowed_tools))

        summary = runtime.run_turn(prompt)

        logger.info("[%s] 完成 | iterations=%d", agent_def.display_name, summary.iterations)

        # Extract final text from the last assistant message
        result_text = summary.get_final_text()

        if not result_text:
            result_text = "(Sub-agent produced no text output)"

        return result_text


def register_agent_tools(registry: ToolRegistry):
    """Register all 4 sub-agents as tools in the main tool registry."""
    for agent_def in ALL_AGENTS:
        registry.register(ToolSpec(
            name=agent_def.name,
            description=agent_def.description,
            input_schema=agent_def.input_schema,
            handler=None,  # Handled by AgentRunner, not direct call
        ))


def build_save_chapter_tool() -> ToolSpec:
    """Build the save_chapter utility tool for the main agent."""
    import yaml

    def save_chapter(chapter_id: int, content: str,
                     summary_yaml: str = "", raw_output: str = "") -> str:
        """Save chapter output files."""
        from .project_config import (
            get_chapters_dir, get_summaries_dir, get_output_dir
        )

        chapters_dir = get_chapters_dir()
        summaries_dir = get_summaries_dir()
        raw_dir = get_output_dir() / "raw_outputs"

        chapters_dir.mkdir(parents=True, exist_ok=True)
        summaries_dir.mkdir(parents=True, exist_ok=True)
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Save chapter
        chapter_file = chapters_dir / f"chapter_{chapter_id}_final.md"
        with open(chapter_file, "w", encoding="utf-8") as f:
            f.write(f"# 第 {chapter_id} 章\n\n")
            f.write(content)

        result = f"已保存章节: {chapter_file}"

        # Save summary
        if summary_yaml:
            summary_file = summaries_dir / f"chapter_{chapter_id}_summary.yaml"
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(summary_yaml)
            result += f"\n已保存摘要: {summary_file}"

        # Save raw output
        if raw_output:
            raw_file = raw_dir / f"chapter_{chapter_id}_raw.yaml"
            with open(raw_file, "w", encoding="utf-8") as f:
                f.write(raw_output)
            result += f"\n已保存原始输出: {raw_file}"

        return result

    return ToolSpec(
        name="save_chapter",
        description="保存章节输出文件（最终章节、摘要卡、原始输出）。",
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章节ID"},
                "content": {"type": "string", "description": "章节正文内容"},
                "summary_yaml": {"type": "string", "description": "章节摘要卡(YAML格式)"},
                "raw_output": {"type": "string", "description": "原始输出(可选)"},
            },
            "required": ["chapter_id", "content"]
        },
        handler=save_chapter,
    )


def build_load_chapter_data_tool() -> ToolSpec:
    """Build a tool to load chapter input data (outline, character cards)."""
    import yaml

    def load_chapter_data(chapter_id: int) -> str:
        """Load chapter input data including outline and character cards."""
        from .project_config import (
            get_character_cards_path, get_summaries_dir
        )

        # Load character cards
        cards_path = get_character_cards_path()
        if not cards_path.exists():
            return f"Error: 人物卡文件不存在。\n请创建: {cards_path}\n\n参考格式:\nmetadata:\n  version: '1.0'\n  protagonist: 你的主角名\ns_tier:\n  characters:\n    主角名:\n      name: 主角名\n      role: 主角\n      core_personality: [性格1, 性格2]\n      unique_speaking_style:\n        tone: 语调描述\n        example_dialogues: [示例台词1, 示例台词2]"

        with open(cards_path, "r", encoding="utf-8") as f:
            character_cards = yaml.safe_load(f)

        # Load previous chapter summary if exists
        prev_summary = None
        if chapter_id > 1:
            prev_path = get_summaries_dir() / f"chapter_{chapter_id - 1}_summary.yaml"
            if prev_path.exists():
                with open(prev_path, "r", encoding="utf-8") as f:
                    prev_summary = f.read()

        # Extract world info from character cards metadata
        metadata = character_cards.get("metadata", {})
        story_world = metadata.get("story_world", "未设定")
        protagonist = metadata.get("protagonist", "未设定")

        # Build chapter data
        data = {
            "chapter_id": chapter_id,
            "chapter_title": f"第{chapter_id}章",
            "story_world": story_world,
            "protagonist": protagonist,
        }

        result = f"## 章节 {chapter_id} 输入数据\n\n"
        result += f"### 章节信息\n```yaml\n{yaml.dump(data, allow_unicode=True, default_flow_style=False)}```\n\n"
        result += f"### 人物卡库\n```yaml\n{yaml.dump(character_cards, allow_unicode=True, default_flow_style=False)}```\n\n"

        if prev_summary:
            result += f"### 前章摘要\n```yaml\n{prev_summary}```\n"
        else:
            result += "### 前章摘要\n无（第1章或前章摘要不存在）\n"

        return result

    return ToolSpec(
        name="load_chapter_data",
        description="加载章节创作所需的输入数据，包含章节信息、人物卡库、前章摘要。",
        input_schema={
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章节ID"}
            },
            "required": ["chapter_id"]
        },
        handler=load_chapter_data,
    )
