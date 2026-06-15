"""
单元测试：章节标题验证

测试范围：
1. 确认 title 值正确赋值给 record.title
2. 确保无 null、undefined 或错误值
3. 验证标题与生成文章标题匹配
4. 跨多种文章类型和标题格式验证
"""

import pytest
import asyncio
from pathlib import Path
import yaml
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from novels_project.api.content import get_chapters, get_chapter


class TestChapterTitleAssignment:
    """测试章节标题正确赋值"""

    def test_title_from_summary_yaml(self, tmp_path, monkeypatch):
        """测试从摘要 YAML 中读取标题"""
        # Mock 项目目录
        monkeypatch.setattr("novels_project.api.content.get_chapters_dir", lambda: tmp_path / "chapters")
        monkeypatch.setattr("novels_project.api.content.get_summaries_dir", lambda: tmp_path / "summaries")
        
        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"
        chapters_dir.mkdir()
        summaries_dir.mkdir()
        
        # 创建章节文件
        chapter_file = chapters_dir / "chapter_1_final.md"
        chapter_file.write_text("# 第一章：测试标题\n\n内容", encoding="utf-8")
        
        # 创建摘要文件（包含标题）
        summary_file = summaries_dir / "chapter_1_summary.yaml"
        summary_data = {"title": "从YAML读取的标题", "summary": "测试摘要"}
        with open(summary_file, "w", encoding="utf-8") as f:
            yaml.dump(summary_data, f, allow_unicode=True)
        
        # 调用 get_chapters
        chapters = asyncio.run(get_chapters())
        
        assert len(chapters) == 1
        assert chapters[0]["title"] == "从YAML读取的标题"
        assert chapters[0]["chapter_id"] == "1"

    def test_title_fallback_to_default(self, tmp_path, monkeypatch):
        """测试无摘要时回退到默认标题"""
        monkeypatch.setattr("novels_project.api.content.get_chapters_dir", lambda: tmp_path / "chapters")
        monkeypatch.setattr("novels_project.api.content.get_summaries_dir", lambda: tmp_path / "summaries")
        
        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"
        chapters_dir.mkdir()
        summaries_dir.mkdir()
        
        # 创建章节文件（无摘要）
        chapter_file = chapters_dir / "chapter_5_final.md"
        chapter_file.write_text("# 第五章\n\n内容", encoding="utf-8")
        
        chapters = asyncio.run(get_chapters())
        
        assert len(chapters) == 1
        assert chapters[0]["title"] == "第 5 章"
        assert chapters[0]["chapter_id"] == "5"

    def test_title_no_null_or_undefined(self, tmp_path, monkeypatch):
        """测试标题不会为 null 或空值"""
        monkeypatch.setattr("novels_project.api.content.get_chapters_dir", lambda: tmp_path / "chapters")
        monkeypatch.setattr("novels_project.api.content.get_summaries_dir", lambda: tmp_path / "summaries")
        
        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"
        chapters_dir.mkdir()
        summaries_dir.mkdir()
        
        # 创建多个章节文件
        for i in range(1, 4):
            chapter_file = chapters_dir / f"chapter_{i}_final.md"
            chapter_file.write_text(f"# 第{i}章\n\n内容", encoding="utf-8")
        
        chapters = asyncio.run(get_chapters())
        
        for chapter in chapters:
            assert chapter["title"] is not None
            assert chapter["title"] != ""
            assert isinstance(chapter["title"], str)
            assert len(chapter["title"]) > 0

    def test_title_matches_intended_title(self, tmp_path, monkeypatch):
        """测试标题与预期标题匹配"""
        monkeypatch.setattr("novels_project.api.content.get_chapters_dir", lambda: tmp_path / "chapters")
        monkeypatch.setattr("novels_project.api.content.get_summaries_dir", lambda: tmp_path / "summaries")
        
        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"
        chapters_dir.mkdir()
        summaries_dir.mkdir()
        
        # 创建带特定标题的章节
        chapter_file = chapters_dir / "chapter_10_final.md"
        chapter_file.write_text("# 第十章：决战前夕\n\n内容", encoding="utf-8")
        
        # 创建摘要（标题与文件内容一致）
        summary_file = summaries_dir / "chapter_10_summary.yaml"
        summary_data = {"title": "第十章：决战前夕", "summary": "决战前的准备"}
        with open(summary_file, "w", encoding="utf-8") as f:
            yaml.dump(summary_data, f, allow_unicode=True)
        
        chapters = asyncio.run(get_chapters())
        
        assert chapters[0]["title"] == "第十章：决战前夕"

    def test_title_various_formats(self, tmp_path, monkeypatch):
        """测试多种标题格式"""
        monkeypatch.setattr("novels_project.api.content.get_chapters_dir", lambda: tmp_path / "chapters")
        monkeypatch.setattr("novels_project.api.content.get_summaries_dir", lambda: tmp_path / "summaries")
        
        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"
        chapters_dir.mkdir()
        summaries_dir.mkdir()
        
        test_cases = [
            ("1", "第一章：入门", "简单标题"),
            ("2", "Chapter 2: The Journey", "英文标题"),
            ("3", "第3章 - 特殊符号!@#", "特殊字符"),
            ("4", "", "空标题（应回退）"),
        ]
        
        for chapter_id, title, description in test_cases:
            chapter_file = chapters_dir / f"chapter_{chapter_id}_final.md"
            chapter_file.write_text(f"# {title}\n\n内容", encoding="utf-8")
            
            if title:  # 只有非空标题才创建摘要
                summary_file = summaries_dir / f"chapter_{chapter_id}_summary.yaml"
                summary_data = {"title": title, "summary": description}
                with open(summary_file, "w", encoding="utf-8") as f:
                    yaml.dump(summary_data, f, allow_unicode=True)
        
        chapters = asyncio.run(get_chapters())
        
        # 验证各种格式
        titles = {c["chapter_id"]: c["title"] for c in chapters}
        
        assert titles["1"] == "第一章：入门"
        assert titles["2"] == "Chapter 2: The Journey"
        assert titles["3"] == "第3章 - 特殊符号!@#"
        # 第4章没有摘要且标题为空，应回退到默认
        assert titles["4"] == "第 4 章"

    def test_title_from_markdown_header(self, tmp_path, monkeypatch):
        """测试从 Markdown 文件头读取标题（get_chapter 单章接口）"""
        monkeypatch.setattr("novels_project.api.content.get_chapters_dir", lambda: tmp_path / "chapters")
        monkeypatch.setattr("novels_project.api.content.get_summaries_dir", lambda: tmp_path / "summaries")
        
        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"
        chapters_dir.mkdir()
        summaries_dir.mkdir()
        
        # 创建章节文件
        chapter_file = chapters_dir / "chapter_7_final.md"
        chapter_file.write_text("# 第七章：秘境探险\n\n内容", encoding="utf-8")
        
        # 测试 get_chapter 单章接口
        chapter = asyncio.run(get_chapter("7"))
        
        assert chapter["title"] == "第七章：秘境探险"
        assert chapter["chapter_id"] == "7"


class TestChapterTitleEdgeCases:
    """测试章节标题边界情况"""

    def test_empty_chapters_dir(self, tmp_path, monkeypatch):
        """测试空章节目录"""
        monkeypatch.setattr("novels_project.api.content.get_chapters_dir", lambda: tmp_path / "chapters")
        monkeypatch.setattr("novels_project.api.content.get_summaries_dir", lambda: tmp_path / "summaries")
        
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        
        chapters = asyncio.run(get_chapters())
        
        assert isinstance(chapters, list)
        assert len(chapters) == 0

    def test_summary_without_title_field(self, tmp_path, monkeypatch):
        """测试摘要中没有 title 字段"""
        monkeypatch.setattr("novels_project.api.content.get_chapters_dir", lambda: tmp_path / "chapters")
        monkeypatch.setattr("novels_project.api.content.get_summaries_dir", lambda: tmp_path / "summaries")
        
        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"
        chapters_dir.mkdir()
        summaries_dir.mkdir()
        
        chapter_file = chapters_dir / "chapter_8_final.md"
        chapter_file.write_text("# 第八章\n\n内容", encoding="utf-8")
        
        # 创建没有 title 字段的摘要
        summary_file = summaries_dir / "chapter_8_summary.yaml"
        summary_data = {"summary": "没有标题的摘要"}
        with open(summary_file, "w", encoding="utf-8") as f:
            yaml.dump(summary_data, f, allow_unicode=True)
        
        chapters = asyncio.run(get_chapters())
        
        assert chapters[0]["title"] == "第 8 章"  # 应回退到默认

    def test_unicode_title(self, tmp_path, monkeypatch):
        """测试 Unicode 标题"""
        monkeypatch.setattr("novels_project.api.content.get_chapters_dir", lambda: tmp_path / "chapters")
        monkeypatch.setattr("novels_project.api.content.get_summaries_dir", lambda: tmp_path / "summaries")
        
        chapters_dir = tmp_path / "chapters"
        summaries_dir = tmp_path / "summaries"
        chapters_dir.mkdir()
        summaries_dir.mkdir()
        
        unicode_title = "第九章：🐉 龙族觉醒"
        chapter_file = chapters_dir / "chapter_9_final.md"
        chapter_file.write_text(f"# {unicode_title}\n\n内容", encoding="utf-8")
        
        summary_file = summaries_dir / "chapter_9_summary.yaml"
        summary_data = {"title": unicode_title, "summary": "Unicode测试"}
        with open(summary_file, "w", encoding="utf-8") as f:
            yaml.dump(summary_data, f, allow_unicode=True)
        
        chapters = asyncio.run(get_chapters())
        
        assert chapters[0]["title"] == unicode_title


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
