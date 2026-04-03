"""
Layer 2: Persistence - Session Store

Handles saving/loading/listing sessions as JSON files.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .session import Session


def generate_session_id() -> str:
    """Generate a unique session ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"session_{timestamp}_{short_uuid}"


class SessionStore:
    """JSON file-based session persistence."""

    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session: Session, session_id: str) -> Path:
        """Save session to JSON file. Returns the file path."""
        path = self._path_for(session_id)
        data = session.to_dict()
        data["_meta"] = {
            "session_id": session_id,
            "saved_at": datetime.now().isoformat(),
            "message_count": session.message_count(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def load(self, session_id: str) -> Optional[Session]:
        """Load session from JSON file."""
        path = self._path_for(session_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Remove metadata before parsing
        data.pop("_meta", None)
        return Session.from_dict(data)

    def list_sessions(self) -> list[dict]:
        """List all saved sessions with metadata."""
        sessions = []
        for path in sorted(self.sessions_dir.glob("*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("_meta", {})
                sessions.append({
                    "session_id": meta.get("session_id", path.stem),
                    "saved_at": meta.get("saved_at", "unknown"),
                    "message_count": meta.get("message_count", 0),
                    "path": str(path),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def _path_for(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"
