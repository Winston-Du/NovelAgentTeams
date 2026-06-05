"""
项目配置 - 管理当前故事项目的路径

所有路径基于 PROJECT_ROOT。
优先级：
1. 代码中显式调用 set_project_root()
2. 环境变量 NOVEL_PROJECT_ROOT
3. 项目配置文件 novels_project/novels.yaml（随项目分发）
4. 当前工作目录（默认）

用户可以在不同故事目录下运行系统，每个故事有独立的配置和输出。
"""
from pathlib import Path
from typing import Optional
import os
import yaml

# 全局项目根目录
_PROJECT_ROOT: Optional[Path] = None

# 项目配置文件路径（相对于 src/novels_project/ 的上一级）
_PROJECT_CONFIG_NAME = "novels.yaml"


def _get_package_root() -> Path:
    """获取 novels_project 包所在的目录。"""
    # src/novels_project/project_config.py -> novels_project/
    return Path(__file__).parent.parent.parent


def _load_project_config() -> dict:
    """加载项目配置文件。"""
    config_path = _get_package_root() / _PROJECT_CONFIG_NAME
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    return {}


def _get_default_project_root() -> Path:
    """
    获取默认项目根目录。

    优先级：
    1. 环境变量 NOVEL_PROJECT_ROOT
    2. 项目配置文件 novels_project/novels.yaml
    3. 当前工作目录
    """
    # 1. 环境变量
    env_root = os.getenv('NOVEL_PROJECT_ROOT')
    if env_root:
        path = Path(env_root).expanduser().resolve()
        if path.exists():
            return path
        print(f"[警告] 环境变量 NOVEL_PROJECT_ROOT 指向的目录不存在: {path}")

    # 2. 项目配置文件
    config = _load_project_config()
    config_root = config.get('project_root')
    if config_root:
        path = Path(config_root).expanduser().resolve()
        if path.exists():
            return path
        print(f"[警告] 配置文件 project_root 指向的目录不存在: {path}")

    # 3. 当前工作目录
    return Path.cwd()


def get_project_root() -> Path:
    """获取当前项目根目录。"""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = _get_default_project_root()
    return _PROJECT_ROOT


def set_project_root(path: Optional[Path] = None):
    """
    设置项目根目录。

    Args:
        path: 项目路径，None 表示使用默认逻辑
    """
    global _PROJECT_ROOT
    if path is None:
        _PROJECT_ROOT = _get_default_project_root()
    else:
        _PROJECT_ROOT = path


def get_project_config_path() -> Path:
    """获取项目配置文件路径。"""
    return _get_package_root() / _PROJECT_CONFIG_NAME


def get_config_dir() -> Path:
    """获取配置目录（工作空间级别，存储人物卡等）。"""
    return get_project_root() / "config"


def get_system_config_dir() -> Path:
    """获取系统级配置目录（包级别，存储全局设置、Agent配置等）。

    该目录独立于工作空间，确保模型供应商、系统设置等跨工作空间配置
    存储在 NovelAgentTeams 项目目录下，而非工作空间目录下。
    """
    return _get_package_root() / "config"


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
    legacy_path = get_project_root() / "DESIGN" / "PROMPTS"  # pragma: no cover
    if legacy_path.exists():  # pragma: no cover
        return legacy_path  # pragma: no cover

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
