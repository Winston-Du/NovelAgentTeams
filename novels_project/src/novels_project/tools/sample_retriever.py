"""
样例检索工具
"""
from typing import Optional

# 延迟导入以避免循环依赖
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        from ..retrieval_engine import get_retrieval_engine
        _engine = get_retrieval_engine()
    return _engine


def retrieve_writing_samples(query: str,
                            chapter_type: Optional[str] = None,
                            num_samples: int = 3) -> str:
    """
    检索相似的写作样例，用于参考

    Args:
        query: 描述你想写的场景或类型
            比如："权谋听证、多角色对话、逻辑碾压"
        chapter_type: 可选的章节类型筛选
            选项: "战斗章", "情感章", "权谋章", "经营章", "节奏章"
        num_samples: 返回的样例数（1-5）

    Returns:
        相似样例内容

    Examples:
        retrieve_writing_samples("描写激烈战斗的动作细节", "战斗章", 3)
        retrieve_writing_samples("市集场景+商人谈判", "权谋章")
    """
    try:
        engine = get_engine()
        samples = engine.retrieve_samples(
            query=query,
            k=num_samples,
            chapter_type=chapter_type
        )

        if not samples:
            return "❌ 未找到相关样例，请检查查询词或样例库"

        result = f"📚 找到 {len(samples)} 个相似样例:\n\n"
        for sample in samples:
            result += sample + "\n"

        return result

    except Exception as e:
        return f"❌ 样例检索失败: {str(e)}"


# 用于手动刷新向量库
def refresh_sample_library():
    """刷新样例库（有新样例时调用）"""
    engine = get_engine()
    engine.refresh()
    return "✅ 样例库已刷新"
