"""
Tests for chapter_fix_tools.
TDD: Write failing test first, then make it pass.
"""
import pytest
import tempfile
from pathlib import Path
import yaml


class TestChapterFixTools:
    """Test suite for chapter fix tools."""

    @pytest.fixture
    def temp_output_dir(self, tmp_path):
        """Create a temporary output directory with test chapters."""
        output_dir = tmp_path / "output"
        chapters_dir = output_dir / "chapters"
        chapters_dir.mkdir(parents=True)

        # Create test chapters
        for i in [1, 2, 3]:
            chapter_file = chapters_dir / f"chapter_{i}_final.md"
            chapter_file.write_text(f"# 第 {i} 章\n\n这是第{i}章的测试内容。", encoding="utf-8")

        return tmp_path

    def test_list_generated_chapters(self, temp_output_dir):
        """Test listing all generated chapters."""
        from novels_project.tools.chapter_fix_tools import list_generated_chapters

        result = list_generated_chapters(output_dir=str(temp_output_dir / "output"))

        assert "已生成章节" in result
        assert "3 章" in result
        assert "第1章" in result

    def test_get_chapter_content(self, temp_output_dir):
        """Test getting chapter content."""
        from novels_project.tools.chapter_fix_tools import get_chapter_content

        result = get_chapter_content(chapter_id=1, output_dir=str(temp_output_dir / "output"))

        assert "第1章" in result
        assert "测试内容" in result

    def test_get_nonexistent_chapter(self, temp_output_dir):
        """Test getting a chapter that doesn't exist."""
        from novels_project.tools.chapter_fix_tools import get_chapter_content

        result = get_chapter_content(chapter_id=99, output_dir=str(temp_output_dir / "output"))

        assert "尚未生成" in result

    def test_fix_chapter_issue(self, temp_output_dir):
        """Test recording a chapter issue."""
        from novels_project.tools.chapter_fix_tools import fix_chapter_issue

        result = fix_chapter_issue(
            chapter_id=3,
            issue_description="结尾反杀太突兀，缺乏铺垫",
            original_text="陆商曜冷笑一声，契约印光芒大作...",
            fix_instruction="增加契约印的伏笔",
            severity="high",
            output_dir=str(temp_output_dir / "output"),
        )

        assert "修正任务" in result
        assert "结尾反杀太突兀" in result
        assert "增加契约印的伏笔" in result

    def test_fix_chapter_issue_minimal(self, temp_output_dir):
        """Test recording a chapter issue with minimal info."""
        from novels_project.tools.chapter_fix_tools import fix_chapter_issue

        result = fix_chapter_issue(
            chapter_id=1,
            issue_description="对话不够生动",
            output_dir=str(temp_output_dir / "output"),
        )

        assert "修正任务" in result
        assert "对话不够生动" in result
