"""
Unit tests for novels_project.iterative_writer
"""
import pytest
from unittest.mock import patch, MagicMock
from novels_project.iterative_writer import get_iteration_report, MAX_SAFETY_LIMIT
from novels_project.iteration_controller import IterationStatus, IterationResult, IterationSession


class TestMaxSafetyLimit:
    def test_max_safety_limit_value(self):
        assert MAX_SAFETY_LIMIT == 10
        assert isinstance(MAX_SAFETY_LIMIT, int)


class TestGetIterationReport:
    """get_iteration_report function tests"""

    @patch("novels_project.iterative_writer.get_iteration_controller")
    def test_no_session(self, mock_get_controller):
        mock_controller = MagicMock()
        mock_controller.get_session.return_value = None
        mock_get_controller.return_value = mock_controller

        report = get_iteration_report(42)
        mock_controller.get_session.assert_called_once_with(42)
        assert "章节 42 没有迭代记录" in report

    @patch("novels_project.iterative_writer.get_iteration_controller")
    def test_with_session_having_iterations(self, mock_get_controller):
        session = IterationSession(chapter_id=1, max_iterations=3, quality_threshold=7)
        session.add_iteration(
            IterationResult(
                iteration=1,
                draft="draft v1",
                review_issues=[{}, {}],
                quality_score=5,
                status=IterationStatus.CONTINUE,
            )
        )
        session.add_iteration(
            IterationResult(
                iteration=2,
                draft="draft v2",
                review_issues=[{}, {}, {}],
                quality_score=8,
                status=IterationStatus.ACCEPT,
                feedback="Looks good",
            )
        )

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_controller.return_value = mock_controller

        report = get_iteration_report(1)
        assert "章节 1 迭代报告" in report
        assert "总迭代次数: 2" in report
        assert "最佳质量分数: 8/10" in report
        assert "质量阈值: 7/10" in report
        assert "最终状态: accept" in report
        assert "第1轮: 分数 5, 问题 2个" in report
        assert "第2轮: 分数 8, 问题 3个" in report

    @patch("novels_project.iterative_writer.get_iteration_controller")
    def test_with_session_multiple_iterations(self, mock_get_controller):
        session = IterationSession(chapter_id=5, max_iterations=5, quality_threshold=6)
        for i in range(4):
            session.add_iteration(
                IterationResult(
                    iteration=i + 1,
                    draft=f"draft {i}",
                    review_issues=[{}] * (i + 1),
                    quality_score=4 + i,
                    status=IterationStatus.CONTINUE if i < 3 else IterationStatus.ACCEPT,
                )
            )

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_controller.return_value = mock_controller

        report = get_iteration_report(5)
        assert "总迭代次数: 4" in report
        assert "第1轮: 分数 4, 问题 1个" in report
        assert "第2轮: 分数 5, 问题 2个" in report
        assert "第3轮: 分数 6, 问题 3个" in report
        assert "第4轮: 分数 7, 问题 4个" in report

    @patch("novels_project.iterative_writer.get_iteration_controller")
    def test_session_with_empty_iterations(self, mock_get_controller):
        session = IterationSession(chapter_id=99)

        mock_controller = MagicMock()
        mock_controller.get_session.return_value = session
        mock_get_controller.return_value = mock_controller

        report = get_iteration_report(99)
        assert "总迭代次数: 0" in report
        assert "最佳质量分数: 0/10" in report
        assert "最终状态: " not in report or "None" in report