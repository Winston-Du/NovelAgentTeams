"""
迭代写作流程 - 管理多轮写作-校对迭代
"""
from typing import Dict, Any
from .iteration_controller import get_iteration_controller, IterationStatus, IterationResult

# 安全上限，防止意外的无限循环
MAX_SAFETY_LIMIT = 10


def run_iterative_writing(crew, chapter_id: int, inputs: Dict[str, Any],
                          max_iterations: int = 3, quality_threshold: int = 7) -> Dict[str, Any]:
    """
    运行迭代写作流程
    
    Args:
        crew: NovelsCrewAI 实例
        chapter_id: 章节ID
        inputs: 输入数据
        max_iterations: 最大迭代次数
        quality_threshold: 质量阈值
    
    Returns:
        包含最终结果的字典
    """
    controller = get_iteration_controller(
        max_iterations=max_iterations,
        quality_threshold=quality_threshold
    )
    
    # 开始迭代会话
    session = controller.start_session(chapter_id)
    
    # 启动日志和指标
    crew.logger.start_chapter(chapter_id)
    crew.metrics.start_chapter(chapter_id)
    crew.logger.log(f"第 {chapter_id} 章迭代写作开始", "START")
    
    print(f"\n{'='*50}")
    print(f"🔄 开始迭代写作流程 - 章节 {chapter_id}")
    print(f"   最大迭代次数: {max_iterations}")
    print(f"   质量阈值: {quality_threshold}/10")
    print(f"{'='*50}\n")
    
    # 确保 inputs 中有 revision_feedback 默认值（避免首轮 KeyError）
    if 'revision_feedback' not in inputs:
        inputs['revision_feedback'] = '（首次创作，无历史反馈）'
    
    iteration = 0
    metrics_data = None
    # 首轮使用完整 Crew（4个Agent），后续使用精简 Crew（2个Agent）
    full_crew = crew.crew()
    
    try:
        while iteration < MAX_SAFETY_LIMIT:
            iteration += 1
            print(f"\n📝 第 {iteration} 轮迭代")
            print("-" * 30)
            
            if iteration == 1:
                # 首轮：完整流程（总编→人物设计师→剧情撰写员→校对）
                print("   🏗️ 完整流程（4个Agent）")
                result = full_crew.kickoff(inputs=inputs)
            else:
                # 后续轮次：仅重跑剧情撰写员和校对
                print("   🔄 修改流程（2个Agent：撰写员+校对）")
                rev_crew = crew.revision_crew()  # 每次都创建新实例
                result = rev_crew.kickoff(inputs=inputs)
            
            # 从校对输出中解析质量评分和问题列表
            issues, quality_score, feedback = controller.parse_review_output(str(result))
            
            # 判断是否继续
            status = session.should_continue(quality_score)
            
            # 记录迭代结果
            iter_result = IterationResult(
                iteration=iteration,
                draft=str(result),
                review_issues=issues,
                quality_score=quality_score,
                status=status,
                feedback=feedback,
            )
            session.add_iteration(iter_result)
            
            print(f"   质量评分: {quality_score}/10")
            print(f"   问题数量: {len(issues)}")
            print(f"   状态: {status.value}")
            
            if status == IterationStatus.ACCEPT:
                print(f"\n✅ 质量达标，接受结果")
                break
            elif status == IterationStatus.MAX_ITER:
                print(f"\n⚠️ 达到最大迭代次数，使用最佳结果")
                break
            else:
                print(f"\n🔄 需要继续迭代...")
                # 生成修改提示并传递给下一轮
                revision_prompt = controller.create_revision_prompt(
                    original_draft=str(result),
                    feedback=feedback,
                    issues=issues,
                    iteration=iteration,
                )
                inputs = {**inputs, 'revision_feedback': revision_prompt}
        else:
            print(f"\n⛔ 达到安全上限 {MAX_SAFETY_LIMIT} 次迭代，强制停止")
    finally:
        # 结束日志和指标
        crew.logger.log(f"第 {chapter_id} 章迭代写作结束", "END")
        crew.logger.end_chapter()
        metrics_data = crew.metrics.end_chapter()
    
    # 返回最佳结果
    best_draft, best_score = session.get_best_draft()
    summary = session.get_summary()
    
    return {
        "success": True,
        "final_draft": best_draft,
        "quality_score": best_score,
        "iteration_summary": summary,
        "iterations": session.iterations,
        "metrics": metrics_data,
    }


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
        return f"📭 章节 {chapter_id} 没有迭代记录"
    
    summary = session.get_summary()
    
    report = f"""
📊 章节 {chapter_id} 迭代报告
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
