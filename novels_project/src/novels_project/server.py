"""
NovelAgentTeams Web Server - FastAPI 后端服务

启动方式: PYTHONPATH=src novels-server
访问地址: http://127.0.0.1:8000
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api import (
    workspace_router,
    content_router,
    agent_router,
    settings_router,
    memory_router,
)
from .project_config import set_project_root, get_project_root, ensure_directories


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    app = FastAPI(
        title="NovelAgentTeams",
        description="AI 小说创作系统 Web 管理平台",
        version="0.3.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(workspace_router, prefix="/api/workspaces", tags=["工作空间"])
    app.include_router(content_router, prefix="/api/content", tags=["内容管理"])
    app.include_router(agent_router, prefix="/api/agents", tags=["Agent 配置"])
    app.include_router(settings_router, prefix="/api/settings", tags=["系统设置"])
    app.include_router(memory_router, prefix="/api/memory", tags=["记忆管理"])

    # 健康检查
    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.3.0"}

    # 前端静态文件（生产模式）
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # favicon / vite.svg
        @app.get("/vite.svg", include_in_schema=False)
        async def serve_vite_svg():
            svg_path = frontend_dist / "vite.svg"
            if svg_path.exists():
                return FileResponse(svg_path)

        # SPA fallback: 所有非 API 路径返回 index.html
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            # 已由 API 路由处理的路径不会到达这里
            index_path = frontend_dist / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return {"detail": "Frontend not built. Run: cd frontend && npm run build"}

    return app


def main():
    """启动 Web 服务器。"""
    import uvicorn

    # 设置项目根目录
    set_project_root()
    ensure_directories()

    project_root = get_project_root()
    print(f"[Server] 项目根目录: {project_root}")
    print(f"[Server] 启动地址: http://127.0.0.1:8000")

    host = os.getenv("NOVEL_HOST", "127.0.0.1")
    port = int(os.getenv("NOVEL_PORT", "8000"))

    uvicorn.run(
        "novels_project.server:create_app",
        host=host,
        port=port,
        reload=True,
        factory=True,
    )


if __name__ == "__main__":
    main()