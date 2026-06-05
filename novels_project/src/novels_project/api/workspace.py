"""
工作空间管理 API

管理多个小说项目（工作空间），每个工作空间对应一个独立的小说项目目录。
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..project_config import (
    get_project_root, set_project_root, get_project_info,
    format_project_status, check_project_ready,
)

router = APIRouter()

# 工作空间注册表目录（记录所有工作空间）
# 优先使用项目内的注册表，避免权限问题
WORKSPACE_REGISTRY_DIR = Path(__file__).parent.parent.parent.parent / "workspaces_registry"


def _ensure_registry():
    """确保注册表目录存在。"""
    WORKSPACE_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def _get_registry_path(workspace_name: str) -> Path:
    """获取工作空间注册文件路径。"""
    return WORKSPACE_REGISTRY_DIR / f"{workspace_name}.json"


def _list_registered_workspaces() -> list[dict]:
    """列出所有已注册的工作空间。"""
    _ensure_registry()
    workspaces = []
    for f in sorted(WORKSPACE_REGISTRY_DIR.glob("*.json")):
        import json
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            workspaces.append(data)
        except Exception:
            continue
    return workspaces


def _save_workspace_registry(name: str, path: str):
    """保存工作空间注册信息。"""
    import json
    _ensure_registry()
    data = {
        "name": name,
        "path": str(path),
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }
    with open(_get_registry_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _remove_workspace_registry(name: str):
    """删除工作空间注册信息。"""
    reg_path = _get_registry_path(name)
    if reg_path.exists():
        reg_path.unlink()


# ============================================================
# Pydantic 模型
# ============================================================

class WorkspaceCreate(BaseModel):
    name: str
    base_path: Optional[str] = None  # 默认在 ~/novels/ 下创建


class WorkspaceRename(BaseModel):
    new_name: str


class WorkspaceInfo(BaseModel):
    name: str
    path: str
    is_current: bool = False
    chapters_count: int = 0
    is_ready: bool = False


# ============================================================
# API 端点
# ============================================================

@router.get("/", response_model=list[WorkspaceInfo])
async def list_workspaces():
    """获取所有工作空间列表。"""
    workspaces = _list_registered_workspaces()
    current_root = str(get_project_root())

    result = []
    for ws in workspaces:
        ws_path = Path(ws["path"])
        is_current = str(ws_path.resolve()) == str(Path(current_root).resolve())
        chapters_count = 0
        is_ready = False

        if ws_path.exists():
            chapters_dir = ws_path / "output" / "chapters"
            if chapters_dir.exists():
                chapters_count = len(list(chapters_dir.glob("chapter_*_final.md")))
            is_ready = (ws_path / "config" / "character_base_cards.yaml").exists()

        result.append(WorkspaceInfo(
            name=ws["name"],
            path=ws["path"],
            is_current=is_current,
            chapters_count=chapters_count,
            is_ready=is_ready,
        ))

    # 如果当前项目不在注册表中，也显示
    if not any(w["path"] == current_root for w in workspaces):
        current = Path(current_root)
        result.append(WorkspaceInfo(
            name=current.name,
            path=current_root,
            is_current=True,
            chapters_count=len(list((current / "output" / "chapters").glob("chapter_*_final.md")))
                if (current / "output" / "chapters").exists() else 0,
            is_ready=(current / "config" / "character_base_cards.yaml").exists(),
        ))

    return result


@router.post("/")
async def create_workspace(data: WorkspaceCreate):
    """创建新工作空间。"""
    base = Path(data.base_path) if data.base_path else Path.home() / "novels"
    base.mkdir(parents=True, exist_ok=True)

    workspace_path = base / data.name
    if workspace_path.exists():
        raise HTTPException(status_code=400, detail=f"工作空间 '{data.name}' 已存在")

    # 创建目录结构
    dirs = [
        "config",
        "output/chapters",
        "output/chapter_summaries",
        "samples",
        "sessions",
        "feedback",
        "graph",
        "DESIGN/PROMPTS",
    ]
    for d in dirs:
        (workspace_path / d).mkdir(parents=True, exist_ok=True)

    # 注册
    _save_workspace_registry(data.name, str(workspace_path.resolve()))

    return {"name": data.name, "path": str(workspace_path.resolve()), "status": "created"}


@router.put("/{name}")
async def rename_workspace(name: str, data: WorkspaceRename):
    """重命名工作空间。"""
    old_reg = _get_registry_path(name)
    if not old_reg.exists():
        raise HTTPException(status_code=404, detail=f"工作空间 '{name}' 不存在")

    import json
    with open(old_reg, "r", encoding="utf-8") as f:
        ws_data = json.load(f)

    old_path = Path(ws_data["path"])
    if not old_path.exists():
        raise HTTPException(status_code=404, detail=f"工作空间目录 '{ws_data['path']}' 不存在")

    # 重命名目录
    new_path = old_path.parent / data.new_name
    if new_path.exists():
        raise HTTPException(status_code=400, detail=f"目标目录 '{data.new_name}' 已存在")

    old_path.rename(new_path)

    # 更新注册表
    _remove_workspace_registry(name)
    _save_workspace_registry(data.new_name, str(new_path.resolve()))

    return {"name": data.new_name, "path": str(new_path.resolve()), "old_name": name}


@router.delete("/{name}")
async def delete_workspace(name: str):
    """删除工作空间。"""
    reg_path = _get_registry_path(name)
    if not reg_path.exists():
        raise HTTPException(status_code=404, detail=f"工作空间 '{name}' 不存在")

    import json
    with open(reg_path, "r", encoding="utf-8") as f:
        ws_data = json.load(f)

    ws_path = Path(ws_data["path"])
    if ws_path.exists():
        shutil.rmtree(ws_path)

    _remove_workspace_registry(name)

    return {"name": name, "status": "deleted"}


@router.post("/{name}/switch")
async def switch_workspace(name: str):
    """切换到指定工作空间。"""
    reg_path = _get_registry_path(name)
    if not reg_path.exists():
        raise HTTPException(status_code=404, detail=f"工作空间 '{name}' 不存在")

    import json
    with open(reg_path, "r", encoding="utf-8") as f:
        ws_data = json.load(f)

    new_root = Path(ws_data["path"])
    if not new_root.exists():
        raise HTTPException(status_code=404, detail=f"工作空间目录 '{ws_data['path']}' 不存在")

    set_project_root(new_root)
    info = get_project_info()

    return {
        "name": name,
        "path": str(new_root.resolve()),
        "status": "switched",
        "info": info,
    }


@router.get("/{name}/status")
async def workspace_status(name: str):
    """获取工作空间状态。"""
    reg_path = _get_registry_path(name)
    if not reg_path.exists():
        raise HTTPException(status_code=404, detail=f"工作空间 '{name}' 不存在")

    import json
    with open(reg_path, "r", encoding="utf-8") as f:
        ws_data = json.load(f)

    ws_path = Path(ws_data["path"])
    if not ws_path.exists():
        raise HTTPException(status_code=404, detail=f"工作空间目录不存在")

    # 临时切换获取信息
    original_root = get_project_root()
    try:
        set_project_root(ws_path)
        info = get_project_info()
        is_ready, missing = check_project_ready()
    finally:
        set_project_root(original_root)

    return {
        "name": name,
        "path": str(ws_path.resolve()),
        "info": info,
        "is_ready": is_ready,
        "missing": missing,
    }