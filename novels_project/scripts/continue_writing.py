#!/usr/bin/env python
"""
继续章节创作脚本 - 从指定章节继续创作
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


def get_current_word_count() -> int:
    """获取当前总字数"""
    total = 0
    chapters_dir = project_root / "output" / "chapters"
    if chapters_dir.exists():
        for f in chapters_dir.glob("chapter_*_final.md"):
            content = f.read_text(encoding='utf-8')
            total += count_words(content)
    return total


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


# 第一卷完整章纲（60章）
VOLUME_1_CHAPTERS = [
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
    {"id": 11, "title": "关税司暗查账本，发现契约古印影子", "type": "权谋/规则", "progress": "铺垫"},
    {"id": 12, "title": "主角以折扣券换口碑，压垮黑商利润链", "type": "经营/打脸", "progress": "爆点"},
    {"id": 13, "title": "夜谈风控，薛灵槿提出合规红线", "type": "情感/权谋", "progress": "铺垫"},
    {"id": 14, "title": "魏执铗抓人施压，主角用冥约保人", "type": "规则/反转", "progress": "转折"},
    {"id": 15, "title": "云舟船队首航，遭不明阵流阻截", "type": "奇观/战斗", "progress": "铺垫"},
    {"id": 16, "title": "郁衡以小阵套大阵，反向借力突围", "type": "战斗/阵法", "progress": "爆点"},
    {"id": 17, "title": "货栈升级为分仓，库存周转加速", "type": "经营", "progress": "回收"},
    {"id": 18, "title": "黑商勾连皇甫系，提出特许独家权", "type": "权谋", "progress": "铺垫"},
    {"id": 19, "title": "主角公开成本与税率，组织听证", "type": "权谋/打脸", "progress": "爆点"},
    {"id": 20, "title": "听证反被钓鱼问话，薛灵槿及时纠偏", "type": "权谋/情感", "progress": "转折"},
    {"id": 21, "title": "引入保价赔付，市场信心回升", "type": "经营", "progress": "回收"},
    {"id": 22, "title": "内鬼再现，账本被盗，言墨锁定幕后", "type": "信息/反转", "progress": "铺垫"},
    {"id": 23, "title": "器傀示威护航，黑市保护费崩盘", "type": "战斗/打脸", "progress": "爆点"},
    {"id": 24, "title": "关口试点绿色通道，合规套利成形", "type": "经营/权谋", "progress": "回收"},
    {"id": 25, "title": "皇甫青闳放出币制整顿风声", "type": "权谋", "progress": "铺垫"},
    {"id": 26, "title": "主角设计天券兜底平价包", "type": "经营/规则", "progress": "转折"},
    {"id": 27, "title": "夜袭再临，云舟折翼，主角弃舟保货", "type": "战斗/反转", "progress": "爆点"},
    {"id": 28, "title": "冥约置换出场，付命火一缕换保全", "type": "规则/奇观", "progress": "爆点"},
    {"id": 29, "title": "木九公揭示命灯簇的潜能", "type": "成长/信息", "progress": "铺垫"},
    {"id": 30, "title": "市场围剿升级，主角抛成本红线协定", "type": "权谋/经营", "progress": "爆点"},
    {"id": 31, "title": "摊盟内斗爆发，主角并购其仓与渠道", "type": "经营/反转", "progress": "回收"},
    {"id": 32, "title": "郁衡完成封关阵试验，待选时机", "type": "阵法", "progress": "铺垫"},
    {"id": 33, "title": "薛灵槿被问责，主角递交双轨合规方案", "type": "权谋/情感", "progress": "转折"},
    {"id": 34, "title": "白璃首次出手，云舟群压阵，渠道互换", "type": "奇观/渠道", "progress": "爆点"},
    {"id": 35, "title": "器胚失窃案，锁定税关仓中内应", "type": "信息/权谋", "progress": "铺垫"},
    {"id": 36, "title": "以契约盲签诱出魏执铗案底", "type": "谋局/反转", "progress": "爆点"},
    {"id": 37, "title": "建立风控与审计双线，KPI上墙", "type": "经营", "progress": "回收"},
    {"id": 38, "title": "黑金流入市，币价震荡，主角丹券换稳", "type": "经营/规则", "progress": "转折"},
    {"id": 39, "title": "器傀军与护商队合编，首次整建制出击", "type": "战斗", "progress": "爆点"},
    {"id": 40, "title": "关口试点扩容，合规红利扩散", "type": "经营/权谋", "progress": "回收"},
    {"id": 41, "title": "皇甫系抛特许免税试点诱杀", "type": "权谋", "progress": "铺垫"},
    {"id": 42, "title": "主角以公域定价反卡免税独占", "type": "谋局/经营", "progress": "爆点"},
    {"id": 43, "title": "命灯受损后遗，方清砚以巫脉稳体丹稳住", "type": "成长/情感", "progress": "回收"},
    {"id": 44, "title": "行情被做空，主角发布库存与订单透明", "type": "经营/打脸", "progress": "转折"},
    {"id": 45, "title": "货栈晋升域商中台，三线联运成型", "type": "经营", "progress": "回收"},
    {"id": 46, "title": "皇甫青闳施压薛灵槿父线，家庭与公义冲突", "type": "情感/权谋", "progress": "铺垫"},
    {"id": 47, "title": "主角立下善因合约，愿力抵扣违约金", "type": "规则/经营", "progress": "爆点"},
    {"id": 48, "title": "冥约司盯上古印，玄烛示警", "type": "信息/规则", "progress": "转折"},
    {"id": 49, "title": "黑商周桓最后一搏，火拼于港道", "type": "战斗/反转", "progress": "爆点"},
    {"id": 50, "title": "主角以封关阵截断其退路，当场公证契约", "type": "阵法/打脸", "progress": "爆点"},
    {"id": 51, "title": "周桓锤死案背后现皇甫系刀人", "type": "权谋/信息", "progress": "铺垫"},
    {"id": 52, "title": "以合约多签保全薛灵槿风评", "type": "情感/权谋", "progress": "回收"},
    {"id": 53, "title": "天券小额试点通过，清算速度倍增", "type": "经营/规则", "progress": "回收"},
    {"id": 54, "title": "器傀与阵盘联测，构建护航走廊", "type": "战斗/阵法", "progress": "转折"},
    {"id": 55, "title": "市民自发商誉榜，主角位列首席", "type": "经营/立信", "progress": "爆点"},
    {"id": 56, "title": "皇甫系撤换魏执铗，换更隐蔽的代理人", "type": "权谋", "progress": "转折"},
    {"id": 57, "title": "合规许可证签发，主角拿到长期指标", "type": "经营/权谋", "progress": "回收"},
    {"id": 58, "title": "初代商会成立，KPI与分红制度落地", "type": "经营", "progress": "回收"},
    {"id": 59, "title": "上苍行在发来审视令，慕容瑶光抵达", "type": "规则/情感", "progress": "铺垫"},
    {"id": 60, "title": "终章收束：首条安全航线贯通，古印异动映出神印残影", "type": "奇观/反转", "progress": "爆点"},
]


def main():
    """主函数"""
    from novels_project.crew import NovelsCrewAI
    from novels_project.iteration_controller import get_iteration_controller, IterationStatus, IterationResult
    
    # 获取起始章节（默认从第11章开始）
    start_chapter = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    
    print("\n" + "="*60)
    print("🚀 继续章节创作系统")
    print(f"   质量阈值: {QUALITY_THRESHOLD}/10")
    print(f"   目标字数: {TARGET_WORD_COUNT} 字")
    print(f"   起始章节: 第 {start_chapter} 章")
    print("="*60)
    
    # 获取当前字数
    current_words = get_current_word_count()
    print(f"   当前字数: {current_words} 字")
    
    if current_words >= TARGET_WORD_COUNT:
        print(f"\n✅ 已达到目标字数 {TARGET_WORD_COUNT}，无需继续创作")
        return
    
    # 初始化 Crew
    crew = NovelsCrewAI()
    
    total_words = current_words
    chapter_count = 0
    
    # 加载上一章摘要
    prev_summary = load_previous_summary(start_chapter)
    
    # 从指定章节开始创作
    for chapter_info in VOLUME_1_CHAPTERS[start_chapter - 1:]:
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
            from novels_project.iteration_controller import IterationResult
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
