"""
项目配置 - 管理当前故事项目的路径

所有路径基于 PROJECT_ROOT（默认为当前工作目录）。
用户可以在不同故事目录下运行系统，每个故事有独立的配置和输出。
"""
from pathlib import Path
from typing import Optional

# 全局项目根目录（默认为当前工作目录）
_PROJECT_ROOT: Optional[Path] = None


def get_project_root() -> Path:
    """获取当前项目根目录。"""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = Path.cwd()
    return _PROJECT_ROOT


def set_project_root(path: Optional[Path] = None):
    """
    设置项目根目录。

    Args:
        path: 项目路径，None 表示使用当前工作目录
    """
    global _PROJECT_ROOT
    _PROJECT_ROOT = path if path else Path.cwd()


def get_config_dir() -> Path:
    """获取配置目录。"""
    return get_project_root() / "config"


def get_character_cards_path() -> Path:
    """获取人物卡文件路径。"""
    # 首先检查当前项目的 config/ 目录
    path = get_config_dir() / "character_base_cards.yaml"
    if path.exists():
        return path

    # 向后兼容：检查 src/novels_project/config/ 目录
    # （适用于 novels_project 本身作为故事项目的情况）
    legacy_path = get_project_root() / "src" / "novels_project" / "config" / "character_base_cards.yaml"
    if legacy_path.exists():
        return legacy_path

    # 返回标准路径（即使不存在，用于错误提示）
    return path


def get_design_dir() -> Path:
    """获取设计文档目录。"""
    return get_project_root() / "DESIGN"


def get_prompts_dir() -> Path:
    """获取提示模板目录。"""
    # 首先检查当前项目的 DESIGN/PROMPTS/ 目录
    path = get_design_dir() / "PROMPTS"
    if path.exists():
        return path

    # 向后兼容：检查 src/novels_project/../DESIGN/PROMPTS/
    legacy_path = get_project_root() / "DESIGN" / "PROMPTS"
    if legacy_path.exists():
        return legacy_path

    return path


def get_output_dir() -> Path:
    """获取输出目录。"""
    return get_project_root() / "output"


def get_chapters_dir() -> Path:
    """获取章节输出目录。"""
    return get_output_dir() / "chapters"


def get_summaries_dir() -> Path:
    """获取摘要输出目录。"""
    return get_output_dir() / "chapter_summaries"


def get_samples_dir() -> Path:
    """获取样例目录。"""
    return get_project_root() / "samples"


def get_vector_db_dir() -> Path:
    """获取向量库目录。"""
    return get_project_root() / "vector_db"


def get_sessions_dir() -> Path:
    """获取会话目录。"""
    return get_project_root() / "sessions"


def get_feedback_dir() -> Path:
    """获取反馈目录。"""
    return get_project_root() / "feedback"


def get_feedback_path() -> Path:
    """获取反馈文件路径。"""
    return get_feedback_dir() / "proofreading_feedback.yaml"


def ensure_directories():
    """确保所有必要的目录都存在。"""
    dirs = [
        get_output_dir(),
        get_chapters_dir(),
        get_summaries_dir(),
        get_sessions_dir(),
        get_feedback_dir(),
        get_vector_db_dir(),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def get_project_info() -> dict:
    """获取项目信息。"""
    root = get_project_root()

    info = {
        "project_root": str(root),
        "config_exists": get_config_dir().exists(),
        "character_cards_exists": get_character_cards_path().exists(),
        "design_exists": get_design_dir().exists(),
        "prompts_exists": get_prompts_dir().exists(),
        "samples_exists": get_samples_dir().exists(),
        "output_exists": get_output_dir().exists(),
    }

    # 统计已生成章节
    chapters_dir = get_chapters_dir()
    if chapters_dir.exists():
        info["generated_chapters"] = len(list(chapters_dir.glob("chapter_*_final.md")))
    else:
        info["generated_chapters"] = 0

    return info


def check_project_ready() -> tuple[bool, list[str]]:
    """
    检查项目是否就绪。

    Returns:
        (is_ready, missing_items)
    """
    missing = []

    if not get_character_cards_path().exists():
        missing.append("config/character_base_cards.yaml - 人物卡文件")

    if not get_prompts_dir().exists():
        missing.append("DESIGN/PROMPTS/ - 提示模板目录（可选，有默认值）")

    return len(missing) == 0, missing


def format_project_status() -> str:
    """格式化项目状态报告。"""
    info = get_project_info()
    is_ready, missing = check_project_ready()

    lines = [
        "=" * 50,
        "  当前故事项目",
        "=" * 50,
        f"  项目目录: {info['project_root']}",
        "",
    ]

    if info["generated_chapters"] > 0:
        lines.append(f"  已生成章节: {info['generated_chapters']} 章")
        lines.append("")

    if is_ready:
        lines.append("  状态: 就绪")
    else:
        lines.append("  状态: 需要准备以下文件:")
        for item in missing:
            lines.append(f"    - {item}")

    lines.append("=" * 50)

    return "\n".join(lines)
