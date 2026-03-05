#!/usr/bin/env python
"""
主运行脚本 - 执行章节创作流程
"""
import sys
import argparse
import yaml
import re
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from novels_project.crew import NovelsCrewAI
from novels_project.iterative_writer import run_iterative_writing


def load_chapter_outline(chapter_id: int, outline_file: str = None) -> dict:
    """
    加载章节大纲信息

    Args:
        chapter_id: 章节ID
        outline_file: 大纲文件路径（可选）

    Returns:
        包含章节信息的字典
    """
    if outline_file:
        print(f"⚠️  --outline 参数尚未实现，使用内置测试数据")

    # MVP 测试数据 - 使用正确的人物设定
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
        "story_world": {
            "setting": "大周朝，商业繁荣但帮派横行",
            "protagonist": "陆商曜",
            "protagonist_identity": "落魄商族庶子，掌握契约古印",
            "key_rules": ["《大周商律》是法律体系", "契约古印是主角金手指"]
        }
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


def parse_yaml_from_output(output_text: str) -> dict:
    """
    从输出文本中解析 YAML 内容

    Args:
        output_text: 包含 YAML 的文本

    Returns:
        解析后的字典
    """
    if not output_text:
        return {}

    # 尝试提取 ```yaml ... ``` 中的内容
    yaml_pattern = r'```yaml\s*(.*?)\s*```'
    matches = re.findall(yaml_pattern, output_text, re.DOTALL)

    if matches:
        # 取最后一个匹配（通常是最终版本）
        yaml_content = matches[-1]
        try:
            return yaml.safe_load(yaml_content)
        except yaml.YAMLError:
            pass

    # 如果没有找到代码块，尝试直接解析
    try:
        result = yaml.safe_load(output_text)
        if isinstance(result, dict):
            return result
        return {}
    except yaml.YAMLError:
        print("⚠️  无法从输出中解析 YAML，将保存原始输出")
        return {}


def extract_final_content(result: dict) -> dict:
    """
    从结果中提取最终内容

    Args:
        result: Crew 执行结果

    Returns:
        包含 final_content 和 summary_card 的字典
    """
    output_text = str(result.get('result', ''))

    # 解析 YAML
    parsed = parse_yaml_from_output(output_text)

    final_content = ""
    summary_card = {}

    # 提取最终章节内容
    if 'chapter_final' in parsed:
        final_content = parsed['chapter_final'].get('final_content', '')
    elif 'chapter_draft' in parsed:
        final_content = parsed['chapter_draft'].get('content', '')

    # 提取章节摘要卡
    if 'chapter_summary_card' in parsed:
        summary_card = parsed['chapter_summary_card']

    return {
        'final_content': final_content,
        'summary_card': summary_card,
        'proofreading_log': parsed.get('chapter_final', {}).get('proofreading_log', {}),
        'raw_output': output_text
    }


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
    raw_dir = output_dir / "raw_outputs"

    chapters_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 提取内容
    extracted = extract_final_content(result)
    final_content = extracted['final_content']
    summary_card = extracted['summary_card']

    # 保存最终版章节（纯文本格式）
    chapter_file = chapters_dir / f"chapter_{chapter_id}_final.md"
    with open(chapter_file, 'w', encoding='utf-8') as f:
        # 写入标题
        f.write(f"# 第 {chapter_id} 章\n\n")
        # 写入正文
        if final_content:
            f.write(final_content)
        else:
            # 如果无法解析，保存原始输出
            f.write(extracted['raw_output'])
    print(f"   章节: {chapter_file}")

    # 保存章节摘要卡（YAML 格式）
    if summary_card:
        summary_file = summaries_dir / f"chapter_{chapter_id}_summary.yaml"
        with open(summary_file, 'w', encoding='utf-8') as f:
            yaml.dump(summary_card, f, allow_unicode=True, default_flow_style=False)
        print(f"   摘要: {summary_file}")

    # 保存原始输出（用于调试）
    raw_file = raw_dir / f"chapter_{chapter_id}_raw.yaml"
    with open(raw_file, 'w', encoding='utf-8') as f:
        f.write(extracted['raw_output'])
    print(f"   原始: {raw_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="CrewAI 小说创作系统")
    parser.add_argument('--chapter', type=int, default=1, help='章节ID')
    parser.add_argument('--model', type=str, help='指定模型名称')
    parser.add_argument('--outline', type=str, help='大纲文件路径')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行（不调用 LLM）')
    parser.add_argument('--init-vectordb', action='store_true', help='初始化向量库')
    parser.add_argument('--iterative', action='store_true', help='启用迭代写作模式（多轮写作-校对迭代）')
    parser.add_argument('--max-iterations', type=int, default=3, help='最大迭代次数（默认: 3）')
    parser.add_argument('--quality-threshold', type=int, default=7, help='质量阈值 1-10（默认: 7）')

    args = parser.parse_args()

    print("=" * 60)
    print("🚀 CrewAI 小说创作系统")
    print("=" * 60)
    print()

    # 初始化向量库模式
    if args.init_vectordb:
        print("📚 初始化向量库...")
        from novels_project.retrieval_engine import get_retrieval_engine
        engine = get_retrieval_engine()
        engine._ensure_initialized()
        if engine.vectorstore:
            print("✅ 向量库初始化完成")
        else:
            print("⚠️  向量库初始化失败，请检查样例目录和 API 配置")
        return

    # 加载数据
    print("📖 加载章节信息...")
    chapter_info = load_chapter_outline(args.chapter, args.outline)
    print(f"   章节: 第 {args.chapter} 章 - {chapter_info.get('chapter_title', '未知')}")
    story_world = chapter_info.get('story_world', {})
    if story_world:
        print(f"   主角: {story_world.get('protagonist', '未指定')} ({story_world.get('protagonist_identity', '未指定')})")

    print("👥 加载人物卡库...")
    try:
        character_cards = load_character_cards()
        char_count = sum(
            len(tier.get('characters', {}))
            for tier in [character_cards.get('s_tier', {}), character_cards.get('a_tier', {})]
        )
        print(f"   人物数: {char_count}")
        print(f"   主角: {character_cards.get('s_tier', {}).get('characters', {}).get('陆商曜', {}).get('name', '未设置')}")
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
    mode_str = "迭代模式" if args.iterative else "标准模式"
    print(f"\n🤖 初始化 CrewAI（模型: {args.model or '双模型模式'}, 模式: {mode_str}）...")
    try:
        crew = NovelsCrewAI(model_name=args.model)
        print("   ✅ Crew 已初始化")
    except Exception as e:
        print(f"   ❌ 初始化失败: {e}")
        sys.exit(1)

    # 执行创作流程
    if args.iterative:
        # 迭代写作模式
        print(f"\n📝 开始迭代写作模式 - 第 {args.chapter} 章")
        print(f"   最大迭代次数: {args.max_iterations}")
        print(f"   质量阈值: {args.quality_threshold}/10")
        print("   （每轮迭代可能需要几分钟，请耐心等待）")
        print()

        result = run_iterative_writing(
            crew=crew,
            chapter_id=args.chapter,
            inputs=inputs,
            max_iterations=args.max_iterations,
            quality_threshold=args.quality_threshold
        )
    else:
        # 标准模式（单轮执行）
        print(f"\n📝 开始执行第 {args.chapter} 章创作流程...")
        print("   （这可能需要几分钟，请耐心等待）")
        print()

        result = crew.run_chapter(args.chapter, inputs)

    # 处理结果
    if result['success']:
        print("\n✅ 章节创作完成！")

        # 保存输出（迭代模式需要适配格式）
        if args.iterative:
            save_result = {
                'success': True,
                'result': result.get('final_draft', ''),
            }
            save_output(args.chapter, save_result)
        else:
            save_output(args.chapter, result)

        # 如果是迭代模式，显示迭代摘要
        if args.iterative and 'iteration_summary' in result:
            summary = result['iteration_summary']
            print(f"\n🔄 迭代摘要:")
            print(f"   总迭代次数: {summary.get('total_iterations', '?')}")
            print(f"   最佳质量分数: {summary.get('best_quality_score', '?')}/10")
            print(f"   最终状态: {summary.get('final_status', '?')}")

        # 显示指标（标准模式）
        if not args.iterative and 'metrics' in result:
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
