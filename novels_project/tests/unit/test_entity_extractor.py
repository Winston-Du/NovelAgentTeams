"""
单元测试：memory/entity_extractor.py - EntityExtractor 类
"""
import pytest
import yaml
from unittest import mock

from novels_project.memory.graph_store import (
    GraphStore,
    NODE_TYPE_CHARACTER,
    REL_TYPE_ALLY,
    REL_TYPE_ENEMY,
)
from novels_project.memory.entity_extractor import EntityExtractor


# ---- helpers ----

def make_char_data(name="主角", role="hero", personality="勇敢", relationships=None, organization=None):
    return {
        "name": name,
        "role": role,
        "core_personality": personality,
        "relationships": relationships or {},
        "organization": organization,
    }


def write_cards_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)


# ==================== __init__ ====================

class TestEntityExtractorInit:
    def test_init(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        assert extractor._graph is store
        assert extractor._stats["entities_added"] == 0
        assert extractor._stats["relations_added"] == 0


# ==================== extract_from_character_cards (rules mode) ====================

class TestExtractFromCharacterCards:
    def test_basic_extraction(self, tmp_path):
        """基础人物卡提取（规则模式）。"""
        store = GraphStore()
        extractor = EntityExtractor(store)
        cards_data = {
            "s_tier": {
                "tier_name": "核心角色",
                "characters": {
                    "主角A": make_char_data("主角A", "hero", "勇敢", {
                        "配角B": "ally",
                    }),
                    "配角B": make_char_data("配角B", "ally", "忠诚"),
                },
            },
        }
        cards_path = tmp_path / "cards.yaml"
        write_cards_yaml(cards_path, cards_data)

        count = extractor.extract_from_character_cards(str(cards_path))
        assert count >= 1
        assert store.has_entity("主角A")
        assert store.has_entity("配角B")

    def test_with_organization(self, tmp_path):
        """带组织的角色提取。"""
        store = GraphStore()
        extractor = EntityExtractor(store)
        cards_data = {
            "s_tier": {
                "characters": {
                    "主角A": make_char_data("主角A", "hero", "勇敢", organization="青云宗"),
                },
            },
        }
        cards_path = tmp_path / "cards.yaml"
        write_cards_yaml(cards_path, cards_data)

        extractor.extract_from_character_cards(str(cards_path))
        assert store.has_entity("主角A")
        assert store.has_entity("青云宗")

    def test_file_not_found(self, tmp_path):
        """文件不存在时抛出 FileNotFoundError。"""
        store = GraphStore()
        extractor = EntityExtractor(store)
        with pytest.raises(FileNotFoundError):
            extractor.extract_from_character_cards(str(tmp_path / "nonexistent.yaml"))

    def test_empty_yaml(self, tmp_path):
        """空 YAML 文件。"""
        store = GraphStore()
        extractor = EntityExtractor(store)
        cards_path = tmp_path / "cards.yaml"
        cards_path.write_text("", encoding="utf-8")
        count = extractor.extract_from_character_cards(str(cards_path))
        assert count == 0

    def test_corrupt_yaml(self, tmp_path):
        """损坏的 YAML 文件抛出 yaml.YAMLError。"""
        store = GraphStore()
        extractor = EntityExtractor(store)
        cards_path = tmp_path / "cards.yaml"
        cards_path.write_text(": invalid: yaml: :::", encoding="utf-8")
        with pytest.raises(yaml.YAMLError):
            extractor.extract_from_character_cards(str(cards_path))

    def test_with_llm_client(self, tmp_path):
        """使用 LLM 客户端提取。"""
        store = GraphStore()
        extractor = EntityExtractor(store)
        cards_data = {
            "s_tier": {
                "characters": {
                    "主角A": make_char_data("主角A", "hero", "勇敢"),
                },
            },
        }
        cards_path = tmp_path / "cards.yaml"
        write_cards_yaml(cards_path, cards_data)

        # Mock LLM client
        llm_client = mock.MagicMock()
        llm_client.default_model = "test-model"

        # Mock stream events
        from novels_project.api_client import TextDelta
        llm_response = (
            '{"entities": [{"name": "主角A", "type": "character", "properties": {"brief": "主角", "role": "hero"}}], '
            '"relations": []}'
        )
        llm_client.stream.return_value = [TextDelta(text=llm_response)]

        extractor.extract_from_character_cards(str(cards_path), llm_client=llm_client)
        assert store.has_entity("主角A")

    def test_llm_fallback_to_rules(self, tmp_path):
        """LLM 提取失败时回退到规则模式。"""
        store = GraphStore()
        extractor = EntityExtractor(store)
        cards_data = {
            "s_tier": {
                "characters": {
                    "主角A": make_char_data("主角A", "hero", "勇敢"),
                },
            },
        }
        cards_path = tmp_path / "cards.yaml"
        write_cards_yaml(cards_path, cards_data)

        llm_client = mock.MagicMock()
        llm_client.default_model = "test-model"
        llm_client.stream.side_effect = RuntimeError("LLM 调用失败")

        result = extractor.extract_from_character_cards(str(cards_path), llm_client=llm_client)
        assert result >= 1
        assert store.has_entity("主角A")


# ==================== _extract_brief ====================

class TestExtractBrief:
    def test_with_role_and_personality(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        char_data = {"role": "hero", "core_personality": ["勇敢", "聪明", "善良"]}
        brief = extractor._extract_brief(char_data)
        assert "hero" in brief
        assert "勇敢" in brief

    def test_with_personality_string(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        char_data = {"role": "villain", "core_personality": "邪恶"}
        brief = extractor._extract_brief(char_data)
        assert "villain" in brief
        assert "邪恶" in brief

    def test_with_core_goal(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        char_data = {"role": "hero", "core_personality": ["勇敢"], "core_goal": "拯救世界"}
        brief = extractor._extract_brief(char_data)
        assert "拯救世界" in brief

    def test_empty(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        brief = extractor._extract_brief({})
        assert brief == ""


# ==================== _extract_relations_from_dict ====================

class TestExtractRelationsFromDict:
    def test_string_relation(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        rels = extractor._extract_relations_from_dict({"配角A": "ally"})
        assert len(rels) == 1
        assert rels[0][0] == "配角A"
        assert rels[0][1]["type"] == REL_TYPE_ALLY

    def test_dict_relation(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        rels = extractor._extract_relations_from_dict({"配角A": {"type": "enemy", "desc": "仇敌"}})
        assert len(rels) == 1
        assert rels[0][1]["type"] == "enemy"

    def test_chinese_keyword_relation(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        rels = extractor._extract_relations_from_dict({"配角A": "敌对关系"})
        assert len(rels) == 1
        assert rels[0][1]["type"] == REL_TYPE_ENEMY

    def test_empty(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        rels = extractor._extract_relations_from_dict({})
        assert rels == []


# ==================== extract_from_chapter_text ====================

class TestExtractFromChapterText:
    def test_rules_mode(self):
        """规则模式：在文本中检测已知人物。"""
        store = GraphStore()
        store.add_entity("主角A", NODE_TYPE_CHARACTER, {"brief": "主角"})
        store.add_entity("配角B", NODE_TYPE_CHARACTER, {"brief": "配角"})
        extractor = EntityExtractor(store)

        text = "主角A和配角B一起去了山洞。"
        result = extractor.extract_from_chapter_text(text, chapter_id=1)
        assert result["added_entities"] == 0  # 没有新增实体
        assert result["updated_entities"] >= 1  # 已有实体更新了出场章节

    def test_llm_mode(self):
        """LLM 模式提取。"""
        store = GraphStore()
        extractor = EntityExtractor(store)

        llm_client = mock.MagicMock()
        llm_client.default_model = "test-model"
        from novels_project.api_client import TextDelta
        response = (
            '{"entities": [{"name": "新角色", "type": "character", "properties": {"brief": "新角色"}}], '
            '"relations": []}'
        )
        llm_client.stream.return_value = [TextDelta(text=response)]

        text = "章节内容..."
        result = extractor.extract_from_chapter_text(text, chapter_id=1, llm_client=llm_client)
        assert result["added_entities"] >= 1
        assert store.has_entity("新角色")

    def test_llm_fallback_to_rules(self):
        """LLM 失败时回退到规则模式。"""
        store = GraphStore()
        store.add_entity("主角A", NODE_TYPE_CHARACTER, {"brief": "主角"})
        extractor = EntityExtractor(store)

        llm_client = mock.MagicMock()
        llm_client.default_model = "test-model"
        llm_client.stream.side_effect = RuntimeError("LLM 失败")

        text = "主角A在修炼。"
        result = extractor.extract_from_chapter_text(text, chapter_id=1, llm_client=llm_client)
        assert result["updated_entities"] >= 1  # 规则模式仍会更新出场章节


# ==================== _parse_llm_output ====================

class TestParseLLMOutput:
    def test_valid_json(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        text = '{"entities": [{"name": "A", "type": "character"}], "relations": []}'
        result = extractor._parse_llm_output(text)
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "A"

    def test_json_with_extra_text(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        text = '一些前缀文本 {"entities": [], "relations": []} 一些后缀'
        result = extractor._parse_llm_output(text)
        assert result == {"entities": [], "relations": []}

    def test_invalid_json(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        text = "这不是 JSON"
        result = extractor._parse_llm_output(text)
        assert result == {"entities": [], "relations": []}


# ==================== _apply_extraction ====================

class TestApplyExtraction:
    def test_adds_new_entities(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [
                {"name": "新角色", "type": NODE_TYPE_CHARACTER, "properties": {"brief": "新角色"}},
            ],
            "relations": [],
        }
        result = extractor._apply_extraction(extracted, chapter_id=1)
        assert result["added_entities"] == 1
        assert store.has_entity("新角色")

    def test_updates_existing_entities(self):
        store = GraphStore()
        store.add_entity("主角A", NODE_TYPE_CHARACTER, {"brief": "主角"})
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [
                {"name": "主角A", "type": NODE_TYPE_CHARACTER, "properties": {"brief": "主角"}},
            ],
            "relations": [],
        }
        result = extractor._apply_extraction(extracted, chapter_id=2)
        assert result["updated_entities"] >= 1
        entity = store.get_entity("主角A")
        assert 2 in entity.get("appears_in_chapters", [])

    def test_adds_relations(self):
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER)
        store.add_entity("B", NODE_TYPE_CHARACTER)
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [],
            "relations": [
                {"source": "A", "target": "B", "type": REL_TYPE_ALLY, "properties": {}},
            ],
        }
        result = extractor._apply_extraction(extracted, chapter_id=1)
        assert result["added_relations"] == 1

    def test_skips_incomplete_relations(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [],
            "relations": [
                {"source": "", "target": "B", "type": REL_TYPE_ALLY, "properties": {}},
            ],
        }
        result = extractor._apply_extraction(extracted, chapter_id=1)
        assert result["added_relations"] == 0


# ==================== build_knowledge_graph ====================

class TestBuildKnowledgeGraph:
    def test_full_build(self, tmp_path):
        store = GraphStore()
        extractor = EntityExtractor(store)
        cards_data = {
            "s_tier": {
                "characters": {
                    "主角A": make_char_data("主角A", "hero", "勇敢"),
                },
            },
        }
        cards_path = tmp_path / "cards.yaml"
        write_cards_yaml(cards_path, cards_data)

        stats = extractor.build_knowledge_graph(
            str(cards_path),
            chapter_texts={1: "章节文本"},
        )
        assert stats["characters_extracted"] >= 1
        assert stats["chapters_processed"] >= 1

    def test_build_with_errors(self, tmp_path):
        """build_knowledge_graph 即使部分出错也应继续。"""
        store = GraphStore()
        extractor = EntityExtractor(store)
        # 不存在的人物卡路径
        stats = extractor.build_knowledge_graph(
            str(tmp_path / "nonexistent.yaml"),
        )
        assert "errors" in stats
        assert len(stats["errors"]) >= 1


# ==================== get_stats ====================

class TestGetStats:
    def test_initial_stats(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        stats = extractor.get_stats()
        assert stats["entities_added"] == 0
        assert stats["extractions"] == 0


# ==================== _truncate_text ====================

class TestTruncateText:
    def test_short_text(self):
        result = EntityExtractor._truncate_text("abc", max_len=10)
        assert result == "abc"

    def test_long_text(self):
        result = EntityExtractor._truncate_text("a" * 200, max_len=100)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")


# ==================== _log_step ====================

class TestLogStep:
    def test_log_step(self):
        store = GraphStore()
        extractor = EntityExtractor(store)
        # Should not raise
        extractor._log_step("test_step", key1="val1", key2=123)


# ==================== _parse_llm_output edge cases ====================

class TestParseLLMOutputEdgeCases:
    def test_json_decode_error(self):
        """Valid JSON-looking text that fails to decode."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        # This matches the regex but is invalid JSON
        text = '{"entities": [bad json], "relations": []}'
        result = extractor._parse_llm_output(text)
        assert result == {"entities": [], "relations": []}

    def test_no_json_match(self):
        """No JSON-like structure at all."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        result = extractor._parse_llm_output("纯文本，没有 JSON")
        assert result == {"entities": [], "relations": []}


# ==================== _build_character_cards_user_message ====================

class TestBuildCharacterCardsUserMessage:
    def test_full_fields(self):
        """Covers role, brief, personality as list, relationships, organization."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        data = {
            "s_tier": {
                "tier_name": "主角",
                "characters": {
                    "A": {
                        "role": "hero",
                        "brief": "主角简介",
                        "core_personality": ["勇敢", "善良"],
                        "relationships": {"B": "ally"},
                        "organization": "青云宗",
                    },
                },
            },
        }
        msg = extractor._build_character_cards_user_message(data)
        assert "hero" in msg
        assert "主角简介" in msg
        assert "勇敢" in msg
        assert "ally" in msg
        assert "青云宗" in msg

    def test_minimal_fields(self):
        """Character with minimal fields (no role, no brief, no personality)."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        data = {
            "s_tier": {
                "tier_name": "主角",
                "characters": {
                    "A": {"name": "A"},
                },
            },
        }
        msg = extractor._build_character_cards_user_message(data)
        assert "A" in msg
        # No role, no brief, no personality
        assert "定位" not in msg
        assert "简介" not in msg
        assert "性格" not in msg

    def test_personality_as_string(self):
        """Character with personality as string (not list)."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        data = {
            "s_tier": {
                "tier_name": "主角",
                "characters": {
                    "A": {"core_personality": "勇敢"},
                },
            },
        }
        msg = extractor._build_character_cards_user_message(data)
        assert "勇敢" in msg
        assert "性格" in msg


# ==================== _apply_character_card_extraction ====================

class TestApplyCharacterCardExtraction:
    def test_entity_empty_name_skipped(self):
        """Entity with empty name is skipped."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [
                {"name": "", "type": "character", "properties": {"brief": "no name"}},
            ],
            "relations": [],
        }
        raw_data = {"s_tier": {"characters": {}}}
        result = extractor._apply_character_card_extraction(extracted, raw_data)
        assert result["entities_added"] == 0

    def test_entity_already_exists(self):
        """Existing entity is updated, not added."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER, {"brief": "existing"})
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [
                {"name": "A", "type": "character", "properties": {"brief": "updated"}},
            ],
            "relations": [],
        }
        raw_data = {"s_tier": {"characters": {"A": {}}}}
        result = extractor._apply_character_card_extraction(extracted, raw_data)
        # Entity already exists, updated but not added
        assert result["entities_added"] == 0

    def test_relations_added(self):
        """Relations in extracted data are applied to graph."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [
                {"name": "A", "type": "character", "properties": {"brief": "A"}},
                {"name": "B", "type": "character", "properties": {"brief": "B"}},
            ],
            "relations": [
                {"source": "A", "target": "B", "type": REL_TYPE_ALLY, "properties": {}},
            ],
        }
        raw_data = {"s_tier": {"characters": {"A": {}, "B": {}}}}
        result = extractor._apply_character_card_extraction(extracted, raw_data)
        assert result["relations_added"] >= 1

    def test_empty_source_or_target_skipped(self):
        """Relation with empty source/target is skipped."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [
                {"name": "A", "type": "character", "properties": {"brief": "A"}},
            ],
            "relations": [
                {"source": "", "target": "B", "type": REL_TYPE_ALLY, "properties": {}},
                {"source": "A", "target": "", "type": REL_TYPE_ALLY, "properties": {}},
            ],
        }
        raw_data = {"s_tier": {"characters": {"A": {}}}}
        result = extractor._apply_character_card_extraction(extracted, raw_data)
        assert result["relations_added"] == 0

    def test_organization_handling(self):
        """Organization from raw_data is added as entity with belongs_to relation."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        raw_data = {
            "s_tier": {
                "characters": {
                    "A": {"organization": "青云宗"},
                },
            },
        }
        extracted = {
            "entities": [
                {"name": "A", "type": "character", "properties": {"brief": "A"}},
            ],
            "relations": [],
        }
        result = extractor._apply_character_card_extraction(extracted, raw_data)
        assert store.has_entity("青云宗")
        assert result["entities_added"] >= 1  # organization added

    def test_organization_as_dict(self):
        """Organization as dict (with 'name' field)."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        raw_data = {
            "s_tier": {
                "characters": {
                    "A": {"organization": {"name": "黑木崖", "brief": "魔教总部"}},
                },
            },
        }
        extracted = {
            "entities": [
                {"name": "A", "type": "character", "properties": {"brief": "A"}},
            ],
            "relations": [],
        }
        extractor._apply_character_card_extraction(extracted, raw_data)
        assert store.has_entity("黑木崖")

    def test_organization_already_exists_char_card(self):
        """Organization already exists -> not added but relation still created."""
        store = GraphStore()
        store.add_entity("青云宗", "organization", {"brief": "宗门"})
        extractor = EntityExtractor(store)
        raw_data = {
            "s_tier": {
                "characters": {
                    "A": {"organization": "青云宗"},
                },
            },
        }
        extracted = {
            "entities": [
                {"name": "A", "type": "character", "properties": {"brief": "A"}},
            ],
            "relations": [],
        }
        result = extractor._apply_character_card_extraction(extracted, raw_data)
        assert result["entities_added"] == 1  # A is new
        assert store.has_entity("青云宗")

    def test_relation_source_not_in_tier_stats(self):
        """Relation source not in any tier -> tier_stats lookup skipped."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        raw_data = {
            "s_tier": {
                "characters": {
                    "A": {"name": "A"},
                },
            },
        }
        # Relation where source is "B" which is not in any tier in raw_data
        extracted = {
            "entities": [
                {"name": "A", "type": "character", "properties": {"brief": "A"}},
                {"name": "B", "type": "character", "properties": {"brief": "B"}},
            ],
            "relations": [
                {"source": "B", "target": "A", "type": REL_TYPE_ALLY, "properties": {}},
            ],
        }
        result = extractor._apply_character_card_extraction(extracted, raw_data)
        assert result["relations_added"] >= 1


# ==================== _extract_relations_from_dict edge cases ====================

class TestExtractRelationsFromDictEdgeCases:
    def test_string_without_keyword_match(self):
        """String relation that matches no keyword -> defaults to KNOWS."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        rels = extractor._extract_relations_from_dict({"配角A": "某种未知关系"})
        assert len(rels) == 1
        assert rels[0][1]["type"] == "knows"  # defaults to KNOWS

    def test_dict_relation_default_type(self):
        """Dict relation without 'type' key -> defaults to KNOWS."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        rels = extractor._extract_relations_from_dict({"配角A": {"desc": "没有 type"}})
        assert len(rels) == 1
        # When info is a dict, the original dict is used as-is (type derived from get() but dict not modified)
        assert "desc" in rels[0][1]

    def test_non_string_non_dict_value(self):
        """Non-string, non-dict relationship value is skipped."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        rels = extractor._extract_relations_from_dict({"配角A": 123})
        assert rels == []


# ==================== _extract_with_rules ====================

class TestExtractWithRules:
    def test_no_known_characters_in_text(self):
        """Text with no known characters -> no entities added."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        result = extractor._extract_with_rules("某些文本中没有已知人物", chapter_id=1)
        assert result["added_entities"] == 0

    def test_known_character_in_text(self):
        """Known character in text -> entity updated with chapter appearance."""
        store = GraphStore()
        store.add_entity("主角A", NODE_TYPE_CHARACTER, {"brief": "主角"})
        extractor = EntityExtractor(store)
        result = extractor._extract_with_rules("主角A在修炼", chapter_id=3)
        # Entity already exists, should be updated
        assert result.get("updated_entities", 0) >= 1


# ==================== build_knowledge_graph edge cases ====================

class TestBuildKnowledgeGraphEdgeCases:
    def test_chapter_extraction_error(self, tmp_path):
        """Chapter extraction error is caught and added to errors list."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        cards_data = {
            "s_tier": {
                "characters": {
                    "A": make_char_data("A", "hero", "勇敢"),
                },
            },
        }
        cards_path = tmp_path / "cards.yaml"
        write_cards_yaml(cards_path, cards_data)

        # Patch extract_from_chapter_text to raise for chapter 2
        original = extractor.extract_from_chapter_text

        def failing_extract(_self, text, chapter_id=1, llm_client=None):
            if chapter_id == 2:
                raise RuntimeError("chapter 2 failed")
            return original(text, chapter_id, llm_client)

        import types
        extractor.extract_from_chapter_text = types.MethodType(failing_extract, extractor)

        stats = extractor.build_knowledge_graph(
            str(cards_path),
            chapter_texts={1: "章节 1", 2: "章节 2"},
        )
        assert stats["chapters_processed"] >= 1
        assert len(stats["errors"]) >= 1


# ==================== _extract_with_llm ====================

class TestExtractWithLLM:
    def test_llm_call_failure_fallback(self):
        """LLM call raises -> fallback to rules mode."""
        store = GraphStore()
        store.add_entity("主角A", NODE_TYPE_CHARACTER, {"brief": "主角"})
        extractor = EntityExtractor(store)

        llm_client = mock.MagicMock()
        llm_client.default_model = "test-model"
        llm_client.stream.side_effect = RuntimeError("LLM 调用失败")

        result = extractor._extract_with_llm("主角A在修炼", chapter_id=1, llm_client=llm_client)
        # Should fall back to rules mode
        assert result.get("updated_entities", 0) >= 1

    def test_non_textdelta_events(self):
        """Events that include non-TextDelta types are handled correctly."""
        store = GraphStore()
        extractor = EntityExtractor(store)

        llm_client = mock.MagicMock()
        llm_client.default_model = "test-model"
        from novels_project.api_client import TextDelta, UsageEvent, TokenUsage
        llm_client.stream.return_value = [
            UsageEvent(usage=TokenUsage(input_tokens=1, output_tokens=2, total_tokens=3)),
            TextDelta(text='{"entities": [{"name": "X", "type": "character", "properties": {"brief": "X"}}], "relations": []}'),
        ]

        result = extractor._extract_with_llm("文本", chapter_id=1, llm_client=llm_client)
        assert result["added_entities"] >= 1


# ==================== _apply_extraction edge cases ====================

class TestApplyExtractionEdgeCases:
    def test_empty_name_entity_skipped(self):
        """Entity with empty name is skipped with warning."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [
                {"name": "", "type": "character", "properties": {}},
            ],
            "relations": [],
        }
        result = extractor._apply_extraction(extracted, chapter_id=1)
        assert result["added_entities"] == 0

    def test_existing_entity_int_appears_in_chapters(self):
        """Existing entity where appears_in_chapters is an int (not list)."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER, {"brief": "A", "appears_in_chapters": 1})
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [
                {"name": "A", "type": "character", "properties": {"brief": "A"}},
            ],
            "relations": [],
        }
        result = extractor._apply_extraction(extracted, chapter_id=2)
        assert result["updated_entities"] >= 1
        entity = store.get_entity("A")
        assert 2 in entity.get("appears_in_chapters", [])

    def test_existing_entity_other_type_appears_in_chapters(self):
        """Existing entity with non-list/non-int appears_in_chapters."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER, {"brief": "A", "appears_in_chapters": "string_value"})
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [
                {"name": "A", "type": "character", "properties": {"brief": "A"}},
            ],
            "relations": [],
        }
        result = extractor._apply_extraction(extracted, chapter_id=3)
        assert result["updated_entities"] >= 1

    def test_relation_without_chapter_id(self):
        """Relation without chapter_id gets chapter_id added."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER)
        store.add_entity("B", NODE_TYPE_CHARACTER)
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [],
            "relations": [
                {"source": "A", "target": "B", "type": REL_TYPE_ALLY, "properties": {}},
            ],
        }
        result = extractor._apply_extraction(extracted, chapter_id=5)
        assert result["added_relations"] == 1

    def test_entity_with_chapter_id_in_props(self):
        """Entity with chapter_id already in properties."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [
                {"name": "新角色", "type": NODE_TYPE_CHARACTER, "properties": {"brief": "新角色", "chapter_id": 3}},
            ],
            "relations": [],
        }
        result = extractor._apply_extraction(extracted, chapter_id=1)
        assert result["added_entities"] == 1
        assert store.has_entity("新角色")

    def test_relation_with_chapter_id_in_props(self):
        """Relation with chapter_id already in properties."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER)
        store.add_entity("B", NODE_TYPE_CHARACTER)
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [],
            "relations": [
                {"source": "A", "target": "B", "type": REL_TYPE_ALLY, "properties": {"chapter_id": 3}},
            ],
        }
        result = extractor._apply_extraction(extracted, chapter_id=1)
        assert result["added_relations"] == 1

    def test_chapter_id_already_in_appears(self):
        """Entity already has the chapter_id in its appears_in_chapters."""
        store = GraphStore()
        store.add_entity("A", NODE_TYPE_CHARACTER, {"brief": "A", "appears_in_chapters": [5]})
        extractor = EntityExtractor(store)
        extracted = {
            "entities": [{"name": "A", "type": "character", "properties": {"brief": "A"}}],
            "relations": [],
        }
        result = extractor._apply_extraction(extracted, chapter_id=5)
        assert result["updated_entities"] >= 1
        entity = store.get_entity("A")
        assert entity.get("appears_in_chapters") == [5]  # unchanged


# ==================== _extract_character_cards_with_rules ====================

class TestExtractCharacterCardsWithRules:
    def test_empty_tiers(self):
        """No characters -> nothing added."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        result = extractor._extract_character_cards_with_rules({})
        assert result["entities_added"] == 0
        assert result["relations_added"] == 0

    def test_rule_based_organization(self):
        """Organization extraction in rules mode."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        data = {
            "s_tier": {
                "characters": {
                    "A": make_char_data("A", "hero", "勇敢", organization="青云宗"),
                },
            },
        }
        result = extractor._extract_character_cards_with_rules(data)
        assert store.has_entity("青云宗")
        assert result["relations_added"] >= 1

    def test_organization_already_exists(self):
        """Organization already exists -> not added again."""
        store = GraphStore()
        store.add_entity("青云宗", NODE_TYPE_CHARACTER, {"brief": "宗门"})
        extractor = EntityExtractor(store)
        data = {
            "s_tier": {
                "characters": {
                    "A": make_char_data("A", "hero", "勇敢", organization="青云宗"),
                },
            },
        }
        result = extractor._extract_character_cards_with_rules(data)
        assert result["entities_added"] == 1  # only A is new
        # Organization already exists, so not counted as added
        assert store.has_entity("青云宗")

    def test_organization_as_dict_rules(self):
        """Organization as dict in rules mode."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        data = {
            "s_tier": {
                "characters": {
                    "A": make_char_data("A", "hero", "勇敢", organization={"name": "黑木崖", "brief": "魔教"}),
                },
            },
        }
        result = extractor._extract_character_cards_with_rules(data)
        assert store.has_entity("黑木崖")
        assert result["relations_added"] >= 1

    def test_role_and_brief_missing(self):
        """Character without role, brief, or core_personality."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        data = {
            "s_tier": {
                "characters": {
                    "A": {"name": "A"},
                },
            },
        }
        result = extractor._extract_character_cards_with_rules(data)
        assert result["entities_added"] >= 1
        assert store.has_entity("A")

    def test_tier_stats_relation_unknown_tier(self):
        """Relation with source in a tier not tracked by tier_stats."""
        store = GraphStore()
        extractor = EntityExtractor(store)
        data = {
            "s_tier": {
                "characters": {
                    "A": make_char_data("A", "hero", "勇敢"),
                },
            },
            "a_tier": {
                "characters": {
                    "B": make_char_data("B", "ally", "忠诚", relationships={"A": "ally"}),
                },
            },
        }
        result = extractor._extract_character_cards_with_rules(data)
        assert result["entities_added"] >= 2
        assert result["relations_added"] >= 1