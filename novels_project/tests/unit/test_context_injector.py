"""
单元测试：章节摘要提取和向量库存储功能

测试覆盖：
1. 章节摘要提取功能
2. 向量库存储功能（含各种边缘情况）
3. 上下文注入功能
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import unittest
from unittest.mock import MagicMock, patch, mock_open
from novels_project.context_injector import ContextInjector


class TestChapterSummaryExtraction(unittest.TestCase):
    """章节摘要提取测试"""
    
    def setUp(self):
        self.injector = ContextInjector()
    
    def test_extract_chapter_summary_with_title(self):
        """测试提取带标题的章节摘要"""
        chapter_text = """# 第三章：神秘山洞

林羽进入山洞深处，发现了一个古老的石棺。
棺盖上刻满了神秘的符文，散发着诡异的光芒。
他小心翼翼地推开棺盖，里面躺着一具保存完好的尸体。"""
        
        summary = self.injector.extract_chapter_summary(chapter_text)
        
        self.assertIn("【章节标题】第三章：神秘山洞", summary)
        self.assertIn("【内容摘要】", summary)
        self.assertIn("林羽进入山洞深处", summary)
        # 摘要长度应该在合理范围内
        self.assertLess(len(summary), 500)
    
    def test_extract_chapter_summary_without_title(self):
        """测试提取无标题的章节摘要"""
        chapter_text = """林羽进入山洞深处，发现了一个古老的石棺。
棺盖上刻满了神秘的符文，散发着诡异的光芒。"""
        
        summary = self.injector.extract_chapter_summary(chapter_text)
        
        self.assertNotIn("【章节标题】", summary)
        self.assertIn("【内容摘要】", summary)
        self.assertIn("林羽进入山洞深处", summary)
    
    def test_extract_chapter_summary_empty_content(self):
        """测试提取空内容的章节摘要"""
        chapter_text = ""
        summary = self.injector.extract_chapter_summary(chapter_text)
        self.assertEqual(summary, "【内容摘要】")
    
    def test_extract_chapter_summary_long_content(self):
        """测试提取超长内容的章节摘要（应被截断）"""
        long_text = "# 测试章节\n" + "这是一段很长的内容。" * 100
        summary = self.injector.extract_chapter_summary(long_text)
        
        # 摘要不应超过300字符（内容）+ 标题
        self.assertLess(len(summary), 400)
        self.assertIn("【章节标题】测试章节", summary)
    
    def test_extract_chapter_summary_with_markdown_headings(self):
        """测试提取包含二级标题的章节摘要（二级标题应被忽略）"""
        chapter_text = """# 第一章：开始
这是第一章的内容。

## 小节标题
这是小节内容。"""
        
        summary = self.injector.extract_chapter_summary(chapter_text)
        
        self.assertIn("【章节标题】第一章：开始", summary)
        self.assertIn("这是第一章的内容。", summary)
        # 二级标题不应出现在摘要中
        self.assertNotIn("小节标题", summary)


class TestVectorDbStorage(unittest.TestCase):
    """向量库存储测试"""
    
    def setUp(self):
        self.injector = ContextInjector()
    
    @patch('novels_project.context_injector.get_retrieval_engine')
    def test_add_chapter_to_vector_db_success(self, mock_get_engine):
        """测试成功添加章节到向量库"""
        # 创建模拟的检索引擎
        mock_engine = MagicMock()
        mock_engine._initialized = True
        mock_engine.vectorstore = MagicMock()
        mock_get_engine.return_value = mock_engine
        
        chapter_text = "# 测试章节\n测试内容"
        
        result = self.injector.add_chapter_to_vector_db(chapter_text, chapter_id=1)
        
        self.assertTrue(result)
        mock_engine.vectorstore.add_documents.assert_called_once()
        mock_engine.vectorstore.persist.assert_called_once()
    
    @patch('novels_project.context_injector.get_retrieval_engine')
    def test_add_chapter_to_vector_db_not_initialized(self, mock_get_engine):
        """测试向量库未初始化时的处理"""
        mock_engine = MagicMock()
        mock_engine._initialized = False
        mock_engine.vectorstore = MagicMock()
        mock_get_engine.return_value = mock_engine
        
        chapter_text = "# 测试章节\n测试内容"
        
        result = self.injector.add_chapter_to_vector_db(chapter_text, chapter_id=1)
        
        self.assertFalse(result)
        mock_engine.vectorstore.add_documents.assert_not_called()
    
    @patch('novels_project.context_injector.get_retrieval_engine')
    def test_add_chapter_to_vector_db_empty_vectorstore(self, mock_get_engine):
        """测试向量库对象为空时的处理"""
        mock_engine = MagicMock()
        mock_engine._initialized = True
        mock_engine.vectorstore = None
        mock_get_engine.return_value = mock_engine
        
        chapter_text = "# 测试章节\n测试内容"
        
        result = self.injector.add_chapter_to_vector_db(chapter_text, chapter_id=1)
        
        self.assertFalse(result)
    
    @patch('novels_project.context_injector.get_retrieval_engine')
    def test_add_chapter_to_vector_db_add_documents_failure(self, mock_get_engine):
        """测试添加文档失败时的处理"""
        mock_engine = MagicMock()
        mock_engine._initialized = True
        mock_engine.vectorstore = MagicMock()
        mock_engine.vectorstore.add_documents.side_effect = Exception("网络错误")
        mock_get_engine.return_value = mock_engine
        
        chapter_text = "# 测试章节\n测试内容"
        
        result = self.injector.add_chapter_to_vector_db(chapter_text, chapter_id=1)
        
        self.assertFalse(result)
    
    @patch('novels_project.context_injector.get_retrieval_engine')
    def test_add_chapter_to_vector_db_persist_failure(self, mock_get_engine):
        """测试持久化失败时的处理（不应影响整体结果）"""
        mock_engine = MagicMock()
        mock_engine._initialized = True
        mock_engine.vectorstore = MagicMock()
        mock_engine.vectorstore.persist.side_effect = Exception("权限不足")
        mock_get_engine.return_value = mock_engine
        
        chapter_text = "# 测试章节\n测试内容"
        
        result = self.injector.add_chapter_to_vector_db(chapter_text, chapter_id=1)
        
        # 持久化失败不应导致整体失败
        self.assertTrue(result)
    
    @patch('novels_project.context_injector.get_retrieval_engine')
    def test_add_chapter_to_vector_db_no_chapter_id(self, mock_get_engine):
        """测试不提供chapter_id时的处理"""
        mock_engine = MagicMock()
        mock_engine._initialized = True
        mock_engine.vectorstore = MagicMock()
        mock_get_engine.return_value = mock_engine
        
        chapter_text = "# 测试章节\n测试内容"
        
        result = self.injector.add_chapter_to_vector_db(chapter_text)
        
        self.assertTrue(result)
        mock_engine.vectorstore.add_documents.assert_called_once()


class TestContextInjector(unittest.TestCase):
    """上下文注入器综合测试"""
    
    def setUp(self):
        self.injector = ContextInjector()
    
    @patch('novels_project.context_injector.get_graph_integrator')
    def test_extract_character_names_from_graph(self, mock_get_integrator):
        """测试从图谱中识别角色名称"""
        # 创建模拟的图谱集成器
        mock_integrator = MagicMock()
        mock_integrator.is_initialized.return_value = True
        mock_graph_store = MagicMock()
        mock_graph_store.get_all_characters.return_value = [
            {"name": "林羽"},
            {"name": "苏晴"},
            {"name": "王师傅"}
        ]
        mock_integrator.graph_store = mock_graph_store
        mock_get_integrator.return_value = mock_integrator
        
        text = "林羽和苏晴一起前往青云宗"
        names = self.injector.extract_character_names(text)
        
        self.assertIn("林羽", names)
        self.assertIn("苏晴", names)
        self.assertNotIn("王师傅", names)  # 王师傅不在文本中
    
    @patch('novels_project.context_injector.get_graph_integrator')
    def test_extract_character_names_graph_not_initialized(self, mock_get_integrator):
        """测试图谱未初始化时使用正则表达式"""
        mock_integrator = MagicMock()
        mock_integrator.is_initialized.return_value = False
        mock_get_integrator.return_value = mock_integrator
        
        text = "林羽在山洞中发现了一本神秘的功法"
        names = self.injector.extract_character_names(text)
        
        # 当图谱未初始化时，使用正则表达式匹配
        self.assertIn("林羽", names)
    
    @patch('novels_project.context_injector.get_graph_integrator')
    def test_extract_character_names_no_names(self, mock_get_integrator):
        """测试不包含角色名称的文本"""
        mock_integrator = MagicMock()
        mock_integrator.is_initialized.return_value = True
        mock_graph_store = MagicMock()
        mock_graph_store.get_all_characters.return_value = []
        mock_integrator.graph_store = mock_graph_store
        mock_get_integrator.return_value = mock_integrator
        
        text = "今天天气很好，适合修炼"
        names = self.injector.extract_character_names(text)
        
        self.assertEqual(len(names), 0)
    
    @patch('novels_project.context_injector.get_graph_integrator')
    def test_inject_context_with_characters(self, mock_get_integrator):
        """测试注入角色上下文"""
        # 模拟图谱中有角色信息
        mock_integrator = MagicMock()
        mock_integrator.is_initialized.return_value = True
        mock_graph_store = MagicMock()
        mock_graph_store.get_all_characters.return_value = [{"name": "林羽"}]
        mock_integrator.graph_store = mock_graph_store
        mock_integrator.inject_graph_context_into_prompt.return_value = "林羽：青云宗外门弟子，修炼天赋惊人"
        mock_get_integrator.return_value = mock_integrator
        
        user_input = "让林羽修炼功法"
        result = self.injector.inject_context(user_input)
        
        # 应该包含上下文信息
        self.assertIn("【上下文信息】", result)
        self.assertIn("林羽：青云宗外门弟子", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)