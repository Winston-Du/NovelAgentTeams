#!/usr/bin/env python
"""
系统测试用例 - 自动验证所有组件
"""
import sys
import os
from pathlib import Path
import yaml

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest
from unittest.mock import Mock, patch


class TestInitialization(unittest.TestCase):
    """测试初始化检查"""

    def setUp(self):
        """测试前准备"""
        self.project_root = Path(__file__).parent.parent

    def test_design_documents_exist(self):
        """测试设计文档是否存在"""
        design_dir = self.project_root / "DESIGN"
        required_files = [
            "BRAINSTORM_SUMMARY.md",
            "WORKFLOW.md",
            "AGENTS_DEFINITION.md",
            "DATA_STRUCTURES.md",
            "PROMPTS/chief_editor_prompt.md",
            "PROMPTS/character_designer_prompt.md",
            "PROMPTS/plot_writer_prompt.md",
            "PROMPTS/proofreader_prompt.md",
        ]

        for file in required_files:
            file_path = design_dir / file
            self.assertTrue(
                file_path.exists(),
                f"设计文档缺失: {file}"
            )
            self.assertGreater(
                file_path.stat().st_size,
                100,
                f"设计文档内容过少: {file}"
            )

    def test_environment_variables(self):
        """测试环境变量配置"""
        api_key = os.getenv('COMPANY_API_KEY')

        self.assertIsNotNone(
            api_key,
            "环境变量 COMPANY_API_KEY 未设置"
        )

        self.assertIn(
            ':',
            api_key,
            "COMPANY_API_KEY 格式不正确（应为 APP_ID:APP_KEY）"
        )

    def test_character_cards_format(self):
        """测试人物卡库格式"""
        cards_file = self.project_root / "src" / "novels_project" / "config" / "character_base_cards.yaml"

        if not cards_file.exists():
            self.skipTest("人物卡库文件不存在，跳过测试")

        with open(cards_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        self.assertIsNotNone(data, "人物卡库为空")

        # 检查 S 级人物
        if 's_tier' in data:
            s_tier = data['s_tier']
            self.assertIn('characters', s_tier, "S级人物缺少 characters 字段")

            characters = s_tier['characters']
            self.assertGreater(
                len(characters),
                0,
                "S级人物数量为0"
            )

            # 检查第一个人物的必填字段
            for name, char in characters.items():
                required_fields = ['name', 'role', 'core_personality', 'unique_speaking_style']
                for field in required_fields:
                    self.assertIn(
                        field,
                        char,
                        f"人物 {name} 缺少必填字段: {field}"
                    )
                break  # 只检查第一个


class TestComponents(unittest.TestCase):
    """测试各个组件"""

    def setUp(self):
        """测试前准备"""
        self.project_root = Path(__file__).parent.parent

    def test_logger_creation(self):
        """测试日志管理器创建"""
        from novels_project.logger import ExecutionLogger, MetricsCollector

        logger = ExecutionLogger(log_dir="logs/test_execution")
        self.assertIsNotNone(logger)

        metrics = MetricsCollector(metrics_dir="logs/test_metrics")
        self.assertIsNotNone(metrics)

    def test_retrieval_engine_initialization(self):
        """测试向量库引擎初始化"""
        try:
            from novels_project.retrieval_engine import SampleRetrievalEngine

            # Mock 环境变量
            with patch.dict(os.environ, {'COMPANY_API_KEY': 'test:key'}):
                engine = SampleRetrievalEngine(
                    sample_dir="samples",
                    persist_dir="vector_db/test_data"
                )
                self.assertIsNotNone(engine)

        except ImportError as e:
            self.skipTest(f"依赖包未安装: {e}")

    def test_sample_retriever_tool(self):
        """测试样例检索工具（现在是普通函数）"""
        try:
            from novels_project.tools.sample_retriever import retrieve_writing_samples

            self.assertIsNotNone(retrieve_writing_samples)
            # 现在是普通可调用函数，不再有 CrewAI 的 run() 方法
            self.assertTrue(callable(retrieve_writing_samples))

        except ImportError as e:
            self.skipTest(f"依赖包未安装: {e}")


class TestRuntime(unittest.TestCase):
    """测试新架构 Runtime"""

    def setUp(self):
        """测试前准备"""
        self.project_root = Path(__file__).parent.parent

    def test_agent_definitions(self):
        """测试 4 个 Agent 定义"""
        from novels_project.agents import ALL_AGENTS

        self.assertEqual(len(ALL_AGENTS), 4)

        agent_names = [a.name for a in ALL_AGENTS]
        self.assertIn('chief_editor', agent_names)
        self.assertIn('character_designer', agent_names)
        self.assertIn('plot_writer', agent_names)
        self.assertIn('proofreader', agent_names)

    def test_agent_models(self):
        """测试 Agent 模型配置"""
        from novels_project.agents import ALL_AGENTS

        for agent in ALL_AGENTS:
            self.assertIsNotNone(agent.model)
            if agent.name in ['chief_editor', 'proofreader']:
                self.assertEqual(agent.model, 'gemini-3-pro')
            else:
                self.assertEqual(agent.model, 'glm-5')

    def test_tool_registry(self):
        """测试工具注册表"""
        from novels_project.tool_spec import build_builtin_tool_registry

        registry = build_builtin_tool_registry()
        specs = registry.all_specs()

        self.assertGreater(len(specs), 10)

        # 检查关键工具存在
        tool_names = [s.name for s in specs]
        self.assertIn('retrieve_writing_samples', tool_names)
        self.assertIn('check_character_voice', tool_names)
        self.assertIn('update_character_card', tool_names)
        self.assertIn('fix_chapter_issue', tool_names)

    def test_session_model(self):
        """测试 Session 数据模型"""
        from novels_project.session import Session, ConversationMessage

        session = Session()
        session.messages.append(ConversationMessage.user_text('hello'))

        self.assertEqual(session.message_count(), 1)

        # 测试序列化
        json_str = session.to_json()
        restored = Session.from_json(json_str)
        self.assertEqual(restored.message_count(), 1)

    def test_system_prompt_builder(self):
        """测试系统提示构建"""
        from novels_project.system_prompt import (
            build_main_agent_system_prompt,
            build_sub_agent_system_prompt,
        )

        main_prompt = build_main_agent_system_prompt()
        self.assertGreater(len(main_prompt), 100)

        for agent_name in ['chief_editor', 'character_designer', 'plot_writer', 'proofreader']:
            prompt = build_sub_agent_system_prompt(agent_name)
            self.assertGreater(len(prompt), 100)


class TestEndToEnd(unittest.TestCase):
    """端到端测试（需要真实 API）"""

    @unittest.skip("需要真实 API，手动运行")
    def test_chapter_1_creation(self):
        """测试第 1 章创作流程"""
        from novels_project.cli import _build_runtime

        runtime, session_id = _build_runtime()
        summary = runtime.run_turn("创作第1章")

        self.assertGreater(summary.iterations, 0)


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestComponents))
    suite.addTests(loader.loadTestsFromTestCase(TestRuntime))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 60)
    print("小说创作系统 - 自动测试")
    print("=" * 60)
    print()

    success = run_tests()

    print()
    print("=" * 60)
    if success:
        print("所有测试通过！")
        sys.exit(0)
    else:
        print("部分测试失败，请检查错误信息")
        sys.exit(1)
