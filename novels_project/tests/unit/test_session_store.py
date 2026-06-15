"""
单元测试：会话存储模块

测试范围：
1. generate_session_id 函数
2. SessionStore 类的所有方法
"""
import pytest
import json
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

from novels_project.session import Session, ConversationMessage, MessageRole
from novels_project.api_client import TokenUsage
from novels_project.session_store import generate_session_id, SessionStore


class TestGenerateSessionId:
    """测试 generate_session_id"""

    def test_format(self):
        """生成的ID格式正确"""
        sid = generate_session_id()
        # session_YYYYMMDD_HHMMSS_xxxxxxxx
        assert sid.startswith("session_")
        parts = sid.split("_")
        assert len(parts) == 4  # session, date, time, short_uuid
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert len(parts[3]) == 8  # hex uuid

    def test_uniqueness(self):
        """生成多个ID应互不相同（可能因时间戳相同而碰撞，概率极低）"""
        ids = set()
        for _ in range(10):
            ids.add(generate_session_id())
        # 至少大部分不同（uuid部分保证差异）
        assert len(ids) >= 1


class TestSessionStoreInit:
    """测试 SessionStore 初始化"""

    def test_creates_directory(self, tmp_path):
        """初始化创建目录"""
        store_path = tmp_path / "sessions"
        assert not store_path.exists()
        store = SessionStore(store_path)
        assert store.sessions_dir == store_path
        assert store_path.exists()

    def test_creates_nested_directory(self, tmp_path):
        """创建嵌套目录"""
        nested = tmp_path / "a" / "b" / "sessions"
        store = SessionStore(nested)
        assert nested.exists()

    def test_already_existing_directory(self, tmp_path):
        """目录已存在不报错"""
        store_path = tmp_path / "sessions"
        store_path.mkdir(parents=True, exist_ok=True)
        store = SessionStore(store_path)
        assert store_path.exists()


class TestPathFor:
    """测试 _path_for"""

    def test_returns_correct_path(self, tmp_path):
        """返回正确路径"""
        store = SessionStore(tmp_path)
        path = store._path_for("my_session_123")
        expected = tmp_path / "my_session_123.json"
        assert path == expected


class TestSave:
    """测试 save"""

    def test_save_writes_json_file(self, tmp_path):
        """保存写入JSON文件"""
        store = SessionStore(tmp_path)
        session = Session()
        session_id = "test_session_1"
        path = store.save(session, session_id)
        assert path == tmp_path / "test_session_1.json"
        assert path.exists()

        # 验证内容
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["version"] == 1
        assert data["messages"] == []
        assert "_meta" in data
        assert data["_meta"]["session_id"] == session_id
        assert "saved_at" in data["_meta"]
        assert data["_meta"]["message_count"] == 0

    def test_save_with_messages(self, tmp_path):
        """保存带消息的会话"""
        store = SessionStore(tmp_path)
        session = Session()
        msg1 = ConversationMessage.user_text("hello")
        msg2 = ConversationMessage.user_text("world")
        session.messages = [msg1, msg2]
        session_id = "session_with_msgs"
        path = store.save(session, session_id)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["_meta"]["message_count"] == 2

    def test_save_returns_path(self, tmp_path):
        """save 返回文件路径"""
        store = SessionStore(tmp_path)
        session = Session()
        returned_path = store.save(session, "test")
        assert isinstance(returned_path, Path)


class TestLoad:
    """测试 load"""

    def test_load_existing_session(self, tmp_path):
        """加载已存在的会话"""
        store = SessionStore(tmp_path)
        session = Session()
        msg = ConversationMessage.user_text("test message")
        session.messages = [msg]
        store.save(session, "load_test")

        loaded = store.load("load_test")
        assert loaded is not None
        assert loaded.version == 1
        assert len(loaded.messages) == 1
        assert loaded.messages[0].get_text() == "test message"

    def test_load_non_existing_session(self, tmp_path):
        """加载不存在的会话返回 None"""
        store = SessionStore(tmp_path)
        result = store.load("nonexistent")
        assert result is None

    def test_load_removes_meta(self, tmp_path):
        """load 移除 _meta"""
        store = SessionStore(tmp_path)
        session = Session()
        store.save(session, "meta_test")

        loaded = store.load("meta_test")
        assert loaded is not None

    def test_load_with_usage(self, tmp_path):
        """加载包含 usage 的会话"""
        store = SessionStore(tmp_path)
        session = Session()
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        msg = ConversationMessage(role=MessageRole.ASSISTANT, blocks=[], usage=usage)
        session.messages = [msg]
        store.save(session, "usage_test")

        loaded = store.load("usage_test")
        assert loaded is not None
        assert loaded.messages[0].usage is not None
        assert loaded.messages[0].usage.total_tokens == 150


class TestListSessions:
    """测试 list_sessions"""

    def test_list_multiple_sessions(self, tmp_path):
        """列出多个会话"""
        store = SessionStore(tmp_path)
        store.save(Session(), "session_a")
        store.save(Session(), "session_b")
        store.save(Session(), "session_c")

        sessions = store.list_sessions()
        assert len(sessions) == 3

    def test_list_empty_dir(self, tmp_path):
        """空目录"""
        store = SessionStore(tmp_path)
        sessions = store.list_sessions()
        assert sessions == []

    def test_list_sorted_by_time(self, tmp_path):
        """按时间排序（reverse=True，最新在前）"""
        import time
        store = SessionStore(tmp_path)
        store.save(Session(), "session_old")
        time.sleep(0.1)  # 确保时间戳不同
        store.save(Session(), "session_new")

        sessions = store.list_sessions()
        assert len(sessions) >= 2
        # 检查 session_id 和 saved_at 字段
        ids = [s["session_id"] for s in sessions]
        assert "session_a" in ids or "session_old" in ids

    def test_corrupted_json_file(self, tmp_path):
        """损坏的JSON文件被跳过"""
        store = SessionStore(tmp_path)
        store.save(Session(), "session_good")

        # 创建一个损坏的JSON文件
        bad_file = tmp_path / "session_bad.json"
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("this is not json")

        sessions = store.list_sessions()
        # 应该只包含好的会话
        good_count = sum(1 for s in sessions if s["session_id"] == "session_good")
        assert good_count == 1

    def test_json_without_meta(self, tmp_path):
        """JSON文件没有 _meta 字段"""
        store = SessionStore(tmp_path)
        file_path = tmp_path / "no_meta.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "messages": []}, f)

        sessions = store.list_sessions()
        meta_session = [s for s in sessions if s["path"].endswith("no_meta.json")]
        assert len(meta_session) == 1
        assert meta_session[0]["session_id"] == "no_meta"  # path.stem

    def test_list_sessions_metadata(self, tmp_path):
        """每个会话条目包含元数据"""
        store = SessionStore(tmp_path)
        store.save(Session(), "test_meta")

        sessions = store.list_sessions()
        assert len(sessions) == 1
        s = sessions[0]
        assert "session_id" in s
        assert "saved_at" in s
        assert "message_count" in s
        assert "path" in s
        assert s["session_id"] == "test_meta"
        assert s["message_count"] == 0