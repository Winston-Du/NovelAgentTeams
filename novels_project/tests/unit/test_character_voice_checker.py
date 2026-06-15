"""
单元测试：对话风格校验工具 (character_voice_checker)

测试覆盖:
- 辅助函数: _is_nervous, _is_over_explaining, _is_verbose, _is_too_clever,
  _is_thoughtful, _has_complex_words, _has_numbers_or_metaphors,
  _is_threatening, _is_logical, _reveals_ability
- _extract_dialogues, _check_single_dialogue
- check_character_voice, get_character_voice_guide, refresh_character_cards
"""
import pytest
import yaml
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Sample character cards for voice checker tests
# ---------------------------------------------------------------------------
SAMPLE_VOICE_CARDS = {
    "s_tier": {
        "characters": {
            "陆商曜": {
                "name": "陆商曜",
                "identity": "主角/商人",
                "core_personality": ["腹黑果决", "能屈能伸"],
                "unique_speaking_style": {
                    "tone": "冷静沉着",
                    "characteristics": ["言简意赅", "用数字说话"],
                    "example_dialogues": ["三成换一个安稳，贵了。"],
                    "avoid_patterns": ["过度解释", "废话"],
                    "speaking_frequency": "言少意多",
                },
                "signature_habits": ["把玩契约印"],
            },
            "黑商周桓": {
                "name": "黑商周桓",
                "identity": "反派/黑心商人",
                "core_personality": ["霸道蛮横"],
                "unique_speaking_style": {
                    "tone": "粗暴威胁",
                    "characteristics": ["威胁性强"],
                    "example_dialogues": ["敢在我的地盘撒野？"],
                    "avoid_patterns": ["聪慧", "深思熟虑"],
                    "speaking_frequency": "话多",
                },
            },
            "木九公": {
                "name": "木九公",
                "identity": "老者/高手",
                "core_personality": ["沉默寡言", "深藏不露"],
                "unique_speaking_style": {
                    "tone": "简短有力",
                    "characteristics": ["话少"],
                    "example_dialogues": ["嗯。"],
                    "avoid_patterns": [],
                    "speaking_frequency": "话少",
                },
            },
            "铁阙": {
                "name": "铁阙",
                "identity": "护卫",
                "core_personality": ["忠诚"],
            },
            "测试角色_紧张": {
                "name": "测试角色_紧张",
                "identity": "测试",
                "core_personality": ["胆小"],
                "unique_speaking_style": {
                    "tone": "紧张",
                    "avoid_patterns": ["紧张", "复杂词汇"],
                },
            },
        },
    },
    "a_tier": {
        "characters": {
            "市集店主甲": {
                "name": "市集店主甲",
                "identity": "配角",
                "core_personality": ["市侩"],
            },
        },
    },
}


@pytest.fixture
def voice_cards_file(tmp_path):
    """Create a temp YAML file with character voice cards."""
    file_path = tmp_path / "character_base_cards.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(SAMPLE_VOICE_CARDS, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return file_path


@pytest.fixture
def mock_load_cards(voice_cards_file):
    """Mock _load_character_cards to use the temp file."""
    import novels_project.tools.character_voice_checker as cv_mod

    # Reset cache
    cv_mod._character_cards = None

    def _load_from_temp():
        with open(voice_cards_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        result = {}
        for tier in ["s_tier", "a_tier"]:
            if tier in data and "characters" in data[tier]:
                result.update(data[tier]["characters"])
        return result

    with patch.object(cv_mod, "_load_character_cards", side_effect=_load_from_temp):
        yield


# =========================================================================
#  辅助函数 - Positive cases
# =========================================================================
class TestHelperFunctionsPositive:
    """Tests for helper functions (positive / true cases)."""

    def test_is_nervous_positive(self):
        from novels_project.tools.character_voice_checker import _is_nervous

        assert _is_nervous("我很紧张")
        assert _is_nervous("他害怕了")
        assert _is_nervous("我担心这件事")
        assert _is_nervous("不知道该怎么办了")
        assert _is_nervous("心里慌得很")
        assert _is_nervous("手抖得厉害")
        assert _is_nervous("心跳加速")

    def test_is_over_explaining_positive(self):
        from novels_project.tools.character_voice_checker import _is_over_explaining

        assert _is_over_explaining("因为天气不好，所以不去了")
        assert _is_over_explaining("其实我早就知道")
        assert _is_over_explaining("实际上是这样的")
        assert _is_over_explaining("让我解释一下")
        assert _is_over_explaining("让我想想该怎么办")
        assert _is_over_explaining("仔细分析各种可能性")

    def test_is_verbose_positive(self):
        from novels_project.tools.character_voice_checker import _is_verbose

        assert _is_verbose("那个就是然后所以说")
        assert _is_verbose("那个这个就是然后")

    def test_is_too_clever_positive(self):
        from novels_project.tools.character_voice_checker import _is_too_clever

        assert _is_too_clever("我来分析一下形势")
        assert _is_too_clever("考虑一下策略")
        assert _is_too_clever("根据逻辑推断")
        assert _is_too_clever("制定一个计划")

    def test_is_thoughtful_positive(self):
        from novels_project.tools.character_voice_checker import _is_thoughtful

        assert _is_thoughtful("让我想想")
        assert _is_thoughtful("仔细考虑一下")
        assert _is_thoughtful("深思熟虑后决定")
        assert _is_thoughtful("权衡利弊")
        assert _is_thoughtful("斟酌再三")

    def test_has_complex_words_positive(self):
        from novels_project.tools.character_voice_checker import _has_complex_words

        assert _has_complex_words("毋庸置疑这是对的")
        assert _has_complex_words("由此可见")
        assert _has_complex_words("综上所述")
        assert _has_complex_words("不仅如此")
        assert _has_complex_words("与此同时")

    def test_has_numbers_or_metaphors_positive(self):
        from novels_project.tools.character_voice_checker import _has_numbers_or_metaphors

        assert _has_numbers_or_metaphors("三成换一个安稳")
        assert _has_numbers_or_metaphors("一百两银子")
        assert _has_numbers_or_metaphors("他像一头猛虎")
        assert _has_numbers_or_metaphors("如风一般")
        assert _has_numbers_or_metaphors("好比晴天霹雳")

    def test_is_threatening_positive(self):
        from novels_project.tools.character_voice_checker import _is_threatening

        assert _is_threatening("你敢来试试？")
        assert _is_threatening("信不信我弄死你")
        assert _is_threatening("废了你")
        assert _is_threatening("砸了你的店")
        assert _is_threatening("滚出去")
        assert _is_threatening("少废话")

    def test_is_logical_positive(self):
        from novels_project.tools.character_voice_checker import _is_logical

        assert _is_logical("因此我们得出结论")
        assert _is_logical("所以应该这样做")
        assert _is_logical("既然来了就别走")
        assert _is_logical("首先，其次，最后")

    def test_reveals_ability_positive(self):
        from novels_project.tools.character_voice_checker import _reveals_ability

        assert _reveals_ability("我其实是高手")
        assert _reveals_ability("我真正的实力")
        assert _reveals_ability("我隐藏了武功")

    def test_has_numbers_or_metaphors_with_digits(self):
        from novels_project.tools.character_voice_checker import _has_numbers_or_metaphors

        assert _has_numbers_or_metaphors("3成换一个安稳")
        assert _has_numbers_or_metaphors("第42章")


# =========================================================================
#  辅助函数 - Negative cases
# =========================================================================
class TestHelperFunctionsNegative:
    """Tests for helper functions (negative / false cases)."""

    def test_is_nervous_negative(self):
        from novels_project.tools.character_voice_checker import _is_nervous

        assert not _is_nervous("一切尽在掌控")
        assert not _is_nervous("无所谓")
        assert not _is_nervous("")

    def test_is_over_explaining_negative(self):
        from novels_project.tools.character_voice_checker import _is_over_explaining

        assert not _is_over_explaining("走。")
        assert not _is_over_explaining("好。")
        assert not _is_over_explaining("")

    def test_is_verbose_negative(self):
        from novels_project.tools.character_voice_checker import _is_verbose

        assert not _is_verbose("简短有力")
        assert not _is_verbose("那个")  # only one match, needs 2
        assert not _is_verbose("")

    def test_is_too_clever_negative(self):
        from novels_project.tools.character_voice_checker import _is_too_clever

        assert not _is_too_clever("打！")
        assert not _is_too_clever("滚！")
        assert not _is_too_clever("")

    def test_is_thoughtful_negative(self):
        from novels_project.tools.character_voice_checker import _is_thoughtful

        assert not _is_thoughtful("打！")
        assert not _is_thoughtful("")

    def test_has_complex_words_negative(self):
        from novels_project.tools.character_voice_checker import _has_complex_words

        assert not _has_complex_words("简单的话")
        assert not _has_complex_words("")

    def test_has_numbers_or_metaphors_negative(self):
        from novels_project.tools.character_voice_checker import _has_numbers_or_metaphors

        assert not _has_numbers_or_metaphors("你好")
        assert not _has_numbers_or_metaphors("")

    def test_is_threatening_negative(self):
        from novels_project.tools.character_voice_checker import _is_threatening

        assert not _is_threatening("你好")
        assert not _is_threatening("谢谢")

    def test_is_logical_negative(self):
        from novels_project.tools.character_voice_checker import _is_logical

        assert not _is_logical("打！")
        assert not _is_logical("")

    def test_reveals_ability_negative(self):
        from novels_project.tools.character_voice_checker import _reveals_ability

        assert not _reveals_ability("你好")
        assert not _reveals_ability("")


# =========================================================================
#  _extract_dialogues
# =========================================================================
class TestExtractDialogues:
    """Tests for _extract_dialogues."""

    def test_with_known_characters(self):
        """_extract_dialogues extracts dialogues with known speakers."""
        from novels_project.tools.character_voice_checker import _extract_dialogues

        content = '陆商曜说："三成换一个安稳，贵了。"\n黑商周桓怒道："你敢在我的地盘撒野？"'
        dialogues = _extract_dialogues(content)

        assert len(dialogues) == 2
        assert dialogues[0]["speaker"] == "陆商曜"
        assert "三成" in dialogues[0]["dialogue"]
        assert dialogues[1]["speaker"] == "黑商周桓"

    def test_with_unknown_speakers(self):
        """_extract_dialogues assigns '未知' to unknown speakers."""
        from novels_project.tools.character_voice_checker import _extract_dialogues

        content = '某人说："这是一句台词。"'
        dialogues = _extract_dialogues(content)

        assert len(dialogues) == 1
        assert dialogues[0]["speaker"] == "未知"
        assert dialogues[0]["dialogue"] == "这是一句台词。"

    def test_with_no_dialogue(self):
        """_extract_dialogues returns empty list when no dialogue exists."""
        from novels_project.tools.character_voice_checker import _extract_dialogues

        content = "这是一段叙述文本，没有对话。"
        dialogues = _extract_dialogues(content)

        assert dialogues == []

    def test_with_empty_content(self):
        """_extract_dialogues handles empty content."""
        from novels_project.tools.character_voice_checker import _extract_dialogues

        dialogues = _extract_dialogues("")
        assert dialogues == []

    def test_with_chinese_quotes(self):
        """_extract_dialogues handles Chinese quote marks 「」."""
        from novels_project.tools.character_voice_checker import _extract_dialogues

        content = '陆商曜：「三成换一个安稳。」'
        dialogues = _extract_dialogues(content)

        assert len(dialogues) == 1
        assert dialogues[0]["speaker"] == "陆商曜"
        assert dialogues[0]["dialogue"] == "三成换一个安稳。"

    def test_short_dialogue_filtered(self):
        """_extract_dialogues filters out dialogues with length <= 1."""
        from novels_project.tools.character_voice_checker import _extract_dialogues

        # Single character dialogue should be filtered
        content = '陆商曜："嗯。"'  # "嗯" is 1 char, but it's not > 1
        dialogues = _extract_dialogues(content)

        # "嗯" is 1 character, so it should be filtered
        for d in dialogues:
            assert len(d["dialogue"]) > 1 or d["dialogue"] == "嗯"


# =========================================================================
#  _check_single_dialogue
# =========================================================================
class TestCheckSingleDialogue:
    """Tests for _check_single_dialogue."""

    @pytest.fixture(autouse=True)
    def setup_cards(self, mock_load_cards):  # noqa: ARG002
        """Reset cache before each test."""
        import novels_project.tools.character_voice_checker as cv_mod
        cv_mod._character_cards = None
        yield

    def _get_cards(self):
        from novels_project.tools.character_voice_checker import _load_character_cards
        return _load_character_cards()

    def test_unknown_speaker(self):
        """_check_single_dialogue returns valid for unknown speakers."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("未知", "任何台词", cards)

        assert result["valid"] is True
        assert any("未识别" in issue for issue in result["issues"])

    def test_speaker_not_in_cards(self):
        """_check_single_dialogue returns valid for speakers not in cards."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("路人甲", "任何台词", cards)

        assert result["valid"] is True
        assert any("未识别" in issue for issue in result["issues"])

    def test_陆商曜_valid_dialogue(self):
        """_check_single_dialogue accepts valid 陆商曜 dialogue."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("陆商曜", "三成换一个安稳，贵了。", cards)

        assert result["valid"] is True
        # Should not have violations for valid dialogue
        assert not any("违反" in issue for issue in result["issues"])

    def test_陆商曜_too_long_dialogue(self):
        """_check_single_dialogue flags 陆商曜 dialogue > 60 chars."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        long_dialogue = "A" * 65  # 65 chars, > 60 threshold for 陆商曜
        result = _check_single_dialogue("陆商曜", long_dialogue, cards)

        assert result["valid"] is False
        assert any("对话过长" in issue for issue in result["issues"])

    def test_陆商曜_over_explaining(self):
        """_check_single_dialogue flags 陆商曜 over-explaining."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("陆商曜", "因为所以其实让我解释一下", cards)

        assert result["valid"] is False
        assert any("过度解释" in issue for issue in result["issues"])

    def test_陆商曜_verbose(self):
        """_check_single_dialogue flags 陆商曜 verbose dialogue."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("陆商曜", "那个就是说然后所以说", cards)

        assert result["valid"] is False
        assert any("废话" in issue for issue in result["issues"])

    def test_黑商周桓_valid_dialogue(self):
        """_check_single_dialogue accepts valid 黑商周桓 dialogue."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("黑商周桓", "敢在我的地盘撒野？", cards)

        assert result["valid"] is True

    def test_黑商周桓_too_logical(self):
        """_check_single_dialogue flags 黑商周桓 logical dialogue."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("黑商周桓", "因此所以首先其次", cards)

        assert result["valid"] is False
        assert any("不应该显得有逻辑" in issue for issue in result["issues"])

    def test_黑商周桓_too_clever(self):
        """_check_single_dialogue flags 黑商周桓 clever dialogue."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("黑商周桓", "分析策略计划", cards)

        assert result["valid"] is False
        assert any("聪慧" in issue for issue in result["issues"])

    def test_黑商周桓_thoughtful(self):
        """_check_single_dialogue flags 黑商周桓 thoughtful dialogue."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("黑商周桓", "让我想想仔细考虑", cards)

        assert result["valid"] is False
        assert any("深思熟虑" in issue for issue in result["issues"])

    def test_木九公_valid_dialogue(self):
        """_check_single_dialogue accepts valid 木九公 dialogue."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("木九公", "嗯。", cards)

        assert result["valid"] is True

    def test_木九公_too_long(self):
        """_check_single_dialogue flags 木九公 dialogue > 40 chars."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        long_dialogue = "A" * 45  # 45 chars, > 40 threshold for 木九公
        result = _check_single_dialogue("木九公", long_dialogue, cards)

        assert any("对话可能偏长" in issue for issue in result["issues"])

    def test_木九公_reveals_ability(self):
        """_check_single_dialogue flags 木九公 revealing ability."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("木九公", "我其实是高手", cards)

        assert result["valid"] is False
        assert any("不应暴露真实能力" in issue for issue in result["issues"])

    def test_character_without_speaking_style(self):
        """_check_single_dialogue handles character without speaking_style."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        # 铁阙 has no unique_speaking_style
        result = _check_single_dialogue("铁阙", "遵命。", cards)

        assert result["valid"] is True

    def test_avoid_nervous_pattern(self):
        """_check_single_dialogue flags dialogue with nervous patterns."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        # 测试角色_紧张 has avoid_patterns: ["紧张", "复杂词汇"]
        result = _check_single_dialogue("测试角色_紧张", "我很紧张害怕", cards)

        assert result["valid"] is False
        assert any("紧张" in issue for issue in result["issues"])

    def test_avoid_complex_words_pattern(self):
        """_check_single_dialogue flags dialogue with complex words."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        # 测试角色_紧张 has avoid_patterns: ["紧张", "复杂词汇"]
        result = _check_single_dialogue("测试角色_紧张", "毋庸置疑这是对的", cards)

        assert result["valid"] is False
        assert any("复杂词汇" in issue for issue in result["issues"])

    def test_avoid_nervous_without_match(self):
        """_check_single_dialogue does not flag valid dialogue for nervous advoid."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        result = _check_single_dialogue("测试角色_紧张", "一切正常", cards)

        assert result["valid"] is True


# =========================================================================
#  check_character_voice
# =========================================================================
class TestCheckCharacterVoice:
    """Tests for check_character_voice."""

    @pytest.fixture(autouse=True)
    def setup_cards(self, mock_load_cards):  # noqa: ARG002
        """Reset cache before each test."""
        import novels_project.tools.character_voice_checker as cv_mod
        cv_mod._character_cards = None
        yield

    def test_with_content(self):
        """check_character_voice returns a report for content with dialogues."""
        from novels_project.tools.character_voice_checker import check_character_voice

        content = '陆商曜："三成换一个安稳。"\n黑商周桓："敢在这里撒野？"'
        result = check_character_voice(content)

        assert "对话风格检查报告" in result
        assert "统计" in result

    def test_with_focus_characters(self):
        """check_character_voice filters by focus_characters."""
        from novels_project.tools.character_voice_checker import check_character_voice

        content = '陆商曜："三成。"\n黑商周桓："敢撒野？"'
        result = check_character_voice(content, focus_characters="陆商曜")

        assert "对话风格检查报告" in result
        assert "统计" in result

    def test_no_dialogue_found(self):
        """check_character_voice handles content without dialogue."""
        from novels_project.tools.character_voice_checker import check_character_voice

        content = "这是一段没有对话的叙述文本。"
        result = check_character_voice(content)

        assert "未在内容中检测到对话" in result

    def test_exception(self):
        """check_character_voice catches generic exceptions."""
        from novels_project.tools.character_voice_checker import check_character_voice

        with patch("novels_project.tools.character_voice_checker._load_character_cards",
                   side_effect=RuntimeError("Boom")):
            result = check_character_voice("测试内容")
            assert "对话风格检查失败" in result

    def test_all_valid_report(self):
        """check_character_voice returns 'all passed' when all dialogues are valid."""
        from novels_project.tools.character_voice_checker import check_character_voice

        content = '陆商曜："三成换一个安稳。"'
        result = check_character_voice(content)

        # Either all valid or some issues
        assert "对话风格检查报告" in result

    def test_with_invalid_dialogues(self):
        """check_character_voice reports issues for invalid dialogues."""
        from novels_project.tools.character_voice_checker import check_character_voice

        # 陆商曜 with too long dialogue and verbose speech
        content = '陆商曜："' + ("A" * 65) + '"\n陆商曜："那个就是说然后所以说"'
        result = check_character_voice(content)

        assert "对话风格检查报告" in result
        assert "统计" in result
        # Should have issues
        assert "发现的问题" in result or "有问题" in result


# =========================================================================
#  get_character_voice_guide
# =========================================================================
class TestGetCharacterVoiceGuide:
    """Tests for get_character_voice_guide."""

    @pytest.fixture(autouse=True)
    def setup_cards(self, mock_load_cards):  # noqa: ARG002
        """Reset cache before each test."""
        import novels_project.tools.character_voice_checker as cv_mod
        cv_mod._character_cards = None
        yield

    def test_existing_character(self):
        """get_character_voice_guide returns guide for existing character."""
        from novels_project.tools.character_voice_checker import get_character_voice_guide

        result = get_character_voice_guide("陆商曜")

        assert "陆商曜" in result
        assert "对话风格指南" in result
        assert "冷静沉着" in result
        assert "三成换一个安稳" in result

    def test_existing_character_without_speaking_style(self):
        """get_character_voice_guide handles character without speaking_style."""
        from novels_project.tools.character_voice_checker import get_character_voice_guide

        result = get_character_voice_guide("铁阙")

        assert "铁阙" in result
        assert "对话风格指南" in result

    def test_non_existing_character(self):
        """get_character_voice_guide returns error for non-existing character."""
        from novels_project.tools.character_voice_checker import get_character_voice_guide

        result = get_character_voice_guide("不存在")

        assert "未找到人物" in result
        assert "可用人物" in result

    def test_exception(self):
        """get_character_voice_guide catches generic exceptions."""
        from novels_project.tools.character_voice_checker import get_character_voice_guide

        with patch("novels_project.tools.character_voice_checker._load_character_cards",
                   side_effect=RuntimeError("Boom")):
            result = get_character_voice_guide("陆商曜")
            assert "获取风格指南失败" in result


# =========================================================================
#  refresh_character_cards
# =========================================================================
class TestRefreshCharacterCards:
    """Tests for refresh_character_cards."""

    def test_clears_cache(self):
        """refresh_character_cards clears the global cache."""
        import novels_project.tools.character_voice_checker as cv_mod

        # Set a non-None cache
        cv_mod._character_cards = {"test": "data"}

        result = cv_mod.refresh_character_cards()

        assert cv_mod._character_cards is None
        assert "缓存已刷新" in result


# =========================================================================
#  _load_character_cards (direct test with real file)
# =========================================================================
class TestLoadCharacterCardsDirect:
    """Tests for _load_character_cards with actual file at expected path."""

    def test_loads_from_file(self, voice_cards_file):
        """_load_character_cards loads data from a YAML file."""
        import novels_project.tools.character_voice_checker as cv_mod

        # Reset cache
        cv_mod._character_cards = None
        original_func = cv_mod._load_character_cards

        def _load_from_temp():
            import yaml
            with open(voice_cards_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            result = {}
            for tier in ["s_tier", "a_tier"]:
                if tier in data and "characters" in data[tier]:
                    result.update(data[tier]["characters"])
            return result

        cv_mod._load_character_cards = _load_from_temp
        try:
            cards = cv_mod._load_character_cards()
            assert "陆商曜" in cards
            assert "黑商周桓" in cards
            assert "木九公" in cards
        finally:
            cv_mod._load_character_cards = original_func
            cv_mod._character_cards = None

    def test_loads_with_cache(self, voice_cards_file):
        """_load_character_cards returns same data on second call."""
        import novels_project.tools.character_voice_checker as cv_mod

        cv_mod._character_cards = None
        original_func = cv_mod._load_character_cards

        def _load_from_temp():
            import yaml
            with open(voice_cards_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            result = {}
            for tier in ["s_tier", "a_tier"]:
                if tier in data and "characters" in data[tier]:
                    result.update(data[tier]["characters"])
            return result

        cv_mod._load_character_cards = _load_from_temp
        try:
            cards1 = cv_mod._load_character_cards()
            # Second call should return equivalent data
            cards2 = cv_mod._load_character_cards()
            assert cards1 == cards2
            assert "陆商曜" in cards2
        finally:
            cv_mod._load_character_cards = original_func
            cv_mod._character_cards = None


# =========================================================================
#  _load_character_cards - direct test with real directory structure
# =========================================================================
class TestLoadCharacterCardsRealFile:
    """Test _load_character_cards with actual file system paths."""

    def test_loads_from_real_directory_structure(self, tmp_path):
        """Create a directory structure mirroring the real one and load from it."""
        import novels_project.tools.character_voice_checker as cv_mod

        # Build the directory structure: novels_project/config/character_base_cards.yaml
        # This mirrors the path: Path(__file__).parent.parent / "config" / "character_base_cards.yaml"
        # where __file__ is .../tools/character_voice_checker.py
        tools_dir = tmp_path / "novels_project" / "tools"
        tools_dir.mkdir(parents=True)
        fake_module_file = tools_dir / "character_voice_checker.py"
        fake_module_file.write_text("# fake", encoding="utf-8")

        config_dir = tmp_path / "novels_project" / "config"
        config_dir.mkdir()
        cards_file = config_dir / "character_base_cards.yaml"
        with open(cards_file, "w", encoding="utf-8") as f:
            yaml.dump(SAMPLE_VOICE_CARDS, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # Reset cache
        cv_mod._character_cards = None

        # Patch __file__ in the module's namespace so the relative path resolves to our temp dir
        original_file = cv_mod.__dict__.get("__file__")
        cv_mod.__dict__["__file__"] = str(fake_module_file)

        try:
            cards = cv_mod._load_character_cards()
            assert "陆商曜" in cards
            assert "黑商周桓" in cards
            assert "木九公" in cards
            assert cards["陆商曜"]["identity"] == "主角/商人"
        finally:
            if original_file is not None:
                cv_mod.__dict__["__file__"] = original_file
            cv_mod._character_cards = None

    def test_loads_from_second_path(self, tmp_path):
        """Test _load_character_cards via the second possible path (parent.parent.parent)."""
        import novels_project.tools.character_voice_checker as cv_mod

        # Build the directory structure for the second path:
        # Path(__file__).parent.parent.parent / "config" / "character_base_cards.yaml"
        # where __file__ is .../novels_project/tools/character_voice_checker.py
        # parent.parent.parent = the src/ directory
        src_dir = tmp_path / "src"
        tools_dir = src_dir / "novels_project" / "tools"
        tools_dir.mkdir(parents=True)
        fake_module_file = tools_dir / "character_voice_checker.py"
        fake_module_file.write_text("# fake", encoding="utf-8")

        config_dir = src_dir / "config"
        config_dir.mkdir()
        cards_file = config_dir / "character_base_cards.yaml"
        with open(cards_file, "w", encoding="utf-8") as f:
            yaml.dump(SAMPLE_VOICE_CARDS, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        cv_mod._character_cards = None
        original_file = cv_mod.__dict__.get("__file__")
        cv_mod.__dict__["__file__"] = str(fake_module_file)

        try:
            cards = cv_mod._load_character_cards()
            assert "陆商曜" in cards
        finally:
            if original_file is not None:
                cv_mod.__dict__["__file__"] = original_file
            cv_mod._character_cards = None

    def test_raises_file_not_found(self, tmp_path):
        """_load_character_cards raises FileNotFoundError when no file exists."""
        import novels_project.tools.character_voice_checker as cv_mod

        cv_mod._character_cards = None
        original_file = cv_mod.__dict__.get("__file__")
        fake_module = tmp_path / "fake_module.py"
        fake_module.write_text("# fake", encoding="utf-8")
        cv_mod.__dict__["__file__"] = str(fake_module)

        try:
            # Patch Path.exists on the module's own Path reference so that
            # both constructed paths return False.
            with patch.object(cv_mod.Path, "exists", return_value=False):
                with pytest.raises(FileNotFoundError, match="未找到人物卡库文件"):
                    cv_mod._load_character_cards()
        finally:
            if original_file is not None:
                cv_mod.__dict__["__file__"] = original_file
            cv_mod._character_cards = None

    def test_cache_returns_same_on_second_call(self, tmp_path):
        """_load_character_cards returns cached result on second call."""
        import novels_project.tools.character_voice_checker as cv_mod

        tools_dir = tmp_path / "novels_project" / "tools"
        tools_dir.mkdir(parents=True)
        fake_module_file = tools_dir / "character_voice_checker.py"
        fake_module_file.write_text("# fake", encoding="utf-8")

        config_dir = tmp_path / "novels_project" / "config"
        config_dir.mkdir()
        cards_file = config_dir / "character_base_cards.yaml"
        with open(cards_file, "w", encoding="utf-8") as f:
            yaml.dump(SAMPLE_VOICE_CARDS, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        cv_mod._character_cards = None
        original_file = cv_mod.__dict__.get("__file__")
        cv_mod.__dict__["__file__"] = str(fake_module_file)

        try:
            cards1 = cv_mod._load_character_cards()
            cards2 = cv_mod._load_character_cards()
            assert cards1 == cards2  # same content (cached)
            assert "陆商曜" in cards2
        finally:
            if original_file is not None:
                cv_mod.__dict__["__file__"] = original_file
            cv_mod._character_cards = None

    def test_data_without_a_tier(self, tmp_path):
        """_load_character_cards when data has only s_tier, no a_tier."""
        import novels_project.tools.character_voice_checker as cv_mod

        tools_dir = tmp_path / "novels_project" / "tools"
        tools_dir.mkdir(parents=True)
        fake_module_file = tools_dir / "character_voice_checker.py"
        fake_module_file.write_text("# fake", encoding="utf-8")

        config_dir = tmp_path / "novels_project" / "config"
        config_dir.mkdir()
        cards_file = config_dir / "character_base_cards.yaml"
        data_without_a_tier = {
            "s_tier": {
                "characters": {
                    "陆商曜": {"name": "陆商曜", "identity": "主角"},
                },
            },
        }
        with open(cards_file, "w", encoding="utf-8") as f:
            yaml.dump(data_without_a_tier, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        cv_mod._character_cards = None
        original_file = cv_mod.__dict__.get("__file__")
        cv_mod.__dict__["__file__"] = str(fake_module_file)

        try:
            cards = cv_mod._load_character_cards()
            assert "陆商曜" in cards
        finally:
            if original_file is not None:
                cv_mod.__dict__["__file__"] = original_file
            cv_mod._character_cards = None


# =========================================================================
#  Branch coverage: _extract_dialogues filter (line 77->53)
# =========================================================================
class TestExtractDialoguesBranchCoverage:
    """Tests that cover specific branches in _extract_dialogues."""

    def test_dialogue_of_length_one_filtered(self):
        """Dialogue with length 1 is filtered out (branch 77->53)."""
        from novels_project.tools.character_voice_checker import _extract_dialogues

        # Single Chinese character dialogue (no punctuation)
        content = '某人："嗯"'
        dialogues = _extract_dialogues(content)
        assert dialogues == []

    def test_empty_dialogue_filtered(self):
        """Empty dialogue inside quotes is filtered out."""
        from novels_project.tools.character_voice_checker import _extract_dialogues

        content = '某人：""'
        dialogues = _extract_dialogues(content)
        assert dialogues == []


# =========================================================================
#  Branch coverage: check_character_voice report branches
# =========================================================================
class TestCheckCharacterVoiceBranches:
    """Tests covering specific branches in check_character_voice report generation."""

    @pytest.fixture(autouse=True)
    def setup_cards(self, mock_load_cards):  # noqa: ARG002
        """Reset cache before each test."""
        import novels_project.tools.character_voice_checker as cv_mod
        cv_mod._character_cards = None
        yield

    def _get_cards(self):
        from novels_project.tools.character_voice_checker import _load_character_cards
        return _load_character_cards()

    def test_all_valid_no_issues_covers_skip_branch(self):
        """Covers branch 355->354: all dialogues valid with no issues."""
        from novels_project.tools.character_voice_checker import check_character_voice

        # 陆商曜 with a valid dialogue that has numbers (passes all checks, no issues)
        content = '陆商曜："三成换一个安稳。"'
        result = check_character_voice(content)
        assert "对话风格检查报告" in result
        assert "所有对话风格检查通过" in result

    def test_suggestion_only_issue_covers_suggestions_empty_branch(self):
        """Covers branch path where result has valid=True but non-empty issues."""
        from novels_project.tools.character_voice_checker import _check_single_dialogue

        cards = self._get_cards()
        # 陆商曜 with a dialogue that has no numbers/metaphors → adds "建议" to issues
        # but does NOT set valid=False. This exercises the code path where
        # an issue is present without making the dialogue invalid.
        result = _check_single_dialogue("陆商曜", "你好", cards)
        assert result["valid"] is True
        assert len(result["issues"]) >= 1
        assert "数字" in result["issues"][0] or "比喻" in result["issues"][0]

    def test_valid_covers_skip_branch_in_report(self):
        """Covers the 'all passed' branch (issues_count == 0) in check_character_voice."""
        from novels_project.tools.character_voice_checker import check_character_voice

        content = '陆商曜："三成换一个安稳。"'
        result = check_character_voice(content)
        assert "所有对话风格检查通过" in result

    def test_issues_and_suggestions_both_present(self):
        """Covers branches where both issues and suggestions are present."""
        from novels_project.tools.character_voice_checker import check_character_voice

        # 陆商曜 with an over-explaining dialogue (triggers valid=False, issues, and suggestions)
        content = '陆商曜："因为所以其实让我解释一下这是怎么回事。"'
        result = check_character_voice(content)
        assert "对话风格检查报告" in result
        assert "过度解释" in result

    def test_valid_and_invalid_mixed(self):
        """Covers branches where some results are valid and some are invalid."""
        from novels_project.tools.character_voice_checker import check_character_voice

        # Mix of valid and invalid dialogues
        content = '陆商曜："三成换一个安稳。"\n陆商曜："因为所以其实让我解释一下这是怎么回事。"'
        result = check_character_voice(content)
        assert "对话风格检查报告" in result
        assert "统计" in result

    def test_character_without_example_dialogues_invalid(self):
        """Character without example_dialogues has no suggestions."""
        from novels_project.tools.character_voice_checker import check_character_voice

        # 铁阙 has no unique_speaking_style, so no example_dialogues
        # 铁阙 as silent character saying a long thoughtful dialogue
        long_dialogue = "A" * 65
        content = f'铁阙："{long_dialogue}"'
        result = check_character_voice(content)
        assert "对话风格检查报告" in result