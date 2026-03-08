#!/usr/bin/env python
"""
连续章节创作脚本 - 自动迭代直到质量达标或达到字数限制
"""
import sys
import os
import yaml
import re
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# 配置
QUALITY_THRESHOLD = 8  # 质量阈值
MAX_ITERATIONS = 3     # 最大迭代次数
TARGET_WORD_COUNT = 30000  # 目标字数


def load_previous_summary(chapter_id: int) -> dict:
    """加载上一章摘要"""
    summary_file = project_root / "output" / "chapter_summaries" / f"chapter_{chapter_id - 1}_summary.yaml"
    if summary_file.exists():
        with open(summary_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def count_words(text: str) -> int:
    """统计字数（中文字符）"""
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars)


def extract_chapter_content(output: str) -> tuple:
    """从输出中提取章节内容和摘要"""
    try:
        clean_output = output.strip()
        if clean_output.startswith("```"):
            lines = clean_output.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_output = "\n".join(lines)
        
        data = yaml.safe_load(clean_output)
        
        if isinstance(data, dict):
            chapter_final = data.get("chapter_final", {})
            content = chapter_final.get("final_content", "")
            summary = data.get("chapter_summary_card", {})
            
            # 尝试从 raw 输出中提取更多内容
            if not content:
                content = data.get("content", "")
            
            return content, summary, data
    except Exception as e:
        print(f"   ⚠️ 解析输出失败: {e}")
    
    return "", {}, {}


def save_chapter(chapter_id: int, chapter_title: str, content: str, summary: dict, raw_output: str):
    """保存章节到文件"""
    # 保存最终章节
    chapters_dir = project_root / "output" / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    
    chapter_file = chapters_dir / f"chapter_{chapter_id}_final.md"
    with open(chapter_file, 'w', encoding='utf-8') as f:
        f.write(f"# 第 {chapter_id} 章\n\n")
        f.write(f"**{chapter_title}**\n\n")
        f.write(content)
    print(f"   📝 已保存: {chapter_file}")
    
    # 保存摘要
    if summary:
        summaries_dir = project_root / "output" / "chapter_summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        
        summary_file = summaries_dir / f"chapter_{chapter_id}_summary.yaml"
        with open(summary_file, 'w', encoding='utf-8') as f:
            yaml.dump(summary, f, allow_unicode=True, default_flow_style=False)
        print(f"   📋 已保存摘要: {summary_file}")
    
    # 保存原始输出
    raw_dir = project_root / "output" / "raw_outputs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    raw_file = raw_dir / f"chapter_{chapter_id}_raw.yaml"
    with open(raw_file, 'w', encoding='utf-8') as f:
        f.write(raw_output)
    print(f"   📦 已保存原始输出: {raw_file}")


def parse_quality_score(output: str) -> int:
    """从输出中解析质量评分"""
    try:
        clean_output = output.strip()
        if clean_output.startswith("```"):
            lines = clean_output.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_output = "\n".join(lines)
        
        data = yaml.safe_load(clean_output)
        
        if isinstance(data, dict):
            self_check = data.get("self_check_report", {})
            if "quality_after" in self_check:
                return int(self_check["quality_after"])
            if "quality_score" in self_check:
                return int(self_check["quality_score"])
            
            chapter_final = data.get("chapter_final", {})
            self_check = chapter_final.get("self_check_report", {})
            if "quality_after" in self_check:
                return int(self_check["quality_after"])
    except:
        pass
    
    return 5


def main():
    """主函数"""
    from novels_project.crew import NovelsCrewAI
    from novels_project.iteration_controller import get_iteration_controller, IterationStatus, IterationResult
    
    print("\n" + "="*60)
    print("🚀 连续章节创作系统")
    print(f"   质量阈值: {QUALITY_THRESHOLD}/10")
    print(f"   目标字数: {TARGET_WORD_COUNT} 字")
    print("="*60)
    
    # 初始化 Crew
    crew = NovelsCrewAI()
    
    # 第一卷章纲
    volume_1_chapters = [
        {"id": 1, "title": "市集开局，落魄货栈遭围堵", "type": "打脸/经营", "progress": "铺垫"},
        {"id": 2, "title": "黑商周桓逼签霸王条款，主角反以契约漏洞脱身", "type": "打脸/谋局", "progress": "转折"},
        {"id": 3, "title": "货源断供危机，木九公出手重构账目与供给", "type": "经营/信息", "progress": "铺垫"},
        {"id": 4, "title": "夜袭仓库被内鬼引路，铁阙率器傀反追击", "type": "战斗/反转", "progress": "爆点"},
        {"id": 5, "title": "薛灵槿审查来访，冻结清算，主角提合规试点", "type": "权谋/经营", "progress": "铺垫"},
        {"id": 6, "title": "建立信誉分与保证金制度，首批摊贩加盟", "type": "经营", "progress": "回收"},
        {"id": 7, "title": "阵盘中转受卡，主角以阵材置换打通小脉", "type": "经营/阵法", "progress": "转折"},
        {"id": 8, "title": "税关临检，魏执铗设套，主角公示成本结构", "type": "权谋/打脸", "progress": "爆点"},
        {"id": 9, "title": "黑市摊盟围殴，器傀护航通关，立威", "type": "战斗/立威", "progress": "爆点"},
        {"id": 10, "title": "首场拍卖会试水，丹器符傀组合包大卖", "type": "经营", "progress": "回收"},
    ]
    
    total_words = 0
    chapter_count = 0
    start_chapter = 2  # 从第二章开始
    
    prev_summary = load_previous_summary(2)
    
    for chapter_info in volume_1_chapters[start_chapter - 1:]:
        chapter_id = chapter_info["id"]
        chapter_title = chapter_info["title"]
        
        print(f"\n{'='*60}")
        print(f"📖 第 {chapter_id} 章: {chapter_title}")
        print(f"{'='*60}")
        
        # 准备输入
        inputs = {
            "chapter_id": chapter_id,
            "chapter_title": chapter_title,
            "chapter_type": chapter_info["type"],
            "progress_type": chapter_info["progress"],
            "previous_summary": str(prev_summary),
            "volume_goal": "立信立威，初谋关税",
        }
        
        # 初始化迭代控制器
        controller = get_iteration_controller(
            max_iterations=MAX_ITERATIONS,
            quality_threshold=QUALITY_THRESHOLD
        )
        session = controller.start_session(chapter_id)
        
        iteration = 0
        
        while True:
            iteration += 1
            print(f"\n--- 第 {iteration} 轮迭代 ---")
            
            # 执行创作流程
            result = crew.crew().kickoff(inputs=inputs)
            output = str(result)
            
            # 解析质量评分
            quality_score = parse_quality_score(output)
            print(f"   质量评分: {quality_score}/10")
            
            # 判断是否继续
            status = session.should_continue(quality_score)
            
            # 记录迭代结果
            iter_result = IterationResult(
                iteration=iteration,
                draft=output,
                review_issues=[],
                quality_score=quality_score,
                status=status
            )
            session.add_iteration(iter_result)
            
            if status.value == "accept":
                print(f"\n✅ 质量达标 ({quality_score}/10 >= {QUALITY_THRESHOLD})")
                break
            elif status.value == "max_iter":
                print(f"\n⚠️ 达到最大迭代次数 ({MAX_ITERATIONS})")
                break
            else:
                print(f"\n🔄 需要继续迭代...")
                inputs['iteration'] = iteration
                inputs['previous_quality_score'] = quality_score
        
        # 获取最佳结果
        best_draft, best_score = session.get_best_draft()
        
        # 提取章节内容和摘要
        content, summary, raw_data = extract_chapter_content(best_draft)
        
        # 如果提取失败，使用原始输出
        if not content:
            content = best_draft
        
        # 统计字数
        word_count = count_words(content)
        total_words += word_count
        chapter_count += 1
        
        print(f"\n📊 第 {chapter_id} 章完成:")
        print(f"   质量评分: {best_score}/10")
        print(f"   迭代次数: {iteration}")
        print(f"   字数: {word_count}")
        print(f"   累计字数: {total_words}")
        
        # 保存章节
        save_chapter(chapter_id, chapter_title, content, summary, best_draft)
        
        # 更新上一章摘要
        prev_summary = summary if summary else {"chapter_id": chapter_id, "word_count": word_count}
        
        # 检查是否达到目标字数
        if total_words >= TARGET_WORD_COUNT:
            print(f"\n🎉 已达到目标字数 {TARGET_WORD_COUNT}，停止创作")
            break
    
    print("\n" + "="*60)
    print("📈 创作完成统计")
    print(f"   完成章节: {chapter_count} 章")
    print(f"   总字数: {total_words}")
    print("="*60)


if __name__ == "__main__":
    main()
