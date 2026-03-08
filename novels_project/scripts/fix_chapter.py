#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
章节修正工具 - 自动修正已生成章节中的问题

用法:
  单条修正:
    python scripts/fix_chapter.py --chapter 16 --text "原文片段" --problem "问题描述"

  批量修正（只需指定文件名，默认从 DESIGN/FIX/ 目录读取）:
    python scripts/fix_chapter.py --batch fix_ch16.yaml

  预览模式（不写入任何文件）:
    python scripts/fix_chapter.py --batch fix_ch16.yaml --dry-run
"""

import sys
import os
import argparse
import yaml
import uuid
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher

# 项目根目录
project_root = Path(__file__).parent.parent

# 批量修正 YAML 默认目录
FIX_DIR = project_root / "DESIGN" / "FIX"
sys.path.insert(0, str(project_root / "src"))

# ========== 配置 ==========

DEFAULT_MODEL = "glm-5"
SUMMARY_UPDATE_ISSUE_TYPES = {"内容事实错误", "逻辑漏洞", "人物OOC"}

# 需要更新摘要卡的 issue_type 关键词（部分匹配）
SUMMARY_UPDATE_KEYWORDS = ["事实", "逻辑", "OOC", "矛盾", "时间线"]


# ========== LLM 调用 ==========


def create_openai_client():
    """创建 OpenAI 兼容客户端（复用系统 LLM 配置）"""
    from openai import OpenAI

    api_key = os.getenv("COMPANY_API_KEY")
    api_base_url = os.getenv(
        "API_BASE_URL", "http://ai-service.tal.com/openai-compatible/v1"
    )

    if not api_key:
        print("❌ COMPANY_API_KEY 环境变量未设置")
        print("   请设置: export COMPANY_API_KEY=your_api_key")
        sys.exit(1)

    return OpenAI(api_key=api_key, base_url=api_base_url)


def call_llm(client, model: str, prompt: str, max_retries: int = 2) -> str:
    """调用 LLM 生成文本，失败自动重试"""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️  LLM 调用失败，重试中... ({e})")
            else:
                print(f"   ❌ LLM 调用失败: {e}")
                return ""
    return ""


# ========== 人物卡库 ==========


def load_character_cards() -> Dict[str, Any]:
    """加载人物卡库"""
    cards_path = (
        project_root / "src" / "novels_project" / "config" / "character_base_cards.yaml"
    )
    if not cards_path.exists():
        return {}
    with open(cards_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # 合并所有层级的人物
    characters = {}
    for tier in ["s_tier", "a_tier"]:
        if tier in data and "characters" in data[tier]:
            characters.update(data[tier]["characters"])
    return characters


def get_character_context(character_name: str, characters: Dict[str, Any]) -> str:
    """获取人物风格上下文（用于 LLM prompt）"""
    if not character_name or character_name not in characters:
        return ""

    char = characters[character_name]
    style = char.get("unique_speaking_style", {})

    lines = [f"\n## 人物「{character_name}」的说话风格"]
    if style.get("tone"):
        lines.append(f"- 语气: {style['tone']}")
    for c in style.get("characteristics", []):
        lines.append(f"- {c}")
    for ex in style.get("example_dialogues", []):
        lines.append(f'- 示例台词: "{ex}"')
    for av in style.get("avoid_patterns", []):
        lines.append(f"- 禁止: {av}")
    return "\n".join(lines)


# ========== LLM Prompt 构建 ==========


def build_fix_prompt(original_text: str, problem: str, character_context: str) -> str:
    """构建修正 Prompt"""
    prompt = f"""你是一位资深小说编辑。以下是一段需要修正的小说文本。

## 原文
{original_text}

## 问题
{problem}
{character_context}

## 要求
请直接给出修正后的文本。要求：
1. 保持东方玄幻小说的语言风格
2. 遵循 Show not Tell 原则
3. 如果涉及对话，必须符合人物说话风格
4. 修正后的文本长度与原文相近
5. 只输出修正后的文本，不要解释、不要加引号、不要加前缀

## 修正后的文本
"""
    return prompt


def build_summary_update_prompt(
    original_text: str, fix_applied: str, problem: str, summary_yaml: str
) -> str:
    """构建摘要卡更新 Prompt"""
    return f"""你是一位小说编辑助手。我修正了一段章节内容，需要你判断章节摘要卡是否需要同步更新。

## 修正内容
原文: {original_text}
问题: {problem}
修正后: {fix_applied}

## 当前摘要卡
```yaml
{summary_yaml}
```

## 要求
如果这个修正影响了摘要卡中记录的关键事件、人物状态、伏笔等信息，请输出更新后的完整摘要卡（纯 YAML 格式，不要加 ```yaml 标记）。
如果摘要卡无需更新，只输出一个字：无
"""


# ========== 反馈库操作 ==========


def load_feedback_store() -> Dict[str, Any]:
    """加载反馈库"""
    feedback_file = project_root / "feedback" / "proofreading_feedback.yaml"
    if not feedback_file.exists():
        return {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
                "description": "校对反馈库 - 记录发现的问题供后续创作参考",
            },
            "feedback_by_type": {},
            "feedback_by_character": {},
            "feedback_history": [],
        }
    with open(feedback_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_feedback_store(data: Dict[str, Any]):
    """保存反馈库"""
    feedback_dir = project_root / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    feedback_file = feedback_dir / "proofreading_feedback.yaml"
    with open(feedback_file, "w", encoding="utf-8") as f:
        yaml.dump(
            data, f, allow_unicode=True, default_flow_style=False, sort_keys=False
        )


def inject_feedback(
    store: Dict[str, Any],
    chapter_id: int,
    issue_type: str,
    character: Optional[str],
    original_text: str,
    problem: str,
    fix_applied: str,
    severity: str = "medium",
) -> str:
    """向反馈库注入一条记录，返回 feedback_id"""
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
    hex_suffix = uuid.uuid4().hex[:6]
    feedback_id = f"FB_FIX_{ts}_{chapter_id}_{hex_suffix}"

    entry = {
        "id": feedback_id,
        "chapter_id": chapter_id,
        "issue_type": issue_type,
        "character": character,
        "original_text": original_text[:200],  # 截断过长原文
        "problem": problem,
        "fix_applied": fix_applied[:200],
        "severity": severity,
        "created_at": datetime.now().isoformat(),
    }

    store["feedback_history"].append(entry)

    # 更新类型索引
    if issue_type not in store["feedback_by_type"]:
        store["feedback_by_type"][issue_type] = []
    store["feedback_by_type"][issue_type].append(feedback_id)

    # 更新人物索引
    if character:
        if character not in store["feedback_by_character"]:
            store["feedback_by_character"][character] = []
        store["feedback_by_character"][character].append(feedback_id)

    # 更新元数据
    store["metadata"]["last_updated"] = datetime.now().isoformat()
    store["metadata"]["total_feedback"] = len(store["feedback_history"])

    return feedback_id


# ========== 正文修正 ==========


def find_and_replace_in_chapter(
    chapter_id: int, original_text: str, fix_applied: str
) -> Tuple[bool, str]:
    """
    在章节正文中查找原文并替换

    Returns:
        (是否成功, 消息)
    """
    chapter_file = (
        project_root / "output" / "chapters" / f"chapter_{chapter_id}_final.md"
    )
    if not chapter_file.exists():
        return False, f"章节文件不存在: {chapter_file.name}"

    content = chapter_file.read_text(encoding="utf-8")

    # 规范化原文：去除 YAML 块标量带来的首尾空白
    original_text = original_text.strip()
    fix_applied = fix_applied.strip()

    # 精确匹配
    if original_text in content:
        new_content = content.replace(original_text, fix_applied, 1)
        chapter_file.write_text(new_content, encoding="utf-8")
        return True, f"精确匹配替换成功 ({chapter_file.name})"

    # 子串匹配：原文可能是某一行的一部分，用滑动窗口在原始内容上匹配
    best_ratio = 0.0
    best_start = -1
    best_end = -1
    best_candidate = ""

    # 按行拆分进行窗口搜索
    lines = content.split("\n")
    original_lines = original_text.count("\n") + 1
    window = max(original_lines, 3)

    for i in range(len(lines)):
        for j in range(i + 1, min(i + window + 2, len(lines) + 1)):
            candidate = "\n".join(lines[i:j]).strip()
            if not candidate:
                continue
            ratio = SequenceMatcher(None, original_text, candidate).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_start = i
                best_end = j
                best_candidate = candidate

    if best_ratio >= 0.6:
        lines[best_start:best_end] = [fix_applied]
        new_content = "\n".join(lines)
        chapter_file.write_text(new_content, encoding="utf-8")
        return True, f"模糊匹配替换成功 (相似度 {best_ratio:.0%}, {chapter_file.name})"

    return (
        False,
        f"未在 {chapter_file.name} 中找到匹配段落 (最高相似度 {best_ratio:.0%})",
    )


# ========== 摘要卡更新 ==========


def should_update_summary(issue_type: str) -> bool:
    """判断是否需要更新摘要卡"""
    if issue_type in SUMMARY_UPDATE_ISSUE_TYPES:
        return True
    for keyword in SUMMARY_UPDATE_KEYWORDS:
        if keyword in issue_type:
            return True
    return False


def update_summary_card(
    client,
    model: str,
    chapter_id: int,
    original_text: str,
    fix_applied: str,
    problem: str,
) -> Tuple[bool, str]:
    """更新摘要卡"""
    summary_file = (
        project_root
        / "output"
        / "chapter_summaries"
        / f"chapter_{chapter_id}_summary.yaml"
    )
    if not summary_file.exists():
        return False, f"摘要卡不存在: {summary_file.name}"

    summary_content = summary_file.read_text(encoding="utf-8")
    prompt = build_summary_update_prompt(
        original_text, fix_applied, problem, summary_content
    )
    response = call_llm(client, model, prompt)

    if not response or response.strip() == "无":
        return False, "LLM 判断摘要卡无需更新"

    # 尝试解析 LLM 返回的 YAML
    try:
        # 清理可能的 markdown 代码块
        clean = response.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean = "\n".join(lines)

        new_summary = yaml.safe_load(clean)
        if isinstance(new_summary, dict):
            with open(summary_file, "w", encoding="utf-8") as f:
                yaml.dump(new_summary, f, allow_unicode=True, default_flow_style=False)
            return True, f"摘要卡已更新 ({summary_file.name})"
        else:
            return False, "LLM 返回的摘要卡格式无效"
    except yaml.YAMLError as e:
        return False, f"摘要卡 YAML 解析失败: {e}"


# ========== 单条问题处理 ==========


def process_issue(
    client,
    model: str,
    characters: Dict[str, Any],
    store: Dict[str, Any],
    issue: Dict[str, Any],
    index: int,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    处理单条问题

    Args:
        client: OpenAI 客户端
        model: 模型名称
        characters: 人物卡库
        store: 反馈库数据
        issue: 问题字典
        index: 序号
        dry_run: 预览模式

    Returns:
        处理结果
    """
    chapter_id = issue["chapter_id"]
    original_text = issue["original_text"]
    problem = issue["problem"]
    issue_type = issue.get("issue_type", "")
    character = issue.get("character")
    severity = issue.get("severity", "medium")

    print(f"\n{'━' * 50}")
    print(f"📝 修正 #{index} — 第{chapter_id}章")
    print(f"{'━' * 50}")

    # 获取人物上下文
    char_context = get_character_context(character, characters) if character else ""

    # 1. LLM 生成修正文本
    print("   🤖 生成修正文本...")
    fix_prompt = build_fix_prompt(original_text, problem, char_context)
    fix_applied = call_llm(client, model, fix_prompt)

    if not fix_applied:
        print("   ❌ LLM 未能生成修正文本，跳过此条")
        return {"success": False, "reason": "LLM 未返回结果"}

    # 2. 如果未指定 issue_type，让 LLM 自动判断
    if not issue_type:
        type_prompt = f"""请判断以下小说校对问题属于哪种类型（只输出类型名，不要解释）：
可选类型：对话风格偏离、Tell而非Show、节奏问题、逻辑漏洞、重复结构、环境描写空洞、爽点执行不力、人物OOC、内容事实错误、结构失衡

问题描述：{problem}
原文片段：{original_text[:100]}"""
        issue_type = call_llm(client, model, type_prompt)
        if not issue_type or len(issue_type) > 20:
            issue_type = "写作问题"
        issue_type = issue_type.strip().strip('"').strip("'")

    # 打印结果
    print(f"   问题类型: {issue_type}")
    if character:
        print(f"   人物: {character}")
    print(f'   原文: "{original_text[:60]}{"..." if len(original_text) > 60 else ""}"')
    print(f"   问题: {problem}")
    print(f'   修正: "{fix_applied[:60]}{"..." if len(fix_applied) > 60 else ""}"')
    print()

    if dry_run:
        print("   🔍 [预览模式] 以下操作将在实际运行时执行：")
        print("      → 写入反馈库")
        print(f"      → 修正正文 chapter_{chapter_id}_final.md")
        if should_update_summary(issue_type):
            print(f"      → 更新摘要卡 chapter_{chapter_id}_summary.yaml")
        else:
            print("      → 摘要卡无需更新（非剧情/逻辑类问题）")
        return {"success": True, "dry_run": True, "fix_applied": fix_applied}

    result = {"success": True, "fix_applied": fix_applied}

    # 3. 注入反馈库
    feedback_id = inject_feedback(
        store,
        chapter_id,
        issue_type,
        character,
        original_text,
        problem,
        fix_applied,
        severity,
    )
    print(f"   ✅ 反馈库已更新 ({feedback_id})")
    result["feedback_id"] = feedback_id

    # 4. 修正正文
    replaced, msg = find_and_replace_in_chapter(chapter_id, original_text, fix_applied)
    if replaced:
        print(f"   ✅ 正文已修正 ({msg})")
    else:
        print(f"   ⚠️  正文未修正: {msg}")
    result["chapter_updated"] = replaced

    # 5. 摘要卡更新
    if should_update_summary(issue_type):
        updated, msg = update_summary_card(
            client, model, chapter_id, original_text, fix_applied, problem
        )
        if updated:
            print(f"   ✅ {msg}")
        else:
            print(f"   ⏭️  {msg}")
        result["summary_updated"] = updated
    else:
        print("   ⏭️  摘要卡无需更新（非剧情/逻辑类问题）")
        result["summary_updated"] = False

    return result


# ========== 批量输入解析 ==========


def load_batch_file(batch_path: str) -> List[Dict[str, Any]]:
    """加载批量修正 YAML 文件（优先从 DESIGN/FIX/ 目录查找）"""
    path = Path(batch_path)
    if not path.exists():
        # 优先在 DESIGN/FIX/ 目录查找
        path = FIX_DIR / batch_path
    if not path.exists():
        # 兜底：在项目根目录查找
        path = project_root / batch_path
    if not path.exists():
        print(f"❌ 批量文件不存在: {batch_path}")
        print(f"   已查找路径:")
        print(f"     1. {Path(batch_path).resolve()}")
        print(f"     2. {FIX_DIR / batch_path}")
        print(f"     3. {project_root / batch_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "issues" not in data:
        print(f"❌ 批量文件格式错误，缺少 'issues' 字段")
        sys.exit(1)

    issues = data["issues"]
    # 验证必填字段
    for i, issue in enumerate(issues):
        if "chapter_id" not in issue:
            print(f"❌ 第 {i + 1} 条缺少 chapter_id")
            sys.exit(1)
        if "original_text" not in issue:
            print(f"❌ 第 {i + 1} 条缺少 original_text")
            sys.exit(1)
        if "problem" not in issue:
            print(f"❌ 第 {i + 1} 条缺少 problem")
            sys.exit(1)

    return issues


# ========== 主函数 ==========


def main():
    parser = argparse.ArgumentParser(
        description="章节修正工具 - 自动修正已生成章节中的问题",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  单条修正:
    python scripts/fix_chapter.py --chapter 16 --text "原文" --problem "问题"
  
  批量修正（只需文件名，默认从 DESIGN/FIX/ 目录读取）:
    python scripts/fix_chapter.py --batch fix_ch16.yaml
  
  预览模式:
    python scripts/fix_chapter.py --batch fix_ch16.yaml --dry-run
        """,
    )

    # 单条模式参数
    parser.add_argument("--chapter", type=int, help="章节ID")
    parser.add_argument("--text", type=str, help="有问题的原文片段")
    parser.add_argument("--problem", type=str, help="问题描述")
    parser.add_argument(
        "--issue-type", type=str, default="", help="问题类型（可选，不填则自动判断）"
    )
    parser.add_argument(
        "--character", type=str, default=None, help="涉及的人物（可选）"
    )
    parser.add_argument(
        "--severity",
        type=str,
        default="medium",
        choices=["high", "medium", "low"],
        help="严重程度",
    )

    # 批量模式参数
    parser.add_argument("--batch", type=str, help="批量修正 YAML 文件名（默认从 DESIGN/FIX/ 目录读取）")

    # 通用参数
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"使用的模型（默认: {DEFAULT_MODEL}）",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="预览模式，不写入任何文件"
    )

    args = parser.parse_args()

    # 验证参数
    if args.batch:
        mode = "batch"
    elif args.chapter and args.text and args.problem:
        mode = "single"
    else:
        parser.print_help()
        print("\n❌ 请使用 --batch 或同时指定 --chapter --text --problem")
        sys.exit(1)

    # 打印头部
    print("=" * 50)
    print("🔧 章节修正工具")
    print("=" * 50)
    print(f"   模型: {args.model}")
    print(f"   模式: {'批量' if mode == 'batch' else '单条'}")
    if args.dry_run:
        print("   ⚠️  预览模式（不写入文件）")
    print()

    # 初始化
    client = create_openai_client()
    characters = load_character_cards()
    store = load_feedback_store()

    # 构建问题列表
    if mode == "batch":
        issues = load_batch_file(args.batch)
        print(f"📋 加载了 {len(issues)} 条修正任务")
    else:
        issues = [
            {
                "chapter_id": args.chapter,
                "original_text": args.text,
                "problem": args.problem,
                "issue_type": args.issue_type,
                "character": args.character,
                "severity": args.severity,
            }
        ]

    # 逐条处理
    results = []
    for i, issue in enumerate(issues, 1):
        result = process_issue(
            client, args.model, characters, store, issue, i, args.dry_run
        )
        results.append(result)

    # 保存反馈库（非预览模式）
    if not args.dry_run:
        save_feedback_store(store)

    # 汇总
    print(f"\n{'=' * 50}")
    print("📊 修正汇总")
    print(f"{'=' * 50}")
    total = len(results)
    success = sum(1 for r in results if r.get("success"))
    chapter_fixed = sum(1 for r in results if r.get("chapter_updated"))
    summary_fixed = sum(1 for r in results if r.get("summary_updated"))

    print(f"   总计: {total} 条")
    print(f"   成功: {success} 条")
    if not args.dry_run:
        print(f"   正文已修正: {chapter_fixed} 处")
        print(f"   摘要卡已更新: {summary_fixed} 处")
        print(f"   反馈库: {success} 条已注入")
    else:
        print("   (预览模式，未写入任何文件)")
    print()


if __name__ == "__main__":
    main()
