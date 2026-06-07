"""
NovelAgentTeams Web Server - FastAPI 后端服务

启动方式: PYTHONPATH=src novels-server
访问地址: http://127.0.0.1:8000
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .api import (
    workspace_router,
    content_router,
    export_router,
    agent_router,
    settings_router,
    memory_router,
    retrieval_router,
)
from .interfaces.web.agent_sessions_api import router as agent_sessions_router
from .project_config import set_project_root, get_project_root, ensure_directories

logger = logging.getLogger("novels_project.server")


def _get_api_key() -> str | None:
    """Get the configured API key for authentication (empty → no auth)."""
    return os.getenv("NOVEL_API_KEY", "").strip() or None


# Public paths that don't need authentication
_PUBLIC_PATHS = {
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}


async def _auth_middleware(request: Request, call_next):
    """Simple API key authentication middleware.

    When NOVEL_API_KEY is set, all non-public routes require
    an X-API-Key header matching the configured key.
    When not set, authentication is disabled (development mode).
    """
    api_key = _get_api_key()

    # No auth required for public paths or when auth is disabled
    if api_key is None or request.url.path in _PUBLIC_PATHS:
        return await call_next(request)

    # Also allow static assets through
    if request.url.path.startswith("/assets/") or request.url.path == "/vite.svg":
        return await call_next(request)

    # Check API key header
    provided_key = request.headers.get("X-API-Key", "")
    if provided_key != api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    return await call_next(request)


async def _global_exception_handler(request: Request, call_next):
    """Catch unhandled exceptions and return consistent JSON errors."""
    try:
        return await call_next(request)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error_type": type(e).__name__},
        )


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    app = FastAPI(
        title="NovelAgentTeams",
        description="AI 小说创作系统 Web 管理平台",
        version="0.3.0",
    )

    # CORS — restrict to known origins in production
    allowed_origins_raw = os.getenv(
        "NOVEL_CORS_ORIGINS",
        "http://localhost:5173,http://localhost:8000,http://127.0.0.1:8000",
    )
    allow_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    )

    # Authentication middleware (optional — enabled when NOVEL_API_KEY is set)
    app.middleware("http")(_auth_middleware)

    # Global exception handler
    app.middleware("http")(_global_exception_handler)

    # 注册路由
    app.include_router(workspace_router, prefix="/api/workspaces", tags=["工作空间"])
    app.include_router(content_router, prefix="/api/content", tags=["内容管理"])
    app.include_router(export_router, prefix="/api/content", tags=["章节导出"])
    app.include_router(agent_router, prefix="/api/agents", tags=["Agent 配置"])
    app.include_router(settings_router, prefix="/api/settings", tags=["系统设置"])
    app.include_router(memory_router, prefix="/api/memory", tags=["记忆管理"])
    app.include_router(retrieval_router, tags=["向量检索"])
    # Phase 2: 统一 Agent 会话 API
    app.include_router(agent_sessions_router, tags=["Agent 会话"])

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
    logger.info("项目根目录: %s", project_root)
    logger.info("启动地址: http://127.0.0.1:8000")

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