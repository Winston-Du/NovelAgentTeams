"""
单元测试：反馈闭环模块

测试范围：
1. FeedbackStore 类的所有方法
2. get_feedback_store() 单例函数
"""
import pytest
import tempfile
import json
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from novels_project.feedback_loop import FeedbackStore, get_feedback_store


class TestFeedbackStoreInit:
    """测试 FeedbackStore 初始化"""

    def test_init_with_custom_dir(self, tmp_path):
        """使用自定义目录初始化"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        assert store.feedback_dir == tmp_path
        assert store.feedback_file == tmp_path / "proofreading_feedback.yaml"
        assert store.feedback_file.exists()

    def test_init_with_default_dir(self, tmp_path):
        """使用默认目录初始化（相对路径）"""
        import os
        cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            store = FeedbackStore(feedback_dir="feedback")
            # 相对路径被转换为 Path 对象，不 resolve
            assert store.feedback_dir == Path("feedback")
            assert store.feedback_file.exists()
        finally:
            os.chdir(cwd)

    def test_init_creates_nested_dir(self, tmp_path):
        """初始化创建嵌套目录"""
        nested = tmp_path / "a" / "b" / "c"
        store = FeedbackStore(feedback_dir=str(nested))
        assert nested.exists()
        assert store.feedback_file.exists()


class TestEnsureFileExists:
    """测试 _ensure_file_exists"""

    def test_creates_file_when_not_exists(self, tmp_path):
        """文件不存在时创建"""
        fpath = tmp_path / "proofreading_feedback.yaml"
        assert not fpath.exists()
        store = FeedbackStore(feedback_dir=str(tmp_path))
        assert fpath.exists()

    def test_does_not_overwrite_existing(self, tmp_path):
        """文件已存在时不覆盖"""
        fpath = tmp_path / "proofreading_feedback.yaml"
        original_data = {"custom": "data"}
        fpath.parent.mkdir(parents=True, exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            yaml.dump(original_data, f)

        store = FeedbackStore(feedback_dir=str(tmp_path))
        with open(fpath, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        assert loaded == original_data


class TestAddFeedback:
    """测试 add_feedback"""

    def test_add_feedback_basic(self, tmp_path):
        """基本添加反馈"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        fid = store.add_feedback(
            chapter_id=1,
            issue_type="逻辑错误",
            character=None,
            original_text="原文",
            problem="问题描述",
            fix_applied="修复内容",
        )
        assert fid.startswith("FB_")
        data = store._load()
        assert len(data["feedback_history"]) == 1
        assert data["metadata"]["total_feedback"] == 1

    def test_add_feedback_with_character(self, tmp_path):
        """添加带人物的反馈"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(
            chapter_id=1,
            issue_type="人物性格",
            character="张三",
            original_text="原文",
            problem="问题",
            fix_applied="修复",
        )
        data = store._load()
        assert "张三" in data["feedback_by_character"]
        assert len(data["feedback_by_character"]["张三"]) == 1

    def test_add_feedback_different_severity(self, tmp_path):
        """不同严重级别"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(
            chapter_id=1,
            issue_type="逻辑错误",
            character=None,
            original_text="原文",
            problem="问题",
            fix_applied="修复",
            severity="high",
        )
        data = store._load()
        entry = data["feedback_history"][0]
        assert entry["severity"] == "high"

    def test_add_feedback_default_severity(self, tmp_path):
        """默认严重级别"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(
            chapter_id=1,
            issue_type="逻辑错误",
            character=None,
            original_text="原文",
            problem="问题",
            fix_applied="修复",
        )
        data = store._load()
        entry = data["feedback_history"][0]
        assert entry["severity"] == "medium"

    def test_add_multiple_feedback_same_type(self, tmp_path):
        """同类型多条反馈"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "逻辑错误", None, "原文1", "问题1", "修复1")
        store.add_feedback(1, "逻辑错误", None, "原文2", "问题2", "修复2")
        data = store._load()
        assert len(data["feedback_by_type"]["逻辑错误"]) == 2

    def test_add_feedback_multiple_types(self, tmp_path):
        """不同类型反馈"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "逻辑错误", None, "原文1", "问题1", "修复1")
        store.add_feedback(1, "语法错误", None, "原文2", "问题2", "修复2")
        data = store._load()
        assert "逻辑错误" in data["feedback_by_type"]
        assert "语法错误" in data["feedback_by_type"]

    def test_add_feedback_updates_timestamp(self, tmp_path):
        """添加反馈后更新元数据时间戳"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "测试", None, "原文", "问题", "修复")
        data = store._load()
        assert "last_updated" in data["metadata"]

    def test_add_feedback_same_character_multiple(self, tmp_path):
        """同人物多条反馈"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "逻辑错误", "张三", "原文1", "问题1", "修复1")
        store.add_feedback(2, "语法错误", "张三", "原文2", "问题2", "修复2")
        data = store._load()
        assert len(data["feedback_by_character"]["张三"]) == 2

    def test_add_feedback_different_characters(self, tmp_path):
        """不同人物反馈"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "逻辑错误", "张三", "原文1", "问题1", "修复1")
        store.add_feedback(1, "逻辑错误", "李四", "原文2", "问题2", "修复2")
        data = store._load()
        assert len(data["feedback_history"]) == 2


class TestAddBatchFeedback:
    """测试 add_batch_feedback"""

    def test_add_batch_feedback_empty(self, tmp_path):
        """空列表不会出错"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        count = store.add_batch_feedback(1, [])
        assert count == 0

    def test_add_batch_feedback_multiple(self, tmp_path):
        """批量添加多条反馈"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        issues = [
            {
                "issue_type": "逻辑错误",
                "character": "张三",
                "original_text": "原文1",
                "problem": "问题1",
                "fix_applied": "修复1",
                "severity": "high",
            },
            {
                "issue_type": "语法错误",
                "character": None,
                "original_text": "原文2",
                "problem": "问题2",
                "fix_applied": "修复2",
            },
            {
                "issue_type": "连贯性问题",
                "character": "李四",
                "original_text": "原文3",
                "problem": "问题3",
                "fix_applied": "修复3",
                "severity": "low",
            },
        ]
        count = store.add_batch_feedback(1, issues)
        assert count == 3
        data = store._load()
        assert len(data["feedback_history"]) == 3

    def test_add_batch_feedback_defaults(self, tmp_path):
        """批量添加使用默认值"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        issues = [
            {},  # 完全空项
            {"issue_type": "测试"},  # 部分字段
        ]
        count = store.add_batch_feedback(1, issues)
        assert count == 2
        data = store._load()
        assert data["feedback_history"][0]["issue_type"] == "未知问题"
        assert data["feedback_history"][0]["severity"] == "medium"


class TestGetFeedbackByType:
    """测试 get_feedback_by_type"""

    def test_existing_type(self, tmp_path):
        """获取存在的类型"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "逻辑错误", None, "原文", "问题", "修复")
        results = store.get_feedback_by_type("逻辑错误")
        assert len(results) == 1
        assert results[0]["issue_type"] == "逻辑错误"

    def test_non_existing_type(self, tmp_path):
        """获取不存在的类型"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        results = store.get_feedback_by_type("不存在")
        assert results == []

    def test_type_with_multiple(self, tmp_path):
        """获取包含多条反馈的类型"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "逻辑错误", None, "原文1", "问题1", "修复1")
        store.add_feedback(2, "逻辑错误", None, "原文2", "问题2", "修复2")
        store.add_feedback(3, "语法错误", None, "原文3", "问题3", "修复3")
        results = store.get_feedback_by_type("逻辑错误")
        assert len(results) == 2


class TestGetFeedbackByCharacter:
    """测试 get_feedback_by_character"""

    def test_existing_character(self, tmp_path):
        """获取存在的人物反馈"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "逻辑错误", "张三", "原文", "问题", "修复")
        results = store.get_feedback_by_character("张三")
        assert len(results) == 1
        assert results[0]["character"] == "张三"

    def test_non_existing_character(self, tmp_path):
        """获取不存在的人物反馈"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        results = store.get_feedback_by_character("不存在")
        assert results == []

    def test_character_with_multiple(self, tmp_path):
        """获取包含多条反馈的人物"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "逻辑错误", "张三", "原文1", "问题1", "修复1")
        store.add_feedback(2, "语法错误", "张三", "原文2", "问题2", "修复2")
        results = store.get_feedback_by_character("张三")
        assert len(results) == 2


class TestGetRecentFeedback:
    """测试 get_recent_feedback"""

    def test_with_limit(self, tmp_path):
        """获取指定数量的最近反馈"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        for i in range(10):
            store.add_feedback(i, "测试", None, f"原文{i}", f"问题{i}", f"修复{i}")
        results = store.get_recent_feedback(limit=3)
        assert len(results) == 3

    def test_default_limit(self, tmp_path):
        """默认 limit=10"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        for i in range(5):
            store.add_feedback(i, "测试", None, f"原文{i}", f"问题{i}", f"修复{i}")
        results = store.get_recent_feedback()
        assert len(results) == 5

    def test_empty_history(self, tmp_path):
        """空历史"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        results = store.get_recent_feedback()
        assert results == []

    def test_limit_greater_than_history(self, tmp_path):
        """limit 大于历史记录数"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "测试", None, "原文", "问题", "修复")
        results = store.get_recent_feedback(limit=50)
        assert len(results) == 1


class TestGetFeedbackStats:
    """测试 get_feedback_stats"""

    def test_empty_stats(self, tmp_path):
        """空反馈统计"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        stats = store.get_feedback_stats()
        assert stats["total_feedback"] == 0
        assert stats["by_type"] == {}
        assert stats["by_character"] == {}
        assert stats["by_severity"] == {"high": 0, "medium": 0, "low": 0}

    def test_stats_with_data(self, tmp_path):
        """有数据的统计"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "逻辑错误", "张三", "原文1", "问题1", "修复1", "high")
        store.add_feedback(2, "语法错误", "李四", "原文2", "问题2", "修复2", "low")
        store.add_feedback(3, "逻辑错误", None, "原文3", "问题3", "修复3", "medium")
        stats = store.get_feedback_stats()
        assert stats["total_feedback"] == 3
        assert stats["by_type"]["逻辑错误"] == 2
        assert stats["by_type"]["语法错误"] == 1
        assert stats["by_character"]["张三"] == 1
        assert stats["by_character"]["李四"] == 1
        assert stats["by_severity"]["high"] == 1
        assert stats["by_severity"]["medium"] == 1
        assert stats["by_severity"]["low"] == 1


class TestGetCommonIssues:
    """测试 get_common_issues"""

    def test_with_limit(self, tmp_path):
        """获取最常见问题（带限制）"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        for _ in range(5):
            store.add_feedback(1, "逻辑错误", None, "原文", "问题", "修复")
        for _ in range(3):
            store.add_feedback(1, "语法错误", None, "原文", "问题", "修复")
        for _ in range(1):
            store.add_feedback(1, "连贯性", None, "原文", "问题", "修复")
        results = store.get_common_issues(limit=2)
        assert len(results) == 2
        assert results[0]["issue_type"] == "逻辑错误"
        assert results[0]["count"] == 5
        assert results[1]["issue_type"] == "语法错误"

    def test_default_limit(self, tmp_path):
        """默认 limit=5"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        for i in range(10):
            store.add_feedback(1, f"类型{i}", None, "原文", "问题", "修复")
        results = store.get_common_issues()
        assert len(results) == 5

    def test_empty_data(self, tmp_path):
        """空数据"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        results = store.get_common_issues()
        assert results == []


class TestGetFeedbackStore:
    """测试 get_feedback_store 单例函数"""

    def test_singleton_behavior(self, tmp_path):
        """单例行为"""
        import novels_project.feedback_loop as fbl
        fbl._feedback_store = None
        try:
            store1 = get_feedback_store(feedback_dir=str(tmp_path))
            store2 = get_feedback_store()
            assert store1 is store2
            # 使用不同的 dir 也应该返回同一个
            other_dir = tmp_path / "other"
            store3 = get_feedback_store(feedback_dir=str(other_dir))
            assert store1 is store3
        finally:
            fbl._feedback_store = None

    def test_with_custom_dir(self, tmp_path):
        """使用自定义目录"""
        import novels_project.feedback_loop as fbl
        fbl._feedback_store = None
        try:
            custom_dir = tmp_path / "custom_feedback"
            store = get_feedback_store(feedback_dir=str(custom_dir))
            assert store.feedback_dir == custom_dir
        finally:
            fbl._feedback_store = None

    def test_with_none_dir_uses_project_config(self, tmp_path):
        """None dir 使用 project_config"""
        import novels_project.feedback_loop as fbl
        fbl._feedback_store = None
        try:
            with patch("novels_project.project_config.get_feedback_dir") as mock_get_dir:
                mock_get_dir.return_value = tmp_path / "from_config"
                store = get_feedback_store(feedback_dir=None)
                mock_get_dir.assert_called_once()
                assert store.feedback_dir == tmp_path / "from_config"
        finally:
            fbl._feedback_store = None

    def test_singleton_reset(self, tmp_path):
        """单例重置后重新创建"""
        import novels_project.feedback_loop as fbl
        fbl._feedback_store = None
        try:
            store1 = get_feedback_store(feedback_dir=str(tmp_path))
            fbl._feedback_store = None
            other = tmp_path / "other"
            store2 = get_feedback_store(feedback_dir=str(other))
            assert store1 is not store2
            assert store2.feedback_dir == other
        finally:
            fbl._feedback_store = None


class TestEdgeCases:
    """边缘情况测试"""

    def test_duplicate_ids(self, tmp_path):
        """不同时间添加的反馈ID应不同（时间戳不同）"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        fid1 = store.add_feedback(1, "测试", None, "原文", "问题", "修复")
        fid2 = store.add_feedback(1, "测试", None, "原文", "问题", "修复")
        assert fid1 != fid2

    def test_feedback_history_order(self, tmp_path):
        """反馈按添加顺序排列"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "类型A", None, "原文1", "问题1", "修复1")
        store.add_feedback(2, "类型B", None, "原文2", "问题2", "修复2")
        store.add_feedback(3, "类型C", None, "原文3", "问题3", "修复3")
        data = store._load()
        assert data["feedback_history"][0]["chapter_id"] == 1
        assert data["feedback_history"][2]["chapter_id"] == 3

    def test_unicode_content(self, tmp_path):
        """Unicode 内容"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(
            1, "逻辑错误", "张三",
            "原文🎉中文", "问题：人称不符", "修复：改为「他」",
        )
        data = store._load()
        entry = data["feedback_history"][0]
        assert entry["original_text"] == "原文🎉中文"
        assert entry["character"] == "张三"

    def test_load_and_save_roundtrip(self, tmp_path):
        """加载和保存的往返测试"""
        store = FeedbackStore(feedback_dir=str(tmp_path))
        store.add_feedback(1, "类型A", "人物X", "原文A", "问题A", "修复A", "high")
        store.add_feedback(2, "类型B", None, "原文B", "问题B", "修复B", "low")

        # 重新加载
        data = store._load()
        assert len(data["feedback_history"]) == 2
        assert data["metadata"]["total_feedback"] == 2
        assert "类型A" in data["feedback_by_type"]
        assert "类型B" in data["feedback_by_type"]
        assert "人物X" in data["feedback_by_character"]