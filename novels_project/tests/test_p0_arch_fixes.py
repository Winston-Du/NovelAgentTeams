"""
P0 阻塞测试用例 - 架构优化修复验证

覆盖三个 P0 修复：
1. 异常分类逻辑 - entity_extractor.py 中的 FALLBACK_EXCEPTIONS
2. 动态角色加载 - character_voice_checker.py 去除硬编码
3. 统一 LLM 工厂 - transport/llm_factory.py

目标：60 条测试用例
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest
import yaml

# ---- 确保 src 在 path 中 ----
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from novels_project.shared.exceptions import (
    NovelAgentError,
    ConfigError,
    LLMError,
    EntityExtractionError,
    CharacterCardsError,
    FALLBACK_EXCEPTIONS,
)

from novels_project.shared.character_cards_utils import (
    flatten_characters,
    get_character_names,
    load_character_cards_dict,
)


# ================================================================
# 第一部分：异常体系测试 (20 条)
# ================================================================

class TestExceptionHierarchy:
    """异常分层体系验证。"""

    def test_novel_agent_error_is_base(self):
        assert issubclass(ConfigError, NovelAgentError)
        assert issubclass(LLMError, NovelAgentError)
        assert issubclass(EntityExtractionError, NovelAgentError)
        assert issubclass(CharacterCardsError, NovelAgentError)

    def test_llm_error_is_not_caught_by_fallback(self):
        with pytest.raises(LLMError):
            try:
                raise LLMError("API Key 过期")
            except FALLBACK_EXCEPTIONS:
                pass

    def test_entity_extraction_error_is_fallback(self):
        assert issubclass(EntityExtractionError, FALLBACK_EXCEPTIONS)

    def test_json_decode_error_in_fallback(self):
        assert json.JSONDecodeError in FALLBACK_EXCEPTIONS

    def test_value_error_in_fallback(self):
        assert ValueError in FALLBACK_EXCEPTIONS

    def test_key_error_in_fallback(self):
        assert KeyError in FALLBACK_EXCEPTIONS

    def test_type_error_in_fallback(self):
        assert TypeError in FALLBACK_EXCEPTIONS

    def test_config_error_str(self):
        assert "配置文件缺失" in str(ConfigError("配置文件缺失"))

    def test_llm_error_str(self):
        assert "网络超时" in str(LLMError("网络超时"))

    def test_entity_extraction_error_str(self):
        assert "JSON 解析失败" in str(EntityExtractionError("JSON 解析失败"))

    def test_character_cards_error_str(self):
        assert "文件未找到" in str(CharacterCardsError("文件未找到"))

    def test_fallback_exceptions_is_tuple(self):
        assert isinstance(FALLBACK_EXCEPTIONS, tuple)

    def test_no_duplicate_in_fallback(self):
        assert len(FALLBACK_EXCEPTIONS) == len(set(FALLBACK_EXCEPTIONS))

    def test_llm_error_preserves_cause(self):
        original = ValueError("原错误")
        try:
            raise LLMError("LLM 错误") from original
        except LLMError as e:
            assert e.__cause__ is original

    def test_config_error_preserves_cause(self):
        original = FileNotFoundError("文件不存在")
        try:
            raise ConfigError("配置错误") from original
        except ConfigError as e:
            assert e.__cause__ is original

    def test_non_llm_exception_not_in_fallback(self):
        assert OSError not in FALLBACK_EXCEPTIONS
        assert ConnectionError not in FALLBACK_EXCEPTIONS
        assert RuntimeError not in FALLBACK_EXCEPTIONS

    def test_entity_extraction_error_subclass_detection(self):
        try:
            raise EntityExtractionError("测试")
        except NovelAgentError:
            pass
        else:
            pytest.fail("NovelAgentError 应能捕获 EntityExtractionError")

    def test_empty_config_error(self):
        err = ConfigError()
        assert isinstance(err, NovelAgentError)

    def test_fallback_only_contains_exception_types(self):
        for exc in FALLBACK_EXCEPTIONS:
            assert issubclass(exc, BaseException)

    def test_raise_llm_error_in_production_path(self):
        def handler():
            try:
                raise LLMError("不可恢复")
            except FALLBACK_EXCEPTIONS:
                return "fallback"
            except Exception:
                raise

        with pytest.raises(LLMError):
            handler()


# ================================================================
# 第二部分：人物卡工具函数测试 (15 条)
# ================================================================

class TestFlattenCharacters:

    @pytest.fixture
    def standard_data(self):
        return {
            "s_tier": {
                "tier_name": "主角",
                "characters": {
                    "陆商曜": {"role": "hero", "brief": "主角"},
                    "黑商周桓": {"role": "anti_hero", "brief": "亦正亦邪"},
                },
            },
            "a_tier": {
                "tier_name": "重要配角",
                "characters": {"木九公": {"role": "support", "brief": "神秘老者"}},
            },
        }

    @pytest.fixture
    def legacy_data(self):
        return {
            "s_tier": {
                "陆商曜": {"role": "hero"},
                "黑商周桓": {"role": "anti_hero"},
            },
        }

    def test_flatten_standard_structure(self, standard_data):
        assert len(flatten_characters(standard_data)) == 3

    def test_flatten_legacy_structure(self, legacy_data):
        assert len(flatten_characters(legacy_data)) == 2

    def test_flatten_adds_tier_field(self, standard_data):
        for item in flatten_characters(standard_data):
            assert "tier" in item

    def test_flatten_adds_name_field(self, standard_data):
        for item in flatten_characters(standard_data):
            assert "name" in item

    def test_flatten_custom_tiers(self, standard_data):
        result = flatten_characters(standard_data, tiers=("a_tier",))
        assert len(result) == 1
        assert result[0]["name"] == "木九公"

    def test_flatten_skips_underscore_keys(self, standard_data):
        standard_data["s_tier"]["characters"]["_internal"] = {"role": "internal"}
        result = flatten_characters(standard_data)
        names = [r["name"] for r in result]
        assert "_internal" not in names

    def test_flatten_empty_data(self):
        assert flatten_characters({}) == []

    def test_flatten_non_dict_tier(self):
        assert flatten_characters({"s_tier": "invalid_string"}) == []

    def test_flatten_non_dict_characters(self):
        assert flatten_characters({"s_tier": {"characters": "invalid"}}) == []


class TestGetCharacterNames:

    def test_get_names_from_standard(self):
        data = {
            "s_tier": {"characters": {
                "陆商曜": {"role": "hero"},
                "黑商周桓": {"role": "anti_hero"},
            }}
        }
        names = get_character_names(data)
        assert "陆商曜" in names
        assert "黑商周桓" in names
        assert len(names) == 2

    def test_get_names_empty_data(self):
        assert get_character_names({}) == []

    def test_get_names_skips_underscore(self):
        data = {"s_tier": {"characters": {"_config": {"key": "val"}, "正常角色": {"role": "hero"}}}}
        names = get_character_names(data)
        assert "_config" not in names
        assert "正常角色" in names

    def test_get_names_legacy_format(self):
        names = get_character_names({"s_tier": {"陆商曜": {"role": "hero"}}})
        assert "陆商曜" in names

    def test_get_names_all_tiers(self):
        data = {
            "s_tier": {"characters": {"A": {"role": "hero"}}},
            "a_tier": {"characters": {"B": {"role": "support"}}},
            "b_tier": {"characters": {"C": {"role": "minor"}}},
        }
        assert len(get_character_names(data)) == 3

    def test_get_names_skips_non_dict(self):
        data = {"s_tier": {"characters": {"valid": {"role": "hero"}, "bad": "string"}}}
        names = get_character_names(data)
        assert names == ["valid"]


# ================================================================
# 第三部分：LLM 工厂测试 (15 条)
# ================================================================

class TestLLMClientFactory:
    """LLMClientFactory 行为验证测试。

    依赖 _mock_heavy_deps fixture 提供的 sys.modules mock。
    """

    @staticmethod
    def _mock_cls():
        """获取并重置 api_client mock 上的 OpenAICompatibleClient。"""
        mock = sys.modules["novels_project.api_client"].OpenAICompatibleClient
        mock.reset_mock()
        return mock

    @staticmethod
    def _mock_settings(providers_override=None):
        mock_settings = MagicMock()
        mock_settings.load_model_providers.return_value = providers_override or {"providers": {}}
        mock_settings._resolve_api_key.return_value = ""
        sys.modules["novels_project.api.settings"] = mock_settings
        return mock_settings

    def test_create_with_explicit_params(self):
        mock_cls = self._mock_cls()
        from novels_project.transport.llm_factory import create_llm_client

        create_llm_client(api_key="k", base_url="http://test")
        mock_cls.assert_called_once()
        assert mock_cls.call_args[1]["api_key"] == "k"

    def test_falls_back_to_env_when_only_api_key(self):
        self._mock_settings()
        mock_cls = self._mock_cls()
        from novels_project.transport.llm_factory import create_llm_client

        with patch.dict(os.environ, {"COMPANY_API_KEY": "env-key"}, clear=True):
            create_llm_client(api_key="test-key")
            mock_cls.assert_called_once()

    def test_create_from_env(self):
        self._mock_settings()
        mock_cls = self._mock_cls()
        from novels_project.transport.llm_factory import create_llm_client

        with patch.dict(os.environ, {
            "COMPANY_API_KEY": "env-key",
            "MODEL_NAME": "env-model",
        }, clear=True):
            create_llm_client()
            mock_cls.assert_called_once()

    def test_create_no_config_raises(self):
        self._mock_settings()
        from novels_project.transport.llm_factory import create_llm_client, ConfigurationError

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError):
                create_llm_client()

    def test_create_with_provider_id(self):
        settings = self._mock_settings({
            "providers": {
                "gemini": {
                    "base_url": "http://gemini/v1",
                    "api_key": "g-key",
                    "models": [{"id": "gemini-pro"}],
                }
            }
        })
        settings._resolve_api_key.return_value = "g-key"
        mock_cls = self._mock_cls()
        from novels_project.transport.llm_factory import create_llm_client

        create_llm_client(provider_id="gemini")
        mock_cls.assert_called_once()

    def test_provider_id_not_found(self):
        self._mock_settings({"providers": {}})
        mock_cls = self._mock_cls()
        from novels_project.transport.llm_factory import create_llm_client

        with patch.dict(os.environ, {"COMPANY_API_KEY": "env-key"}, clear=True):
            create_llm_client(provider_id="nonexistent")
            mock_cls.assert_called_once()

    def test_cache_invalidate_single(self):
        from novels_project.transport.llm_factory import invalidate_cache, _instances
        _instances["gemini"] = "fake-client"
        invalidate_cache("gemini")
        assert "gemini" not in _instances

    def test_cache_invalidate_all(self):
        from novels_project.transport.llm_factory import invalidate_cache, _instances
        _instances["a"] = _instances["b"] = "fake"
        invalidate_cache()
        assert len(_instances) == 0

    def test_get_cached_client(self):
        from novels_project.transport.llm_factory import get_cached_client, _instances
        _instances["openai"] = "client-obj"
        assert get_cached_client("openai") == "client-obj"
        assert get_cached_client("nonexistent") is None

    def test_configuration_error_message(self):
        from novels_project.transport.llm_factory import ConfigurationError
        assert "自定义消息" in str(ConfigurationError("自定义消息"))

    def test_default_model_fallback(self):
        self._mock_settings()
        mock_cls = self._mock_cls()
        from novels_project.transport.llm_factory import create_llm_client

        with patch.dict(os.environ, {"COMPANY_API_KEY": "k"}, clear=True):
            create_llm_client()
            assert mock_cls.call_args[1]["default_model"] == "gemini-3-pro"

    def test_env_model_name_used(self):
        self._mock_settings()
        mock_cls = self._mock_cls()
        from novels_project.transport.llm_factory import create_llm_client

        with patch.dict(os.environ, {
            "COMPANY_API_KEY": "k",
            "MODEL_NAME": "env-specific-model",
        }, clear=True):
            create_llm_client()
            assert mock_cls.call_args[1]["default_model"] == "env-specific-model"

    def test_explicit_model_overrides_default(self):
        mock_cls = self._mock_cls()
        from novels_project.transport.llm_factory import create_llm_client

        create_llm_client(api_key="k", base_url="http://test", default_model="custom-model")
        assert mock_cls.call_args[1]["default_model"] == "custom-model"

    def test_provider_import_error_graceful(self):
        """api.settings 不可导入时优雅降级到环境变量。"""
        sys.modules.pop("novels_project.api.settings", None)
        mock_cls = self._mock_cls()
        from novels_project.transport.llm_factory import create_llm_client

        with patch.dict(os.environ, {"COMPANY_API_KEY": "env-key"}, clear=True):
            create_llm_client(provider_id="gemini")
            mock_cls.assert_called_once()
        sys.modules.pop("novels_project.api.settings", None)

    def test_explicit_model_wins_over_env(self):
        mock_cls = self._mock_cls()
        from novels_project.transport.llm_factory import create_llm_client

        with patch.dict(os.environ, {"MODEL_NAME": "env-model"}, clear=True):
            create_llm_client(api_key="k", base_url="http://test", default_model="explicit-model")
            assert mock_cls.call_args[1]["default_model"] == "explicit-model"


# ================================================================
# 第四部分：entity_extractor 异常处理测试 (10 条)
# ================================================================

@pytest.fixture(scope="module", autouse=True)
def _mock_heavy_deps():
    """
    模块级 mock：阻断 networkx / graph_store 和 api_client 的实际 import。
    所有测试共享同一组 mock，避免硬依赖阻塞。
    """
    mock_graph = MagicMock()
    mock_graph.GraphStore = MagicMock()
    for name in [
        "NODE_TYPE_CHARACTER", "NODE_TYPE_EVENT", "NODE_TYPE_ITEM",
        "NODE_TYPE_LOCATION", "NODE_TYPE_ORGANIZATION", "NODE_TYPE_CONCEPT",
        "REL_TYPE_ALLY", "REL_TYPE_ENEMY", "REL_TYPE_FAMILY", "REL_TYPE_MENTOR",
        "REL_TYPE_FRIEND", "REL_TYPE_LOVER", "REL_TYPE_SUBORDINATE",
        "REL_TYPE_KNOWS", "REL_TYPE_PARTICIPATED_IN", "REL_TYPE_CAUSED",
        "REL_TYPE_OWNS", "REL_TYPE_LOCATED_AT", "REL_TYPE_BELONGS_TO",
        "REL_TYPE_REFERS_TO", "REL_TYPE_FORESHAODWS",
    ]:
        setattr(mock_graph, name, name)
    sys.modules["novels_project.memory.graph_store"] = mock_graph

    mock_api = MagicMock()
    mock_api.ApiRequest = MagicMock()
    mock_api.TextDelta = MagicMock()
    # 单独创建一个可追踪的 OpenAICompatibleClient mock
    mock_api.OpenAICompatibleClient = MagicMock()
    sys.modules["novels_project.api_client"] = mock_api
    yield


class TestEntityExtractorExceptionHandling:

    def test_character_cards_fallback_on_json_error(self):
        from novels_project.memory.entity_extractor import EntityExtractor
        graph = MagicMock()
        extractor = EntityExtractor(graph)

        with patch.object(extractor, "_extract_character_cards_with_llm",
                          side_effect=json.JSONDecodeError("bad", "", 0)):
            with patch.object(extractor, "_extract_character_cards_with_rules",
                              return_value={"entities_added": 3, "relations_added": 1, "tier_stats": {}}):
                yaml_content = yaml.dump({"s_tier": {"characters": {"A": {"role": "hero"}}}})
                yaml_mock = mock_open(read_data=yaml_content)
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("builtins.open", yaml_mock):
                        result = extractor.extract_from_character_cards("fake.yaml", llm_client=True)
                        assert result == 3

    def test_character_cards_fallback_on_value_error(self):
        from novels_project.memory.entity_extractor import EntityExtractor
        graph = MagicMock()
        extractor = EntityExtractor(graph)

        with patch.object(extractor, "_extract_character_cards_with_llm",
                          side_effect=ValueError("bad data")):
            with patch.object(extractor, "_extract_character_cards_with_rules",
                              return_value={"entities_added": 5, "relations_added": 2, "tier_stats": {}}):
                yaml_content = yaml.dump({"s_tier": {"characters": {"A": {"role": "hero"}}}})
                yaml_mock = mock_open(read_data=yaml_content)
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("builtins.open", yaml_mock):
                        result = extractor.extract_from_character_cards("fake.yaml", llm_client=True)
                        assert result == 5

    def test_character_cards_raises_on_llm_error(self):
        from novels_project.memory.entity_extractor import EntityExtractor
        graph = MagicMock()
        extractor = EntityExtractor(graph)

        with patch.object(extractor, "_extract_character_cards_with_llm",
                          side_effect=LLMError("API Key 过期")):
            yaml_content = yaml.dump({"s_tier": {"characters": {"A": {"role": "hero"}}}})
            yaml_mock = mock_open(read_data=yaml_content)
            with patch("pathlib.Path.exists", return_value=True):
                with patch("builtins.open", yaml_mock):
                    with pytest.raises(LLMError):
                        extractor.extract_from_character_cards("fake.yaml", llm_client=True)

    def test_chapter_text_fallback_on_json_error(self):
        """llm_client.stream 抛出 JSONDecodeError 时降级为规则模式。"""
        from novels_project.memory.entity_extractor import EntityExtractor
        graph = MagicMock()
        extractor = EntityExtractor(graph)

        with patch.object(extractor, "_extract_with_rules",
                          return_value={"added_entities": 1, "added_relations": 0}):
            llm_mock = MagicMock()
            llm_mock.default_model = "test"
            # stream 抛出 JSONDecodeError（在 FALLBACK_EXCEPTIONS 中）
            llm_mock.stream.side_effect = json.JSONDecodeError("bad", "", 0)
            result = extractor._extract_with_llm("fake text", 1, llm_mock)
            assert result["added_entities"] == 1

    def test_chapter_text_raises_on_llm_error(self):
        """llm_client.stream 抛出 LLMError 时向上传播。"""
        from novels_project.memory.entity_extractor import EntityExtractor
        graph = MagicMock()
        extractor = EntityExtractor(graph)

        llm_mock = MagicMock()
        llm_mock.default_model = "test"
        # stream 抛出 LLMError（不在 FALLBACK_EXCEPTIONS 中，不可降级）
        llm_mock.stream.side_effect = LLMError("速率限制")
        with pytest.raises(LLMError):
            extractor._extract_with_llm("fake text", 1, llm_mock)

    def test_entity_extractor_imports_fallback_exceptions(self):
        from novels_project.memory.entity_extractor import FALLBACK_EXCEPTIONS as imported
        assert isinstance(imported, tuple)
        assert json.JSONDecodeError in imported

    def test_build_knowledge_graph_handles_character_cards_error(self):
        from novels_project.memory.entity_extractor import EntityExtractor
        graph = MagicMock()
        extractor = EntityExtractor(graph)

        with patch.object(extractor, "extract_from_character_cards",
                          side_effect=FileNotFoundError("no file")):
            stats = extractor.build_knowledge_graph("no.yaml")
            assert "character_cards" in stats["errors"][0]

    def test_build_knowledge_graph_handles_chapter_error(self):
        from novels_project.memory.entity_extractor import EntityExtractor
        graph = MagicMock()
        extractor = EntityExtractor(graph)

        with patch.object(extractor, "extract_from_character_cards", return_value=5):
            with patch.object(extractor, "extract_from_chapter_text",
                              side_effect=[{"added_entities": 1, "added_relations": 0},
                                           RuntimeError("chapter 2 fail")]):
                stats = extractor.build_knowledge_graph(
                    "cards.yaml", chapter_texts={1: "ch1", 2: "ch2"},
                )
                assert stats["chapters_processed"] == 1
                assert len(stats["errors"]) == 1

    def test_entity_extractor_init_logs_stats(self):
        from novels_project.memory.entity_extractor import EntityExtractor
        graph = MagicMock()
        graph.entity_count.return_value = 10
        extractor = EntityExtractor(graph)
        assert extractor._stats["entities_added"] == 0

    def test_get_stats_returns_dict(self):
        from novels_project.memory.entity_extractor import EntityExtractor
        graph = MagicMock()
        extractor = EntityExtractor(graph)
        stats = extractor.get_stats()
        assert isinstance(stats, dict)
        assert "entities_added" in stats
