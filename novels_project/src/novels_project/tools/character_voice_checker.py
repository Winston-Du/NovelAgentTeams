"""
对话风格校验工具 - 检查对话是否符合人物卡库设定
"""
from typing import List, Dict, Any, Optional
import yaml
import re
from pathlib import Path

from ..shared.character_cards_utils import get_character_names
from ..project_config import get_character_cards_path


# 人物卡库缓存
_character_cards = None


def _load_character_cards() -> Dict[str, Any]:
    """加载人物卡库"""
    global _character_cards
    if _character_cards is not None:
        return _character_cards

    path = get_character_cards_path()
    if not path.exists():
        raise FileNotFoundError(f"未找到人物卡库文件: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        _character_cards = {}
        for tier in ["s_tier", "a_tier"]:
            if tier in data and "characters" in data[tier]:
                _character_cards.update(data[tier]["characters"])
    return _character_cards


def _extract_dialogues(content: str, known_characters: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """
    从章节内容中提取对话

    Args:
        content: 章节内容或包含对话的文本
        known_characters: 已知人物列表，为 None 时自动从人物卡加载

    返回格式: [{"speaker": "人物名", "dialogue": "对话内容", "context": "上下文"}, ...]
    """
    dialogues = []

    # 动态加载人物列表（替代硬编码）
    if known_characters is None:
        try:
            cards = _load_character_cards()
            known_characters = list(cards.keys()) if cards else []
        except FileNotFoundError:
            known_characters = []
    
    lines = content.split('\n')
    current_speaker = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 尝试识别说话者
        # 格式: "人物名" + (可选动词) + "：" + 对话
        # 例如: "陆商曜说："对话"" 或 "陆商曜："对话""
        
        speaker_found = None
        for char in known_characters:
            # 检查人物名是否出现在对话之前
            # 匹配: 人物名 + [可选的动词/描述] + ：/： + 引号
            pattern = rf'{char}[^""「」]*?[：:][""「]'
            if re.search(pattern, line):
                speaker_found = char
                current_speaker = char
                break
        
        # 提取对话（统一使用中文引号模式）
        # 匹配 "..." 或 「...」 或 "..."
        dialogue_match = re.search(r'[""「]([^""」]+)[""」]', line)
        if dialogue_match:
            dialogue = dialogue_match.group(1).strip()
            if dialogue and len(dialogue) > 1:
                speaker = speaker_found or current_speaker or "未知"
                dialogues.append({
                    "speaker": speaker,
                    "dialogue": dialogue,
                    "context": line[:60] + "..." if len(line) > 60 else line
                })
    
    return dialogues


def _check_single_dialogue(speaker: str, dialogue: str, character_cards: Dict) -> Dict[str, Any]:
    """
    检查单句对话是否符合人物风格
    
    Returns:
        {
            "valid": True/False,
            "issues": [...],
            "suggestions": [...]
        }
    """
    result = {
        "speaker": speaker,
        "dialogue": dialogue,
        "valid": True,
        "issues": [],
        "suggestions": []
    }
    
    # 未知人物，跳过检查
    if speaker == "未知" or speaker not in character_cards:
        result["valid"] = True
        result["issues"].append(f"未识别的说话者: {speaker}，请手动检查")
        return result
    
    character = character_cards[speaker]
    speaking_style = character.get("unique_speaking_style", {})
    
    # 获取风格特征
    tone = speaking_style.get("tone", "")
    characteristics = speaking_style.get("characteristics", [])
    example_dialogues = speaking_style.get("example_dialogues", [])
    avoid_patterns = speaking_style.get("avoid_patterns", [])
    speaking_frequency = speaking_style.get("speaking_frequency", "")
    
    # === 检查规则 ===
    
    # 1. 检查是否违反 avoid_patterns
    for avoid in avoid_patterns:
        # 将 avoid 规则转换为检查逻辑
        if "紧张" in avoid and _is_nervous(dialogue):
            result["valid"] = False
            result["issues"].append(f"违反避免模式: {avoid}")
            result["suggestions"].append(f"建议: 保持{speaker}的沉着风格")
        
        if "过度解释" in avoid and _is_over_explaining(dialogue):
            result["valid"] = False
            result["issues"].append(f"违反避免模式: {avoid}")
            result["suggestions"].append(f"建议: {speaker}言简意赅，不要过度解释")
        
        if "废话" in avoid and _is_verbose(dialogue):
            result["valid"] = False
            result["issues"].append(f"违反避免模式: {avoid}")
            result["suggestions"].append(f"建议: 删除冗余表达")
        
        if "聪慧" in avoid and _is_too_clever(dialogue):
            result["valid"] = False
            result["issues"].append(f"违反避免模式: {avoid}")
            result["suggestions"].append(f"建议: {speaker}应该更直接、粗鲁")
        
        if "深思熟虑" in avoid and _is_thoughtful(dialogue):
            result["valid"] = False
            result["issues"].append(f"违反避免模式: {avoid}")
            result["suggestions"].append(f"建议: {speaker}应该更冲动、直接")
        
        if "复杂词汇" in avoid and _has_complex_words(dialogue):
            result["valid"] = False
            result["issues"].append(f"违反避免模式: {avoid}")
            result["suggestions"].append(f"建议: 使用更简单、口语化的表达")
    
    # 2. 检查对话长度是否符合 speaking_frequency
    if "言少意多" in speaking_frequency or "话少" in speaking_frequency:
        if len(dialogue) > 50:
            result["issues"].append(f"注意: {speaker}的对话偏长（{len(dialogue)}字），建议精简")
    
    # 3. 检查特定人物的风格特征
    if speaker == "陆商曜":
        # 检查是否有数字或比喻
        if not _has_numbers_or_metaphors(dialogue):
            result["issues"].append("建议: 陆商曜喜欢用数字或比喻，可以考虑添加")
        
        # 检查是否太长（陆商曜言简意赅）
        if len(dialogue) > 60:
            result["valid"] = False
            result["issues"].append(f"陆商曜言简意赅，对话过长（{len(dialogue)}字）")
            result["suggestions"].append(f"参考风格: {example_dialogues[0] if example_dialogues else '言简意赅'}")
        
        # 检查是否有过度解释
        if _is_over_explaining(dialogue):
            result["valid"] = False
            result["issues"].append("陆商曜不应该过度解释")
            result["suggestions"].append("建议: 删减解释内容，保持简洁")
        
        # 检查是否有废话
        if _is_verbose(dialogue):
            result["valid"] = False
            result["issues"].append("陆商曜不应该说废话")
            result["suggestions"].append("建议: 删除冗余表达，每句话都要有目的")
    
    elif speaker == "黑商周桓":
        # 检查是否有威胁性
        if not _is_threatening(dialogue):
            result["issues"].append("建议: 黑商周桓的对话应该有威胁性")
        
        # 检查是否太有逻辑
        if _is_logical(dialogue):
            result["valid"] = False
            result["issues"].append("黑商周桓不应该显得有逻辑")
            result["suggestions"].append("建议: 使用更直接、粗暴的表达")
    
    elif speaker == "木九公":
        # 检查是否话太多
        if len(dialogue) > 40:
            result["issues"].append("木九公话少，对话可能偏长")
        
        # 检查是否暴露能力
        if _reveals_ability(dialogue):
            result["valid"] = False
            result["issues"].append("木九公不应暴露真实能力")
    
    # 4. 添加参考示例
    if not result["valid"] and example_dialogues:
        result["suggestions"].append(f"参考{speaker}的示例台词: {example_dialogues[0]}")
    
    return result


def _is_nervous(text: str) -> bool:
    """检查是否表现紧张"""
    nervous_patterns = ["紧张", "害怕", "担心", "不知道该怎么办", "慌", "手抖", "心跳"]
    return any(p in text for p in nervous_patterns)


def _is_over_explaining(text: str) -> bool:
    """检查是否过度解释"""
    # 过度解释的特征：有"因为...所以"、"其实"、"实际上"、"让我解释"
    # 或者对话过长（对于言简意赅的角色）
    explain_patterns = ["因为", "所以", "其实", "实际上", "是这样的", "让我解释", "让我想想", "仔细分析", "各种可能性"]
    return any(p in text for p in explain_patterns)


def _is_verbose(text: str) -> bool:
    """检查是否废话多"""
    # 废话特征：重复、无意义的填充词
    verbose_patterns = ["那个", "这个", "就是", "然后", "所以说"]
    count = sum(1 for p in verbose_patterns if p in text)
    return count >= 2


def _is_too_clever(text: str) -> bool:
    """检查是否显得聪慧"""
    clever_patterns = ["分析", "考虑", "策略", "计划", "根据", "逻辑", "推断"]
    return any(p in text for p in clever_patterns)


def _is_thoughtful(text: str) -> bool:
    """检查是否显得深思熟虑"""
    thoughtful_patterns = ["让我想想", "仔细考虑", "深思熟虑", "权衡", "斟酌"]
    return any(p in text for p in thoughtful_patterns)


def _has_complex_words(text: str) -> bool:
    """检查是否有复杂词汇"""
    # 简单判断：是否有四字以上的书面语
    complex_patterns = ["毋庸置疑", "由此可见", "综上所述", "不仅如此", "与此同时"]
    return any(p in text for p in complex_patterns)


def _has_numbers_or_metaphors(text: str) -> bool:
    """检查是否有数字或比喻"""
    # 检查数字
    if re.search(r'[一二三四五六七八九十百千万亿\d]+', text):
        return True
    # 检查比喻（简单判断）
    metaphor_patterns = ["像", "如", "似", "好比", "当作", "当成"]
    return any(p in text for p in metaphor_patterns)


def _is_threatening(text: str) -> bool:
    """检查是否有威胁性"""
    threat_patterns = ["敢", "信不信", "弄死", "废了", "砸", "打", "杀", "滚", "少废话"]
    return any(p in text for p in threat_patterns)


def _is_logical(text: str) -> bool:
    """检查是否太有逻辑"""
    logical_patterns = ["因此", "所以", "既然", "如果...那么", "首先", "其次", "最后"]
    return any(p in text for p in logical_patterns)


def _reveals_ability(text: str) -> bool:
    """检查是否暴露能力"""
    reveal_patterns = ["我其实", "我真正的实力", "我隐藏", "高手", "武功"]
    return any(p in text for p in reveal_patterns)


def check_character_voice(content: str, focus_characters: Optional[str] = None) -> str:
    """
    检查章节内容中的人物对话是否符合人物卡库设定
    
    Args:
        content: 章节内容或包含对话的文本
        focus_characters: 可选，指定要检查的人物（逗号分隔）
            例如: "陆商曜,黑商周桓"
            不指定则检查所有已知人物
    
    Returns:
        检查报告，包含：
        - 检查结果统计
        - 发现的问题列表
        - 修改建议
    
    Examples:
        check_character_voice(chapter_content)
        check_character_voice(dialogue_text, "陆商曜,黑商周桓")
    """
    try:
        # 加载人物卡库
        character_cards = _load_character_cards()
        
        # 解析要检查的人物
        focus_list = None
        if focus_characters:
            focus_list = [c.strip() for c in focus_characters.split(",")]
        
        # 提取对话
        dialogues = _extract_dialogues(content)
        
        if not dialogues:
            return "⚠️ 未在内容中检测到对话，请检查内容格式"
        
        # 检查每句对话
        results = []
        for d in dialogues:
            speaker = d["speaker"]
            # 如果指定了关注人物，跳过其他人物
            if focus_list and speaker not in focus_list and speaker != "未知":
                continue
            
            check_result = _check_single_dialogue(
                speaker, 
                d["dialogue"], 
                character_cards
            )
            results.append(check_result)
        
        # 生成报告
        total = len(results)
        valid_count = sum(1 for r in results if r["valid"])
        issues_count = total - valid_count
        
        report = f"📋 对话风格检查报告\n"
        report += f"{'='*40}\n\n"
        report += f"📊 统计:\n"
        report += f"  - 检查对话数: {total}\n"
        report += f"  - 通过: {valid_count}\n"
        report += f"  - 有问题: {issues_count}\n\n"
        
        if issues_count == 0:
            report += "✅ 所有对话风格检查通过！\n"
            return report
        
        # 列出问题
        report += f"❌ 发现的问题:\n"
        report += f"{'-'*40}\n\n"
        
        for i, r in enumerate(results, 1):
            if not r["valid"] or r["issues"]:
                report += f"【问题 {i}】\n"
                report += f"  人物: {r['speaker']}\n"
                report += f"  对话: \"{r['dialogue']}\"\n"
                
                if r["issues"]:  # pragma: no branch
                    report += f"  问题:\n"
                    for issue in r["issues"]:
                        report += f"    - {issue}\n"
                
                if r["suggestions"]:  # pragma: no branch
                    report += f"  建议:\n"
                    for sug in r["suggestions"]:
                        report += f"    💡 {sug}\n"
                
                report += "\n"
        
        return report
        
    except Exception as e:
        return f"❌ 对话风格检查失败: {str(e)}"


def get_character_voice_guide(character_name: str) -> str:
    """
    获取指定人物的对话风格指南
    
    Args:
        character_name: 人物名称（如：陆商曜、黑商周桓、木九公）
    
    Returns:
        该人物的对话风格指南，包含：
        - 说话语气
        - 风格特征
        - 示例台词
        - 避免事项
    
    Examples:
        get_character_voice_guide("陆商曜")
    """
    try:
        character_cards = _load_character_cards()
        
        if character_name not in character_cards:
            available = ", ".join(character_cards.keys())
            return f"❌ 未找到人物「{character_name}」\n可用人物: {available}"
        
        character = character_cards[character_name]
        speaking_style = character.get("unique_speaking_style", {})
        
        guide = f"📖 {character_name} 对话风格指南\n"
        guide += f"{'='*40}\n\n"
        
        # 基本信息
        guide += f"🎭 身份: {character.get('identity', '未知')}\n"
        guide += f"🌟 性格: {', '.join(character.get('core_personality', []))}\n\n"
        
        # 说话风格
        guide += f"🗣️ 说话语气:\n"
        guide += f"  {speaking_style.get('tone', '未指定')}\n\n"
        
        # 风格特征
        characteristics = speaking_style.get("characteristics", [])
        if characteristics:
            guide += f"📝 风格特征:\n"
            for c in characteristics:
                guide += f"  • {c}\n"
            guide += "\n"
        
        # 示例台词
        examples = speaking_style.get("example_dialogues", [])
        if examples:
            guide += f"💬 示例台词:\n"
            for ex in examples:
                guide += f'  "{ex}"\n'
            guide += "\n"
        
        # 避免事项
        avoid = speaking_style.get("avoid_patterns", [])
        if avoid:
            guide += f"⚠️ 避免事项:\n"
            for a in avoid:
                guide += f"  ❌ {a}\n"
            guide += "\n"
        
        # 说话频率
        frequency = speaking_style.get("speaking_frequency", "")
        if frequency:
            guide += f"📊 说话频率: {frequency}\n"
        
        # 标志动作
        habits = character.get("signature_habits", [])
        if habits:
            guide += f"\n🎬 标志动作:\n"
            for h in habits:
                guide += f"  • {h}\n"
        
        return guide
        
    except Exception as e:
        return f"❌ 获取风格指南失败: {str(e)}"


# 刷新人物卡库缓存
def refresh_character_cards():
    """刷新人物卡库缓存（卡库更新时调用）"""
    global _character_cards
    _character_cards = None
    return "✅ 人物卡库缓存已刷新"
