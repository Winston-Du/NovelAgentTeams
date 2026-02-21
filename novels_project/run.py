#!/usr/bin/env python
"""
主运行脚本 - 执行章节创作流程
"""
import sys
import argparse
import yaml
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from novels_project.crew import NovelsCrewAI


def load_chapter_outline(chapter_id: int, outline_file: str = None) -> dict:
    """
    加载章节大纲信息

    Args:
        chapter_id: 章节ID
        outline_file: 大纲文件路径（可选）

    Returns:
        包含章节信息的字典
    """
    # 简化版：直接从 First/大纲.md 提取
    # 实际使用时可以解析 Markdown 文件
    if outline_file:
        # TODO: 实现从文件读取
        pass

    # MVP 测试数据
    return {
        "volume_id": "卷一",
        "volume_target": "立信立威，初谋关税",
        "chapter_id": chapter_id,
        "chapter_title": "市集开局，落魄货栈遭围堵",
        "chapter_position": "卷一开局",
        "story_arc_label": "铺垫",
        "pace_label": "快",
        "planned_climax": ["打脸", "经营", "立威"],
        "previous_chapter_summary": None,  # 第1章无前章摘要
    }


def load_character_cards(cards_file: str = None) -> dict:
    """
    加载人物卡库

    Args:
        cards_file: 人物卡文件路径

    Returns:
        人物卡库字典
    """
    if cards_file is None:
        cards_file = "src/novels_project/config/character_base_cards.yaml"

    cards_path = Path(cards_file)

    if not cards_path.exists():
        raise FileNotFoundError(f"人物卡库文件不存在: {cards_file}")

    with open(cards_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    return data


def save_output(chapter_id: int, result: dict):
    """
    保存输出文件

    Args:
        chapter_id: 章节ID
        result: 执行结果
    """
    output_dir = Path("output")
    chapters_dir = output_dir / "chapters"
    summaries_dir = output_dir / "chapter_summaries"

    chapters_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    # 保存最终版章节（简化版，实际需要解析 YAML）
    chapter_file = chapters_dir / f"chapter_{chapter_id}_final.md"
    with open(chapter_file, 'w', encoding='utf-8') as f:
        f.write(f"# 第 {chapter_id} 章\n\n")
        f.write(str(result.get('result', '')))

    print(f"\n✅ 输出已保存：")
    print(f"   章节: {chapter_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="CrewAI 小说创作系统")
    parser.add_argument('--chapter', type=int, default=1, help='章节ID')
    parser.add_argument('--model', type=str, help='指定模型名称')
    parser.add_argument('--outline', type=str, help='大纲文件路径')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行（不调用 LLM）')

    args = parser.parse_args()

    print("=" * 60)
    print("🚀 CrewAI 小说创作系统")
    print("=" * 60)
    print()

    # 加载数据
    print("📖 加载章节信息...")
    chapter_info = load_chapter_outline(args.chapter, args.outline)
    print(f"   章节: 第 {args.chapter} 章 - {chapter_info['chapter_title']}")

    print("👥 加载人物卡库...")
    try:
        character_cards = load_character_cards()
        char_count = sum(
            len(tier.get('characters', {}))
            for tier in [character_cards.get('s_tier', {}), character_cards.get('a_tier', {})]
        )
        print(f"   人物数: {char_count}")
    except FileNotFoundError as e:
        print(f"   ❌ {e}")
        print("\n请先准备人物卡库，参考 MVP_QUICKSTART.md")
        sys.exit(1)

    # 准备输入数据
    inputs = {
        **chapter_info,
        "character_base_cards": character_cards,
    }

    if args.dry_run:
        print("\n🔍 模拟运行模式（不调用 LLM）")
        print("   输入数据已准备完毕")
        print(f"   章节ID: {args.chapter}")
        print(f"   人物数: {char_count}")
        return

    # 初始化 Crew
    print(f"\n🤖 初始化 CrewAI（模型: {args.model or 'gemini-3-pro'}）...")
    try:
        crew = NovelsCrewAI(model_name=args.model)
        print("   ✅ Crew 已初始化")
    except Exception as e:
        print(f"   ❌ 初始化失败: {e}")
        sys.exit(1)

    # 执行创作流程
    print(f"\n📝 开始执行第 {args.chapter} 章创作流程...")
    print("   （这可能需要几分钟，请耐心等待）")
    print()

    result = crew.run_chapter(args.chapter, inputs)

    # 处理结果
    if result['success']:
        print("\n✅ 章节创作完成！")

        # 保存输出
        save_output(args.chapter, result)

        # 显示指标
        if 'metrics' in result:
            metrics = result['metrics']
            summary = metrics.get('chapter_summary', {})
            print(f"\n📊 性能指标:")
            print(f"   总耗时: {summary.get('total_duration_seconds', 0):.1f} 秒")
            print(f"   总 Token: {summary.get('total_tokens', 0)}")

        print(f"\n📂 查看详细日志:")
        print(f"   logs/execution_logs/chapter_{args.chapter}_execution.md")
        print(f"   logs/performance_metrics/chapter_{args.chapter}_metrics.json")

    else:
        print("\n❌ 章节创作失败")
        print(f"   错误: {result.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
