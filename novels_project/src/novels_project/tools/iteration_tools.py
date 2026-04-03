"""
迭代写作工具
"""
from typing import Optional


def _get_controller():
    """获取迭代控制器单例（使用默认参数，若实例已存在则直接返回现有实例）"""
    from ..iteration_controller import get_iteration_controller
    return get_iteration_controller()


def check_iteration_status(chapter_id: int) -> str:
    """
    检查当前章节的迭代状态
    
    Args:
        chapter_id: 章节ID
    
    Returns:
        迭代状态信息，包含当前迭代次数、最佳分数等
    
    Examples:
        check_iteration_status(1)
    """
    try:
        controller = _get_controller()
        session = controller.get_session(chapter_id)
        
        if not session:
            return f"📭 章节 {chapter_id} 尚未开始迭代"
        
        summary = session.get_summary()
        
        result = f"📊 章节 {chapter_id} 迭代状态\n"
        result += "=" * 40 + "\n\n"
        result += f"当前迭代: {summary['total_iterations']}/{summary['max_iterations']}\n"
        result += f"最佳分数: {summary['best_quality_score']}/10\n"
        result += f"质量阈值: {summary['quality_threshold']}/10\n"
        
        if summary['final_status']:
            result += f"最终状态: {summary['final_status']}\n"
        
        if summary['improvement_history']:
            result += "\n📈 改进历史:\n"
            for h in summary['improvement_history']:
                result += f"  第{h['iteration']}轮: 分数 {h['score']}, 问题 {h['issues_count']}个\n"
        
        return result
        
    except Exception as e:
        return f"❌ 检查状态失败: {str(e)}"


def should_continue_iteration(chapter_id: int, quality_score: int) -> str:
    """
    判断是否需要继续迭代
    
    Args:
        chapter_id: 章节ID
        quality_score: 当前质量评分 (1-10)
    
    Returns:
        是否需要继续迭代的决定
    
    Examples:
        should_continue_iteration(1, 6)  # 返回 "continue"
        should_continue_iteration(1, 8)  # 返回 "accept"
    """
    try:
        from ..iteration_controller import IterationStatus
        
        controller = _get_controller()
        session = controller.get_session(chapter_id)
        
        if not session:
            return f"❌ 章节 {chapter_id} 尚未开始迭代，请先调用 start_iteration"
        
        status = session.should_continue(quality_score)
        
        if status == IterationStatus.ACCEPT:
            return f"✅ 质量达标 ({quality_score}/10)，无需继续迭代"
        elif status == IterationStatus.MAX_ITER:
            return f"⚠️ 已达最大迭代次数 ({session.max_iterations})，停止迭代"
        else:
            remaining = session.max_iterations - session.current_iteration()
            return f"🔄 需要继续迭代 (当前分数: {quality_score}/10，剩余迭代次数: {remaining})"
        
    except Exception as e:
        return f"❌ 判断失败: {str(e)}"


def get_revision_feedback(chapter_id: int) -> str:
    """
    获取上一轮校对的反馈，用于指导修改
    
    Args:
        chapter_id: 章节ID
    
    Returns:
        校对反馈和修改建议
    
    Examples:
        get_revision_feedback(1)
    """
    try:
        controller = _get_controller()
        session = controller.get_session(chapter_id)
        
        if not session or not session.iterations:
            return "📭 暂无校对反馈"
        
        latest = session.iterations[-1]
        
        result = f"📝 第 {latest.iteration} 轮校对反馈\n"
        result += "=" * 40 + "\n\n"
        result += f"质量评分: {latest.quality_score}/10\n\n"
        result += latest.feedback
        
        return result
        
    except Exception as e:
        return f"❌ 获取反馈失败: {str(e)}"


def record_iteration(chapter_id: int, 
                     draft: str,
                     review_issues: str,
                     quality_score: int) -> str:
    """
    记录一次迭代结果
    
    Args:
        chapter_id: 章节ID
        draft: 草稿内容
        review_issues: 校对发现的问题（JSON 格式）
        quality_score: 质量评分 (1-10)
    
    Returns:
        记录结果
    
    Examples:
        record_iteration(1, "章节内容...", '[{"issue_type": "对话风格偏离", ...}]', 6)
    """
    try:
        import json
        from ..iteration_controller import IterationResult, IterationStatus
        
        controller = _get_controller()
        session = controller.get_session(chapter_id)
        
        if not session:
            session = controller.start_session(chapter_id)
        
        # 解析问题列表
        try:
            issues = json.loads(review_issues) if review_issues else []
        except (json.JSONDecodeError, TypeError) as e:
            issues = []
            print(f"⚠️ review_issues JSON 解析失败: {e}")
        
        # 判断状态
        status = session.should_continue(quality_score)
        
        # 创建迭代结果
        result = IterationResult(
            iteration=session.current_iteration() + 1,
            draft=draft,
            review_issues=issues,
            quality_score=quality_score,
            status=status
        )
        
        session.add_iteration(result)
        
        return f"✅ 已记录第 {result.iteration} 次迭代 (分数: {quality_score}/10, 状态: {status.value})"
        
    except Exception as e:
        return f"❌ 记录失败: {str(e)}"
