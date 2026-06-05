"""
单元测试：Agent 模块测试

测试范围：
1. Agent 配置管理
2. Agent 定义验证
3. Agent 运行器功能
4. 边缘条件测试
"""

import pytest
from novels_project.agents import (
    ALL_AGENTS, CHIEF_EDITOR, CHARACTER_DESIGNER, PLOT_WRITER, PROOFREADER,
    AgentRunner, AgentDefinition, register_agent_tools
)
from novels_project.tool_spec import ToolRegistry


class TestAgentDefinitions:
    """测试 Agent 定义的正确性"""

    def test_all_agents_defined(self):
        """验证所有 Agent 已定义"""
        assert len(ALL_AGENTS) == 4
        agent_names = {a.name for a in ALL_AGENTS}
        assert agent_names == {"chief_editor", "character_designer", "plot_writer", "proofreader"}

    def test_chief_editor_definition(self):
        """验证总编 Agent 定义"""
        assert CHIEF_EDITOR.name == "chief_editor"
        assert CHIEF_EDITOR.display_name == "小说总编"
        assert "章大纲" in CHIEF_EDITOR.description
        assert CHIEF_EDITOR.input_schema["required"] == ["prompt"]

    def test_character_designer_definition(self):
        """验证人物设计师 Agent 定义"""
        assert CHARACTER_DESIGNER.name == "character_designer"
        assert CHARACTER_DESIGNER.display_name == "人物策划设计师"
        assert "人物状态卡" in CHARACTER_DESIGNER.description

    def test_plot_writer_definition(self):
        """验证剧情撰写员 Agent 定义"""
        assert PLOT_WRITER.name == "plot_writer"
        assert PLOT_WRITER.display_name == "剧情撰写员"
        assert PLOT_WRITER.allowed_tools is not None
        assert len(PLOT_WRITER.allowed_tools) > 0

    def test_proofreader_definition(self):
        """验证校对 Agent 定义"""
        assert PROOFREADER.name == "proofreader"
        assert PROOFREADER.display_name == "资深校对"
        assert "章节质量" in PROOFREADER.description

    def test_agent_input_schema(self):
        """验证输入 schema 格式正确"""
        for agent in ALL_AGENTS:
            assert "type" in agent.input_schema
            assert "properties" in agent.input_schema
            assert "prompt" in agent.input_schema["properties"]

    def test_agent_names_are_unique(self):
        """验证所有 Agent 名称唯一"""
        names = [a.name for a in ALL_AGENTS]
        assert len(names) == len(set(names)), "Agent 名称重复"

    def test_agent_display_names_not_empty(self):
        """验证所有 Agent 显示名称非空"""
        for agent in ALL_AGENTS:
            assert agent.display_name is not None
            assert len(agent.display_name.strip()) > 0

    def test_agent_descriptions_not_empty(self):
        """验证所有 Agent 描述非空"""
        for agent in ALL_AGENTS:
            assert agent.description is not None
            assert len(agent.description.strip()) > 0


class TestAgentRunner:
    """测试 Agent 运行器"""

    def test_is_agent_tool(self):
        """验证工具名称识别"""
        runner = AgentRunner(api_client=None)
        assert runner.is_agent_tool("chief_editor") is True
        assert runner.is_agent_tool("unknown_tool") is False

    def test_agent_defs_populated(self):
        """验证 Agent 定义已加载"""
        runner = AgentRunner(api_client=None)
        assert "chief_editor" in runner._agent_defs
        assert "character_designer" in runner._agent_defs
        assert "plot_writer" in runner._agent_defs
        assert "proofreader" in runner._agent_defs

    def test_is_agent_tool_case_sensitive(self):
        """验证工具名称识别区分大小写"""
        runner = AgentRunner(api_client=None)
        assert runner.is_agent_tool("chief_editor") is True
        assert runner.is_agent_tool("Chief_Editor") is False
        assert runner.is_agent_tool("CHIEF_EDITOR") is False

    def test_is_agent_tool_with_empty_string(self):
        """验证空字符串返回 False"""
        runner = AgentRunner(api_client=None)
        assert runner.is_agent_tool("") is False

    def test_is_agent_tool_with_special_characters(self):
        """验证特殊字符工具名返回 False"""
        runner = AgentRunner(api_client=None)
        assert runner.is_agent_tool("agent@tool") is False
        assert runner.is_agent_tool("agent/tool") is False
        assert runner.is_agent_tool("agent tool") is False


class TestAgentToolRegistration:
    """测试 Agent 工具注册"""

    def test_register_agent_tools(self):
        """验证工具注册功能"""
        registry = ToolRegistry()
        register_agent_tools(registry)
        
        for agent in ALL_AGENTS:
            assert registry.has(agent.name)
            spec = registry.get_spec(agent.name)
            assert spec is not None
            assert spec.name == agent.name
            assert spec.description == agent.description

    def test_register_tools_empty_registry(self):
        """验证向空注册表注册工具"""
        registry = ToolRegistry()
        assert len(registry.all_specs()) == 0
        register_agent_tools(registry)
        assert len(registry.all_specs()) == 4

    def test_register_tools_twice(self):
        """验证重复注册工具不会报错"""
        registry = ToolRegistry()
        register_agent_tools(registry)
        initial_count = len(registry.all_specs())
        register_agent_tools(registry)
        assert len(registry.all_specs()) == initial_count

    def test_register_tools_preserves_other_tools(self):
        """验证注册 Agent 工具不影响已存在的工具"""
        from novels_project.tool_spec import ToolSpec
        registry = ToolRegistry()
        custom_tool = ToolSpec(
            name="custom_tool",
            description="自定义工具",
            input_schema={"type": "object", "properties": {"param": {"type": "string"}}}
        )
        registry.register(custom_tool)
        assert registry.has("custom_tool")
        
        register_agent_tools(registry)
        
        assert registry.has("custom_tool")
        assert registry.has("chief_editor")
        assert len(registry.all_specs()) == 5


class TestAgentDefinitionEdgeCases:
    """测试 Agent 定义的边缘条件"""

    def test_agent_with_empty_description(self):
        """测试创建描述为空的 Agent（边界情况）"""
        agent = AgentDefinition(
            name="test_agent",
            display_name="测试 Agent",
            model="test-model",
            description="",
            allowed_tools=[],
            input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}}
        )
        assert agent.name == "test_agent"
        assert agent.description == ""

    def test_agent_with_long_name(self):
        """测试长名称 Agent"""
        long_name = "a" * 100
        agent = AgentDefinition(
            name=long_name,
            display_name="测试 Agent",
            model="test-model",
            description="测试描述",
            allowed_tools=[],
            input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}}
        )
        assert agent.name == long_name

    def test_agent_allowed_tools_empty_list(self):
        """测试 allowed_tools 为空列表"""
        agent = AgentDefinition(
            name="test_agent",
            display_name="测试 Agent",
            model="test-model",
            description="测试描述",
            allowed_tools=[],
            input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}}
        )
        assert agent.allowed_tools == []

    def test_input_schema_without_required(self):
        """测试输入 schema 没有 required 字段"""
        agent = AgentDefinition(
            name="test_agent",
            display_name="测试 Agent",
            model="test-model",
            description="测试描述",
            allowed_tools=[],
            input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}}
        )
        assert "required" not in agent.input_schema

    def test_agent_with_special_characters_in_name(self):
        """测试名称包含特殊字符的 Agent"""
        agent = AgentDefinition(
            name="agent_with_underscore",
            display_name="测试 Agent",
            model="test-model",
            description="测试描述",
            allowed_tools=[],
            input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}}
        )
        assert agent.name == "agent_with_underscore"


class TestAgentRunnerEdgeCases:
    """测试 Agent 运行器边缘条件"""

    def test_runner_with_none_api_client(self):
        """测试 API 客户端为 None"""
        runner = AgentRunner(api_client=None)
        assert runner is not None
        assert runner.api_client is None

    def test_get_agent_def_nonexistent(self):
        """测试获取不存在的 Agent 定义"""
        runner = AgentRunner(api_client=None)
        assert "nonexistent_agent" not in runner._agent_defs

    def test_runner_has_all_agents(self):
        """测试运行器包含所有 Agent"""
        runner = AgentRunner(api_client=None)
        agent_names = set(runner._agent_defs.keys())
        expected_names = {"chief_editor", "character_designer", "plot_writer", "proofreader"}
        assert agent_names == expected_names


class TestAgentRunnerAdvanced:
    """测试 Agent 运行器高级功能"""

    def test_set_builtin_registry(self):
        """测试设置内置工具注册表"""
        runner = AgentRunner(api_client=None)
        registry = ToolRegistry()
        
        runner.set_builtin_registry(registry)
        assert runner._builtin_registry is registry

    def test_set_builtin_registry_twice(self):
        """测试重复设置工具注册表"""
        runner = AgentRunner(api_client=None)
        registry1 = ToolRegistry()
        registry2 = ToolRegistry()
        
        runner.set_builtin_registry(registry1)
        runner.set_builtin_registry(registry2)
        assert runner._builtin_registry is registry2

    def test_runner_with_empty_builtin_registry(self):
        """测试运行器使用空的内置注册表"""
        runner = AgentRunner(api_client=None)
        assert runner._builtin_registry is None

    def test_runner_has_all_agents(self):
        """测试运行器包含所有 Agent 定义"""
        runner = AgentRunner(api_client=None)
        agent_names = set(runner._agent_defs.keys())
        expected_names = {"chief_editor", "character_designer", "plot_writer", "proofreader"}
        assert agent_names == expected_names

    def test_agent_defs_access(self):
        """测试访问 Agent 定义"""
        runner = AgentRunner(api_client=None)
        chief_editor = runner._agent_defs.get("chief_editor")
        assert chief_editor is not None
        assert chief_editor.name == "chief_editor"


class TestAgentToolFunctions:
    """测试工具构建函数"""

    def test_build_save_chapter_tool(self):
        """测试构建保存章节工具"""
        from novels_project.agents import build_save_chapter_tool
        tool = build_save_chapter_tool()
        
        assert tool.name == "save_chapter"
        assert "保存章节输出文件" in tool.description
        assert "chapter_id" in tool.input_schema["properties"]
        assert "content" in tool.input_schema["properties"]
        assert tool.input_schema["required"] == ["chapter_id", "content"]
        assert tool.handler is not None

    def test_build_load_chapter_data_tool(self):
        """测试构建加载章节数据工具"""
        from novels_project.agents import build_load_chapter_data_tool
        tool = build_load_chapter_data_tool()
        
        assert tool.name == "load_chapter_data"
        assert "加载章节创作所需的输入数据" in tool.description
        assert "chapter_id" in tool.input_schema["properties"]
        assert tool.input_schema["required"] == ["chapter_id"]
        assert tool.handler is not None

    def test_register_agent_tools_preserves_existing(self):
        """测试注册 Agent 工具保留现有工具"""
        registry = ToolRegistry()
        from novels_project.tool_spec import ToolSpec
        
        custom_tool = ToolSpec(
            name="custom_tool",
            description="自定义工具",
            input_schema={"type": "object", "properties": {"param": {"type": "string"}}}
        )
        registry.register(custom_tool)
        
        assert registry.has("custom_tool")
        initial_count = len(registry.all_specs())
        
        register_agent_tools(registry)
        
        assert registry.has("custom_tool")
        assert registry.has("chief_editor")
        assert len(registry.all_specs()) == initial_count + 4


class TestAgentDefinitionValidation:
    """测试 Agent 定义验证"""

    def test_agent_definition_with_empty_allowed_tools(self):
        """测试空 allowed_tools 的 Agent"""
        agent = AgentDefinition(
            name="test_agent",
            display_name="测试 Agent",
            model="test-model",
            description="测试描述",
            allowed_tools=[],
            input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}}
        )
        assert agent.allowed_tools == []

    def test_agent_definition_with_none_model(self):
        """测试 model 为 None 的 Agent"""
        agent = AgentDefinition(
            name="test_agent",
            display_name="测试 Agent",
            model=None,
            description="测试描述",
            allowed_tools=[],
            input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}}
        )
        assert agent.model is None

    def test_agent_definition_compare(self):
        """测试 Agent 定义比较"""
        agent1 = AgentDefinition(
            name="agent1",
            display_name="Agent 1",
            model="model1",
            description="desc1",
            allowed_tools=["tool1"],
            input_schema={"type": "object"}
        )
        agent2 = AgentDefinition(
            name="agent2",
            display_name="Agent 2",
            model="model2",
            description="desc2",
            allowed_tools=["tool2"],
            input_schema={"type": "object"}
        )
        assert agent1.name != agent2.name
        assert agent1.model != agent2.model


class TestAgentDescriptionContent:
    """测试 Agent 描述内容"""

    def test_chief_editor_description(self):
        """验证总编描述包含关键职责"""
        assert "章节大纲" in CHIEF_EDITOR.description
        assert "story_structure" in CHIEF_EDITOR.description

    def test_character_designer_description(self):
        """验证人物设计师描述包含关键职责"""
        assert "人物状态卡" in CHARACTER_DESIGNER.description
        assert "chapter_arc" in CHARACTER_DESIGNER.description or "behavior_this_chapter" in CHARACTER_DESIGNER.description

    def test_plot_writer_description(self):
        """验证剧情撰写员描述包含关键职责"""
        assert "剧情" in PLOT_WRITER.description or "故事" in PLOT_WRITER.description

    def test_proofreader_description(self):
        """验证校对描述包含关键职责"""
        assert "校对" in PROOFREADER.description or "质量" in PROOFREADER.description


class TestAgentRunnerRunAgent:
    """测试 AgentRunner.run_agent 执行流程（Mocked）"""

    def test_run_agent_basic_flow(self):
        """测试基本执行流程 - 使用 mock"""
        import json
        import unittest.mock

        # Mock ConversationRuntime
        mock_runtime_cls = unittest.mock.Mock()
        mock_runtime_instance = unittest.mock.MagicMock()
        mock_summary = unittest.mock.MagicMock()
        mock_summary.iterations = 1
        mock_summary.get_final_text.return_value = "Agent 执行结果文本"
        mock_runtime_instance.run_turn.return_value = mock_summary
        mock_runtime_cls.return_value = mock_runtime_instance

        # 替换源模块的 ConversationRuntime（run_agent 内部 from .runtime import）
        import novels_project.runtime as runtime_module
        original_runtime = runtime_module.ConversationRuntime
        runtime_module.ConversationRuntime = mock_runtime_cls

        try:
            runner = AgentRunner(api_client=None)
            tool_input = json.dumps({"prompt": "测试提示词"})

            result = runner.run_agent("chief_editor", tool_input)

            # 验证返回了结果
            assert "Agent 执行结果文本" in result

            # 验证 ConversationRuntime 被正确调用
            call_kwargs = mock_runtime_cls.call_args.kwargs
            assert call_kwargs["model"] == "gemini-3-pro"
            assert "system_prompt" in call_kwargs
            assert call_kwargs["max_iterations"] == 20

        finally:
            runtime_module.ConversationRuntime = original_runtime

    def test_run_agent_no_text_output(self):
        """测试 Agent 无文本输出时的降级处理"""
        import json
        import unittest.mock

        mock_runtime_cls = unittest.mock.Mock()
        mock_runtime_instance = unittest.mock.MagicMock()
        mock_summary = unittest.mock.MagicMock()
        mock_summary.iterations = 0
        mock_summary.get_final_text.return_value = ""
        mock_runtime_instance.run_turn.return_value = mock_summary
        mock_runtime_cls.return_value = mock_runtime_instance

        import novels_project.runtime as runtime_module
        original_runtime = runtime_module.ConversationRuntime
        runtime_module.ConversationRuntime = mock_runtime_cls

        try:
            runner = AgentRunner(api_client=None)
            tool_input = json.dumps({"prompt": "测试"})

            result = runner.run_agent("proofreader", tool_input)
            assert "(Sub-agent produced no text output)" in result
        finally:
            runtime_module.ConversationRuntime = original_runtime

    def test_run_agent_all_four_agents(self):
        """测试所有 4 个 Agent 都可以被调用"""
        import json
        import unittest.mock

        mock_runtime_cls = unittest.mock.Mock()
        mock_runtime_instance = unittest.mock.MagicMock()
        mock_summary = unittest.mock.MagicMock()
        mock_summary.iterations = 1
        mock_summary.get_final_text.return_value = "Output"
        mock_runtime_instance.run_turn.return_value = mock_summary
        mock_runtime_cls.return_value = mock_runtime_instance

        import novels_project.runtime as runtime_module
        original_runtime = runtime_module.ConversationRuntime
        runtime_module.ConversationRuntime = mock_runtime_cls

        try:
            runner = AgentRunner(api_client=None)
            agents = ["chief_editor", "character_designer", "plot_writer", "proofreader"]

            for agent_name in agents:
                tool_input = json.dumps({"prompt": f"测试 {agent_name}"})
                result = runner.run_agent(agent_name, tool_input)
                assert len(result) > 0
        finally:
            runtime_module.ConversationRuntime = original_runtime

    def test_run_agent_parses_json_input(self):
        """测试正确解析 JSON 输入"""
        import json
        import unittest.mock

        mock_runtime_cls = unittest.mock.Mock()
        mock_runtime_instance = unittest.mock.MagicMock()
        mock_summary = unittest.mock.MagicMock()
        mock_summary.iterations = 1
        mock_summary.get_final_text.return_value = "Done"
        mock_runtime_instance.run_turn.return_value = mock_summary
        mock_runtime_cls.return_value = mock_runtime_instance

        import novels_project.runtime as runtime_module
        original_runtime = runtime_module.ConversationRuntime
        runtime_module.ConversationRuntime = mock_runtime_cls

        try:
            runner = AgentRunner(api_client=None)
            tool_input = json.dumps({"prompt": "Hello World"})

            runner.run_agent("chief_editor", tool_input)

            # 验证 run_turn 收到正确 prompt
            mock_runtime_instance.run_turn.assert_called_once_with("Hello World")
        finally:
            runtime_module.ConversationRuntime = original_runtime

    def test_run_agent_with_allowed_tools(self):
        """测试 agent 带 allowed_tools 时过滤工具注册"""
        import json
        import unittest.mock

        from novels_project.tool_spec import ToolRegistry, ToolSpec
        registry = ToolRegistry()
        tool = ToolSpec(
            name="allowed_tool",
            description="测试工具",
            input_schema={"type": "object", "properties": {}}
        )
        registry.register(tool)

        mock_runtime_cls = unittest.mock.Mock()
        mock_runtime_instance = unittest.mock.MagicMock()
        mock_summary = unittest.mock.MagicMock()
        mock_summary.iterations = 1
        mock_summary.get_final_text.return_value = "Output"
        mock_runtime_instance.run_turn.return_value = mock_summary
        mock_runtime_cls.return_value = mock_runtime_instance

        import novels_project.runtime as runtime_module
        original_runtime = runtime_module.ConversationRuntime
        runtime_module.ConversationRuntime = mock_runtime_cls

        try:
            runner = AgentRunner(api_client=None)
            runner.set_builtin_registry(registry)
            tool_input = json.dumps({"prompt": "Test"})

            result = runner.run_agent("plot_writer", tool_input)
            assert result is not None
        finally:
            runtime_module.ConversationRuntime = original_runtime


class TestSaveChapterTool:
    """测试 save_chapter 工具处理函数"""

    def test_save_chapter_basic(self, tmp_path, monkeypatch):
        """测试基本保存章节功能"""
        from novels_project.agents import build_save_chapter_tool

        tool = build_save_chapter_tool()
        handler = tool.handler

        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"

        monkeypatch.setattr(
            "novels_project.project_config.get_chapters_dir", lambda: chapters_dir
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_summaries_dir", lambda: summaries_dir
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_output_dir", lambda: tmp_path
        )

        result = handler(1, "第一章内容")
        assert "已保存章节" in result
        chapter_file = chapters_dir / "chapter_1_final.md"
        assert chapter_file.exists()
        content = chapter_file.read_text(encoding="utf-8")
        assert "# 第 1 章" in content
        assert "第一章内容" in content

    def test_save_chapter_with_summary(self, tmp_path, monkeypatch):
        """测试保存章节含摘要"""
        from novels_project.agents import build_save_chapter_tool

        tool = build_save_chapter_tool()
        handler = tool.handler

        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"

        monkeypatch.setattr(
            "novels_project.project_config.get_chapters_dir", lambda: chapters_dir
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_summaries_dir", lambda: summaries_dir
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_output_dir", lambda: tmp_path
        )

        summary = "characters:\n  - name: 主角"
        result = handler(5, "第五章内容", summary_yaml=summary)

        assert "已保存摘要" in result
        summary_file = summaries_dir / "chapter_5_summary.yaml"
        assert summary_file.exists()
        assert summary_file.read_text(encoding="utf-8") == summary

    def test_save_chapter_with_raw_output(self, tmp_path, monkeypatch):
        """测试保存章节含原始输出"""
        from novels_project.agents import build_save_chapter_tool

        tool = build_save_chapter_tool()
        handler = tool.handler

        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"
        raw_dir = tmp_path / "raw_outputs"

        monkeypatch.setattr(
            "novels_project.project_config.get_chapters_dir", lambda: chapters_dir
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_summaries_dir", lambda: summaries_dir
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_output_dir", lambda: tmp_path
        )

        raw = "raw_data: test"
        result = handler(3, "第三章", raw_output=raw)

        assert "已保存原始输出" in result
        raw_file = raw_dir / "chapter_3_raw.yaml"
        assert raw_file.exists()
        assert raw_file.read_text(encoding="utf-8") == raw

    def test_save_chapter_all_fields(self, tmp_path, monkeypatch):
        """测试保存章节所有字段"""
        from novels_project.agents import build_save_chapter_tool

        tool = build_save_chapter_tool()
        handler = tool.handler

        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"

        monkeypatch.setattr(
            "novels_project.project_config.get_chapters_dir", lambda: chapters_dir
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_summaries_dir", lambda: summaries_dir
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_output_dir", lambda: tmp_path
        )

        result = handler(
            10,
            "第十章全文",
            summary_yaml="summary: data",
            raw_output="raw: data"
        )
        assert "已保存章节" in result
        assert "已保存摘要" in result
        assert "已保存原始输出" in result


class TestLoadChapterDataTool:
    """测试 load_chapter_data 工具处理函数"""

    def test_load_chapter_data_no_file(self, tmp_path, monkeypatch):
        """测试加载章节数据 - 文件不存在"""
        from novels_project.agents import build_load_chapter_data_tool

        tool = build_load_chapter_data_tool()
        handler = tool.handler

        cards_path = tmp_path / "nonexistent.yaml"
        monkeypatch.setattr(
            "novels_project.project_config.get_character_cards_path",
            lambda: cards_path
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_summaries_dir",
            lambda: tmp_path / "summaries"
        )

        result = handler(1)
        assert "Error" in result or "人物卡" in result
        assert "不存在" in result or "请创建" in result or "Error" in result

    def test_load_chapter_data_with_cards(self, tmp_path, monkeypatch):
        """测试加载章节数据 - 人物卡文件存在"""
        import yaml
        from novels_project.agents import build_load_chapter_data_tool

        tool = build_load_chapter_data_tool()
        handler = tool.handler

        cards_path = tmp_path / "character_cards.yaml"
        cards_data = {
            "metadata": {"version": "1.0", "protagonist": "主角"},
            "s_tier": {
                "characters": {
                    "主角": {
                        "name": "主角",
                        "role": "主角",
                        "core_personality": ["勇敢", "正直"],
                        "unique_speaking_style": {
                            "tone": "坚定",
                            "example_dialogues": ["我会保护大家！"]
                        }
                    }
                }
            }
        }
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump(cards_data, f, allow_unicode=True)

        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir(exist_ok=True)

        monkeypatch.setattr(
            "novels_project.project_config.get_character_cards_path",
            lambda: cards_path
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_summaries_dir",
            lambda: summaries_dir
        )

        result = handler(1)
        assert "人物卡库" in result or "主角" in result or "s_tier" in result

    def test_load_chapter_data_with_prev_summary(self, tmp_path, monkeypatch):
        """测试加载章节数据 - 前章摘要存在（覆盖 lines 323-326, 346）"""
        import yaml
        from novels_project.agents import build_load_chapter_data_tool

        tool = build_load_chapter_data_tool()
        handler = tool.handler

        # 创建人物卡文件
        cards_path = tmp_path / "character_cards.yaml"
        cards_data = {
            "metadata": {"version": "1.0", "protagonist": "主角", "story_world": "修真世界"},
            "s_tier": {"characters": {}}
        }
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump(cards_data, f, allow_unicode=True)

        # 创建前章摘要文件
        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir(exist_ok=True)
        prev_summary_path = summaries_dir / "chapter_1_summary.yaml"
        prev_summary_path.write_text("summary: 前章摘要内容", encoding="utf-8")

        monkeypatch.setattr(
            "novels_project.project_config.get_character_cards_path",
            lambda: cards_path
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_summaries_dir",
            lambda: summaries_dir
        )

        result = handler(2)
        assert "前章摘要" in result
        assert "前章摘要内容" in result
        assert "无（第1章或前章摘要不存在）" not in result

    def test_load_chapter_data_chapter_1_no_prev_summary(self, tmp_path, monkeypatch):
        """测试加载章节数据 - 第1章无前章摘要（覆盖 line 346 else 分支）"""
        import yaml
        from novels_project.agents import build_load_chapter_data_tool

        tool = build_load_chapter_data_tool()
        handler = tool.handler

        cards_path = tmp_path / "character_cards.yaml"
        cards_data = {
            "metadata": {"version": "1.0", "protagonist": "主角"},
            "s_tier": {"characters": {}}
        }
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump(cards_data, f, allow_unicode=True)

        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir(exist_ok=True)

        monkeypatch.setattr(
            "novels_project.project_config.get_character_cards_path",
            lambda: cards_path
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_summaries_dir",
            lambda: summaries_dir
        )

        result = handler(1)
        assert "无（第1章或前章摘要不存在）" in result

    def test_load_chapter_data_chapter_2_no_prev_file(self, tmp_path, monkeypatch):
        """测试加载章节数据 - 第2章但前章摘要文件不存在"""
        import yaml
        from novels_project.agents import build_load_chapter_data_tool

        tool = build_load_chapter_data_tool()
        handler = tool.handler

        cards_path = tmp_path / "character_cards.yaml"
        cards_data = {
            "metadata": {"version": "1.0", "protagonist": "主角"},
            "s_tier": {"characters": {}}
        }
        with open(cards_path, "w", encoding="utf-8") as f:
            yaml.dump(cards_data, f, allow_unicode=True)

        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir(exist_ok=True)

        monkeypatch.setattr(
            "novels_project.project_config.get_character_cards_path",
            lambda: cards_path
        )
        monkeypatch.setattr(
            "novels_project.project_config.get_summaries_dir",
            lambda: summaries_dir
        )

        result = handler(2)
        assert "无（第1章或前章摘要不存在）" in result


class TestAgentRunnerRunAgentToolNotFound:
    """测试 run_agent 中工具不在 builtin_registry 的情况（覆盖 line 189）"""

    def test_run_agent_tool_not_in_registry(self):
        """测试 allowed_tools 中的工具名不存在于 builtin_registry（spec is None）"""
        import json
        import unittest.mock

        from novels_project.tool_spec import ToolRegistry, ToolSpec

        # 创建一个只包含部分工具的 registry
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name="retrieve_writing_samples",
            description="测试",
            input_schema={"type": "object", "properties": {}}
        ))
        # 注意：不注册其他 plot_writer 需要的工具，如 check_character_voice 等

        mock_runtime_cls = unittest.mock.Mock()
        mock_runtime_instance = unittest.mock.MagicMock()
        mock_summary = unittest.mock.MagicMock()
        mock_summary.iterations = 1
        mock_summary.get_final_text.return_value = "Output"
        mock_runtime_instance.run_turn.return_value = mock_summary
        mock_runtime_cls.return_value = mock_runtime_instance

        import novels_project.runtime as runtime_module
        original_runtime = runtime_module.ConversationRuntime
        runtime_module.ConversationRuntime = mock_runtime_cls

        try:
            runner = AgentRunner(api_client=None)
            runner.set_builtin_registry(registry)
            tool_input = json.dumps({"prompt": "Test"})

            # plot_writer 有多个 allowed_tools，只有 retrieve_writing_samples 在 registry 中
            result = runner.run_agent("plot_writer", tool_input)
            assert result is not None

            # 验证 sub_executor 只注册了存在的工具
            call_kwargs = mock_runtime_cls.call_args.kwargs
            sub_executor = call_kwargs["tool_executor"]
            # 只有 retrieve_writing_samples 被注册了
            assert sub_executor.registry.has("retrieve_writing_samples")
            # 其他工具不应该被注册
            assert not sub_executor.registry.has("check_character_voice")
        finally:
            runtime_module.ConversationRuntime = original_runtime


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
