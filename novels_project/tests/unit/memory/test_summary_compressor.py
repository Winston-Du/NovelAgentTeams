"""SummaryCompressor 累加触发与滑窗淘汰测试。

覆盖 6 个核心场景：
1. 累加未达阈值：返回 None + accumulator 累积
2. 累加达到阈值：触发压缩 + 返回 ChapterSummaryBlock
3. block_id 格式：5 位补零
4. 滑窗淘汰：保留最近 max_summary_blocks 个
5. 触发后 accumulator 清空
6. _rule_compress 截断逻辑
"""
import pytest

from novels_project.memory.summary_compressor import SummaryCompressor
from novels_project.memory.memory_config import MemoryConfig
from novels_project.memory.chapter_summary_block import ChapterSummaryBlock


@pytest.fixture
def tmp_compressor(tmp_path):
    """Create a SummaryCompressor with small window for testing."""
    config = MemoryConfig(chapter_window=10, max_summary_blocks=3)
    return SummaryCompressor(config=config, storage_dir=tmp_path)


# === 场景 1: 累加未达阈值 ===

def test_add_chapter_below_threshold_returns_none(tmp_compressor):
    """累加未到 chapter_window 时返回 None。"""
    result = tmp_compressor.add_chapter_summary(1, "第1章摘要")
    assert result is None
    assert len(tmp_compressor._accumulator) == 1
    assert tmp_compressor._accumulator[0] == (1, "第1章摘要")


# === 场景 2: 累加达到阈值 ===

def test_add_chapter_reaches_threshold_triggers_compression(tmp_compressor):
    """累加到 chapter_window（10）时触发压缩并返回块。"""
    last_result = None
    for i in range(1, 11):
        last_result = tmp_compressor.add_chapter_summary(i, f"第{i}章摘要")
        if i < 10:
            assert last_result is None, f"第 {i} 章不应触发压缩"

    # 第 10 章应触发压缩
    assert last_result is not None
    assert isinstance(last_result, ChapterSummaryBlock)
    assert last_result.start_chapter == 1
    assert last_result.end_chapter == 10
    assert last_result.chapter_count == 10


# === 场景 3: block_id 格式 ===

def test_block_id_format(tmp_compressor):
    """块 ID 应为 'block_{start:05d}_{end:05d}' 格式。"""
    for i in range(1, 11):
        tmp_compressor.add_chapter_summary(i, f"第{i}章")
    block = tmp_compressor._blocks[0]
    assert block.block_id == "block_00001_00010"


# === 场景 4: 滑窗淘汰 ===

def test_sliding_window_eviction(tmp_compressor):
    """累积到 max_summary_blocks * chapter_window 章时，保留最近 N 个块。"""
    # 添加 4 批（每批 10 章，共 40 章）
    for batch in range(4):
        for j in range(10):
            chapter_id = batch * 10 + j + 1
            tmp_compressor.add_chapter_summary(chapter_id, f"第{chapter_id}章")

    # 应该有 3 个块（max=3）
    assert len(tmp_compressor._blocks) == 3
    # 最旧的应该是第二批（11-20），最早的 1-10 已被淘汰
    assert tmp_compressor._blocks[0].start_chapter == 11
    assert tmp_compressor._blocks[-1].end_chapter == 40


# === 场景 5: 触发后 accumulator 清空 ===

def test_accumulator_clears_after_compression(tmp_compressor):
    """压缩触发后 accumulator 应被清空。"""
    for i in range(1, 11):
        tmp_compressor.add_chapter_summary(i, f"第{i}章")
    assert len(tmp_compressor._accumulator) == 0


# === 场景 6: _rule_compress 截断 ===

def test_rule_compress_truncation(tmp_compressor):
    """长文本应被截断到 summary_max_chars 以内。"""
    long_text = "x" * 5000
    compressed = tmp_compressor._rule_compress(long_text)
    # summary_max_chars 默认 2000
    assert len(compressed) <= 2000
    assert "中间章节省略" in compressed


# === 额外测试: 触发后 accumulator 重新累积 ===

def test_accumulator_starts_fresh_after_compression(tmp_compressor):
    """第一次压缩后，下一章应开始新的 accumulator。"""
    for i in range(1, 11):
        tmp_compressor.add_chapter_summary(i, f"第{i}章")
    # 第二次累加
    result = tmp_compressor.add_chapter_summary(11, "第11章")
    assert result is None
    assert len(tmp_compressor._accumulator) == 1
    assert tmp_compressor._accumulator[0] == (11, "第11章")


# === 额外测试: 截断方法 ===

def test_truncate_short_text_unchanged(tmp_compressor):
    """短文本不应被截断。"""
    short = "短文本"
    assert tmp_compressor._truncate(short, 100) == short


def test_truncate_long_text_has_marker(tmp_compressor):
    """长文本应被截断并包含标记。"""
    long_text = "a" * 1000
    truncated = tmp_compressor._truncate(long_text, 100)
    assert len(truncated) <= 100
    assert "内容已截断" in truncated


# === 额外测试: 元数据提取 ===

def test_extract_metadata_detects_events(tmp_compressor):
    """应识别含关键词的句子为关键事件。"""
    text = "陆商曜击败了敌人。\n他杀死了魔王。\n普通的描述。"
    events, changes = tmp_compressor._extract_metadata(text)
    assert any("击败" in e for e in events)
    assert any("杀死" in e for e in events)
    assert "普通的描述" not in " ".join(events + changes)


def test_extract_metadata_detects_changes(tmp_compressor):
    """应识别含人物变化关键词的句子。"""
    text = "黑商周桓加入了商盟。\n旧友背叛离去。\n普通描述。"
    _, changes = tmp_compressor._extract_metadata(text)
    assert any("加入" in c for c in changes)
    assert any("背叛" in c for c in changes)


def test_extract_metadata_limits_results(tmp_compressor):
    """返回的列表应有合理上限（20 条）。"""
    text = "击败" * 100
    events, changes = tmp_compressor._extract_metadata(text)
    assert len(events) <= 20
    assert len(changes) <= 20


# === 额外测试: 注入文本生成 ===

def test_get_blocks_for_injection_empty(tmp_compressor):
    """无块时应返回空字符串。"""
    assert tmp_compressor.get_blocks_for_injection() == ""


def test_get_blocks_for_injection_contains_block_info(tmp_compressor):
    """注入文本应包含块 ID 和章节范围。"""
    for i in range(1, 11):
        tmp_compressor.add_chapter_summary(i, f"第{i}章")
    text = tmp_compressor.get_blocks_for_injection()
    assert "历史剧情摘要" in text
    assert "block_00001_00010" in text
    assert "1-10" in text


# === 额外测试: 状态报告 ===

def test_get_status_reports_state(tmp_compressor):
    """get_status 应返回完整的状态信息。"""
    for i in range(1, 6):
        tmp_compressor.add_chapter_summary(i, f"第{i}章")
    status = tmp_compressor.get_status()
    assert status["total_blocks"] == 0  # 未到阈值
    assert status["accumulator_size"] == 5
    assert status["accumulator_chapters"] == [1, 2, 3, 4, 5]
    assert status["is_dirty"] is False


def test_get_status_after_compression(tmp_compressor):
    """压缩后 status 应反映已生成的块。"""
    for i in range(1, 11):
        tmp_compressor.add_chapter_summary(i, f"第{i}章")
    status = tmp_compressor.get_status()
    assert status["total_blocks"] == 1
    assert status["accumulator_size"] == 0
    assert status["is_dirty"] is True
    assert status["blocks"][0]["block_id"] == "block_00001_00010"


# === 额外测试: 极端情况 ===

def test_rule_compress_extreme_max_chars(tmp_path):
    """极端情况：max_chars 极小时应优雅降级。"""
    config = MemoryConfig(chapter_window=10, max_summary_blocks=3, summary_max_chars=5)
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    long_text = "x" * 1000
    compressed = compressor._rule_compress(long_text)
    assert len(compressed) <= 5


# === 额外测试: chapters_dir 参数传递 ===

def test_init_with_chapters_dir(tmp_path):
    """应接受 chapters_dir 参数（用于 Task 6 块恢复）。"""
    config = MemoryConfig()
    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    compressor = SummaryCompressor(
        config=config, storage_dir=tmp_path, chapters_dir=chapters_dir
    )
    assert compressor.chapters_dir == chapters_dir


def test_init_without_chapters_dir(tmp_path):
    """未传 chapters_dir 时应为 None。"""
    config = MemoryConfig()
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    assert compressor.chapters_dir is None
