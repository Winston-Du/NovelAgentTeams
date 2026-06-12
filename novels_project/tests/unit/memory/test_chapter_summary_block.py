"""ChapterSummaryBlock 数据类单元测试。

覆盖 7 个核心场景：
1. 基本构造（显式所有字段）
2. from_chapters 工厂方法自动生成 block_id 和元数据
3. to_dict() / from_dict() 序列化
4. 往返一致性（to_dict → from_dict → 等价）
5. __post_init__ 自动计算 char_count
6. 列表字段默认值（key_events, character_changes）
7. block_id 格式验证
"""
from datetime import datetime
from novels_project.memory.chapter_summary_block import ChapterSummaryBlock


# === 场景 1: 基本构造 ===

def test_construct_with_all_fields():
    """显式传入所有字段应正确创建对象。"""
    block = ChapterSummaryBlock(
        block_id="block_00001_00100",
        start_chapter=1,
        end_chapter=100,
        chapter_count=100,
        compressed_text="这是第 1-100 章的压缩摘要。",
        key_events=["事件1", "事件2"],
        character_changes=["陆商曜突破", "周桓加入"],
        created_at="2026-06-11T10:00:00",
        char_count=15,
    )
    assert block.block_id == "block_00001_00100"
    assert block.start_chapter == 1
    assert block.end_chapter == 100
    assert block.chapter_count == 100
    assert block.compressed_text == "这是第 1-100 章的压缩摘要。"
    assert block.key_events == ["事件1", "事件2"]
    assert block.character_changes == ["陆商曜突破", "周桓加入"]
    assert block.created_at == "2026-06-11T10:00:00"
    assert block.char_count == 15


# === 场景 2: from_chapters 工厂方法 ===

def test_from_chapters_generates_block_id():
    """工厂方法应自动生成 block_id 格式 'block_{start:05d}_{end:05d}'。"""
    block = ChapterSummaryBlock.from_chapters(
        start=1, end=100, compressed_text="摘要"
    )
    assert block.block_id == "block_00001_00100"


def test_from_chapters_pads_with_zeros():
    """章节号 < 100 时应补零（5 位）。"""
    block = ChapterSummaryBlock.from_chapters(
        start=7, end=42, compressed_text="x"
    )
    assert block.block_id == "block_00007_00042"


def test_from_chapters_computes_chapter_count():
    """工厂方法应自动计算 chapter_count = end - start + 1。"""
    block = ChapterSummaryBlock.from_chapters(
        start=101, end=200, compressed_text="x"
    )
    assert block.chapter_count == 100
    assert block.start_chapter == 101
    assert block.end_chapter == 200


def test_from_chapters_generates_iso_timestamp():
    """未传 created_at 时应自动生成 ISO 8601 时间戳。"""
    block = ChapterSummaryBlock.from_chapters(start=1, end=10, compressed_text="x")
    # 验证是 ISO 格式
    assert "T" in block.created_at
    # 验证可被 datetime 解析
    datetime.fromisoformat(block.created_at)


def test_from_chapters_preserves_explicit_timestamp():
    """显式传入 created_at 时应保留。"""
    block = ChapterSummaryBlock.from_chapters(
        start=1, end=10, compressed_text="x", created_at="2026-01-01T00:00:00"
    )
    assert block.created_at == "2026-01-01T00:00:00"


# === 场景 3: to_dict() ===

def test_to_dict_returns_all_fields():
    """to_dict() 应返回包含所有字段的字典。"""
    block = ChapterSummaryBlock(
        block_id="b1",
        start_chapter=1,
        end_chapter=10,
        chapter_count=10,
        compressed_text="text",
    )
    d = block.to_dict()
    assert d["block_id"] == "b1"
    assert d["start_chapter"] == 1
    assert d["end_chapter"] == 10
    assert d["chapter_count"] == 10
    assert d["compressed_text"] == "text"
    assert d["key_events"] == []
    assert d["character_changes"] == []


# === 场景 4: from_dict() 往返 ===

def test_from_dict_reconstructs_block():
    """from_dict() 应能从字典重建对象。"""
    original = ChapterSummaryBlock.from_chapters(
        start=1, end=100, compressed_text="摘要内容",
        key_events=["e1", "e2"], character_changes=["c1"]
    )
    d = original.to_dict()
    reconstructed = ChapterSummaryBlock.from_dict(d)
    assert reconstructed.block_id == original.block_id
    assert reconstructed.start_chapter == original.start_chapter
    assert reconstructed.end_chapter == original.end_chapter
    assert reconstructed.compressed_text == original.compressed_text
    assert reconstructed.key_events == original.key_events


def test_roundtrip_preserves_all_data():
    """to_dict → from_dict 往返后所有字段应保持一致。"""
    original = ChapterSummaryBlock(
        block_id="b_special",
        start_chapter=50,
        end_chapter=75,
        chapter_count=26,
        compressed_text="特殊章节块",
        key_events=["决战", "胜利"],
        character_changes=["陆商曜成仙"],
        created_at="2026-06-11T12:00:00",
        char_count=4,
    )
    d = original.to_dict()
    reconstructed = ChapterSummaryBlock.from_dict(d)
    assert reconstructed == original


# === 场景 5: __post_init__ 自动 char_count ===

def test_post_init_computes_char_count_when_zero():
    """char_count=0 且 compressed_text 非空时应自动计算。"""
    block = ChapterSummaryBlock(
        block_id="b",
        start_chapter=1,
        end_chapter=10,
        chapter_count=10,
        compressed_text="这是一些内容" * 3,
        char_count=0,
    )
    assert block.char_count == len("这是一些内容" * 3)
    assert block.char_count == 18  # "这是一些内容"=6 字符 × 3


def test_post_init_preserves_explicit_char_count():
    """显式提供 char_count 时应保留。"""
    block = ChapterSummaryBlock(
        block_id="b",
        start_chapter=1,
        end_chapter=10,
        chapter_count=10,
        compressed_text="x" * 1000,
        char_count=999,  # 故意与 len 不一致
    )
    assert block.char_count == 999  # 不被自动覆盖


def test_post_init_with_empty_compressed_text():
    """compressed_text 为空时 char_count 应保持 0。"""
    block = ChapterSummaryBlock(
        block_id="b",
        start_chapter=1,
        end_chapter=10,
        chapter_count=10,
        compressed_text="",
    )
    assert block.char_count == 0


# === 场景 6: 列表字段默认值 ===

def test_key_events_default_to_empty_list():
    """未传 key_events 时应为独立空列表（非共享可变默认）。"""
    block1 = ChapterSummaryBlock(
        block_id="b1", start_chapter=1, end_chapter=10,
        chapter_count=10, compressed_text="x"
    )
    block2 = ChapterSummaryBlock(
        block_id="b2", start_chapter=11, end_chapter=20,
        chapter_count=10, compressed_text="y"
    )
    # 修改 block1 的 key_events 不应影响 block2
    block1.key_events.append("event")
    assert block2.key_events == []


def test_character_changes_default_to_empty_list():
    """未传 character_changes 时应为空列表。"""
    block = ChapterSummaryBlock(
        block_id="b", start_chapter=1, end_chapter=10,
        chapter_count=10, compressed_text="x"
    )
    assert block.character_changes == []


# === 场景 7: block_id 格式 ===

def test_block_id_with_large_chapter_numbers():
    """章节号 > 99999 时 block_id 仍应正确生成。"""
    block = ChapterSummaryBlock.from_chapters(
        start=100, end=200, compressed_text="x"
    )
    # block_00100_00200
    assert block.block_id == "block_00100_00200"
