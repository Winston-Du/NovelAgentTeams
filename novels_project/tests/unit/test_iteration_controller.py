"""
Unit tests for novels_project.iteration_controller
"""
import pytest
from novels_project.iteration_controller import (
    IterationStatus,
    IterationResult,
    IterationSession,
    IterationController,
    get_iteration_controller,
)


class TestIterationStatus:
    """IterationStatus enum tests"""

    def test_enum_values(self):
        assert IterationStatus.CONTINUE.value == "continue"
        assert IterationStatus.ACCEPT.value == "accept"
        assert IterationStatus.MAX_ITER.value == "max_iter"

    def test_enum_members(self):
        members = list(IterationStatus)
        assert len(members) == 3
        assert IterationStatus.CONTINUE in members
        assert IterationStatus.ACCEPT in members
        assert IterationStatus.MAX_ITER in members


class TestIterationResult:
    """IterationResult dataclass tests"""

    def test_creation_with_all_fields(self):
        result = IterationResult(
            iteration=1,
            draft="some draft content",
            review_issues=[{"issue_type": "style", "severity": "high"}],
            quality_score=7,
            status=IterationStatus.ACCEPT,
            feedback="Good work!",
        )
        assert result.iteration == 1
        assert result.draft == "some draft content"
        assert len(result.review_issues) == 1
        assert result.quality_score == 7
        assert result.status == IterationStatus.ACCEPT
        assert result.feedback == "Good work!"

    def test_creation_with_default_feedback(self):
        result = IterationResult(
            iteration=2,
            draft="another draft",
            review_issues=[],
            quality_score=5,
            status=IterationStatus.CONTINUE,
        )
        assert result.feedback == ""

    def test_status_values(self):
        for status in IterationStatus:
            result = IterationResult(
                iteration=1,
                draft="draft",
                review_issues=[],
                quality_score=5,
                status=status,
            )
            assert result.status == status


class TestIterationSession:
    """IterationSession dataclass tests"""

    def test_creation_with_defaults(self):
        session = IterationSession(chapter_id=1)
        assert session.chapter_id == 1
        assert session.max_iterations == 3
        assert session.quality_threshold == 7
        assert session.iterations == []

    def test_creation_with_custom_params(self):
        session = IterationSession(
            chapter_id=5, max_iterations=5, quality_threshold=9
        )
        assert session.chapter_id == 5
        assert session.max_iterations == 5
        assert session.quality_threshold == 9

    def test_current_iteration_empty(self):
        session = IterationSession(chapter_id=1)
        assert session.current_iteration() == 0

    def test_current_iteration_with_results(self):
        session = IterationSession(chapter_id=1)
        session.add_iteration(
            IterationResult(
                iteration=1,
                draft="draft1",
                review_issues=[],
                quality_score=5,
                status=IterationStatus.CONTINUE,
            )
        )
        assert session.current_iteration() == 1
        session.add_iteration(
            IterationResult(
                iteration=2,
                draft="draft2",
                review_issues=[],
                quality_score=6,
                status=IterationStatus.CONTINUE,
            )
        )
        assert session.current_iteration() == 2

    def test_should_continue_accept(self):
        """ACCEPT when score >= threshold"""
        session = IterationSession(chapter_id=1, quality_threshold=7)
        assert session.should_continue(7) == IterationStatus.ACCEPT
        assert session.should_continue(8) == IterationStatus.ACCEPT
        assert session.should_continue(10) == IterationStatus.ACCEPT

    def test_should_continue_max_iter(self):
        """MAX_ITER when at max iterations"""
        session = IterationSession(chapter_id=1, max_iterations=2)
        session.add_iteration(
            IterationResult(
                iteration=1,
                draft="draft1",
                review_issues=[],
                quality_score=5,
                status=IterationStatus.CONTINUE,
            )
        )
        session.add_iteration(
            IterationResult(
                iteration=2,
                draft="draft2",
                review_issues=[],
                quality_score=6,
                status=IterationStatus.CONTINUE,
            )
        )
        # score=6 < threshold=7, but we've reached max_iterations=2
        assert session.should_continue(6) == IterationStatus.MAX_ITER

    def test_should_continue_continue(self):
        """CONTINUE when below threshold and not at max"""
        session = IterationSession(chapter_id=1, max_iterations=3, quality_threshold=7)
        assert session.should_continue(5) == IterationStatus.CONTINUE
        assert session.should_continue(6) == IterationStatus.CONTINUE

    def test_should_continue_accept_has_priority_over_max_iter(self):
        """ACCEPT takes priority: even if at max iterations, accept if score >= threshold"""
        session = IterationSession(chapter_id=1, max_iterations=1, quality_threshold=7)
        session.add_iteration(
            IterationResult(
                iteration=1,
                draft="draft",
                review_issues=[],
                quality_score=8,
                status=IterationStatus.ACCEPT,
            )
        )
        # current_iteration = 1 >= max_iterations = 1, but quality_score=8 >= threshold=7 -> ACCEPT
        assert session.should_continue(8) == IterationStatus.ACCEPT

    def test_add_iteration(self):
        session = IterationSession(chapter_id=1)
        result = IterationResult(
            iteration=1,
            draft="test draft",
            review_issues=[{"a": 1}],
            quality_score=6,
            status=IterationStatus.CONTINUE,
        )
        session.add_iteration(result)
        assert len(session.iterations) == 1
        assert session.iterations[0] is result

    def test_add_multiple_iterations(self):
        session = IterationSession(chapter_id=1)
        for i in range(3):
            session.add_iteration(
                IterationResult(
                    iteration=i + 1,
                    draft=f"draft{i}",
                    review_issues=[],
                    quality_score=5 + i,
                    status=IterationStatus.CONTINUE,
                )
            )
        assert len(session.iterations) == 3

    def test_get_best_draft_empty(self):
        session = IterationSession(chapter_id=1)
        draft, score = session.get_best_draft()
        assert draft == ""
        assert score == 0

    def test_get_best_draft_with_results(self):
        session = IterationSession(chapter_id=1)
        session.add_iteration(
            IterationResult(
                iteration=1,
                draft="bad draft",
                review_issues=[],
                quality_score=3,
                status=IterationStatus.CONTINUE,
            )
        )
        session.add_iteration(
            IterationResult(
                iteration=2,
                draft="good draft",
                review_issues=[],
                quality_score=8,
                status=IterationStatus.ACCEPT,
            )
        )
        session.add_iteration(
            IterationResult(
                iteration=3,
                draft="medium draft",
                review_issues=[],
                quality_score=5,
                status=IterationStatus.CONTINUE,
            )
        )
        draft, score = session.get_best_draft()
        assert draft == "good draft"
        assert score == 8

    def test_get_best_draft_single_result(self):
        session = IterationSession(chapter_id=1)
        session.add_iteration(
            IterationResult(
                iteration=1,
                draft="only draft",
                review_issues=[],
                quality_score=4,
                status=IterationStatus.CONTINUE,
            )
        )
        draft, score = session.get_best_draft()
        assert draft == "only draft"
        assert score == 4

    def test_get_summary_empty(self):
        session = IterationSession(chapter_id=42, max_iterations=5, quality_threshold=8)
        summary = session.get_summary()
        assert summary["chapter_id"] == 42
        assert summary["total_iterations"] == 0
        assert summary["max_iterations"] == 5
        assert summary["best_quality_score"] == 0
        assert summary["quality_threshold"] == 8
        assert summary["final_status"] is None
        assert summary["improvement_history"] == []

    def test_get_summary_with_iterations(self):
        session = IterationSession(chapter_id=10, max_iterations=3, quality_threshold=7)
        session.add_iteration(
            IterationResult(
                iteration=1,
                draft="d1",
                review_issues=[{}, {}],
                quality_score=5,
                status=IterationStatus.CONTINUE,
            )
        )
        session.add_iteration(
            IterationResult(
                iteration=2,
                draft="d2",
                review_issues=[{}, {}, {}],
                quality_score=8,
                status=IterationStatus.ACCEPT,
            )
        )
        summary = session.get_summary()
        assert summary["chapter_id"] == 10
        assert summary["total_iterations"] == 2
        assert summary["max_iterations"] == 3
        assert summary["best_quality_score"] == 8
        assert summary["quality_threshold"] == 7
        assert summary["final_status"] == "accept"
        assert len(summary["improvement_history"]) == 2
        assert summary["improvement_history"][0] == {
            "iteration": 1,
            "score": 5,
            "issues_count": 2,
        }
        assert summary["improvement_history"][1] == {
            "iteration": 2,
            "score": 8,
            "issues_count": 3,
        }


class TestIterationController:
    """IterationController class tests"""

    def test_init_defaults(self):
        controller = IterationController()
        assert controller.max_iterations == 3
        assert controller.quality_threshold == 7
        assert controller.sessions == {}

    def test_init_custom(self):
        controller = IterationController(max_iterations=5, quality_threshold=9)
        assert controller.max_iterations == 5
        assert controller.quality_threshold == 9
        assert controller.sessions == {}

    def test_start_session_creates_new(self):
        controller = IterationController()
        session = controller.start_session(1)
        assert session.chapter_id == 1
        assert session.max_iterations == controller.max_iterations
        assert session.quality_threshold == controller.quality_threshold
        assert 1 in controller.sessions
        assert controller.sessions[1] is session

    def test_start_session_overwrites_existing(self):
        controller = IterationController()
        session1 = controller.start_session(1)
        session2 = controller.start_session(1)
        assert session1 is not session2
        assert controller.sessions[1] is session2

    def test_start_session_multiple_chapters(self):
        controller = IterationController()
        s1 = controller.start_session(1)
        s2 = controller.start_session(2)
        s3 = controller.start_session(3)
        assert len(controller.sessions) == 3
        assert controller.sessions[1] is s1
        assert controller.sessions[2] is s2
        assert controller.sessions[3] is s3

    def test_get_session_existing(self):
        controller = IterationController()
        session = controller.start_session(5)
        assert controller.get_session(5) is session

    def test_get_session_non_existing(self):
        controller = IterationController()
        assert controller.get_session(999) is None

    def test_parse_review_output_valid_yaml(self):
        controller = IterationController()
        yaml_output = """chapter_final:
  proofreading_log:
    issues_found_and_fixed:
      - issue_type: 对话风格偏离
        severity: high
        original_text: some text
        problem: the problem
        fix_applied: the fix
      - issue_type: 逻辑漏洞
        severity: medium
        original_text: other text
        problem: other problem
        fix_applied: other fix
self_check_report:
  quality_after: 7
"""
        issues, score, feedback = controller.parse_review_output(yaml_output)
        assert len(issues) == 2
        assert issues[0]["issue_type"] == "对话风格偏离"
        assert issues[1]["issue_type"] == "逻辑漏洞"
        assert score == 7
        assert "📊 质量评分: 7/10" in feedback
        assert "高优先级问题" in feedback

    def test_parse_review_output_with_markdown_code_block(self):
        controller = IterationController()
        yaml_output = """```yaml
chapter_final:
  proofreading_log:
    issues_found_and_fixed:
      - issue_type: 节奏问题
        severity: low
        original_text: text
        problem: pacing
        fix_applied: adjusted
self_check_report:
  quality_after: 6
```
"""
        issues, score, feedback = controller.parse_review_output(yaml_output)
        assert len(issues) == 1
        assert issues[0]["issue_type"] == "节奏问题"
        assert score == 6

    def test_parse_review_output_with_markdown_no_lang(self):
        controller = IterationController()
        yaml_output = """```
chapter_final:
  proofreading_log:
    issues_found_and_fixed: []
self_check_report:
  quality_after: 8
```
"""
        issues, score, _ = controller.parse_review_output(yaml_output)
        assert score == 8
        assert issues == []

    def test_parse_review_output_invalid_yaml(self):
        controller = IterationController()
        # Use YAML that is structurally broken (tab indentation + trailing colon causes parse error)
        invalid_output = "key:\n\tvalue:"
        issues, score, feedback = controller.parse_review_output(invalid_output)
        assert issues == []
        assert score == 5
        assert "校对输出解析失败" in feedback

    def test_parse_review_output_with_triple_backtick_start_only(self):
        """Only starts with ``` but no ending"""
        controller = IterationController()
        yaml_output = """```
chapter_final:
  proofreading_log:
    issues_found_and_fixed: []
self_check_report:
  quality_after: 5
"""
        issues, score, _ = controller.parse_review_output(yaml_output)
        assert score == 5
        assert issues == []

    def test_parse_review_output_empty_dict_data(self):
        controller = IterationController()
        yaml_output = "{}"
        issues, score, _ = controller.parse_review_output(yaml_output)
        assert issues == []
        assert score == 5

    def test_parse_review_output_with_missing_keys(self):
        controller = IterationController()
        yaml_output = "chapter_final: {}\nself_check_report: {}"
        issues, score, _ = controller.parse_review_output(yaml_output)
        assert issues == []
        assert score == 5

    def test_parse_review_output_non_dict_yaml(self):
        """YAML that parses as a scalar (not a dict) — edge case"""
        controller = IterationController()
        yaml_output = "just a plain string"
        issues, score, feedback = controller.parse_review_output(yaml_output)
        assert issues == []
        assert score == 5
        assert feedback == ""

    def test_generate_feedback_empty_issues(self):
        controller = IterationController()
        feedback = controller._generate_feedback([], 8)
        assert feedback == "校对未发现明显问题，质量良好。"

    def test_generate_feedback_high_severity(self):
        controller = IterationController()
        issues = [
            {
                "issue_type": "对话风格偏离",
                "severity": "high",
                "original_text": "a" * 60,
                "problem": "bad dialogue",
                "fix_applied": "rewrote",
            }
        ]
        feedback = controller._generate_feedback(issues, 4)
        assert "📊 质量评分: 4/10" in feedback
        assert "🔴 高优先级问题" in feedback
        assert "对话风格偏离" in feedback
        assert "bad dialogue" in feedback

    def test_generate_feedback_medium_severity(self):
        controller = IterationController()
        issues = [
            {
                "issue_type": "节奏问题",
                "severity": "medium",
                "original_text": "text",
                "problem": "pacing off",
                "fix_applied": "adjusted",
            }
        ]
        feedback = controller._generate_feedback(issues, 6)
        assert "🟡 中优先级问题" in feedback
        assert "1 个" in feedback

    def test_generate_feedback_low_severity(self):
        controller = IterationController()
        issues = [
            {
                "issue_type": "typo",
                "severity": "low",
                "original_text": "teh",
                "problem": "spelling",
                "fix_applied": "the",
            }
        ]
        feedback = controller._generate_feedback(issues, 9)
        assert "🟢 低优先级问题" in feedback

    def test_generate_feedback_mixed_severities(self):
        controller = IterationController()
        issues = [
            {"issue_type": "h1", "severity": "high", "original_text": "a", "problem": "p1", "fix_applied": "f1"},
            {"issue_type": "m1", "severity": "medium", "original_text": "b", "problem": "p2", "fix_applied": "f2"},
            {"issue_type": "l1", "severity": "low", "original_text": "c", "problem": "p3", "fix_applied": "f3"},
        ]
        feedback = controller._generate_feedback(issues, 5)
        assert "🔴 高优先级问题" in feedback
        assert "🟡 中优先级问题" in feedback
        assert "🟢 低优先级问题" in feedback
        assert "请根据以上反馈修改章节内容" in feedback

    def test_generate_feedback_high_issues_capped_at_5(self):
        controller = IterationController()
        issues = [
            {"issue_type": f"issue{i}", "severity": "high", "original_text": f"text{i}", "problem": f"p{i}", "fix_applied": f"f{i}"}
            for i in range(7)
        ]
        feedback = controller._generate_feedback(issues, 4)
        # Only first 5 high issues should be detailed
        assert "issue0" in feedback
        assert "issue5" not in feedback  # 6th (index 5) should not appear
        assert "issue6" not in feedback

    def test_generate_feedback_no_severity_field(self):
        controller = IterationController()
        issues = [
            {"issue_type": "未知类型", "problem": "some problem"}
        ]
        feedback = controller._generate_feedback(issues, 5)
        # No severity field means it doesn't match high/medium/low
        assert "📝 发现 1 个问题需要修正" in feedback
        assert "请根据以上反馈修改章节内容" in feedback

    def test_generate_feedback_issue_without_issue_type(self):
        controller = IterationController()
        issues = [
            {"severity": "high", "original_text": "txt", "problem": "prob", "fix_applied": "fix"}
        ]
        feedback = controller._generate_feedback(issues, 4)
        assert "[未知]" in feedback

    def test_create_revision_prompt(self):
        controller = IterationController()
        draft = "original draft content " * 100
        feedback = "Please fix the dialogue"
        issues = [{"issue_type": "style", "severity": "high"}]
        prompt = controller.create_revision_prompt(draft, feedback, issues, 3)
        assert "第 3 次迭代" in prompt
        assert "校对反馈" in prompt
        assert feedback in prompt
        assert "original draft content" in prompt[:2500]
        assert "修改要求" in prompt
        assert "输出要求" in prompt

    def test_create_revision_prompt_truncates_long_draft(self):
        controller = IterationController()
        long_draft = "x" * 3000
        prompt = controller.create_revision_prompt(long_draft, "fb", [], 1)
        assert "..." in prompt
        assert len(prompt) < 3500  # Should be truncated


class TestGetIterationControllerSingleton:
    """get_iteration_controller singleton tests"""

    def setup_method(self):
        # Reset the singleton before each test
        import novels_project.iteration_controller as mod
        mod._controller = None

    def test_first_call_creates_controller(self):
        controller = get_iteration_controller()
        assert isinstance(controller, IterationController)
        assert controller.max_iterations == 3
        assert controller.quality_threshold == 7

    def test_first_call_with_custom_params(self):
        controller = get_iteration_controller(max_iterations=5, quality_threshold=9)
        assert controller.max_iterations == 5
        assert controller.quality_threshold == 9

    def test_second_call_with_same_params_returns_same(self):
        c1 = get_iteration_controller()
        c2 = get_iteration_controller()
        assert c1 is c2

    def test_second_call_with_different_params_updates_config(self):
        c1 = get_iteration_controller(max_iterations=3, quality_threshold=7)
        # Add a session to verify sessions are preserved
        c1.start_session(42)

        c2 = get_iteration_controller(max_iterations=10, quality_threshold=5)
        assert c1 is c2
        assert c2.max_iterations == 10
        assert c2.quality_threshold == 5
        # Sessions should be preserved
        assert c2.get_session(42) is not None

    def test_multiple_calls_preserve_state(self):
        c1 = get_iteration_controller(max_iterations=4, quality_threshold=6)
        c1.start_session(100)

        c2 = get_iteration_controller(max_iterations=8, quality_threshold=9)
        assert c1 is c2
        assert c2.max_iterations == 8
        assert c2.quality_threshold == 9
        assert c2.get_session(100) is not None