"""
迭代写作流程 - 使用 ConversationRuntime 管理多轮写作-校对迭代

在新架构中，迭代由主 Agent 的对话决策驱动。
此模块提供辅助函数用于 /chapter 命令的迭代模式。
"""
from typing import Dict, Any, Optional

from .iteration_controller import get_iteration_controller, IterationStatus, IterationResult


# 安全上限，防止意外的无限循环
MAX_SAFETY_LIMIT = 10


def get_iteration_report(chapter_id: int) -> str:
    """
    获取迭代报告

    Args:
        chapter_id: 章节ID

    Returns:
        迭代报告文本
    """
    controller = get_iteration_controller()
    session = controller.get_session(chapter_id)

    if not session:
        return f"章节 {chapter_id} 没有迭代记录"

    summary = session.get_summary()

    report = f"""
章节 {chapter_id} 迭代报告
{'='*50}

基本信息:
  - 总迭代次数: {summary['total_iterations']}
  - 最佳质量分数: {summary['best_quality_score']}/10
  - 质量阈值: {summary['quality_threshold']}/10
  - 最终状态: {summary['final_status']}

改进历史:
"""

    for h in summary['improvement_history']:
        report += f"  第{h['iteration']}轮: 分数 {h['score']}, 问题 {h['issues_count']}个\n"

    return report
