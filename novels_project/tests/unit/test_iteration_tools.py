"""
Unit tests for novels_project.tools.iteration_tools
"""
import pytest
from unittest.mock import patch, MagicMock
from novels_project.iteration_controller import IterationStatus, IterationResult, IterationSession


class TestCheckIterationStatus:
    """check_iteration_status function tests"""

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_no_session(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import check_iteration_status

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = None
        mock_get_ctrl.return_value = mock_controller

        result = check_iteration_status(42)
        assert "章节 42 尚未开始迭代" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_with_session_no_iterations(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import check_iteration_status

        session = IterationSession(chapter_id=1, max_iterations=3, quality_threshold=7)

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = check_iteration_status(1)
        assert "章节 1 迭代状态" in result
        assert "当前迭代: 0/3" in result
        assert "最佳分数: 0/10" in result
        assert "质量阈值: 7/10" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_with_improvement_history(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import check_iteration_status

        session = IterationSession(chapter_id=1, max_iterations=3, quality_threshold=7)
        session.add_iteration(
            IterationResult(
                iteration=1, draft="d1", review_issues=[{}, {}],
                quality_score=5, status=IterationStatus.CONTINUE
            )
        )
        session.add_iteration(
            IterationResult(
                iteration=2, draft="d2", review_issues=[{}, {}, {}],
                quality_score=8, status=IterationStatus.ACCEPT, feedback="good"
            )
        )

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = check_iteration_status(1)
        assert "当前迭代: 2/3" in result
        assert "最佳分数: 8/10" in result
        assert "最终状态: accept" in result
        assert "改进历史" in result
        assert "第1轮: 分数 5, 问题 2个" in result
        assert "第2轮: 分数 8, 问题 3个" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_exception(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import check_iteration_status

        mock_get_ctrl.side_effect = RuntimeError("test error")
        result = check_iteration_status(1)
        assert "检查状态失败" in result
        assert "test error" in result


class TestShouldContinueIteration:
    """should_continue_iteration function tests"""

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_no_session(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import should_continue_iteration

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = None
        mock_get_ctrl.return_value = mock_controller

        result = should_continue_iteration(1, 6)
        assert "尚未开始迭代" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_accept(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import should_continue_iteration

        session = MagicMock()
        session.should_continue.return_value = IterationStatus.ACCEPT

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = should_continue_iteration(1, 8)
        assert "质量达标" in result
        assert "无需继续迭代" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_max_iter(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import should_continue_iteration

        session = MagicMock()
        session.should_continue.return_value = IterationStatus.MAX_ITER
        session.max_iterations = 3

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = should_continue_iteration(1, 5)
        assert "已达最大迭代次数" in result
        assert "停止迭代" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_continue(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import should_continue_iteration

        session = MagicMock()
        session.should_continue.return_value = IterationStatus.CONTINUE
        session.max_iterations = 5
        session.current_iteration.return_value = 2

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = should_continue_iteration(1, 6)
        assert "需要继续迭代" in result
        assert "剩余迭代次数: 3" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_exception(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import should_continue_iteration

        mock_get_ctrl.side_effect = RuntimeError("test error")
        result = should_continue_iteration(1, 6)
        assert "判断失败" in result
        assert "test error" in result


class TestGetRevisionFeedback:
    """get_revision_feedback function tests"""

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_no_session(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import get_revision_feedback

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = None
        mock_get_ctrl.return_value = mock_controller

        result = get_revision_feedback(1)
        assert "暂无校对反馈" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_empty_iterations(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import get_revision_feedback

        session = IterationSession(chapter_id=1)
        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = get_revision_feedback(1)
        assert "暂无校对反馈" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_with_latest_feedback(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import get_revision_feedback

        session = IterationSession(chapter_id=1)
        session.add_iteration(
            IterationResult(
                iteration=1,
                draft="draft v1",
                review_issues=[],
                quality_score=5,
                status=IterationStatus.CONTINUE,
                feedback="Fix dialogue",
            )
        )

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = get_revision_feedback(1)
        assert "第 1 轮校对反馈" in result
        assert "质量评分: 5/10" in result
        assert "Fix dialogue" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_with_multiple_iterations_gets_latest(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import get_revision_feedback

        session = IterationSession(chapter_id=1)
        session.add_iteration(
            IterationResult(
                iteration=1, draft="v1", review_issues=[],
                quality_score=5, status=IterationStatus.CONTINUE, feedback="first fb"
            )
        )
        session.add_iteration(
            IterationResult(
                iteration=2, draft="v2", review_issues=[],
                quality_score=7, status=IterationStatus.CONTINUE, feedback="second fb"
            )
        )
        session.add_iteration(
            IterationResult(
                iteration=3, draft="v3", review_issues=[],
                quality_score=9, status=IterationStatus.ACCEPT, feedback="final fb"
            )
        )

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = get_revision_feedback(1)
        assert "第 3 轮校对反馈" in result
        assert "final fb" in result
        assert "first fb" not in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_exception(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import get_revision_feedback

        mock_get_ctrl.side_effect = RuntimeError("test error")
        result = get_revision_feedback(1)
        assert "获取反馈失败" in result
        assert "test error" in result


class TestRecordIteration:
    """record_iteration function tests"""

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_no_session_creates_one(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import record_iteration

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = None
        session = IterationSession(chapter_id=1, max_iterations=3, quality_threshold=7)
        mock_controller.start_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = record_iteration(
            chapter_id=1,
            draft="test draft content",
            review_issues='[{"issue_type": "style", "severity": "high"}]',
            quality_score=6,
        )
        mock_controller.start_session.assert_called_once_with(1)
        assert "已记录第 1 次迭代" in result
        assert "分数: 6/10" in result

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_with_existing_session(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import record_iteration

        session = IterationSession(chapter_id=1, max_iterations=3, quality_threshold=7)
        session.add_iteration(
            IterationResult(
                iteration=1, draft="d1", review_issues=[],
                quality_score=5, status=IterationStatus.CONTINUE
            )
        )

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = record_iteration(
            chapter_id=1,
            draft="draft v2",
            review_issues='[{"issue_type": "style", "severity": "low"}]',
            quality_score=8,
        )
        mock_controller.start_session.assert_not_called()
        assert "已记录第 2 次迭代" in result
        assert "分数: 8/10" in result
        assert len(session.iterations) == 2

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_with_invalid_json_review_issues(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import record_iteration

        session = IterationSession(chapter_id=1, max_iterations=3, quality_threshold=7)

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = None
        mock_controller.start_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = record_iteration(
            chapter_id=1,
            draft="test draft",
            review_issues="not valid json{{{",
            quality_score=6,
        )
        assert "已记录第 1 次迭代" in result
        assert session.iterations[0].review_issues == []

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_with_valid_json_review_issues(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import record_iteration

        session = IterationSession(chapter_id=1, max_iterations=3, quality_threshold=7)

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = None
        mock_controller.start_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = record_iteration(
            chapter_id=1,
            draft="test draft",
            review_issues='[{"issue_type": "对话风格偏离", "severity": "high"}, {"issue_type": "逻辑漏洞", "severity": "medium"}]',
            quality_score=6,
        )
        assert "已记录第 1 次迭代" in result
        assert len(session.iterations[0].review_issues) == 2
        assert session.iterations[0].review_issues[0]["issue_type"] == "对话风格偏离"
        assert session.iterations[0].review_issues[1]["severity"] == "medium"

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_with_empty_review_issues(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import record_iteration

        session = IterationSession(chapter_id=1, max_iterations=3, quality_threshold=7)

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = None
        mock_controller.start_session.return_value = session
        mock_get_ctrl.return_value = mock_controller

        result = record_iteration(
            chapter_id=1,
            draft="test draft",
            review_issues="",
            quality_score=6,
        )
        assert session.iterations[0].review_issues == []

    @patch("novels_project.tools.iteration_tools._get_controller")
    def test_exception(self, mock_get_ctrl):
        from novels_project.tools.iteration_tools import record_iteration

        mock_get_ctrl.side_effect = RuntimeError("test error")
        result = record_iteration(1, "draft", "[]", 6)
        assert "记录失败" in result
        assert "test error" in result


class TestGetControllerHelper:
    """Tests that exercise the actual _get_controller helper function"""

    def setup_method(self):
        import novels_project.tools.iteration_tools as mod
        # Reset cached singleton so lazy import is exercised
        import novels_project.iteration_controller as ic_mod
        ic_mod._controller = None

    @patch("novels_project.iteration_controller.get_iteration_controller")
    def test_get_controller_called(self, mock_get_ic):
        from novels_project.tools.iteration_tools import check_iteration_status

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = None
        mock_get_ic.return_value = mock_controller

        result = check_iteration_status(42)
        mock_get_ic.assert_called_once()
        assert "尚未开始迭代" in result