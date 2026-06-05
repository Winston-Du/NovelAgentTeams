"""
单元测试：initialize.py - DesignValidator 类
"""
import os
import pytest
import yaml
from unittest import mock

import sys as _sys_mod
from novels_project.initialize import DesignValidator, main


def create_design_files(design_dir, files):
    """在 design_dir 下创建文件列表，每个至少 200 字节。"""
    design_dir.mkdir(parents=True, exist_ok=True)
    for fname in files:
        fpath = design_dir / fname
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text("X" * 200, encoding="utf-8")


def create_small_file(filepath, size=50):
    """创建一个小于 100 字节的文件。"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text("X" * size, encoding="utf-8")


REQUIRED_DESIGN_FILES = [
    "BRAINSTORM_SUMMARY.md",
    "WORKFLOW.md",
    "AGENTS_DEFINITION.md",
    "DATA_STRUCTURES.md",
    "VALIDATION_CHECKLIST.md",
    "PROMPTS/chief_editor_prompt.md",
    "PROMPTS/character_designer_prompt.md",
    "PROMPTS/plot_writer_prompt.md",
    "PROMPTS/proofreader_prompt.md",
]


# ==================== __init__ ====================

class TestDesignValidatorInit:
    """测试 DesignValidator.__init__"""

    def test_default_project_root(self):
        """使用默认 project_root（基于 __file__ 向上三级）。"""
        validator = DesignValidator()
        assert validator.project_root is not None
        assert isinstance(validator.errors, list)
        assert isinstance(validator.warnings, list)

    def test_custom_project_root(self, tmp_path):
        """使用自定义 project_root。"""
        validator = DesignValidator(project_root=str(tmp_path))
        assert validator.project_root == tmp_path
        assert validator.design_dir == tmp_path / "DESIGN"
        assert validator.config_dir == tmp_path / "src" / "novels_project" / "config"
        assert validator.samples_dir == tmp_path / "samples"


# ==================== validate_all ====================

class TestValidateAll:
    """测试 validate_all 方法"""

    def _setup_valid_project(self, tmp_path):
        """创建一个全部就绪的模拟项目。"""
        validator = DesignValidator(project_root=str(tmp_path))
        create_design_files(validator.design_dir, REQUIRED_DESIGN_FILES)

        config_dir = validator.config_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        cards = {
            "s_tier": {
                "characters": {
                    "主角A": {"name": "主角A", "role": "hero", "core_personality": "勇敢", "unique_speaking_style": {"example_dialogues": ["你好", "再见"]}},
                    "主角B": {"name": "主角B", "role": "heroine", "core_personality": "温柔", "unique_speaking_style": {"example_dialogues": ["你好呀", "再见了"]}},
                    "主角C": {"name": "主角C", "role": "mentor", "core_personality": "智慧", "unique_speaking_style": {"example_dialogues": ["加油", "努力"]}},
                }
            },
            "a_tier": {
                "characters": {
                    "配角A": {"name": "配角A", "role": "friend", "core_personality": "忠诚", "unique_speaking_style": {"example_dialogues": ["明白", "好的"]}},
                }
            },
        }
        with open(config_dir / "character_base_cards.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cards, f)

        samples_dir = validator.samples_dir
        samples_dir.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            (samples_dir / f"sample_{i}.md").write_text(f"Sample {i} content", encoding="utf-8")

        os.environ["COMPANY_API_KEY"] = "app123:key456"
        return validator

    def test_all_checks_pass(self, tmp_path):
        validator = self._setup_valid_project(tmp_path)
        result = validator.validate_all()
        assert result is True
        assert len(validator.errors) == 0

    def test_all_checks_pass_no_warnings(self, tmp_path):
        """所有检查通过且无任何警告 -> 触发 lines 71-72."""
        validator = DesignValidator(project_root=str(tmp_path))
        create_design_files(validator.design_dir, REQUIRED_DESIGN_FILES)

        config_dir = validator.config_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        # 创建可选配置文件以避免警告
        with open(config_dir / "agents.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"dummy": True}, f)
        with open(config_dir / "tasks.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"dummy": True}, f)
        # 创建正确的人物卡以避免警告
        cards = {
            "s_tier": {
                "characters": {
                    "A": {"name": "A", "role": "hero", "core_personality": "勇敢", "unique_speaking_style": {"example_dialogues": ["你好", "再见", "谢谢"]}},
                    "B": {"name": "B", "role": "heroine", "core_personality": "温柔", "unique_speaking_style": {"example_dialogues": ["你好呀", "再见了"]}},
                    "C": {"name": "C", "role": "mentor", "core_personality": "智慧", "unique_speaking_style": {"example_dialogues": ["加油", "努力"]}},
                }
            },
            "a_tier": {"characters": {}},
        }
        with open(config_dir / "character_base_cards.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cards, f)

        samples_dir = validator.samples_dir
        samples_dir.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            (samples_dir / f"sample_{i}.md").write_text(f"Sample {i} content", encoding="utf-8")

        os.environ["COMPANY_API_KEY"] = "app123:key456"
        result = validator.validate_all()
        assert result is True
        assert len(validator.errors) == 0
        assert len(validator.warnings) == 0

    def test_check_returns_false(self, tmp_path):
        """一个 check_func 返回 False -> '⚠️ 警告' 打印."""
        validator = DesignValidator(project_root=str(tmp_path))
        create_design_files(validator.design_dir, REQUIRED_DESIGN_FILES)
        config_dir = validator.config_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        cards = {
            "s_tier": {
                "characters": {
                    "A": {"name": "A", "role": "hero", "core_personality": "勇敢", "unique_speaking_style": {"example_dialogues": ["你好", "再见", "谢谢"]}},
                    "B": {"name": "B", "role": "heroine", "core_personality": "温柔", "unique_speaking_style": {"example_dialogues": ["你好呀", "再见了"]}},
                    "C": {"name": "C", "role": "mentor", "core_personality": "智慧", "unique_speaking_style": {"example_dialogues": ["加油", "努力"]}},
                }
            }
        }
        with open(config_dir / "character_base_cards.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cards, f)
        for fname in ["agents.yaml", "tasks.yaml"]:
            with open(config_dir / fname, "w", encoding="utf-8") as f:
                yaml.dump({"dummy": True}, f)
        samples_dir = validator.samples_dir
        samples_dir.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            (samples_dir / f"sample_{i}.md").write_text(f"Sample {i} content", encoding="utf-8")
        os.environ["COMPANY_API_KEY"] = "app123:key456"

        # Mock one check to return False
        original = validator._check_design_documents
        validator._check_design_documents = lambda: False

        result = validator.validate_all()
        assert result is True  # returning False is a warning, not error

    def test_check_throws_exception(self, tmp_path, monkeypatch):
        """一个 check_func 抛出异常 -> '❌ 失败' + error 记录."""
        validator = DesignValidator(project_root=str(tmp_path))
        create_design_files(validator.design_dir, REQUIRED_DESIGN_FILES)

        config_dir = validator.config_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        # 创建必需的 character_base_cards.yaml
        cards = {
            "s_tier": {
                "characters": {
                    "A": {"name": "A", "role": "hero", "core_personality": "勇敢", "unique_speaking_style": {"example_dialogues": ["你好", "再见"]}},
                    "B": {"name": "B", "role": "heroine", "core_personality": "温柔", "unique_speaking_style": {"example_dialogues": ["你好呀", "再见了"]}},
                    "C": {"name": "C", "role": "mentor", "core_personality": "智慧", "unique_speaking_style": {"example_dialogues": ["加油", "努力"]}},
                }
            }
        }
        with open(config_dir / "character_base_cards.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cards, f)

        # _check_samples 会正常通过，但让 _check_config_files 也通过（创建 agents.yaml, tasks.yaml 避免 warning）
        for fname in ["agents.yaml", "tasks.yaml"]:
            with open(config_dir / fname, "w", encoding="utf-8") as f:
                yaml.dump({"dummy": True}, f)

        # Monkeypatch _check_environment_variables 来抛异常
        def failing_check():
            raise RuntimeError("API 连接失败")
        validator._check_environment_variables = failing_check

        result = validator.validate_all()
        assert result is False
        assert any("_check_environment_variables" in e or "环境变量" in e for e in validator.errors)

    def test_with_errors(self, tmp_path):
        """某些检查抛出异常 -> 有 errors，返回 False。"""
        validator = DesignValidator(project_root=str(tmp_path))
        result = validator.validate_all()
        assert result is False
        assert len(validator.errors) > 0

    def test_with_warnings(self, tmp_path):
        """所有检查通过但有警告 -> 返回 True。"""
        validator = self._setup_valid_project(tmp_path)
        # 让 samples 只有 2 个产生警告
        samples_dir = validator.samples_dir
        for f in samples_dir.iterdir():
            f.unlink()
        for i in range(2):
            (samples_dir / f"sample_{i}.md").write_text("content", encoding="utf-8")
        result = validator.validate_all()
        assert result is True
        assert len(validator.warnings) > 0

    def test_with_both_errors_and_warnings(self, tmp_path):
        """有 errors 也有 warnings -> 返回 False。"""
        validator = self._setup_valid_project(tmp_path)
        # 删除必需文件造成 error，同时缩减 samples 造成 warning
        (validator.design_dir / "BRAINSTORM_SUMMARY.md").unlink()
        samples_dir = validator.samples_dir
        for f in samples_dir.iterdir():
            f.unlink()
        result = validator.validate_all()
        assert result is False
        assert len(validator.errors) > 0
        # 可能也有 warnings
        assert len(validator.errors) + len(validator.warnings) >= 1


# ==================== _check_design_documents ====================

class TestCheckDesignDocuments:
    def test_all_files_exist(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        create_design_files(validator.design_dir, REQUIRED_DESIGN_FILES)
        result = validator._check_design_documents()
        assert result is True

    def test_some_missing(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        create_design_files(validator.design_dir, REQUIRED_DESIGN_FILES[:-2])
        with pytest.raises(Exception, match="缺失设计文档"):
            validator._check_design_documents()

    def test_file_too_small_warning(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        create_design_files(validator.design_dir, REQUIRED_DESIGN_FILES)
        # 把其中一个文件变小
        create_small_file(validator.design_dir / "BRAINSTORM_SUMMARY.md", size=50)
        result = validator._check_design_documents()
        assert result is True
        assert any("内容过少" in w for w in validator.warnings)


# ==================== _check_config_files ====================

class TestCheckConfigFiles:
    def _setup_config(self, config_dir):
        config_dir.mkdir(parents=True, exist_ok=True)
        cards = {"s_tier": {"characters": {}}}
        with open(config_dir / "character_base_cards.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cards, f)

    def test_all_required_files_exist(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        self._setup_config(validator.config_dir)
        result = validator._check_config_files()
        assert result is True

    def test_missing_required_file(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        with pytest.raises(Exception, match="缺失必需配置文件"):
            validator._check_config_files()

    def test_missing_optional_file(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        self._setup_config(validator.config_dir)
        result = validator._check_config_files()
        assert result is True
        # 可选文件不存在应该给警告
        assert any("不存在（可选）" in w for w in validator.warnings)

    def test_yaml_format_error(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        config_dir = validator.config_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "character_base_cards.yaml").write_text(": bad yaml: [", encoding="utf-8")
        with pytest.raises(Exception, match="YAML 格式错误"):
            validator._check_config_files()


# ==================== _check_character_base_cards ====================

class TestCheckCharacterBaseCards:
    def _write_cards(self, config_dir, data):
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(config_dir / "character_base_cards.yaml", "w", encoding="utf-8") as f:
            yaml.dump(data, f)

    def _make_char(self, name, role="hero", personality="勇敢", dialogues=None):
        if dialogues is None:
            dialogues = ["你好", "再见"]
        return {
            "name": name,
            "role": role,
            "core_personality": personality,
            "unique_speaking_style": {"example_dialogues": dialogues},
        }

    def test_file_missing(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        with pytest.raises(Exception, match="人物卡库文件不存在"):
            validator._check_character_base_cards()

    def test_empty_data(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        self._write_cards(validator.config_dir, {})
        with pytest.raises(Exception, match="人物卡库为空"):
            validator._check_character_base_cards()

    def test_s_tier_count_less_than_3_warning(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        data = {
            "s_tier": {
                "characters": {
                    "A": self._make_char("A"),
                }
            }
        }
        self._write_cards(validator.config_dir, data)
        result = validator._check_character_base_cards()
        assert result is True
        assert any("只有 1 个" in w for w in validator.warnings)

    def test_missing_required_field(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        data = {
            "s_tier": {
                "characters": {
                    "A": {"name": "A", "role": "", "core_personality": "勇敢", "unique_speaking_style": {}},
                }
            }
        }
        self._write_cards(validator.config_dir, data)
        with pytest.raises(Exception, match="缺少必填字段"):
            validator._check_character_base_cards()

    def test_fewer_than_2_example_dialogues_warning(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        data = {
            "s_tier": {
                "characters": {
                    "A": self._make_char("A", dialogues=["只有一条"]),
                    "B": self._make_char("B", dialogues=["你好", "再见"]),
                    "C": self._make_char("C", dialogues=["嗨", "拜拜"]),
                }
            }
        }
        self._write_cards(validator.config_dir, data)
        result = validator._check_character_base_cards()
        assert result is True
        assert any("对话示例少于 2 条" in w for w in validator.warnings)

    def test_style_not_dict_skips_dialogue_check(self, tmp_path):
        """unique_speaking_style is not a dict -> skips dialogue check."""
        validator = DesignValidator(project_root=str(tmp_path))
        char_data = {
            "name": "A",
            "role": "hero",
            "core_personality": "勇敢",
            "unique_speaking_style": "简短的说话风格",
        }
        data = {
            "s_tier": {
                "characters": {
                    "A": char_data,
                    "B": self._make_char("B", dialogues=["你好", "再见"]),
                    "C": self._make_char("C", dialogues=["嗨", "拜拜"]),
                }
            },
            "a_tier": {
                "characters": {}
            }
        }
        self._write_cards(validator.config_dir, data)
        result = validator._check_character_base_cards()
        assert result is True


# ==================== _check_samples ====================

class TestCheckSamples:
    def test_dir_not_exist(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        result = validator._check_samples()
        assert result is True
        assert any("目录不存在" in w for w in validator.warnings)

    def test_empty(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        validator.samples_dir.mkdir(parents=True, exist_ok=True)
        result = validator._check_samples()
        assert result is True
        assert any("样例库为空" in w for w in validator.warnings)

    def test_fewer_than_5(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        validator.samples_dir.mkdir(parents=True, exist_ok=True)
        for i in range(3):
            (validator.samples_dir / f"sample_{i}.md").write_text("content", encoding="utf-8")
        result = validator._check_samples()
        assert result is True
        assert any("只有 3 个样例" in w for w in validator.warnings)

    def test_5_or_more_samples(self, tmp_path):
        validator = DesignValidator(project_root=str(tmp_path))
        validator.samples_dir.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            (validator.samples_dir / f"sample_{i}.md").write_text("content", encoding="utf-8")
        result = validator._check_samples()
        assert result is True
        # 不应该有关于样例数量的警告
        warnings_text = " ".join(validator.warnings)
        assert "样例库" not in warnings_text


# ==================== _check_environment_variables ====================

class TestCheckEnvironmentVariables:
    def test_api_key_set(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COMPANY_API_KEY", "app123:key456")
        validator = DesignValidator(project_root=str(tmp_path))
        result = validator._check_environment_variables()
        assert result is True

    def test_api_key_not_set(self, monkeypatch, tmp_path):
        monkeypatch.delenv("COMPANY_API_KEY", raising=False)
        validator = DesignValidator(project_root=str(tmp_path))
        with pytest.raises(Exception, match="COMPANY_API_KEY 未设置"):
            validator._check_environment_variables()

    def test_malformed_format_warning(self, monkeypatch, tmp_path):
        monkeypatch.setenv("COMPANY_API_KEY", "justakeywithoutcolon")
        validator = DesignValidator(project_root=str(tmp_path))
        result = validator._check_environment_variables()
        assert result is True
        assert any("格式可能不正确" in w for w in validator.warnings)


# ==================== main() ====================

class TestMainFunction:
    """测试 main() 入口函数"""

    def test_main_success(self, monkeypatch):
        """main() 成功路径 -> sys.exit(0)."""
        exit_calls = []
        monkeypatch.setattr("sys.exit", exit_calls.append)
        mock_validator = mock.MagicMock()
        mock_validator.validate_all.return_value = True
        monkeypatch.setattr("novels_project.initialize.DesignValidator", lambda: mock_validator)
        main()
        assert exit_calls == [0]

    def test_main_failure(self, monkeypatch):
        """main() 失败路径 -> sys.exit(1)."""
        exit_calls = []
        monkeypatch.setattr("sys.exit", exit_calls.append)
        mock_validator = mock.MagicMock()
        mock_validator.validate_all.return_value = False
        monkeypatch.setattr("novels_project.initialize.DesignValidator", lambda: mock_validator)
        main()
        assert exit_calls == [1]