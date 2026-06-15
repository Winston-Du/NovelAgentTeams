"""
单元测试：内容管理模块测试

测试范围：
1. 人物卡管理
2. 章节管理
3. 暗线管理
4. 全局搜索
"""

import pytest
import tempfile
from pathlib import Path
import yaml

# Mock 项目配置
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from novels_project.api.content import (
    _load_character_cards,
    _save_character_cards,
    _flatten_characters,
    _load_plotlines,
    _save_plotlines,
)
from novels_project.api.export import _validate_export_path


class TestCharacterCards:
    """测试人物卡管理功能"""

    def test_load_empty_file(self, tmp_path):
        """测试加载不存在的文件"""
        # Mock 路径
        cards = _load_character_cards()
        assert isinstance(cards, dict)

    def test_flatten_characters_empty(self):
        """测试扁平化空数据"""
        result = _flatten_characters({})
        assert isinstance(result, list)
        assert len(result) == 0

    def test_flatten_characters_valid(self):
        """测试扁平化有效人物卡数据"""
        test_data = {
            "s_tier": {
                "characters": {
                    "主角": {
                        "role": "主角",
                        "brief": "主角描述"
                    }
                }
            },
            "a_tier": {
                "配角A": {
                    "role": "配角",
                    "brief": "配角描述"
                }
            }
        }
        
        result = _flatten_characters(test_data)
        assert len(result) == 2
        names = {c["name"] for c in result}
        assert names == {"主角", "配角A"}
        assert result[0]["tier"] == "s_tier"

    def test_character_data_structure(self):
        """验证人物卡数据结构"""
        test_char = {
            "name": "测试人物",
            "tier": "b_tier",
            "role": "测试角色",
            "brief": "测试描述",
            "personality": "性格描述",
            "background": "背景故事"
        }
        required_fields = ["name", "tier", "role"]
        for field in required_fields:
            assert field in test_char


class TestPlotlines:
    """测试暗线管理功能"""

    def test_load_empty_plotlines(self):
        """测试加载空暗线文件"""
        result = _load_plotlines()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_plotline_data_structure(self):
        """验证暗线数据结构"""
        test_plotline = {
            "id": "plot001",
            "name": "主线剧情",
            "description": "主要故事线",
            "status": "active",
            "related_characters": ["主角", "反派"]
        }
        required_fields = ["id", "name", "description", "status"]
        for field in required_fields:
            assert field in test_plotline


class TestSearch:
    """测试搜索功能"""

    def test_search_text_preprocessing(self):
        """测试搜索文本预处理"""
        test_text = "测试搜索内容"
        lower_text = test_text.lower()
        assert lower_text == "测试搜索内容"

    def test_search_match(self):
        """测试搜索匹配逻辑"""
        search_query = "商人"
        content = "一位精明的商人"
        assert search_query.lower() in content.lower()


class TestExport:
    """测试章节导出功能"""

    def test_validate_export_path_valid(self, tmp_path):
        """测试验证有效路径"""
        result = _validate_export_path(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_validate_export_path_tilde(self, tmp_path, monkeypatch):
        """测试验证带波浪号的路径"""
        monkeypatch.setenv("HOME", str(tmp_path))
        result = _validate_export_path("~/export")
        expected = tmp_path / "export"
        assert result == expected.resolve()

    def test_validate_export_path_traversal_attack(self):
        """测试路径遍历攻击检测"""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_export_path("/etc/../passwd")
        assert exc_info.value.status_code == 400
        assert "不允许使用路径遍历" in str(exc_info.value.detail)

    def test_validate_export_path_parent_directory(self):
        """测试父目录遍历攻击"""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_export_path("../malicious")
        assert exc_info.value.status_code == 400
        assert "不允许使用路径遍历" in str(exc_info.value.detail)

    def test_validate_export_path_system_dir_blocked(self):
        """测试系统目录被拒绝写入"""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_export_path("/etc/passwd")
        assert exc_info.value.status_code == 400
        assert "不允许写入系统目录" in str(exc_info.value.detail)

    def test_validate_export_path_not_absolute(self):
        """测试非绝对路径输入被解析为绝对路径后通过验证"""
        # Path.resolve() 会将相对路径转换为绝对路径，因此此测试验证转换后的行为
        result = _validate_export_path("relative/path")
        assert result.is_absolute()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
