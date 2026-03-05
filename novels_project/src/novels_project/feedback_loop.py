"""
反馈闭环系统 - 记录校对发现的问题，供后续创作参考
"""
import json
import uuid
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


class FeedbackStore:
    """反馈存储管理"""
    
    def __init__(self, feedback_dir: str = "feedback"):
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_file = self.feedback_dir / "proofreading_feedback.yaml"
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """确保反馈文件存在"""
        if not self.feedback_file.exists():
            initial_data = {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0",
                    "description": "校对反馈库 - 记录发现的问题供后续创作参考"
                },
                "feedback_by_type": {},
                "feedback_by_character": {},
                "feedback_history": []
            }
            self._save(initial_data)
    
    def _load(self) -> Dict[str, Any]:
        """加载反馈数据"""
        with open(self.feedback_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _save(self, data: Dict[str, Any]):
        """保存反馈数据"""
        with open(self.feedback_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    def add_feedback(self, 
                     chapter_id: int,
                     issue_type: str,
                     character: Optional[str],
                     original_text: str,
                     problem: str,
                     fix_applied: str,
                     severity: str = "medium") -> str:
        """添加一条反馈记录"""
        data = self._load()
        
        feedback_id = f"FB_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{chapter_id}_{uuid.uuid4().hex[:6]}"
        
        feedback_entry = {
            "id": feedback_id,
            "chapter_id": chapter_id,
            "issue_type": issue_type,
            "character": character,
            "original_text": original_text,
            "problem": problem,
            "fix_applied": fix_applied,
            "severity": severity,
            "created_at": datetime.now().isoformat()
        }
        
        data["feedback_history"].append(feedback_entry)
        
        if issue_type not in data["feedback_by_type"]:
            data["feedback_by_type"][issue_type] = []
        data["feedback_by_type"][issue_type].append(feedback_id)
        
        if character:
            if character not in data["feedback_by_character"]:
                data["feedback_by_character"][character] = []
            data["feedback_by_character"][character].append(feedback_id)
        
        data["metadata"]["last_updated"] = datetime.now().isoformat()
        data["metadata"]["total_feedback"] = len(data["feedback_history"])
        
        self._save(data)
        return feedback_id
    
    def add_batch_feedback(self, chapter_id: int, issues: List[Dict[str, Any]]) -> int:
        """批量添加反馈"""
        count = 0
        for issue in issues:
            self.add_feedback(
                chapter_id=chapter_id,
                issue_type=issue.get("issue_type", "未知问题"),
                character=issue.get("character"),
                original_text=issue.get("original_text", ""),
                problem=issue.get("problem", ""),
                fix_applied=issue.get("fix_applied", ""),
                severity=issue.get("severity", "medium")
            )
            count += 1
        return count
    
    def get_feedback_by_type(self, issue_type: str) -> List[Dict[str, Any]]:
        """获取指定类型的所有反馈"""
        data = self._load()
        feedback_ids = data["feedback_by_type"].get(issue_type, [])
        id_to_feedback = {f["id"]: f for f in data["feedback_history"]}
        return [id_to_feedback[fid] for fid in feedback_ids if fid in id_to_feedback]
    
    def get_feedback_by_character(self, character: str) -> List[Dict[str, Any]]:
        """获取指定人物相关的所有反馈"""
        data = self._load()
        feedback_ids = data["feedback_by_character"].get(character, [])
        id_to_feedback = {f["id"]: f for f in data["feedback_history"]}
        return [id_to_feedback[fid] for fid in feedback_ids if fid in id_to_feedback]
    
    def get_recent_feedback(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的反馈"""
        data = self._load()
        history = data["feedback_history"]
        return history[-limit:] if history else []
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """获取反馈统计"""
        data = self._load()
        
        stats = {
            "total_feedback": len(data["feedback_history"]),
            "by_type": {},
            "by_character": {},
            "by_severity": {"high": 0, "medium": 0, "low": 0}
        }
        
        for issue_type, ids in data["feedback_by_type"].items():
            stats["by_type"][issue_type] = len(ids)
        
        for character, ids in data["feedback_by_character"].items():
            stats["by_character"][character] = len(ids)
        
        for feedback in data["feedback_history"]:
            severity = feedback.get("severity", "medium")
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1
        
        return stats
    
    def get_common_issues(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取最常见的问题类型"""
        stats = self.get_feedback_stats()
        by_type = stats["by_type"]
        sorted_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)
        return [{"issue_type": t, "count": c} for t, c in sorted_types[:limit]]


_feedback_store = None


def get_feedback_store() -> FeedbackStore:
    """获取反馈存储单例"""
    global _feedback_store
    if _feedback_store is None:
        project_root = Path(__file__).parent.parent.parent
        _feedback_store = FeedbackStore(feedback_dir=str(project_root / "feedback"))
    return _feedback_store
