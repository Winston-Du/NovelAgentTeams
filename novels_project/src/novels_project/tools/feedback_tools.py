"""
反馈检索工具
"""
from typing import Optional, List, Dict, Any

# 延迟导入
_feedback_store = None


def _get_store():
    global _feedback_store
    if _feedback_store is None:
        from ..feedback_loop import get_feedback_store
        _feedback_store = get_feedback_store()
    return _feedback_store


def retrieve_feedback(issue_type: Optional[str] = None,
                      character: Optional[str] = None,
                      limit: int = 5) -> str:
    """
    检索历史校对反馈，用于避免重复犯错
    
    Args:
        issue_type: 可选，按问题类型筛选
            例如: "对话风格偏离", "Tell而非Show", "节奏问题"
        character: 可选，按人物筛选
            例如: "陆商曜", "黑商周桓"
        limit: 返回的反馈数量（1-10）
    
    Returns:
        历史反馈列表，包含问题描述和修正方案
    
    Examples:
        retrieve_feedback("对话风格偏离", "陆商曜", 3)
        retrieve_feedback(character="黑商周桓")
    """
    try:
        store = _get_store()
        
        if issue_type:
            feedbacks = store.get_feedback_by_type(issue_type)
        elif character:
            feedbacks = store.get_feedback_by_character(character)
        else:
            feedbacks = store.get_recent_feedback(limit=limit)
        
        if not feedbacks:
            return "📭 暂无相关历史反馈"
        
        # 限制数量
        feedbacks = feedbacks[-limit:]
        
        result = f"📚 找到 {len(feedbacks)} 条历史反馈:\n\n"
        
        for i, fb in enumerate(feedbacks, 1):
            result += f"【反馈 {i}】\n"
            result += f"  章节: 第{fb.get('chapter_id', '?')}章\n"
            result += f"  类型: {fb.get('issue_type', '未知')}\n"
            if fb.get('character'):
                result += f"  人物: {fb['character']}\n"
            result += f"  问题: {fb.get('problem', '无描述')}\n"
            result += f"  修正: {fb.get('fix_applied', '无')}\n"
            result += f"  原文: \"{fb.get('original_text', '')[:50]}...\"\n\n"
        
        return result
        
    except Exception as e:
        return f"❌ 反馈检索失败: {str(e)}"


def get_common_mistakes(limit: int = 5) -> str:
    """
    获取最常见的创作问题类型，用于预防性检查
    
    Args:
        limit: 返回的问题类型数量（1-10）
    
    Returns:
        最常见的问题类型列表及出现次数
    
    Examples:
        get_common_mistakes(5)
    """
    try:
        store = _get_store()
        common_issues = store.get_common_issues(limit=limit)
        stats = store.get_feedback_stats()
        
        if not common_issues:
            return "📭 暂无历史反馈数据"
        
        result = f"📊 常见问题统计 (共 {stats['total_feedback']} 条反馈)\n"
        result += "=" * 40 + "\n\n"
        
        for i, issue in enumerate(common_issues, 1):
            result += f"{i}. {issue['issue_type']}: {issue['count']} 次\n"
        
        result += "\n💡 建议: 在创作时特别注意以上问题类型"
        
        return result
        
    except Exception as e:
        return f"❌ 获取统计数据失败: {str(e)}"


def record_feedback(chapter_id: int,
                    issue_type: str,
                    character: Optional[str],
                    original_text: str,
                    problem: str,
                    fix_applied: str,
                    severity: str = "medium") -> str:
    """
    记录一条校对反馈到反馈库
    
    Args:
        chapter_id: 章节ID
        issue_type: 问题类型
            例如: "对话风格偏离", "Tell而非Show", "节奏问题", "逻辑漏洞"
        character: 相关人物（可选）
        original_text: 原始有问题的文本
        problem: 问题描述
        fix_applied: 应用的修正方案
        severity: 严重程度 (high/medium/low)
    
    Returns:
        反馈ID
    
    Examples:
        record_feedback(1, "对话风格偏离", "陆商曜", 
                       "我需要仔细分析一下...", 
                       "陆商曜不应该过度解释",
                       "三成换一个安稳，贵了。")
    """
    try:
        store = _get_store()
        feedback_id = store.add_feedback(
            chapter_id=chapter_id,
            issue_type=issue_type,
            character=character,
            original_text=original_text,
            problem=problem,
            fix_applied=fix_applied,
            severity=severity
        )
        return f"✅ 反馈已记录: {feedback_id}"
        
    except Exception as e:
        return f"❌ 记录反馈失败: {str(e)}"


def record_batch_feedback(chapter_id: int,
                          issues_json: str) -> str:
    """
    批量记录校对反馈
    
    Args:
        chapter_id: 章节ID
        issues_json: JSON 格式的问题列表
            格式: [{"issue_type": "...", "character": "...", "original_text": "...", 
                   "problem": "...", "fix_applied": "...", "severity": "..."}]
    
    Returns:
        记录结果
    
    Examples:
        issues = '[{"issue_type": "对话风格偏离", "character": "陆商曜", ...}]'
        record_batch_feedback(1, issues)
    """
    try:
        import json
        store = _get_store()
        issues = json.loads(issues_json)
        count = store.add_batch_feedback(chapter_id, issues)
        return f"✅ 已记录 {count} 条反馈"
        
    except Exception as e:
        return f"❌ 批量记录失败: {str(e)}"
