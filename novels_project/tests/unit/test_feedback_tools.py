"""
Unit tests for novels_project.tools.feedback_tools
"""
import pytest
from unittest.mock import patch, MagicMock


class TestRetrieveFeedback:
    """retrieve_feedback function tests"""

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_by_issue_type(self, mock_get_store):
        from novels_project.tools.feedback_tools import retrieve_feedback

        mock_store = MagicMock()
        mock_store.get_feedback_by_type.return_value = [
            {
                "chapter_id": 1,
                "issue_type": "对话风格偏离",
                "character": "陆商曜",
                "problem": "dialogue too formal",
                "fix_applied": "made casual",
                "original_text": "Hello there",
            }
        ]
        mock_get_store.return_value = mock_store

        result = retrieve_feedback(issue_type="对话风格偏离", limit=5)
        mock_store.get_feedback_by_type.assert_called_once_with("对话风格偏离")
        assert "找到 1 条历史反馈" in result
        assert "对话风格偏离" in result
        assert "陆商曜" in result
        assert "dialogue too formal" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_by_character(self, mock_get_store):
        from novels_project.tools.feedback_tools import retrieve_feedback

        mock_store = MagicMock()
        mock_store.get_feedback_by_character.return_value = [
            {
                "chapter_id": 3,
                "issue_type": "Tell而非Show",
                "character": "黑商周桓",
                "problem": "too much telling",
                "fix_applied": "added action",
                "original_text": "He was angry",
            }
        ]
        mock_get_store.return_value = mock_store

        result = retrieve_feedback(character="黑商周桓")
        mock_store.get_feedback_by_character.assert_called_once_with("黑商周桓")
        assert "找到 1 条历史反馈" in result
        assert "Tell而非Show" in result
        assert "黑商周桓" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_default_recent(self, mock_get_store):
        from novels_project.tools.feedback_tools import retrieve_feedback

        mock_store = MagicMock()
        mock_store.get_recent_feedback.return_value = [
            {"chapter_id": 1, "issue_type": "style", "problem": "p1", "fix_applied": "f1", "original_text": "t1"},
            {"chapter_id": 2, "issue_type": "grammar", "problem": "p2", "fix_applied": "f2", "original_text": "t2"},
        ]
        mock_get_store.return_value = mock_store

        result = retrieve_feedback(limit=2)
        mock_store.get_recent_feedback.assert_called_once_with(limit=2)
        assert "找到 2 条历史反馈" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_empty_results(self, mock_get_store):
        from novels_project.tools.feedback_tools import retrieve_feedback

        mock_store = MagicMock()
        mock_store.get_recent_feedback.return_value = []
        mock_get_store.return_value = mock_store

        result = retrieve_feedback()
        assert "暂无相关历史反馈" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_limit_truncates(self, mock_get_store):
        from novels_project.tools.feedback_tools import retrieve_feedback

        items = [
            {"chapter_id": i, "issue_type": f"type{i}", "problem": f"p{i}", "fix_applied": f"f{i}", "original_text": f"t{i}"}
            for i in range(10)
        ]
        mock_store = MagicMock()
        mock_store.get_recent_feedback.return_value = items
        mock_get_store.return_value = mock_store

        result = retrieve_feedback(limit=3)
        # Uses last 3 (feedbacks[-limit:])
        assert "找到 3 条历史反馈" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_feedback_without_character(self, mock_get_store):
        from novels_project.tools.feedback_tools import retrieve_feedback

        mock_store = MagicMock()
        mock_store.get_recent_feedback.return_value = [
            {
                "chapter_id": 5,
                "issue_type": "节奏问题",
                "problem": "too slow",
                "fix_applied": "tightened",
                "original_text": "long description",
            }
        ]
        mock_get_store.return_value = mock_store

        result = retrieve_feedback()
        assert "人物:" not in result or "第5章" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_exception(self, mock_get_store):
        from novels_project.tools.feedback_tools import retrieve_feedback

        mock_get_store.side_effect = RuntimeError("test error")
        result = retrieve_feedback()
        assert "反馈检索失败" in result
        assert "test error" in result


class TestGetCommonMistakes:
    """get_common_mistakes function tests"""

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_with_data(self, mock_get_store):
        from novels_project.tools.feedback_tools import get_common_mistakes

        mock_store = MagicMock()
        mock_store.get_common_issues.return_value = [
            {"issue_type": "对话风格偏离", "count": 5},
            {"issue_type": "逻辑漏洞", "count": 3},
        ]
        mock_store.get_feedback_stats.return_value = {"total_feedback": 8}
        mock_get_store.return_value = mock_store

        result = get_common_mistakes(limit=5)
        mock_store.get_common_issues.assert_called_once_with(limit=5)
        mock_store.get_feedback_stats.assert_called_once()
        assert "共 8 条反馈" in result
        assert "1. 对话风格偏离: 5 次" in result
        assert "2. 逻辑漏洞: 3 次" in result
        assert "建议" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_empty(self, mock_get_store):
        from novels_project.tools.feedback_tools import get_common_mistakes

        mock_store = MagicMock()
        mock_store.get_common_issues.return_value = []
        mock_get_store.return_value = mock_store

        result = get_common_mistakes()
        assert "暂无历史反馈数据" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_exception(self, mock_get_store):
        from novels_project.tools.feedback_tools import get_common_mistakes

        mock_get_store.side_effect = RuntimeError("test error")
        result = get_common_mistakes()
        assert "获取统计数据失败" in result
        assert "test error" in result


class TestRecordFeedback:
    """record_feedback function tests"""

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_success(self, mock_get_store):
        from novels_project.tools.feedback_tools import record_feedback

        mock_store = MagicMock()
        mock_store.add_feedback.return_value = "FB_001"
        mock_get_store.return_value = mock_store

        result = record_feedback(
            chapter_id=1,
            issue_type="对话风格偏离",
            character="陆商曜",
            original_text="original text",
            problem="too formal",
            fix_applied="made casual",
            severity="high",
        )
        mock_store.add_feedback.assert_called_once_with(
            chapter_id=1,
            issue_type="对话风格偏离",
            character="陆商曜",
            original_text="original text",
            problem="too formal",
            fix_applied="made casual",
            severity="high",
        )
        assert "反馈已记录: FB_001" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_success_with_default_severity(self, mock_get_store):
        from novels_project.tools.feedback_tools import record_feedback

        mock_store = MagicMock()
        mock_store.add_feedback.return_value = "FB_002"
        mock_get_store.return_value = mock_store

        result = record_feedback(
            chapter_id=2,
            issue_type="Tell而非Show",
            character=None,
            original_text="text",
            problem="telling",
            fix_applied="showed",
        )
        mock_store.add_feedback.assert_called_once_with(
            chapter_id=2,
            issue_type="Tell而非Show",
            character=None,
            original_text="text",
            problem="telling",
            fix_applied="showed",
            severity="medium",
        )
        assert "反馈已记录: FB_002" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_exception(self, mock_get_store):
        from novels_project.tools.feedback_tools import record_feedback

        mock_get_store.side_effect = RuntimeError("test error")
        result = record_feedback(
            chapter_id=1,
            issue_type="test",
            character=None,
            original_text="t",
            problem="p",
            fix_applied="f",
        )
        assert "记录反馈失败" in result
        assert "test error" in result


class TestRecordBatchFeedback:
    """record_batch_feedback function tests"""

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_success(self, mock_get_store):
        from novels_project.tools.feedback_tools import record_batch_feedback

        mock_store = MagicMock()
        mock_store.add_batch_feedback.return_value = 3
        mock_get_store.return_value = mock_store

        issues_json = """[
            {"issue_type": "对话风格偏离", "character": "陆商曜", "original_text": "text1", "problem": "p1", "fix_applied": "f1", "severity": "high"},
            {"issue_type": "逻辑漏洞", "character": "黑商周桓", "original_text": "text2", "problem": "p2", "fix_applied": "f2", "severity": "medium"},
            {"issue_type": "节奏问题", "character": null, "original_text": "text3", "problem": "p3", "fix_applied": "f3", "severity": "low"}
        ]"""
        result = record_batch_feedback(chapter_id=5, issues_json=issues_json)
        mock_store.add_batch_feedback.assert_called_once()
        assert "已记录 3 条反馈" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_invalid_json(self, mock_get_store):
        from novels_project.tools.feedback_tools import record_batch_feedback

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        result = record_batch_feedback(chapter_id=5, issues_json="not valid json][[")
        assert "批量记录失败" in result

    @patch("novels_project.tools.feedback_tools._get_store")
    def test_exception(self, mock_get_store):
        from novels_project.tools.feedback_tools import record_batch_feedback

        mock_get_store.side_effect = RuntimeError("test error")
        result = record_batch_feedback(chapter_id=5, issues_json='[]')
        assert "批量记录失败" in result
        assert "test error" in result


class TestGetStoreHelper:
    """Tests that exercise the actual _get_store helper function"""

    def setup_method(self):
        # Reset the module-level cached store so lazy import is exercised
        import novels_project.tools.feedback_tools as mod
        mod._feedback_store = None

    @patch("novels_project.feedback_loop.get_feedback_store")
    def test_get_store_called(self, mock_get_fs):
        from novels_project.tools.feedback_tools import retrieve_feedback

        mock_store = MagicMock()
        mock_store.get_recent_feedback.return_value = []
        mock_get_fs.return_value = mock_store

        result = retrieve_feedback()
        mock_get_fs.assert_called_once()
        assert "暂无相关历史反馈" in result

    @patch("novels_project.feedback_loop.get_feedback_store")
    def test_get_store_cached(self, mock_get_fs):
        """Second call should reuse cached store, not call get_feedback_store again"""
        from novels_project.tools.feedback_tools import retrieve_feedback

        mock_store = MagicMock()
        mock_store.get_recent_feedback.return_value = []
        mock_get_fs.return_value = mock_store

        retrieve_feedback()
        assert mock_get_fs.call_count == 1

        # Second call should NOT call get_feedback_store again
        retrieve_feedback()
        assert mock_get_fs.call_count == 1