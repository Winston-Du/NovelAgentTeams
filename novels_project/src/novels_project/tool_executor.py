"""
Layer 3: Tool System - Tool Executors

MainToolExecutor: routes to built-in tools and sub-agent tools.
SubAgentToolExecutor: restricted whitelist for sub-agents.
"""
import json
from typing import TYPE_CHECKING

from .tool_spec import ToolRegistry

if TYPE_CHECKING:
    from .agents import AgentRunner


class MainToolExecutor:
    """
    Full tool executor for the main agent.
    Routes to built-in tools and sub-agent tools via AgentRunner.
    """

    def __init__(self, registry: ToolRegistry, agent_runner: "AgentRunner"):
        self.registry = registry
        self.agent_runner = agent_runner

    def execute(self, tool_name: str, tool_input: str) -> tuple[str, bool]:
        """Execute a tool. Returns (output, is_error)."""
        # Check if it's a sub-agent tool
        if self.agent_runner.is_agent_tool(tool_name):
            try:
                result = self.agent_runner.run_agent(tool_name, tool_input)
                return result, False
            except Exception as e:
                return f"Sub-agent execution failed: {e}", True

        # Built-in tool
        spec = self.registry.get_spec(tool_name)
        if spec is None:
            return f"Unknown tool: {tool_name}", True

        if spec.handler is None:
            return f"Tool '{tool_name}' has no handler", True

        try:
            parsed_input = json.loads(tool_input) if tool_input else {}
            result = spec.handler(**parsed_input)
            return str(result), False
        except Exception as e:
            return f"Tool execution error: {e}", True


class SubAgentToolExecutor:
    """
    Restricted tool executor for sub-agents.
    Only allows tools in the whitelist.
    """

    def __init__(self, registry: ToolRegistry, allowed_tools: set[str]):
        self.registry = registry
        self.allowed_tools = allowed_tools

    def execute(self, tool_name: str, tool_input: str) -> tuple[str, bool]:
        """Execute a tool with whitelist restriction."""
        if tool_name not in self.allowed_tools:
            return f"Tool '{tool_name}' is not available for this agent.", True

        spec = self.registry.get_spec(tool_name)
        if spec is None:
            return f"Unknown tool: {tool_name}", True

        if spec.handler is None:
            return f"Tool '{tool_name}' has no handler", True

        try:
            parsed_input = json.loads(tool_input) if tool_input else {}
            result = spec.handler(**parsed_input)
            return str(result), False
        except Exception as e:
            return f"Tool execution error: {e}", True
