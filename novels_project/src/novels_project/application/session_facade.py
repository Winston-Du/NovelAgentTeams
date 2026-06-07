"""
统一会话管理 - 屏蔽 CLI Session + SessionStore 与 Web session 存储差异

统一会话创建、恢复、消息追加、turn 元数据写入、usage 汇总、workspace 绑定。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..session import Session, ConversationMessage, MessageRole, TextBlock
from ..session_store import SessionStore, generate_session_id
from ..project_config import get_sessions_dir
from .contracts import SessionStatus, SessionInfo

logger = logging.getLogger("novels_project.session_facade")


def _get_writable_sessions_dir() -> Path:
    """获取可写入的会话目录，优先使用工作空间，回退到项目目录。"""
    ws_dir = get_sessions_dir()
    try:
        ws_dir.mkdir(parents=True, exist_ok=True)
        # 测试写入权限
        test_file = ws_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
        return ws_dir
    except (PermissionError, OSError):
        logger.warning("工作空间会话目录不可写: %s，回退到项目目录", ws_dir)
        # 回退到项目目录
        from ..project_config import _get_package_root
        fallback = _get_package_root() / "sessions"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


class SessionFacade:
    """统一会话管理门面。"""

    def __init__(self, sessions_dir: Optional[Path] = None):
        if sessions_dir is None:
            sessions_dir = _get_writable_sessions_dir()
        self._store = SessionStore(sessions_dir)
        self._workspace: str = "default"

    def set_workspace(self, workspace: str):
        self._workspace = workspace

    def create_session(
        self,
        client_type: str = "web",
        scene: str = "creative_assistant",
        user_id: str = "",
    ) -> tuple[str, Session]:
        """创建新会话，返回 (session_id, session)。"""
        session_id = generate_session_id()
        session = Session()
        self._store.save(session, session_id)
        logger.info(
            "[SessionFacade] session_created id=%s client=%s scene=%s",
            session_id, client_type, scene,
        )
        return session_id, session

    def restore_or_create(
        self,
        session_id: Optional[str] = None,
        client_type: str = "web",
        scene: str = "creative_assistant",
    ) -> tuple[str, Session]:
        """恢复已有会话或创建新会话。"""
        if session_id:
            session = self._store.load(session_id)
            if session is not None:
                logger.info("[SessionFacade] session_restored id=%s", session_id)
                return session_id, session
        return self.create_session(client_type, scene)

    def save(self, session: Session, session_id: str):
        self._store.save(session, session_id)

    def load(self, session_id: str) -> Optional[Session]:
        return self._store.load(session_id)

    def get_messages(self, session_id: str) -> list[dict]:
        """获取会话消息列表。"""
        session = self._store.load(session_id)
        if session is None:
            return []
        return [
            {
                "role": msg.role.value,
                "content": msg.get_text(),
                "blocks": [b.__dict__ if hasattr(b, "__dict__") else str(b) for b in msg.blocks],
            }
            for msg in session.messages
        ]

    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """获取会话信息。"""
        session = self._store.load(session_id)
        if session is None:
            return None
        # 获取文件元数据
        sessions = self._store.list_sessions()
        meta = next((s for s in sessions if s["session_id"] == session_id), {})
        return SessionInfo(
            session_id=session_id,
            workspace=self._workspace,
            client_type="web",
            scene="creative_assistant",
            status=SessionStatus.ACTIVE,
            created_at=meta.get("saved_at", ""),
            updated_at=meta.get("saved_at", ""),
            message_count=session.message_count(),
        )

    def list_sessions(self) -> list[dict]:
        return self._store.list_sessions()


# 全局单例
_session_facade: Optional[SessionFacade] = None


def get_session_facade() -> SessionFacade:
    global _session_facade
    if _session_facade is None:
        _session_facade = SessionFacade()
    return _session_facade