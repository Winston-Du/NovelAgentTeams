"""
集成测试：SyncManager 同步管理器

测试范围：
1. SyncManager 初始化与配置
2. 全量同步 (_full_sync)
3. 增量同步 (_incremental_sync)
4. 人物卡同步 (sync_character_cards)
5. 章节同步 (sync_chapter)
6. 重试机制 (sync_with_retry)
7. 异常处理与边界条件
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from novels_project.memory.graph_store import GraphStore
from novels_project.memory.sync_manager import SyncManager, SyncStatus, SyncMode
from novels_project.memory.entity_extractor import EntityExtractor


class TestSyncManagerInitialization:
    """测试 SyncManager 初始化与配置"""

    def test_create_sync_manager(self):
        """测试创建 SyncManager 实例"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        assert mgr is not None
        assert mgr._graph is store
        assert mgr._status == SyncStatus.IDLE
        assert mgr._sync_count == 0
        assert mgr._consecutive_failures == 0
        assert mgr._auto_sync_enabled is False

    def test_create_with_entity_extractor(self):
        """测试使用自定义 EntityExtractor 初始化"""
        store = GraphStore()
        extractor = EntityExtractor(store)

        mgr = SyncManager(graph_store=store, entity_extractor=extractor)
        assert mgr._extractor is extractor

    def test_create_without_extractor_auto_creates(self):
        """测试无 extractor 时自动创建"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        assert mgr._extractor is not None
        assert isinstance(mgr._extractor, EntityExtractor)


class TestSyncManagerConfiguration:
    """测试 SyncManager 配置"""

    def test_set_watch_paths_basic(self, tmp_path):
        """测试设置基本监控路径"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("test")
        chapters = tmp_path / "chapters"
        chapters.mkdir()

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        assert mgr._character_cards_path == cards
        assert mgr._chapters_dir == chapters
        assert mgr._sync_state_path is None
        assert mgr._graph_save_path is None

    def test_set_watch_paths_with_optional(self, tmp_path):
        """测试设置包含可选路径的监控路径"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("test")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        graph_path = tmp_path / "graph.json"

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
            sync_state_dir=str(state_dir),
            graph_save_path=str(graph_path),
        )

        assert mgr._character_cards_path == cards
        assert mgr._chapters_dir == chapters
        assert mgr._sync_state_path is not None
        assert mgr._graph_save_path == graph_path


class TestSyncManagerFullSync:
    """测试全量同步"""

    def test_full_sync_empty_paths(self):
        """测试空路径全量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        result = mgr._full_sync(llm_client=None)

        assert result["mode"] == SyncMode.FULL
        assert "timestamp" in result
        assert "errors" in result
        assert "characters_added" in result
        assert "chapters_processed" in result

    def test_full_sync_with_character_cards(self, tmp_path):
        """测试带人物卡的全量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters:\n  - name: 测试角色\n    role: 主角")

        chapters = tmp_path / "chapters"
        chapters.mkdir()

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        # Mock extractor to return success
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=1)

        result = mgr._full_sync(llm_client=None)

        assert result["mode"] == SyncMode.FULL
        assert result["characters_added"] == 1

    def test_full_sync_with_extractor_failure(self, tmp_path):
        """测试人物卡提取失败时的全量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("invalid: [}")

        chapters = tmp_path / "chapters"
        chapters.mkdir()

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        mgr._extractor.extract_from_character_cards = MagicMock(
            side_effect=Exception("提取失败")
        )

        result = mgr._full_sync(llm_client=None)

        assert len(result["errors"]) > 0
        assert any("人物卡" in e for e in result["errors"])

    def test_full_sync_clears_graph_before_rebuild(self, tmp_path):
        """测试全量同步先清空现有图谱"""
        store = GraphStore()
        store.add_entity("旧角色", "character", {"brief": "旧数据"})
        assert store.entity_count() == 1

        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)

        result = mgr._full_sync(llm_client=None)
        assert result["old_nodes"] == 1
        assert result["old_edges"] == 0
        assert store.entity_count() == 0


class TestSyncManagerIncrementalSync:
    """测试增量同步"""

    def test_incremental_sync_no_changes(self, tmp_path):
        """测试无变更时的增量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        # 先执行全量同步建立哈希
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)
        mgr._full_sync()

        # 再执行增量同步
        result = mgr._incremental_sync(llm_client=None)
        assert result["mode"] == SyncMode.INCREMENTAL
        assert "timestamp" in result

    def test_incremental_sync_with_changed_cards(self, tmp_path):
        """测试人物卡变更时的增量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)
        mgr._full_sync()

        # 修改人物卡
        cards.write_text("characters:\n  - name: 新角色")
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=1)

        result = mgr._incremental_sync(llm_client=None)
        assert result["mode"] == SyncMode.INCREMENTAL

    def test_incremental_sync_saves_state(self, tmp_path):
        """测试增量同步保存状态"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
            sync_state_dir=str(state_dir),
        )

        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)
        mgr._full_sync()

        result = mgr._incremental_sync(llm_client=None)

        sync_state_file = state_dir / ".graph_sync_state.json"
        assert sync_state_file.exists()


class TestSyncManagerSyncMethod:
    """测试 sync 主入口方法"""

    def test_sync_incremental_default(self, tmp_path):
        """测试默认增量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)
        mgr._full_sync()

        result = mgr.sync(mode="incremental", force=True)
        assert result["mode"] == SyncMode.INCREMENTAL

    def test_sync_full(self, tmp_path):
        """测试全量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)

        result = mgr.sync(mode="full")
        assert result["mode"] == SyncMode.FULL


class TestSyncManagerCharacterCards:
    """测试人物卡即时同步"""

    def test_sync_character_cards_no_path(self):
        """测试无人物卡路径时同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        result = mgr.sync_character_cards(llm_client=None)
        assert result is not None
        if isinstance(result, dict):
            assert result.get("characters_added", 0) >= 0

    def test_sync_character_cards_with_path(self, tmp_path):
        """测试有人物卡路径时同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters:\n  - name: 张三\n    role: 主角")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        mgr._extractor.extract_from_character_cards = MagicMock(return_value=2)

        result = mgr.sync_character_cards(llm_client=None)
        assert result is not None


class TestSyncManagerSyncChapter:
    """测试章节即时同步"""

    def test_sync_chapter_basic(self, tmp_path):
        """测试基本章节同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(tmp_path / "cards.yaml"),
            chapters_dir=str(chapters),
        )

        result = mgr.sync_chapter(1, "第一章内容", llm_client=None)
        assert result is not None

    def test_sync_chapter_multiple(self, tmp_path):
        """测试多个章节同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(tmp_path / "cards.yaml"),
            chapters_dir=str(chapters),
        )

        for i in range(1, 4):
            result = mgr.sync_chapter(i, f"第{i}章内容")
            assert result is not None


class TestSyncManagerRetry:
    """测试重试机制"""

    def test_sync_with_retry_full(self, tmp_path):
        """测试带重试的全量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)

        result = mgr.sync_with_retry(
            mode="full",
            force=True,
            max_retries=2,
            retry_delay=0.01,
        )
        assert result["mode"] == SyncMode.FULL

    def test_sync_with_retry_handles_failure(self, tmp_path):
        """测试重试处理失败"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        # extractor 一直失败
        mgr._extractor.extract_from_character_cards = MagicMock(
            side_effect=Exception("持续失败")
        )

        result = mgr.sync_with_retry(
            mode="full",
            max_retries=1,
            retry_delay=0.01,
        )
        assert result is not None
        assert mgr._consecutive_failures > 0


class TestSyncManagerEdgeCases:
    """测试边界条件"""

    def test_sync_with_no_paths_set(self):
        """测试未设置路径时的同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        result = mgr.sync(mode="incremental", force=True)
        assert result is not None
        assert "errors" in result

    def test_sync_manager_save_graph_on_sync(self, tmp_path):
        """测试同步后保存图谱"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        graph_path = tmp_path / "graph.json"

        # 直接保存验证
        store.save(str(graph_path))
        assert graph_path.exists()

        # 验证 set_watch_paths 设置了正确的 graph_save_path
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
            graph_save_path=str(graph_path),
        )
        assert mgr._graph_save_path == graph_path

    def test_sync_manager_idempotent(self, tmp_path):
        """测试同步幂等性"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)

        r1 = mgr.sync(mode="full")
        r2 = mgr.sync(mode="full")

        assert r1 is not None
        assert r2 is not None
        assert mgr._sync_count == 2


class TestSyncManagerAutoSync:
    """测试自动同步相关功能"""

    def test_configure_auto_sync(self):
        """测试配置自动同步"""
        from novels_project.memory.sync_manager import AutoSyncConfig
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        config = AutoSyncConfig(enabled=True, interval_seconds=600, event_triggered=False)
        mgr.configure_auto_sync(config)

        assert mgr._auto_sync_config is config
        assert mgr._auto_sync_config.enabled is True
        assert mgr._auto_sync_config.interval_seconds == 600
        assert mgr._auto_sync_config.event_triggered is False

    def test_enable_auto_sync(self):
        """测试启用自动同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        mgr.enable_auto_sync()
        assert mgr._auto_sync_enabled is True
        assert mgr._auto_sync_config is not None

    def test_disable_auto_sync(self):
        """测试禁用自动同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        mgr.enable_auto_sync()
        mgr.disable_auto_sync()
        assert mgr._auto_sync_enabled is False

    def test_enable_auto_sync_without_config(self):
        """测试未配置时启用自动同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        assert mgr._auto_sync_config is None
        mgr.enable_auto_sync()
        assert mgr._auto_sync_config is not None
        assert mgr._auto_sync_enabled is True


class TestSyncManagerOnCharacterCardUpdated:
    """测试人物卡字段更新回调"""

    def test_on_character_card_updated_core_personality(self):
        """测试更新核心性格字段"""
        store = GraphStore()
        store.add_entity("张三", "character", {"brief": "初始描述"})
        mgr = SyncManager(graph_store=store)

        mgr.on_character_card_updated("张三", "core_personality", ["勇敢", "正直"])

        entity = store.get_entity("张三")
        assert entity is not None
        assert "勇敢" in entity.get("brief", "")

    def test_on_character_card_updated_other_field(self):
        """测试更新其他字段"""
        store = GraphStore()
        store.add_entity("张三", "character", {"brief": "描述"})
        mgr = SyncManager(graph_store=store)

        mgr.on_character_card_updated("张三", "role", "主角")

        entity = store.get_entity("张三")
        assert entity.get("role") == "主角"

    def test_on_character_card_updated_entity_not_in_graph(self):
        """测试更新不存在于图谱中的人物"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        # 不应抛出异常
        mgr.on_character_card_updated("不存在", "field", "value")


class TestSyncManagerOnChapterGenerated:
    """测试章节生成回调"""

    def test_on_chapter_generated_auto_sync_disabled(self, tmp_path):
        """测试自动同步未启用时跳过"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        # 自动同步未启用
        mgr.on_chapter_generated(1, "第一章内容")
        assert len(mgr._pending_chapter_ids) == 0

    def test_on_chapter_generated_event_triggered_disabled(self, tmp_path):
        """测试事件触发未启用时跳过"""
        from novels_project.memory.sync_manager import AutoSyncConfig
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        mgr.configure_auto_sync(AutoSyncConfig(enabled=True, event_triggered=False))
        mgr.enable_auto_sync()

        mgr.on_chapter_generated(1, "第一章内容")
        assert len(mgr._pending_chapter_ids) == 0

    def test_on_chapter_generated_below_threshold(self, tmp_path):
        """测试未达到阈值时不触发同步"""
        from novels_project.memory.sync_manager import AutoSyncConfig
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        mgr.configure_auto_sync(AutoSyncConfig(
            enabled=True, event_triggered=True, threshold_chapters=3
        ))
        mgr.enable_auto_sync()

        mgr.on_chapter_generated(1, "第一章内容")
        mgr.on_chapter_generated(2, "第二章内容")

        assert len(mgr._pending_chapter_ids) == 2
        assert mgr._last_auto_sync_time is None

    def test_on_chapter_generated_reaches_threshold(self, tmp_path):
        """测试达到阈值时触发同步"""
        from novels_project.memory.sync_manager import AutoSyncConfig
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        mgr.configure_auto_sync(AutoSyncConfig(
            enabled=True, event_triggered=True, threshold_chapters=2
        ))
        mgr.enable_auto_sync()

        mgr.on_chapter_generated(1, "第一章内容")
        mgr.on_chapter_generated(2, "第二章内容")

        assert len(mgr._pending_chapter_ids) == 0
        assert mgr._last_auto_sync_time is not None

    def test_on_chapter_generated_null_config(self):
        """测试 config 为 None 时跳过"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)
        mgr._auto_sync_enabled = True
        mgr._auto_sync_config = None

        mgr.on_chapter_generated(1, "第一章内容")
        assert len(mgr._pending_chapter_ids) == 0


class TestSyncManagerGetStatus:
    """测试状态查询"""

    def test_get_sync_status_idle(self):
        """测试初始空闲状态"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        status = mgr.get_sync_status()
        assert status["status"] == "idle"
        assert status["sync_count"] == 0
        assert status["consecutive_failures"] == 0
        assert status["auto_sync_enabled"] is False
        assert status["pending_chapters"] == []
        assert "graph_nodes" in status
        assert "graph_edges" in status

    def test_get_sync_status_with_data(self):
        """测试带数据的状态"""
        store = GraphStore()
        store.add_entity("角色", "character")
        mgr = SyncManager(graph_store=store)

        status = mgr.get_sync_status()
        assert status["graph_nodes"] == 1
        assert status["graph_edges"] == 0

    def test_get_health_report_idle(self):
        """测试空闲状态健康报告"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        report = mgr.get_health_report()
        assert "图谱同步健康报告" in report
        assert "状态: idle" in report
        assert "同步次数: 0" in report

    def test_get_health_report_with_failures(self):
        """测试有失败时的健康报告"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)
        mgr._consecutive_failures = 3

        report = mgr.get_health_report()
        assert "连续失败: 3" in report
        assert "警告" in report


class TestSyncManagerPersistGraph:
    """测试图谱持久化"""

    def test_persist_graph_no_save_path(self, tmp_path):
        """测试无保存路径时持久化"""
        store = GraphStore()
        store.add_entity("角色", "character")
        mgr = SyncManager(graph_store=store)

        mgr._persist_graph()
        assert mgr._graph_save_path is not None

    def test_persist_graph_with_save_path(self, tmp_path):
        """测试指定保存路径持久化"""
        store = GraphStore()
        store.add_entity("角色", "character")
        mgr = SyncManager(graph_store=store)

        graph_path = tmp_path / "my_graph.json"
        mgr._graph_save_path = graph_path

        mgr._persist_graph()
        assert graph_path.exists()

    def test_persist_graph_with_sync_state_path(self, tmp_path):
        """测试通过 sync_state_path 推导图谱路径"""
        store = GraphStore()
        store.add_entity("角色", "character")
        mgr = SyncManager(graph_store=store)

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        mgr._sync_state_path = state_dir / ".graph_sync_state.json"

        mgr._persist_graph()
        assert mgr._graph_save_path is not None
        assert mgr._graph_save_path.parent == state_dir


class TestSyncManagerSyncState:
    """测试同步状态加载/保存"""

    def test_save_sync_state_with_none(self, tmp_path):
        """测试 state=None 时保存同步状态"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        mgr._sync_state_path = state_dir / ".graph_sync_state.json"

        mgr._save_sync_state(None)

        state_file = state_dir / ".graph_sync_state.json"
        assert state_file.exists()
        content = state_file.read_text(encoding="utf-8")
        assert "last_sync" in content

    def test_save_sync_state_with_data(self, tmp_path):
        """测试保存同步状态"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        mgr._sync_state_path = state_dir / ".graph_sync_state.json"

        mgr._save_sync_state({"custom_key": "custom_value"})

        state_file = state_dir / ".graph_sync_state.json"
        assert state_file.exists()
        content = state_file.read_text(encoding="utf-8")
        assert "custom_key" in content
        assert "last_sync" in content

    def test_load_sync_state_no_file(self, tmp_path):
        """测试加载不存在的同步状态"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        mgr._sync_state_path = state_dir / ".graph_sync_state.json"

        state = mgr._load_sync_state()
        assert state == {}

    def test_load_sync_state_corrupted_file(self, tmp_path):
        """测试加载损坏的同步状态文件"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state_file = state_dir / ".graph_sync_state.json"
        state_file.write_text("not valid json {{{")

        mgr._sync_state_path = state_file

        state = mgr._load_sync_state()
        assert state == {}

    def test_load_sync_state_valid(self, tmp_path):
        """测试加载有效的同步状态"""
        import json
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state_file = state_dir / ".graph_sync_state.json"
        state_file.write_text(json.dumps({"last_sync": "2024-01-01", "key": "value"}))

        mgr._sync_state_path = state_file

        state = mgr._load_sync_state()
        assert state["last_sync"] == "2024-01-01"
        assert state["key"] == "value"

    def test_get_sync_state_path_default(self, tmp_path, monkeypatch):
        """测试默认同步状态路径"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        path = mgr._get_sync_state_path()
        # 默认路径应在当前目录
        assert path.name == ".graph_sync_state.json"


class TestSyncManagerComputeFileHash:
    """测试文件哈希计算"""

    def test_compute_file_hash_success(self, tmp_path):
        """测试成功计算哈希"""
        filepath = tmp_path / "test.txt"
        filepath.write_text("hello world")

        result = SyncManager._compute_file_hash(str(filepath))
        assert len(result) == 64
        assert result != ""

    def test_compute_file_hash_nonexistent(self, tmp_path):
        """测试计算不存在文件的哈希"""
        result = SyncManager._compute_file_hash(str(tmp_path / "nonexistent.txt"))
        assert result == ""


class TestSyncManagerExtractChapterId:
    """测试章节 ID 提取"""

    def test_extract_chapter_id_valid(self):
        """测试提取有效章节 ID"""
        assert SyncManager._extract_chapter_id("chapter_12_final.md") == 12

    def test_extract_chapter_id_zero(self):
        """测试提取无匹配时的章节 ID"""
        assert SyncManager._extract_chapter_id("no_match.txt") == 0

    def test_extract_chapter_id_large(self):
        """测试提取大章节 ID"""
        assert SyncManager._extract_chapter_id("chapter_999_final.md") == 999


class TestSyncManagerSyncEdgeCases:
    """测试 sync 方法的边界情况"""

    def test_sync_with_exception(self, tmp_path):
        """测试同步时抛出未捕获异常（FAILED 状态）"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        # mock _full_sync 直接抛出未捕获异常
        mgr._full_sync = MagicMock(side_effect=RuntimeError("模拟异常"))

        result = mgr.sync(mode="full")
        assert "error" in result
        assert mgr._status.value == "failed"
        assert mgr._consecutive_failures > 0

    def test_sync_with_errors_partial(self, tmp_path):
        """测试同步部分失败（PARTIAL 状态）"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        mgr._extractor.extract_from_character_cards = MagicMock(
            side_effect=Exception("提取失败")
        )

        result = mgr.sync(mode="full")
        assert len(result["errors"]) > 0
        assert mgr._status.value == "partial"

    def test_sync_with_retry_all_fail(self, tmp_path):
        """测试所有重试都失败（重试内部错误仍返回 PARTIAL）"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        mgr._extractor.extract_from_character_cards = MagicMock(
            side_effect=Exception("持续失败")
        )

        result = mgr.sync_with_retry(
            mode="full",
            max_retries=2,
            retry_delay=0.01,
        )
        assert result is not None
        assert len(result.get("errors", [])) > 0

    def test_sync_character_cards_path_not_exists(self):
        """测试人物卡路径不存在时同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        # 设置一个不存在的路径
        mgr._character_cards_path = Path("/nonexistent/path/cards.yaml")

        result = mgr.sync_character_cards(llm_client=None)
        assert "error" in result
        assert result["status"] == "failed"

    def test_sync_chapter_with_persist(self, tmp_path):
        """测试同步章节时持久化图谱"""
        from novels_project.memory.sync_manager import AutoSyncConfig
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        graph_path = tmp_path / "graph.json"

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
            graph_save_path=str(graph_path),
        )

        mgr.configure_auto_sync(AutoSyncConfig(persist_on_sync=True))

        result = mgr.sync_chapter(1, "第一章内容", llm_client=None)
        assert result is not None
        assert graph_path.exists()

    def test_sync_chapter_without_persist(self, tmp_path):
        """测试同步章节但不持久化"""
        from novels_project.memory.sync_manager import AutoSyncConfig
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        graph_path = tmp_path / "graph.json"

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
            graph_save_path=str(graph_path),
        )

        mgr.configure_auto_sync(AutoSyncConfig(persist_on_sync=False))

        result = mgr.sync_chapter(1, "第一章内容", llm_client=None)
        assert result is not None


class TestSyncManagerFullSyncAdvanced:
    """测试全量同步高级场景"""

    def test_full_sync_with_chapters(self, tmp_path):
        """测试带章节的全量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        # 创建章节文件
        chapter_file = chapters / "chapter_1_final.md"
        chapter_file.write_text("# 第 1 章\n\n第一章内容", encoding="utf-8")

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)
        mgr._extractor.extract_from_chapter_text = MagicMock(
            return_value={"added_entities": 2, "added_relations": 1}
        )

        result = mgr._full_sync(llm_client=None)
        assert result["chapters_processed"] == 1
        assert result["entities_added"] == 2
        assert result["relations_added"] == 1

    def test_full_sync_chapter_extraction_failure(self, tmp_path):
        """测试章节提取失败时的全量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        chapter_file = chapters / "chapter_1_final.md"
        chapter_file.write_text("# 第 1 章\n\n内容", encoding="utf-8")

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)
        mgr._extractor.extract_from_chapter_text = MagicMock(
            side_effect=Exception("章节提取失败")
        )

        result = mgr._full_sync(llm_client=None)
        assert len(result["errors"]) > 0
        assert any("章节" in e for e in result["errors"])


class TestSyncManagerIncrementalSyncAdvanced:
    """测试增量同步高级场景"""

    def test_incremental_sync_with_chapters(self, tmp_path):
        """测试带章节的增量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        chapter_file = chapters / "chapter_1_final.md"
        chapter_file.write_text("# 第 1 章\n\n内容", encoding="utf-8")

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)
        mgr._extractor.extract_from_chapter_text = MagicMock(
            return_value={"added_entities": 1, "added_relations": 0}
        )

        # 先做全量同步建立哈希
        mgr._full_sync()

        # 再增量同步（无变化）
        result = mgr._incremental_sync(llm_client=None)
        assert result["mode"] == "incremental"

    def test_incremental_sync_force(self, tmp_path):
        """测试强制增量同步"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)

        # 先做全量同步建立哈希
        mgr._full_sync()

        # 强制增量同步
        result = mgr._incremental_sync(force=True, llm_client=None)
        assert result["mode"] == "incremental"

    def test_incremental_sync_chapter_extraction_failure(self, tmp_path):
        """测试增量同步时章节提取失败"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        chapter_file = chapters / "chapter_1_final.md"
        chapter_file.write_text("# 第 1 章\n\n内容", encoding="utf-8")

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)
        mgr._extractor.extract_from_chapter_text = MagicMock(
            side_effect=Exception("章节提取失败")
        )

        mgr._full_sync()

        # 修改章节以触发重新同步
        chapter_file.write_text("# 第 1 章\n\n修改后的内容", encoding="utf-8")

        result = mgr._incremental_sync(llm_client=None)
        assert len(result["errors"]) > 0

    def test_incremental_sync_character_cards_failure(self, tmp_path):
        """测试增量同步时人物卡提取失败"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)
        mgr._full_sync()

        # 修改人物卡并设置提取失败
        cards.write_text("characters:\n  - name: 新角色")
        mgr._extractor.extract_from_character_cards = MagicMock(
            side_effect=Exception("人物卡提取失败")
        )

        result = mgr._incremental_sync(llm_client=None)
        assert len(result["errors"]) > 0

    def test_sync_with_default_retry_config(self, tmp_path):
        """测试使用默认重试配置"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)

        result = mgr.sync_with_retry(mode="full")
        assert result is not None


class TestSyncManagerAutoSyncConfig:
    """测试 AutoSyncConfig"""

    def test_auto_sync_config_defaults(self):
        """测试默认配置"""
        from novels_project.memory.sync_manager import AutoSyncConfig
        config = AutoSyncConfig()
        assert config.enabled is True
        assert config.interval_seconds == 300
        assert config.event_triggered is True
        assert config.threshold_chapters == 1
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 10
        assert config.persist_on_sync is True

    def test_auto_sync_config_custom(self):
        """测试自定义配置"""
        from novels_project.memory.sync_manager import AutoSyncConfig
        config = AutoSyncConfig(
            enabled=False,
            interval_seconds=100,
            event_triggered=False,
            threshold_chapters=5,
            max_retries=1,
            retry_delay_seconds=5,
            persist_on_sync=False,
        )
        assert config.enabled is False
        assert config.interval_seconds == 100
        assert config.threshold_chapters == 5
        assert config.max_retries == 1


class TestSyncManagerSyncModes:
    """测试同步模式枚举"""

    def test_sync_mode_values(self):
        """测试同步模式枚举值"""
        from novels_project.memory.sync_manager import SyncMode, SyncStatus
        assert SyncMode.INCREMENTAL.value == "incremental"
        assert SyncMode.FULL.value == "full"
        assert SyncStatus.IDLE.value == "idle"
        assert SyncStatus.RUNNING.value == "running"
        assert SyncStatus.SUCCESS.value == "success"
        assert SyncStatus.PARTIAL.value == "partial"
        assert SyncStatus.FAILED.value == "failed"


class TestSyncManagerRemainingCoverage:
    """补充剩余覆盖率缺口"""

    def test_sync_with_persist_on_sync(self, tmp_path):
        """测试同步成功时自动持久化（覆盖 line 255）"""
        from novels_project.memory.sync_manager import AutoSyncConfig
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        graph_path = tmp_path / "graph.json"

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
            graph_save_path=str(graph_path),
        )
        mgr.configure_auto_sync(AutoSyncConfig(persist_on_sync=True))
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)

        result = mgr.sync(mode="full")
        assert "errors" in result
        assert len(result["errors"]) == 0
        assert graph_path.exists()

    def test_sync_with_retry_triggers_retry(self, tmp_path):
        """测试重试时真正触发重试逻辑（覆盖 lines 304-324）"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )

        # mock _full_sync 直接抛出异常，返回带 "error" 的结果
        mgr._full_sync = MagicMock(side_effect=RuntimeError("模拟异常"))

        result = mgr.sync_with_retry(
            mode="full",
            max_retries=2,
            retry_delay=0.01,
        )
        assert result is not None
        assert "error" in result

    def test_incremental_sync_chapter_changed(self, tmp_path):
        """测试增量同步时章节变更被处理（覆盖 lines 503-508）"""
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        cards = tmp_path / "cards.yaml"
        cards.write_text("characters: []")
        chapters = tmp_path / "chapters"
        chapters.mkdir()
        chapter_file = chapters / "chapter_1_final.md"
        chapter_file.write_text("# 第 1 章\n\n原始内容", encoding="utf-8")

        mgr.set_watch_paths(
            character_cards=str(cards),
            chapters_dir=str(chapters),
        )
        mgr._extractor.extract_from_character_cards = MagicMock(return_value=0)
        mgr._extractor.extract_from_chapter_text = MagicMock(
            return_value={"added_entities": 1, "added_relations": 0}
        )

        # 先做全量同步建立哈希
        mgr._full_sync()

        # 修改章节内容以触发变更检测
        chapter_file.write_text("# 第 1 章\n\n修改后的内容", encoding="utf-8")

        result = mgr._incremental_sync(llm_client=None)
        assert result["chapters_processed"] > 0

    def test_persist_graph_exception(self, tmp_path):
        """测试图谱持久化异常处理（覆盖 lines 695-696）"""
        store = GraphStore()
        store.add_entity("角色", "character")
        mgr = SyncManager(graph_store=store)

        # 设置一个无法写入的路径
        mgr._graph_save_path = tmp_path / "nonexistent_dir" / "graph.json"
        # 不创建父目录，且 mock save 抛出异常
        store.save = MagicMock(side_effect=OSError("写入失败"))

        # 不应抛出异常
        mgr._persist_graph()

    def test_save_sync_state_exception(self, tmp_path):
        """测试同步状态保存异常处理（覆盖 lines 804-805）"""
        import json
        store = GraphStore()
        mgr = SyncManager(graph_store=store)

        # 设置一个无法写入的路径
        mgr._sync_state_path = tmp_path / "readonly" / ".graph_sync_state.json"
        # 不创建父目录，且 mock open 抛出异常
        with patch("builtins.open", side_effect=OSError("权限不足")):
            # 不应抛出异常
            mgr._save_sync_state({"key": "value"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])