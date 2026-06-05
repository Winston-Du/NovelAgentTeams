"""
单元测试：章节修正工具 (chapter_fix_tools)

测试覆盖:
- fix_chapter_issue, get_chapter_content, list_generated_chapters
"""
from unittest.mock import patch


# =========================================================================
#  fix_chapter_issue
# =========================================================================
class TestFixChapterIssue:
    """Tests for fix_chapter_issue."""

    def test_with_all_params(self):
        """fix_chapter_issue with all parameters."""
        from novels_project.tools.chapter_fix_tools import fix_chapter_issue

        with patch("novels_project.tools.feedback_tools.record_feedback",
                   return_value="反馈ID: FB-001") as mock_record:
            result = fix_chapter_issue(
                chapter_id=3,
                issue_description="结尾反杀太突兀，缺乏铺垫",
                original_text="陆商曜冷笑一声，契约印光芒大作...",
                fix_instruction="增加契约印的伏笔，让读者提前感受到主角的准备",
                severity="high",
            )

            # Verify record_feedback was called correctly
            mock_record.assert_called_once_with(
                chapter_id=3,
                issue_type="用户反馈-需修正",
                character=None,
                original_text="陆商曜冷笑一声，契约印光芒大作...",
                problem="结尾反杀太突兀，缺乏铺垫",
                fix_applied="增加契约印的伏笔，让读者提前感受到主角的准备",
                severity="high",
            )

            assert "第3章修正任务" in result
            assert "结尾反杀太突兀" in result
            assert "陆商曜冷笑一声" in result
            assert "增加契约印的伏笔" in result
            assert "FB-001" in result

    def test_without_original_text(self):
        """fix_chapter_issue without original_text uses fallback."""
        from novels_project.tools.chapter_fix_tools import fix_chapter_issue

        with patch("novels_project.tools.feedback_tools.record_feedback",
                   return_value="反馈ID: FB-002") as mock_record:
            result = fix_chapter_issue(
                chapter_id=5,
                issue_description="节奏太慢",
                fix_instruction="加快节奏",
                severity="low",
            )

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args[1]
            assert call_kwargs["original_text"] == "第5章问题"
            assert call_kwargs["chapter_id"] == 5
            assert call_kwargs["severity"] == "low"

            assert "第5章修正任务" in result
            assert "节奏太慢" in result
            # original_text should NOT appear in guidance when empty
            assert "原文片段" not in result

    def test_without_fix_instruction(self):
        """fix_chapter_issue without fix_instruction uses fallback."""
        from novels_project.tools.chapter_fix_tools import fix_chapter_issue

        with patch("novels_project.tools.feedback_tools.record_feedback",
                   return_value="反馈ID: FB-003") as mock_record:
            result = fix_chapter_issue(
                chapter_id=2,
                issue_description="人物性格不一致",
                original_text="某段文本",
            )

            call_kwargs = mock_record.call_args[1]
            assert call_kwargs["fix_applied"] == "待修正"
            assert call_kwargs["severity"] == "medium"  # default

            assert "第2章修正任务" in result
            assert "人物性格不一致" in result
            assert "原文片段" in result
            # fix_instruction should NOT appear when empty
            assert "**修正方向**" not in result

    def test_with_custom_severity(self):
        """fix_chapter_issue with custom severity."""
        from novels_project.tools.chapter_fix_tools import fix_chapter_issue

        for sev in ["high", "medium", "low"]:
            with patch("novels_project.tools.feedback_tools.record_feedback",
                       return_value="OK"):
                result = fix_chapter_issue(
                    chapter_id=1,
                    issue_description="测试",
                    severity=sev,
                )
                assert f"**严重程度**: {sev}" in result


# =========================================================================
#  get_chapter_content
# =========================================================================
class TestGetChapterContent:
    """Tests for get_chapter_content."""

    def test_chapter_exists(self, tmp_path):
        """get_chapter_content returns content when chapter exists."""
        from novels_project.tools.chapter_fix_tools import get_chapter_content

        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        chapter_file = chapters_dir / "chapter_3_final.md"
        chapter_file.write_text("# 第三章\n\n这是测试内容。", encoding="utf-8")

        with patch("novels_project.tools.chapter_fix_tools.get_chapters_dir",
                   return_value=chapters_dir):
            result = get_chapter_content(chapter_id=3)
            assert "第3章内容" in result
            assert "测试内容" in result

    def test_chapter_does_not_exist(self, tmp_path):
        """get_chapter_content returns message when chapter doesn't exist."""
        from novels_project.tools.chapter_fix_tools import get_chapter_content

        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()

        with patch("novels_project.tools.chapter_fix_tools.get_chapters_dir",
                   return_value=chapters_dir):
            result = get_chapter_content(chapter_id=99)
            assert "尚未生成" in result

    def test_with_custom_output_dir(self, tmp_path):
        """get_chapter_content with custom output_dir."""
        from novels_project.tools.chapter_fix_tools import get_chapter_content

        output_dir = tmp_path / "custom_output"
        chapters_dir = output_dir / "chapters"
        chapters_dir.mkdir(parents=True)
        chapter_file = chapters_dir / "chapter_1_final.md"
        chapter_file.write_text("自定义内容", encoding="utf-8")

        result = get_chapter_content(chapter_id=1, output_dir=str(output_dir))
        assert "第1章内容" in result
        assert "自定义内容" in result

    def test_chapter_exists_with_default_dir(self, tmp_path):
        """get_chapter_content uses default get_chapters_dir when no output_dir."""
        from novels_project.tools.chapter_fix_tools import get_chapter_content

        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        chapter_file = chapters_dir / "chapter_7_final.md"
        chapter_file.write_text("第七章测试", encoding="utf-8")

        with patch("novels_project.tools.chapter_fix_tools.get_chapters_dir",
                   return_value=chapters_dir):
            result = get_chapter_content(chapter_id=7)
            assert "第七章测试" in result


# =========================================================================
#  list_generated_chapters
# =========================================================================
class TestListGeneratedChapters:
    """Tests for list_generated_chapters."""

    def test_chapters_exist(self, tmp_path):
        """list_generated_chapters lists all generated chapters."""
        from novels_project.tools.chapter_fix_tools import list_generated_chapters

        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        for i in range(1, 6):
            (chapters_dir / f"chapter_{i}_final.md").write_text(f"Chapter {i}", encoding="utf-8")

        with patch("novels_project.tools.chapter_fix_tools.get_chapters_dir",
                   return_value=chapters_dir):
            result = list_generated_chapters()
            assert "已生成章节" in result
            assert "5 章" in result
            for i in range(1, 6):
                assert f"第{i}章" in result

    def test_no_chapters(self, tmp_path):
        """list_generated_chapters when directory exists but no chapter files."""
        from novels_project.tools.chapter_fix_tools import list_generated_chapters

        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()

        with patch("novels_project.tools.chapter_fix_tools.get_chapters_dir",
                   return_value=chapters_dir):
            result = list_generated_chapters()
            assert "尚未生成任何章节" in result

    def test_chapters_dir_does_not_exist(self, tmp_path):
        """list_generated_chapters when the chapters directory doesn't exist."""
        from novels_project.tools.chapter_fix_tools import list_generated_chapters

        nonexistent = tmp_path / "nonexistent_chapters"

        with patch("novels_project.tools.chapter_fix_tools.get_chapters_dir",
                   return_value=nonexistent):
            result = list_generated_chapters()
            assert "尚未生成任何章节" in result

    def test_with_custom_output_dir(self, tmp_path):
        """list_generated_chapters with custom output_dir."""
        from novels_project.tools.chapter_fix_tools import list_generated_chapters

        output_dir = tmp_path / "custom_output"
        chapters_dir = output_dir / "chapters"
        chapters_dir.mkdir(parents=True)
        for i in [1, 2]:
            (chapters_dir / f"chapter_{i}_final.md").write_text(f"C{i}", encoding="utf-8")

        result = list_generated_chapters(output_dir=str(output_dir))
        assert "已生成章节" in result
        assert "2 章" in result
        assert "第1章" in result
        assert "第2章" in result

    def test_with_custom_output_dir_no_chapters(self, tmp_path):
        """list_generated_chapters with custom output_dir that has no chapter files."""
        from novels_project.tools.chapter_fix_tools import list_generated_chapters

        output_dir = tmp_path / "empty_output"
        chapters_dir = output_dir / "chapters"
        chapters_dir.mkdir(parents=True)

        result = list_generated_chapters(output_dir=str(output_dir))
        assert "尚未生成任何章节" in result

    def test_with_custom_output_dir_nonexistent(self, tmp_path):
        """list_generated_chapters with custom output_dir that doesn't exist."""
        from novels_project.tools.chapter_fix_tools import list_generated_chapters

        result = list_generated_chapters(output_dir=str(tmp_path / "ghost"))
        assert "尚未生成任何章节" in result

    def test_non_matching_filenames(self, tmp_path):
        """list_generated_chapters with files that don't match the regex pattern."""
        from novels_project.tools.chapter_fix_tools import list_generated_chapters

        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        # Files that don't match the regex pattern
        (chapters_dir / "chapter_1_draft.md").write_text("draft", encoding="utf-8")
        (chapters_dir / "notes.md").write_text("notes", encoding="utf-8")
        (chapters_dir / "chapter_1_final.md").write_text("Chapter 1", encoding="utf-8")

        with patch("novels_project.tools.chapter_fix_tools.get_chapters_dir",
                   return_value=chapters_dir):
            result = list_generated_chapters()
            assert "已生成章节" in result
            assert "第1章" in result