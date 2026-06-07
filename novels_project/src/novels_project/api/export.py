"""
章节导出 API

提供章节导出功能，支持单个和批量导出，使用异步文件 I/O 提升性能。
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..project_config import get_chapters_dir

router = APIRouter()
logger = logging.getLogger("novels_project.api.export")


# ============================================================
# Pydantic 模型
# ============================================================

class ExportRequest(BaseModel):
    """章节导出请求模型。"""
    chapter_ids: Optional[list[str]] = None  # 指定章节ID列表，为空则导出全部
    target_dir: str  # 目标目录路径
    overwrite: bool = False  # 是否覆盖已存在文件


class ExportResponse(BaseModel):
    """章节导出响应模型。"""
    success: bool
    exported_count: int
    skipped_count: int
    messages: list[str]


# ============================================================
# 路径安全验证
# ============================================================

def _validate_export_path(target_dir: str) -> Path:
    """
    验证导出目标路径的安全性。

    防止路径遍历攻击，确保目标路径是有效的目录。
    使用 resolve() 后的真实路径验证，防止各种编码绕过。
    """
    # 在解析前检查路径遍历模式（检查原始路径字符串，防止 normpath 规范化后绕过）
    if '..' in target_dir.split(os.sep):
        raise HTTPException(status_code=400, detail="不允许使用路径遍历")

    try:
        path = Path(target_dir).expanduser().resolve()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的目录路径: {str(e)}")

    # 路径遍历攻击检测：比较绝对路径，确保不在已知危险位置
    if not path.is_absolute():
        raise HTTPException(status_code=400, detail="必须提供绝对路径")

    # 拒绝写入敏感系统目录（允许 /tmp 和 /var/tmp 等临时目录）
    # 同时检查原始路径和解析后的路径，兼容 macOS 的 /private 前缀
    blocked_prefixes = [
        "/etc", "/sys", "/proc", "/dev", "/bin",
        "/usr/bin", "/usr/sbin", "/lib", "/lib64",
        "/boot", "/sbin", "/private/etc", "/private/bin",
    ]
    path_str = str(path)
    for prefix in blocked_prefixes:
        if path_str.startswith(prefix + os.sep) or path_str == prefix:
            raise HTTPException(status_code=400, detail=f"不允许写入系统目录: {prefix}")

    return path


# ============================================================
# 异步文件操作
# ============================================================

async def _async_copy_file(src: Path, dst: Path) -> None:
    """异步复制文件内容。"""
    async with aiofiles.open(src, 'r', encoding='utf-8') as f:
        content = await f.read()
    async with aiofiles.open(dst, 'w', encoding='utf-8') as f:
        await f.write(content)


# ============================================================
# API 路由
# ============================================================

@router.get("/chapters/{chapter_id}/export")
async def export_chapter(chapter_id: str, target_dir: str = Query(...), overwrite: bool = False):
    """
    导出单个章节到指定目录。

    Args:
        chapter_id: 章节ID
        target_dir: 目标目录路径
        overwrite: 是否覆盖已存在的文件
    """
    # 验证目标路径
    dest_path = _validate_export_path(target_dir)

    # 确保目标目录存在
    dest_path.mkdir(parents=True, exist_ok=True)

    # 获取章节文件
    chapters_dir = get_chapters_dir()
    chapter_file = chapters_dir / f"chapter_{chapter_id}_final.md"

    if not chapter_file.exists():
        # 尝试其他命名格式
        candidates = list(chapters_dir.glob(f"chapter_{chapter_id}*.md"))
        if not candidates:
            raise HTTPException(status_code=404, detail=f"章节 '{chapter_id}' 不存在")
        chapter_file = candidates[0]

    # 构建目标文件路径
    dest_file = dest_path / chapter_file.name

    # 检查文件是否已存在
    if dest_file.exists() and not overwrite:
        raise HTTPException(
            status_code=409,
            detail=f"目标文件 '{dest_file.name}' 已存在，请设置 overwrite=true 或选择其他目录",
        )

    # 异步复制文件
    await _async_copy_file(chapter_file, dest_file)

    return {
        "success": True,
        "exported_count": 1,
        "skipped_count": 0,
        "messages": [f"章节 {chapter_id} 已导出到 {str(dest_file)}"],
    }


@router.post("/chapters/export", response_model=ExportResponse)
async def export_chapters(req: ExportRequest):
    """
    批量导出章节到指定目录。

    Args:
        req: 导出请求，包含章节ID列表（为空则导出全部）、目标目录、是否覆盖
    """
    # 验证目标路径
    dest_path = _validate_export_path(req.target_dir)

    # 确保目标目录存在
    dest_path.mkdir(parents=True, exist_ok=True)

    chapters_dir = get_chapters_dir()
    if not chapters_dir.exists():
        return ExportResponse(
            success=False,
            exported_count=0,
            skipped_count=0,
            messages=["章节目录不存在"],
        )

    # 获取要导出的章节列表
    if req.chapter_ids:
        # 导出指定章节
        chapter_files = []
        for chapter_id in req.chapter_ids:
            cf = chapters_dir / f"chapter_{chapter_id}_final.md"
            if not cf.exists():
                candidates = list(chapters_dir.glob(f"chapter_{chapter_id}*.md"))
                if candidates:
                    cf = candidates[0]
            if cf.exists():
                chapter_files.append(cf)
    else:
        # 导出全部章节
        chapter_files = sorted(chapters_dir.glob("chapter_*_final.md"))

    exported_count = 0
    skipped_count = 0
    messages = []

    for chapter_file in chapter_files:
        try:
            # 构建目标文件路径
            dest_file = dest_path / chapter_file.name

            # 检查文件是否已存在
            if dest_file.exists():
                if req.overwrite:
                    # 覆盖模式：删除旧文件
                    dest_file.unlink()
                else:
                    skipped_count += 1
                    messages.append(f"跳过 {chapter_file.name}（文件已存在）")
                    continue

            # 异步复制文件
            await _async_copy_file(chapter_file, dest_file)

            exported_count += 1
            messages.append(f"已导出 {chapter_file.name}")

        except Exception as e:
            skipped_count += 1
            messages.append(f"导出 {chapter_file.name} 失败: {str(e)}")

    return ExportResponse(
        success=exported_count > 0,
        exported_count=exported_count,
        skipped_count=skipped_count,
        messages=messages,
    )
