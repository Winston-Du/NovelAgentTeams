"""
章节修正工具 - 根据用户反馈修改章节并自动记录问题
"""
import json
from pathlib import Path
from typing import Optional
import yaml


def fix_chapter_issue(
    chapter_id: int,
    issue_description: str,
    original_text: str = "",
    fix_instruction: str = "",
    severity: str = "medium",
    output_dir: str = "output",
) -> str:
    """
    记录章节问题并提供修正指导。此工具用于：
    1. 记录用户发现的问题到反馈库
    2. 返回修正指导供 plot_writer 使用

    Args:
        chapter_id: 章节ID
        issue_description: 问题描述（用户发现的具体问题）
        original_text: 有问题的原文片段（可选，帮助定位）
        fix_instruction: 修正指导（用户希望的修改方向）
        severity: 严重程度 (high/medium/low)

    Returns:
        包含反馈ID和修正指导的信息

    Examples:
        fix_chapter_issue(
            chapter_id=3,
            issue_description="结尾反杀太突兀，缺乏铺垫",
            original_text="陆商曜冷笑一声，契约印光芒大作...",
            fix_instruction="增加契约印的伏笔，让读者提前感受到主角的准备",
            severity="high"
        )
    """
    from .feedback_tools import record_feedback

    # 记录到反馈库
    result = record_feedback(
        chapter_id=chapter_id,
        issue_type="用户反馈-需修正",
        character=None,
        original_text=original_text or f"第{chapter_id}章问题",
        problem=issue_description,
        fix_applied=fix_instruction or "待修正",
        severity=severity,
    )

    # 构建修正指导
    guidance = f"""
## 第{chapter_id}章修正任务

**问题描述**: {issue_description}
**严重程度**: {severity}

"""
    if original_text:
        guidance += f"**原文片段**: \"{original_text[:200]}...\"\n\n"
    if fix_instruction:
        guidance += f"**修正方向**: {fix_instruction}\n\n"

    guidance += f"""
**反馈记录**: {result}

请根据以上指导修改第{chapter_id}章。修改完成后确保：
1. 问题已解决
2. 保持人物性格一致
3. 与前后文衔接自然
"""

    return guidance


def get_chapter_content(chapter_id: int, output_dir: str = "output") -> str:
    """
    获取已生成的章节内容，用于查看和修改。

    Args:
        chapter_id: 章节ID
        output_dir: 输出目录

    Returns:
        章节内容
    """
    chapter_file = Path(output_dir) / "chapters" / f"chapter_{chapter_id}_final.md"

    if not chapter_file.exists():
        return f"第{chapter_id}章尚未生成。请先生成章节。"

    with open(chapter_file, "r", encoding="utf-8") as f:
        content = f.read()

    return f"## 第{chapter_id}章内容\n\n{content}"


def list_generated_chapters(output_dir: str = "output") -> str:
    """
    列出所有已生成的章节。

    Args:
        output_dir: 输出目录

    Returns:
        已生成章节列表
    """
    chapters_dir = Path(output_dir) / "chapters"

    if not chapters_dir.exists():
        return "尚未生成任何章节。"

    chapters = sorted(chapters_dir.glob("chapter_*_final.md"))

    if not chapters:
        return "尚未生成任何章节。"

    result = f"已生成章节 ({len(chapters)} 章)\n"
    result += "=" * 40 + "\n\n"

    for path in chapters:
        # 从文件名提取章节号
        filename = path.stem
        import re
        match = re.search(r"chapter_(\d+)_final", filename)
        if match:
            chapter_num = match.group(1)
            # 获取文件大小
            size = path.stat().st_size
            result += f"  第{chapter_num}章: {size:,} 字节\n"

    return result
