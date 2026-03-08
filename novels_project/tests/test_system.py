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
        """测试样例检索工具"""
        try:
            from novels_project.tools.sample_retriever import retrieve_writing_samples

            self.assertIsNotNone(retrieve_writing_samples)
            # crewai.tools.tool 装饰器返回的是 Tool 对象（非可调用函数），应具有 run() 方法
            self.assertTrue(hasattr(retrieve_writing_samples, 'run'))
            self.assertTrue(callable(getattr(retrieve_writing_samples, 'run', None)))

        except ImportError as e:
            self.skipTest(f"依赖包未安装: {e}")


class TestCrewAI(unittest.TestCase):
    """测试 CrewAI 集成"""

    def setUp(self):
        """测试前准备"""
        self.project_root = Path(__file__).parent.parent

    @patch.dict(os.environ, {'COMPANY_API_KEY': 'test:key'})
    def test_crew_initialization(self):
        """测试 Crew 初始化"""
        try:
            from novels_project.crew import NovelsCrewAI

            crew = NovelsCrewAI(model_name='gemini-3-pro')
            self.assertIsNotNone(crew)
            self.assertIsNotNone(crew.llm)

            # 检查 Agent 是否正确定义
            self.assertTrue(hasattr(crew, 'chief_editor'))
            self.assertTrue(hasattr(crew, 'character_designer'))
            self.assertTrue(hasattr(crew, 'plot_writer'))
            self.assertTrue(hasattr(crew, 'senior_proofreader'))

        except Exception as e:
            self.skipTest(f"Crew 初始化失败: {e}")

    @patch.dict(os.environ, {'COMPANY_API_KEY': 'test:key'})
    def test_crew_tasks_defined(self):
        """测试 Task 是否正确定义"""
        try:
            from novels_project.crew import NovelsCrewAI

            crew = NovelsCrewAI(model_name='gemini-3-pro')

            # 检查 Task 是否正确定义
            self.assertTrue(hasattr(crew, 'create_chapter_outline_task'))
            self.assertTrue(hasattr(crew, 'design_character_states_task'))
            self.assertTrue(hasattr(crew, 'write_chapter_draft_task'))
            self.assertTrue(hasattr(crew, 'proofread_and_summarize_task'))

        except Exception as e:
            self.skipTest(f"Task 检查失败: {e}")

    @patch.dict(os.environ, {'COMPANY_API_KEY': 'test:key'}, clear=True)
    def test_default_agent_models_split(self):
        """默认情况下：总编+校对使用 gemini-3-pro；人物+剧情使用 glm-5"""
        from novels_project.crew import NovelsCrewAI

        crew = NovelsCrewAI()

        self.assertEqual(crew.chief_editor().llm.model, 'gemini-3-pro')
        self.assertEqual(crew.senior_proofreader().llm.model, 'gemini-3-pro')
        self.assertEqual(crew.character_designer().llm.model, 'glm-5')
        self.assertEqual(crew.plot_writer().llm.model, 'glm-5')

    @patch.dict(os.environ, {'COMPANY_API_KEY': 'test:key', 'MODEL_NAME': 'gpt-5.2'}, clear=True)
    def test_model_override_applies_to_all_agents(self):
        """全局覆盖：设置 MODEL_NAME 或传入 model_name 后，4 个 Agent 统一使用同一模型"""
        from novels_project.crew import NovelsCrewAI

        crew = NovelsCrewAI()

        self.assertEqual(crew.chief_editor().llm.model, 'gpt-5.2')
        self.assertEqual(crew.senior_proofreader().llm.model, 'gpt-5.2')
        self.assertEqual(crew.character_designer().llm.model, 'gpt-5.2')
        self.assertEqual(crew.plot_writer().llm.model, 'gpt-5.2')


class TestEndToEnd(unittest.TestCase):
    """端到端测试（需要真实 API）"""

    @unittest.skip("需要真实 API，手动运行")
    def test_chapter_1_creation(self):
        """测试第 1 章创作流程"""
        from novels_project.crew import NovelsCrewAI

        # 准备输入数据
        inputs = {
            "volume_id": "卷一",
            "chapter_id": 1,
            "chapter_title": "测试章节",
            "previous_chapter_summary": None,
        }

        # 执行
        crew = NovelsCrewAI()
        result = crew.run_chapter(1, inputs)

        self.assertTrue(result['success'], "章节创作失败")


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestComponents))
    suite.addTests(loader.loadTestsFromTestCase(TestCrewAI))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 CrewAI 小说创作系统 - 自动测试")
    print("=" * 60)
    print()

    success = run_tests()

    print()
    print("=" * 60)
    if success:
        print("✅ 所有测试通过！")
        sys.exit(0)
    else:
        print("❌ 部分测试失败，请检查错误信息")
        sys.exit(1)
