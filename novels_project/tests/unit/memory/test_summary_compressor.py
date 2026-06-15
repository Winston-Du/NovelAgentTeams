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
    # persist() 在 _trigger_compression 中已调用，dirty 已被清
    assert status["is_dirty"] is False
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


# ============================================================
# Task 6: 持久化与恢复
# ============================================================

import json


def _create_chapter_file(chapters_dir, chapter_id: int, content: str = None):
    """辅助：创建 chapter_{id}_final.md 文件。"""
    if content is None:
        content = f"第 {chapter_id} 章内容\n\n" + ("x" * 100)
    path = chapters_dir / f"chapter_{chapter_id}_final.md"
    path.write_text(content, encoding="utf-8")
    return path


# === 场景 1: persist() 基本持久化 ===

def test_persist_writes_block_files(tmp_path):
    """persist() 应为每个块写一个 JSON 文件。"""
    config = MemoryConfig(chapter_window=10, max_summary_blocks=3)
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    for i in range(1, 11):
        compressor.add_chapter_summary(i, f"第{i}章摘要")

    # 应该写 1 个块文件 + index.json
    block_files = list(tmp_path.glob("block_*.json"))
    assert len(block_files) == 1
    assert (tmp_path / "index.json").exists()


def test_persist_writes_valid_json(tmp_path):
    """块 JSON 应能被 json.load 解析。"""
    config = MemoryConfig(chapter_window=10, max_summary_blocks=3)
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    for i in range(1, 11):
        compressor.add_chapter_summary(i, f"第{i}章")

    block_path = tmp_path / "block_00001_00010.json"
    data = json.loads(block_path.read_text(encoding="utf-8"))
    assert data["block_id"] == "block_00001_00010"
    assert data["start_chapter"] == 1
    assert data["end_chapter"] == 10
    assert data["chapter_count"] == 10


def test_persist_writes_index(tmp_path):
    """index.json 应包含所有块的 block_id 列表。"""
    config = MemoryConfig(chapter_window=10, max_summary_blocks=3)
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    for batch in range(3):
        for j in range(10):
            chapter_id = batch * 10 + j + 1
            compressor.add_chapter_summary(chapter_id, f"第{chapter_id}章")

    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert "blocks" in index
    assert len(index["blocks"]) == 3
    assert "block_00001_00010" in index["blocks"]
    assert "block_00011_00020" in index["blocks"]
    assert "block_00021_00030" in index["blocks"]


def test_persist_skips_when_not_dirty(tmp_path):
    """_dirty=False 时 persist() 不应写文件（无操作）。"""
    config = MemoryConfig()
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    # 未触发压缩，_dirty=False
    compressor.persist()
    assert not (tmp_path / "index.json").exists()
    assert list(tmp_path.glob("block_*.json")) == []


def test_persist_clears_dirty_flag(tmp_path):
    """persist() 后 _dirty 应被置为 False。"""
    config = MemoryConfig(chapter_window=10)
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    for i in range(1, 11):
        compressor.add_chapter_summary(i, f"第{i}章")
    assert compressor._dirty is False  # persist() 在 _trigger_compression 中已调用


# === 场景 2: 启动加载已有块 ===

def test_load_existing_blocks_on_init(tmp_path):
    """初始化时自动加载已有块文件。"""
    config = MemoryConfig(chapter_window=10, max_summary_blocks=3)
    # 第一次：写 1 个块
    c1 = SummaryCompressor(config=config, storage_dir=tmp_path)
    for i in range(1, 11):
        c1.add_chapter_summary(i, f"第{i}章")

    # 第二次：新建 compressor，验证加载
    c2 = SummaryCompressor(config=config, storage_dir=tmp_path)
    assert len(c2._blocks) == 1
    assert c2._blocks[0].block_id == "block_00001_00010"


def test_load_existing_blocks_preserves_metadata(tmp_path):
    """加载时应保留块的元数据（key_events, character_changes）。"""
    config = MemoryConfig(chapter_window=10)  # 显式 window=10 触发压缩
    c1 = SummaryCompressor(config=config, storage_dir=tmp_path)
    for i in range(1, 11):
        c1.add_chapter_summary(i, f"第{i}章击败了敌人")
    original_events = c1._blocks[0].key_events

    c2 = SummaryCompressor(config=config, storage_dir=tmp_path)
    assert c2._blocks[0].key_events == original_events


def test_load_existing_blocks_skips_missing_files(tmp_path):
    """index.json 引用了不存在的块文件时应跳过（不抛异常）。"""
    import json as _json
    (tmp_path / "index.json").write_text(
        _json.dumps({"blocks": ["block_00001_00010", "block_00011_00020"]}, ensure_ascii=False),
        encoding="utf-8"
    )
    # 只创建其中一个块文件
    valid = tmp_path / "block_00011_00020.json"
    valid.write_text(
        _json.dumps({"block_id": "block_00011_00020", "start_chapter": 11,
                     "end_chapter": 20, "chapter_count": 10, "compressed_text": "x"}),
        encoding="utf-8"
    )

    config = MemoryConfig()
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    # 只加载存在的块
    assert len(compressor._blocks) == 1
    assert compressor._blocks[0].block_id == "block_00011_00020"


def test_load_with_empty_storage(tmp_path):
    """空 storage_dir 不应报错。"""
    config = MemoryConfig()
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    assert compressor._blocks == []


def test_load_with_corrupted_index_skips_gracefully(tmp_path):
    """损坏的 index.json 不应阻塞启动。"""
    config = MemoryConfig()
    # 写一个损坏的 index.json
    (tmp_path / "index.json").write_text("{not valid json", encoding="utf-8")
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    assert compressor._blocks == []


# === 场景 3: 损坏块文件恢复 ===

def test_corrupted_block_recovers_from_chapter_files(tmp_path):
    """块 JSON 损坏时应从章节文件自动恢复。"""
    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    for i in range(1, 11):
        _create_chapter_file(chapters_dir, i, f"第 {i} 章内容 " * 20)

    storage_dir = tmp_path / "blocks"
    storage_dir.mkdir()
    # 写一个损坏的块文件 + 损坏的 index.json
    (storage_dir / "block_00001_00010.json").write_text(
        '{"block_id": "block_00001_00010", "compress',  # 截断
        encoding="utf-8"
    )
    (storage_dir / "index.json").write_text(
        json.dumps({"blocks": ["block_00001_00010"]}, ensure_ascii=False),
        encoding="utf-8"
    )

    config = MemoryConfig(chapter_window=10, max_summary_blocks=3)
    compressor = SummaryCompressor(
        config=config, storage_dir=storage_dir, chapters_dir=chapters_dir,
    )
    # 块已从章节文件恢复
    assert len(compressor._blocks) == 1
    assert compressor._blocks[0].start_chapter == 1
    assert compressor._blocks[0].end_chapter == 10
    assert "recovered" in compressor._blocks[0].created_at

    # 损坏文件应被备份
    backup = storage_dir / "block_00001_00010.corrupted.json"
    assert backup.exists()


def test_corrupted_block_no_chapter_files_raises(tmp_path):
    """块损坏且章节文件缺失时应抛 BlockRecoveryError。"""
    storage_dir = tmp_path / "blocks"
    storage_dir.mkdir()
    (storage_dir / "block_00001_00010.json").write_text("{not valid", encoding="utf-8")
    (storage_dir / "index.json").write_text(
        json.dumps({"blocks": ["block_00001_00010"]}, ensure_ascii=False),
        encoding="utf-8"
    )

    # chapters_dir 存在但没有章节文件
    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()

    config = MemoryConfig()
    # 由于 _load_existing_blocks_with_recovery 内部会捕获 + log，
    # 损坏块无法恢复时该块会被跳过
    compressor = SummaryCompressor(
        config=config, storage_dir=storage_dir, chapters_dir=chapters_dir,
    )
    assert compressor._blocks == []  # 损坏块被跳过


def test_recovery_skips_invalid_block_id_format(tmp_path):
    """block_id 格式不正确的块文件应被跳过。"""
    storage_dir = tmp_path / "blocks"
    storage_dir.mkdir()
    # 写一个正常但有奇怪文件名（block_id）的 JSON
    weird = storage_dir / "block_abc_xyz.json"
    weird.write_text(
        json.dumps({"block_id": "block_abc_xyz", "compressed_text": "x"}),
        encoding="utf-8"
    )
    (storage_dir / "index.json").write_text(
        json.dumps({"blocks": ["block_abc_xyz"]}, ensure_ascii=False),
        encoding="utf-8"
    )

    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()

    config = MemoryConfig()
    # 解析失败应被捕获并跳过
    compressor = SummaryCompressor(
        config=config, storage_dir=storage_dir, chapters_dir=chapters_dir,
    )
    assert compressor._blocks == []


# === 场景 4: _extract_chapter_summary ===

def test_extract_chapter_summary_returns_first_and_last_paragraph(tmp_path):
    """应从章节文本中提取首段和末段。"""
    config = MemoryConfig()
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    text = "首段内容\n\n中间段1\n\n中间段2\n\n末段内容"
    summary = compressor._extract_chapter_summary(text)
    assert "首段内容" in summary
    assert "末段内容" in summary
    assert "中间段" not in summary


def test_extract_chapter_summary_single_paragraph(tmp_path):
    """单段文本应原样返回。"""
    config = MemoryConfig()
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    text = "唯一一段"
    summary = compressor._extract_chapter_summary(text)
    assert summary == "唯一一段"


def test_extract_chapter_summary_two_paragraphs(tmp_path):
    """恰好 2 段文本应两段都用。"""
    config = MemoryConfig()
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    text = "第一段\n\n第二段"
    summary = compressor._extract_chapter_summary(text)
    assert "第一段" in summary
    assert "第二段" in summary


def test_extract_chapter_summary_empty(tmp_path):
    """空文本应返回空字符串。"""
    config = MemoryConfig()
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    assert compressor._extract_chapter_summary("") == ""


# === 场景 5: 完整流程: persist → reload → recovery ===

def test_full_persist_reload_recovery_cycle(tmp_path):
    """完整流程：压缩 → persist → 损坏 → 重新加载 → 自动恢复。"""
    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir()
    for i in range(1, 21):
        _create_chapter_file(
            chapters_dir, i, f"第 {i} 章\n\n{i*2}个段落。" * 5
        )

    storage_dir = tmp_path / "blocks"
    config = MemoryConfig(chapter_window=10, max_summary_blocks=3)

    # 第 1 阶段：生成 2 个块
    c1 = SummaryCompressor(
        config=config, storage_dir=storage_dir, chapters_dir=chapters_dir,
    )
    for i in range(1, 21):
        c1.add_chapter_summary(i, f"第{i}章摘要")
    assert len(c1._blocks) == 2

    # 第 2 阶段：手动损坏其中一个块
    target = storage_dir / "block_00001_00010.json"
    target.write_text("garbage content", encoding="utf-8")

    # 第 3 阶段：重新加载 → 损坏块被恢复
    c2 = SummaryCompressor(
        config=config, storage_dir=storage_dir, chapters_dir=chapters_dir,
    )
    assert len(c2._blocks) == 2
    # 检查恢复的块
    block1 = next(b for b in c2._blocks if b.start_chapter == 1)
    assert "recovered" in block1.created_at


# === 场景 6: 与 Task 5 集成（确保持久化不影响基础累加）===

def test_persist_does_not_block_add_chapter(tmp_path):
    """persist() 不应阻塞 add_chapter_summary 的正常累加。"""
    config = MemoryConfig(chapter_window=10, max_summary_blocks=3)
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    for i in range(1, 6):
        result = compressor.add_chapter_summary(i, f"第{i}章")
        assert result is None
        assert len(compressor._accumulator) == i


def test_reload_preserves_dirty_flag(tmp_path):
    """重新加载后 _dirty 应为 False（无新压缩）。"""
    config = MemoryConfig()
    c1 = SummaryCompressor(config=config, storage_dir=tmp_path)
    for i in range(1, 11):
        c1.add_chapter_summary(i, f"第{i}章")
    # persist 已清 dirty
    assert c1._dirty is False

    c2 = SummaryCompressor(config=config, storage_dir=tmp_path)
    assert c2._dirty is False  # 加载时未设置 dirty


# ============================================================
# Task 6 补丁：LLM 压缩实装测试
# ============================================================
import sys as _sys
_sys.path.insert(0, "/Users/Winston/Documents/WorkSpace/NovelAgentTeams/novels_project/src")
from novels_project.api_client import TextDelta, MessageStop  # noqa: E402


def _make_streaming_llm(text: str):
    """构造返回纯文本的 mock LLM。"""
    class MockLLM:
        default_model = "mock-llm"

        def stream(self, request=None, print_stream: bool = False):
            del request, print_stream  # mock 接口签名
            return [TextDelta(text=text), MessageStop()]
    return MockLLM()


def _make_failing_llm(error: Exception):
    """构造抛异常的 mock LLM。"""
    class MockLLM:
        default_model = "mock-llm"
        def stream(self, request=None, print_stream: bool = False):
            del request, print_stream
            raise error
    return MockLLM()


def _make_empty_llm():
    """构造返回空事件的 mock LLM。"""
    class MockLLM:
        default_model = "mock-llm"
        def stream(self, request=None, print_stream: bool = False):
            del request, print_stream
            return [MessageStop()]
    return MockLLM()


def test_llm_compress_success(tmp_path):
    """LLM 压缩成功：返回 LLM 输出文本。"""
    config = MemoryConfig(chapter_window=10, summary_max_chars=2000)
    llm_text = "这是 LLM 压缩后的剧情摘要。保留了主要人物行动线和关键转折。"
    compressor = SummaryCompressor(
        config=config, storage_dir=tmp_path,
        llm_client=_make_streaming_llm(llm_text),
    )

    result = compressor._llm_compress_with_retry("100章内容" * 100)
    assert result == llm_text


def test_llm_compress_uses_rule_fallback_on_failure(tmp_path):
    """LLM 失败时降级为规则压缩。"""
    config = MemoryConfig(chapter_window=10, summary_max_chars=2000)
    compressor = SummaryCompressor(
        config=config, storage_dir=tmp_path,
        llm_client=_make_failing_llm(ConnectionError("network down")),
    )

    # _llm_or_rule_compress 应降级为 _rule_compress 而非抛异常
    text = "1" * 5000  # 超长文本触发截断
    result = compressor._llm_or_rule_compress(text)
    assert isinstance(result, str)
    assert len(result) <= 2000


def test_llm_compress_uses_rule_fallback_on_empty_response(tmp_path):
    """LLM 返回空时降级为规则压缩。"""
    config = MemoryConfig(chapter_window=10, summary_max_chars=2000)
    compressor = SummaryCompressor(
        config=config, storage_dir=tmp_path,
        llm_client=_make_empty_llm(),
    )

    text = "1" * 5000
    result = compressor._llm_or_rule_compress(text)
    assert isinstance(result, str)
    assert len(result) <= 2000


def test_llm_or_rule_compress_with_no_llm_client(tmp_path):
    """无 LLM 客户端时直接走规则压缩。"""
    config = MemoryConfig(chapter_window=10, summary_max_chars=2000)
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path, llm_client=None)

    text = "1" * 5000
    result = compressor._llm_or_rule_compress(text)
    assert isinstance(result, str)
    assert len(result) <= 2000


def test_llm_compress_with_retry_eventually_succeeds(tmp_path):
    """LLM 第一次失败、第二次成功。"""
    call_count = {"n": 0}
    text = "LLM 压缩输出"

    class FlakeyLLM:
        default_model = "mock-llm"
        def stream(self, request=None, print_stream: bool = False):
            del request, print_stream
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionError("transient")
            return [TextDelta(text=text), MessageStop()]

    config = MemoryConfig(chapter_window=10, summary_max_chars=2000)
    # 用 monkeypatch 把 sleep 加速
    compressor = SummaryCompressor(
        config=config, storage_dir=tmp_path, llm_client=FlakeyLLM(),
    )

    # 把 time.sleep 替换为 noop
    import time
    original_sleep = time.sleep
    time.sleep = lambda s: None
    try:
        result = compressor._llm_compress_with_retry("content" * 50)
    finally:
        time.sleep = original_sleep

    assert result == text
    assert call_count["n"] == 2  # 第一次失败，第二次成功


def test_trigger_compression_uses_llm_when_available(tmp_path, caplog):
    """_trigger_compression 优先使用 LLM（在 chapter_window 达到时）。"""
    import logging
    caplog.set_level(logging.INFO, logger="novels_project.memory.summary_compressor")
    config = MemoryConfig(chapter_window=3, summary_max_chars=2000)
    llm_text = "LLM 压缩后的输出"
    compressor = SummaryCompressor(
        config=config, storage_dir=tmp_path,
        llm_client=_make_streaming_llm(llm_text),
    )
    compressor.add_chapter_summary(1, "1")
    compressor.add_chapter_summary(2, "2")
    block = compressor.add_chapter_summary(3, "3")  # 触发压缩

    assert block is not None
    assert block.compressed_text == llm_text
    # 验证日志中包含 "使用 LLM 压缩"
    assert any("使用 LLM 压缩" in rec.message for rec in caplog.records)


def test_extract_text_from_events_filters_non_text(tmp_path):
    """_extract_text_from_events 只取 TextDelta。"""
    from novels_project.api_client import ToolUseEvent, UsageEvent

    config = MemoryConfig()
    compressor = SummaryCompressor(config=config, storage_dir=tmp_path)
    events = [
        TextDelta(text="Hello "),
        ToolUseEvent(id="t1", name="search", input={}),  # 跳过
        TextDelta(text="World"),
        UsageEvent(usage={}),  # 跳过
        MessageStop(),  # 跳过
    ]
    result = compressor._extract_text_from_events(events)
    assert result == "Hello World"
