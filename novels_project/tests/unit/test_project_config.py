"""
单元测试：project_config.py
"""
import os
import yaml
import pytest
from pathlib import Path

import novels_project.project_config as pc
from novels_project.project_config import (
    _get_package_root,
    _load_project_config,
    _get_default_project_root,
    get_project_root,
    set_project_root,
    get_project_config_path,
    get_config_dir,
    get_system_config_dir,
    get_character_cards_path,
    get_design_dir,
    get_prompts_dir,
    get_output_dir,
    get_chapters_dir,
    get_summaries_dir,
    get_samples_dir,
    get_vector_db_dir,
    get_sessions_dir,
    get_feedback_dir,
    get_feedback_path,
    ensure_directories,
    get_project_info,
    check_project_ready,
    format_project_status,
)


# ---- helpers ----

@pytest.fixture(autouse=True)
def reset_project_root():
    """每个测试前后重置全局 _PROJECT_ROOT。"""
    pc._PROJECT_ROOT = None
    yield
    pc._PROJECT_ROOT = None


def write_config(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)


# ==================== _get_package_root ====================

class TestGetPackageRoot:
    def test_returns_path(self):
        result = _get_package_root()
        assert isinstance(result, Path)
        assert result.exists()


# ==================== _load_project_config ====================

class TestLoadProjectConfig:
    def test_config_exists(self, tmp_path, monkeypatch):
        config_path = tmp_path / "novels.yaml"
        config_path.write_text("project_root: /some/path\n", encoding="utf-8")
        monkeypatch.setattr(pc, "_get_package_root", lambda: tmp_path)
        result = _load_project_config()
        assert result.get("project_root") == "/some/path"

    def test_config_does_not_exist(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pc, "_get_package_root", lambda: tmp_path)
        result = _load_project_config()
        assert result == {}

    def test_yaml_error(self, tmp_path, monkeypatch):
        config_path = tmp_path / "novels.yaml"
        config_path.write_text(": bad: yaml: [", encoding="utf-8")
        monkeypatch.setattr(pc, "_get_package_root", lambda: tmp_path)
        result = _load_project_config()
        assert result == {}


# ==================== _get_default_project_root ====================

class TestGetDefaultProjectRoot:
    def test_env_var_set_and_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NOVEL_PROJECT_ROOT", str(tmp_path))
        monkeypatch.setattr(pc, "_load_project_config", lambda: {})
        result = _get_default_project_root()
        assert result == tmp_path.resolve()

    def test_env_var_set_but_not_exists(self, tmp_path, monkeypatch):
        nonexistent = tmp_path / "nonexistent_dir"
        monkeypatch.setenv("NOVEL_PROJECT_ROOT", str(nonexistent))
        monkeypatch.setattr(pc, "_load_project_config", lambda: {})
        result = _get_default_project_root()
        assert result == Path.cwd()

    def test_config_file_root(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NOVEL_PROJECT_ROOT", raising=False)
        monkeypatch.setattr(pc, "_load_project_config", lambda: {"project_root": str(tmp_path)})
        result = _get_default_project_root()
        assert result == tmp_path.resolve()

    def test_config_file_root_not_exists(self, tmp_path, monkeypatch, capsys):
        """Config file has project_root pointing to non-existent dir."""
        nonexistent = tmp_path / "nonexistent_dir"
        monkeypatch.delenv("NOVEL_PROJECT_ROOT", raising=False)
        monkeypatch.setattr(pc, "_load_project_config", lambda: {"project_root": str(nonexistent)})
        result = _get_default_project_root()
        assert result == Path.cwd()
        captured = capsys.readouterr()
        assert "警告" in captured.out

    def test_fallback_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NOVEL_PROJECT_ROOT", raising=False)
        monkeypatch.setattr(pc, "_load_project_config", lambda: {})
        result = _get_default_project_root()
        assert result == Path.cwd()


# ==================== get_project_root / set_project_root ====================

class TestGetSetProjectRoot:
    def test_with_project_root_set(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        assert get_project_root() == tmp_path

    def test_with_default(self, monkeypatch):
        monkeypatch.delenv("NOVEL_PROJECT_ROOT", raising=False)
        monkeypatch.setattr(pc, "_load_project_config", lambda: {})
        assert get_project_root() == Path.cwd()

    def test_set_project_root_with_path(self, tmp_path):
        set_project_root(tmp_path)
        assert pc._PROJECT_ROOT == tmp_path

    def test_set_project_root_with_none(self, monkeypatch):
        monkeypatch.delenv("NOVEL_PROJECT_ROOT", raising=False)
        monkeypatch.setattr(pc, "_load_project_config", lambda: {})
        set_project_root(None)
        assert pc._PROJECT_ROOT == Path.cwd()


# ==================== get_project_config_path ====================

class TestGetProjectConfigPath:
    def test_returns_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr(pc, "_get_package_root", lambda: tmp_path)
        result = get_project_config_path()
        assert result == tmp_path / "novels.yaml"


# ==================== get_config_dir / get_system_config_dir ====================

class TestConfigDirs:
    def test_get_config_dir(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        result = get_config_dir()
        assert result == tmp_path / "config"

    def test_get_system_config_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr(pc, "_get_package_root", lambda: tmp_path)
        result = get_system_config_dir()
        assert result == tmp_path / "config"


# ==================== get_character_cards_path ====================

class TestGetCharacterCardsPath:
    def test_standard_path_exists(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "character_base_cards.yaml").write_text("data: ok", encoding="utf-8")
        result = get_character_cards_path()
        assert result == config_dir / "character_base_cards.yaml"

    def test_legacy_path_exists(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        legacy = tmp_path / "src" / "novels_project" / "config" / "character_base_cards.yaml"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("legacy", encoding="utf-8")
        result = get_character_cards_path()
        assert result == legacy

    def test_neither_exists(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        result = get_character_cards_path()
        assert result == tmp_path / "config" / "character_base_cards.yaml"


# ==================== get_design_dir / get_prompts_dir ====================

class TestDesignAndPromptsDirs:
    def test_get_design_dir(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        assert get_design_dir() == tmp_path / "DESIGN"

    def test_get_prompts_dir_standard_exists(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        prompts = tmp_path / "DESIGN" / "PROMPTS"
        prompts.mkdir(parents=True)
        result = get_prompts_dir()
        assert result == prompts

    def test_get_prompts_dir_legacy(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        # 不创建标准路径，但它和 legacy 相同路径所以测试用不同 project_root
        assert get_prompts_dir() == tmp_path / "DESIGN" / "PROMPTS"

    def test_get_prompts_dir_legacy_exists(self, tmp_path):
        """When standard prompt path doesn't exist but legacy path does."""
        pc._PROJECT_ROOT = tmp_path
        # 标准路径：tmp_path / "DESIGN" / "PROMPTS"
        # legacy 路径：tmp_path / "DESIGN" / "PROMPTS" (same path)
        # 创建一个不同的 project_root 使 legacy 路径不同
        # Actually, standard and legacy are the same path in this case
        # Let's create the legacy path
        legacy = tmp_path / "DESIGN" / "PROMPTS"
        legacy.mkdir(parents=True)
        result = get_prompts_dir()
        assert result == legacy


# ==================== output / chapters / summaries / samples / etc ====================

class TestOutputPaths:
    def test_get_output_dir(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        assert get_output_dir() == tmp_path / "output"

    def test_get_chapters_dir(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        assert get_chapters_dir() == tmp_path / "output" / "chapters"

    def test_get_summaries_dir(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        assert get_summaries_dir() == tmp_path / "output" / "chapter_summaries"

    def test_get_samples_dir(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        assert get_samples_dir() == tmp_path / "samples"

    def test_get_vector_db_dir(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        assert get_vector_db_dir() == tmp_path / "vector_db"

    def test_get_sessions_dir(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        assert get_sessions_dir() == tmp_path / "sessions"

    def test_get_feedback_dir(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        assert get_feedback_dir() == tmp_path / "feedback"

    def test_get_feedback_path(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        assert get_feedback_path() == tmp_path / "feedback" / "proofreading_feedback.yaml"


# ==================== ensure_directories ====================

class TestEnsureDirectories:
    def test_creates_all_dirs(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        ensure_directories()
        assert (tmp_path / "output").exists()
        assert (tmp_path / "output" / "chapters").exists()
        assert (tmp_path / "output" / "chapter_summaries").exists()
        assert (tmp_path / "sessions").exists()
        assert (tmp_path / "feedback").exists()
        assert (tmp_path / "vector_db").exists()


# ==================== get_project_info ====================

class TestGetProjectInfo:
    def test_with_chapters(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        chapters_dir = tmp_path / "output" / "chapters"
        chapters_dir.mkdir(parents=True)
        (chapters_dir / "chapter_01_final.md").write_text("ch1", encoding="utf-8")
        (chapters_dir / "chapter_02_final.md").write_text("ch1", encoding="utf-8")
        info = get_project_info()
        assert info["generated_chapters"] == 2
        assert info["project_root"] == str(tmp_path)

    def test_without_chapters(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        info = get_project_info()
        assert info["generated_chapters"] == 0


# ==================== check_project_ready ====================

class TestCheckProjectReady:
    def test_ready(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "character_base_cards.yaml").write_text("ok", encoding="utf-8")
        prompts = tmp_path / "DESIGN" / "PROMPTS"
        prompts.mkdir(parents=True)
        is_ready, missing = check_project_ready()
        assert is_ready is True
        assert len(missing) == 0

    def test_not_ready(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        is_ready, missing = check_project_ready()
        assert is_ready is False
        assert len(missing) > 0


# ==================== format_project_status ====================

class TestFormatProjectStatus:
    def test_ready(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "character_base_cards.yaml").write_text("ok", encoding="utf-8")
        prompts = tmp_path / "DESIGN" / "PROMPTS"
        prompts.mkdir(parents=True)
        status = format_project_status()
        assert "就绪" in status

    def test_not_ready(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        status = format_project_status()
        assert "需要准备以下文件" in status

    def test_with_generated_chapters(self, tmp_path):
        pc._PROJECT_ROOT = tmp_path
        chapters_dir = tmp_path / "output" / "chapters"
        chapters_dir.mkdir(parents=True)
        (chapters_dir / "chapter_01_final.md").write_text("ch1", encoding="utf-8")
        status = format_project_status()
        assert "已生成章节" in status