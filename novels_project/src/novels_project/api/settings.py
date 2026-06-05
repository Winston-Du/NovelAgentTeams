"""
系统设置 API

管理系统级别的配置：主题、语言、通知、数据备份与恢复。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..project_config import get_project_root, get_system_config_dir, get_output_dir

router = APIRouter()


def _get_settings_path() -> Path:
    """获取系统设置文件路径（系统级，独立于工作空间）。"""
    return get_system_config_dir() / "system_settings.yaml"


def _load_settings() -> dict:
    """加载系统设置。"""
    path = _get_settings_path()
    if not path.exists():
        return _get_default_settings()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # 合并默认值
    defaults = _get_default_settings()
    defaults.update(data)
    return defaults


def _save_settings(data: dict):
    """保存系统设置。"""
    path = _get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def _get_default_settings() -> dict:
    """获取默认设置。"""
    return {
        "theme": "light",
        "language": "zh",
        "notifications": {
            "enabled": True,
            "chapter_complete": True,
            "sync_complete": True,
            "backup_reminder": True,
        },
        "editor": {
            "font_size": 14,
            "line_height": 1.8,
            "auto_save": True,
            "auto_save_interval": 60,
        },
        "backup": {
            "auto_backup": False,
            "backup_interval_hours": 24,
            "max_backups": 10,
            "backup_dir": str(get_project_root() / "backups"),
        },
        "vector_retrieval": {
            "enabled": False,
            "api_endpoint": "https://api.siliconflow.cn/v1",
            "api_key": "${siliconflow_api}",
            "timeout": 60,
            "embedding_model": "bge-large-zh",
        },
    }


# ============================================================
# Pydantic 模型
# ============================================================

class VectorRetrievalConfig(BaseModel):
    enabled: Optional[bool] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    timeout: Optional[int] = None
    embedding_model: Optional[str] = None


class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    notifications: Optional[dict] = None
    editor: Optional[dict] = None
    backup: Optional[dict] = None
    vector_retrieval: Optional[VectorRetrievalConfig] = None


class BackupInfo(BaseModel):
    name: str
    path: str
    size: int
    created_at: str


# ============================================================
# API 端点
# ============================================================

@router.get("/")
async def get_settings():
    """获取系统设置。"""
    return _load_settings()


@router.put("/")
async def update_settings(update: SettingsUpdate):
    """更新系统设置。"""
    current = _load_settings()
    update_dict = update.model_dump(exclude_none=True)

    for key, value in update_dict.items():
        if isinstance(value, dict) and isinstance(current.get(key), dict):
            current[key].update(value)
        else:
            current[key] = value

    _save_settings(current)
    return {"status": "updated", "settings": current}


# ============================================================
# 数据备份与恢复
# ============================================================

def _get_backup_dir() -> Path:
    """获取备份目录。"""
    settings = _load_settings()
    backup_dir = settings.get("backup", {}).get("backup_dir", "")
    if backup_dir:
        return Path(backup_dir)
    return get_project_root() / "backups"


@router.get("/backups")
async def list_backups():
    """获取备份列表。"""
    backup_dir = _get_backup_dir()
    if not backup_dir.exists():
        return []

    backups = []
    for bf in sorted(backup_dir.glob("*.zip"), reverse=True):
        stat = bf.stat()
        backups.append(BackupInfo(
            name=bf.name,
            path=str(bf.resolve()),
            size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        ))

    return backups


@router.post("/backup")
async def create_backup():
    """创建数据备份。"""
    backup_dir = _get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)

    project_root = get_project_root()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"

    # 创建临时备份目录
    temp_dir = backup_dir / backup_name
    temp_dir.mkdir(exist_ok=True)

    try:
        # 复制关键数据
        dirs_to_backup = ["config", "output", "sessions", "graph", "feedback"]
        for d in dirs_to_backup:
            src = project_root / d
            if src.exists():
                shutil.copytree(src, temp_dir / d, dirs_exist_ok=True)

        # 打包为 zip
        zip_path = backup_dir / f"{backup_name}.zip"
        shutil.make_archive(str(backup_dir / backup_name), "zip", str(temp_dir))

        # 清理临时目录
        shutil.rmtree(temp_dir)

        # 清理旧备份
        max_backups = _load_settings().get("backup", {}).get("max_backups", 10)
        existing = sorted(backup_dir.glob("*.zip"))
        while len(existing) > max_backups:
            existing[0].unlink()
            existing.pop(0)

        return {
            "name": f"{backup_name}.zip",
            "path": str(zip_path.resolve()),
            "size": zip_path.stat().st_size,
            "created_at": datetime.now().isoformat(),
        }
    except Exception as e:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=f"备份失败: {str(e)}")


@router.post("/restore")
async def restore_backup(backup_name: str):
    """恢复数据备份。"""
    backup_dir = _get_backup_dir()
    backup_path = backup_dir / backup_name

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail=f"备份文件 '{backup_name}' 不存在")

    project_root = get_project_root()

    try:
        # 解压到临时目录
        import zipfile
        temp_dir = backup_dir / f"_restore_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        temp_dir.mkdir(exist_ok=True)

        with zipfile.ZipFile(backup_path, "r") as zf:
            zf.extractall(temp_dir)

        # 恢复数据
        dirs_to_restore = ["config", "output", "sessions", "graph", "feedback"]
        for d in dirs_to_restore:
            src = temp_dir / d
            if src.exists():
                dst = project_root / d
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)

        shutil.rmtree(temp_dir)
        return {"status": "restored", "backup": backup_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")


# ============================================================
# 模型供应商配置
# ============================================================

def _get_model_providers_path() -> Path:
    """获取模型供应商配置文件路径（系统级，独立于工作空间）。"""
    return get_system_config_dir() / "model_providers.yaml"


def _resolve_api_key(api_key: str) -> str:
    """解析 API Key 中的环境变量引用（${ENV_VAR} 格式）。"""
    pattern = re.compile(r'\$\{(\w+)\}')
    def replacer(match):
        return os.environ.get(match.group(1), match.group(0))
    return pattern.sub(replacer, api_key)


def _get_default_model_providers() -> dict:
    """获取默认模型供应商配置。"""
    return {
        "providers": {
            "openai": {
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
                "api_key": "${OPENAI_API_KEY}",
                "protocol": "OpenAI 兼容 (Chat Completions)",
                "models": [
                    {
                        "id": "gpt-4o",
                        "name": "GPT-4o",
                        "max_tokens": 4096,
                        "context_window": 128000,
                        "supports_streaming": True,
                        "supports_json_mode": True,
                    },
                    {
                        "id": "gpt-4-turbo",
                        "name": "GPT-4 Turbo",
                        "max_tokens": 4096,
                        "context_window": 128000,
                        "supports_streaming": True,
                        "supports_json_mode": True,
                    },
                ],
                "advanced": {
                    "temperature": 0.7,
                    "top_p": 1.0,
                    "max_tokens": 4096,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                    "timeout": 120,
                    "system_prompt": "",
                },
            },
            "deepseek": {
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "${DEEPSEEK_API_KEY}",
                "protocol": "OpenAI 兼容 (Chat Completions)",
                "models": [
                    {
                        "id": "deepseek-chat",
                        "name": "DeepSeek Chat",
                        "max_tokens": 4096,
                        "context_window": 65536,
                        "supports_streaming": True,
                        "supports_json_mode": False,
                    },
                ],
                "advanced": {
                    "temperature": 0.7,
                    "top_p": 1.0,
                    "max_tokens": 4096,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                    "timeout": 120,
                    "system_prompt": "",
                },
            },
        }
    }


def load_model_providers(resolve_keys: bool = False) -> dict:
    """加载模型供应商配置。"""
    path = _get_model_providers_path()
    if not path.exists():
        return _get_default_model_providers()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if resolve_keys:
        providers = data.get("providers", {})
        for provider in providers.values():
            if "api_key" in provider:
                provider["api_key"] = _resolve_api_key(provider["api_key"])
    return data


def _save_model_providers(data: dict):
    """保存模型供应商配置。"""
    path = _get_model_providers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


# ============================================================
# Pydantic 模型 - 模型供应商
# ============================================================

class ModelInfo(BaseModel):
    id: str
    name: str
    max_tokens: int = 4096
    context_window: int = 128000
    supports_streaming: bool = True
    supports_json_mode: bool = False


class AdvancedConfig(BaseModel):
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 4096
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 120
    system_prompt: str = ""


class ProviderCreate(BaseModel):
    name: str
    base_url: str
    api_key: str
    protocol: str = "OpenAI 兼容 (Chat Completions)"
    models: list[ModelInfo] = []
    advanced: Optional[AdvancedConfig] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    protocol: Optional[str] = None
    models: Optional[list[ModelInfo]] = None
    advanced: Optional[AdvancedConfig] = None


class ProviderTestRequest(BaseModel):
    base_url: str
    api_key: str
    model_id: str = ""
    protocol: str = "OpenAI 兼容 (Chat Completions)"


# ============================================================
# API 端点 - 模型供应商
# ============================================================

@router.get("/models")
async def get_model_providers(resolve_keys: bool = False):
    """获取所有模型供应商配置。"""
    return load_model_providers(resolve_keys=resolve_keys)


@router.post("/models")
async def create_model_provider(provider: ProviderCreate):
    """创建或更新模型供应商配置。"""
    data = load_model_providers()
    providers = data.get("providers", {})

    # 使用 provider name 的小写下划线形式作为 key
    key = provider.name.lower().replace(" ", "_")

    provider_dict = {
        "name": provider.name,
        "base_url": provider.base_url,
        "api_key": provider.api_key,
        "protocol": provider.protocol or "OpenAI 兼容 (Chat Completions)",
        "models": [m.model_dump() for m in provider.models],
    }
    if provider.advanced:
        provider_dict["advanced"] = provider.advanced.model_dump()

    providers[key] = provider_dict
    data["providers"] = providers
    _save_model_providers(data)
    return {"status": "created", "key": key, "provider": providers[key]}


@router.put("/models/{provider_name}")
async def update_model_provider(provider_name: str, update: ProviderUpdate):
    """更新指定模型供应商配置。"""
    data = load_model_providers()
    providers = data.get("providers", {})

    if provider_name not in providers:
        raise HTTPException(status_code=404, detail=f"模型供应商 '{provider_name}' 不存在")

    update_dict = update.model_dump(exclude_none=True)
    if "models" in update_dict:
        update_dict["models"] = [m.model_dump() for m in update.models]
    if "advanced" in update_dict and update.advanced:
        update_dict["advanced"] = update.advanced.model_dump()

    providers[provider_name].update(update_dict)
    _save_model_providers(data)
    return {"status": "updated", "key": provider_name, "provider": providers[provider_name]}


@router.delete("/models/{provider_name}")
async def delete_model_provider(provider_name: str):
    """删除指定模型供应商。"""
    data = load_model_providers()
    providers = data.get("providers", {})

    if provider_name not in providers:
        raise HTTPException(status_code=404, detail=f"模型供应商 '{provider_name}' 不存在")

    deleted = providers.pop(provider_name)
    _save_model_providers(data)
    return {"status": "deleted", "key": provider_name, "provider": deleted}


# ============================================================
# 向量检索 API 配置
# ============================================================

class VectorProviderTestRequest(BaseModel):
    api_endpoint: str
    api_key: str
    model_id: str
    timeout: int = 60


@router.post("/vector/test")
async def test_vector_provider(request: VectorProviderTestRequest):
    """测试向量检索 API 连接。验证 Embedding 模型是否可用。"""
    import json
    import urllib.request
    import urllib.error

    resolved_key = _resolve_api_key(request.api_key)

    if not request.api_endpoint:
        raise HTTPException(status_code=400, detail="API 端点不能为空")

    url = request.api_endpoint.rstrip("/") + "/embeddings"

    test_text = "测试文本用于验证 Embedding API"
    payload = {
        "model": request.model_id,
        "input": test_text,
    }

    req_body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {resolved_key}",
    }

    http_req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")

    try:
        timeout_val = request.timeout
        with urllib.request.urlopen(http_req, timeout=timeout_val) as response:
            response_body = response.read().decode("utf-8")
            resp_data = json.loads(response_body)

            if "data" in resp_data and isinstance(resp_data["data"], list) and len(resp_data["data"]) > 0:
                embedding = resp_data["data"][0]
                embedding_dim = len(embedding.get("embedding", []))
                
                return {
                    "status": "success",
                    "http_status": response.status,
                    "message": f"连接测试成功！Embedding 维度: {embedding_dim}",
                    "embedding_dimension": embedding_dim,
                    "model": resp_data.get("model", request.model_id),
                }
            else:
                raise HTTPException(status_code=500, detail="响应格式异常")

    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_data = json.loads(err_body)
            err_msg = err_data.get("error", {}).get("message", str(e))
        except Exception:
            err_msg = str(e)
        raise HTTPException(status_code=e.code, detail=f"HTTP {e.code}: {err_msg}")
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"连接失败: {str(e.reason)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


@router.post("/models/test")
async def test_model_provider(request: ProviderTestRequest):
    """测试模型供应商连接。发送简单消息测试 API 是否可用。"""
    import json
    import urllib.request
    import urllib.error

    resolved_key = _resolve_api_key(request.api_key)

    if not request.base_url:
        raise HTTPException(status_code=400, detail="Base URL 不能为空")

    url = request.base_url.rstrip("/") + "/chat/completions"

    test_model = request.model_id or "gpt-4o-mini"
    payload = {
        "model": test_model,
        "messages": [
            {"role": "system", "content": "你是一个测试助手。"},
            {"role": "user", "content": "请回复'测试成功'两个字。"},
        ],
        "max_tokens": 50,
        "temperature": 0.0,
    }

    req_body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {resolved_key}",
    }

    http_req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")

    try:
        timeout_val = 30
        with urllib.request.urlopen(http_req, timeout=timeout_val) as response:
            response_body = response.read().decode("utf-8")
            resp_data = json.loads(response_body)

            # 尝试获取响应内容
            content = ""
            try:
                content = resp_data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                content = "响应格式异常"

            usage = resp_data.get("usage", {})
            return {
                "status": "success",
                "http_status": response.status,
                "response": content.strip() if content else "空响应",
                "usage": usage,
                "model": resp_data.get("model", test_model),
                "latency_ms": 0,
            }
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_data = json.loads(err_body)
            err_msg = err_data.get("error", {}).get("message", str(e))
        except Exception:
            err_msg = str(e)
        raise HTTPException(status_code=e.code, detail=f"HTTP {e.code}: {err_msg}")
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"连接失败: {str(e.reason)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")