"""
Agent 配置 API

管理各 Agent 的独立配置：基本参数、行为模式、交互规则、运行状态。
"""
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..project_config import get_system_config_dir
from .settings import load_model_providers

router = APIRouter()

# 默认 Agent 配置
DEFAULT_AGENTS = {
    "master": {
        "name": "主控 Agent",
        "role": "主编",
        "description": "负责协调各子 Agent，管理整体创作流程",
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 4096,
        "enabled": True,
        "system_prompt": "",
        "rules": {
            "max_turns": 10,
            "auto_approve": False,
            "require_review": True,
        },
    },
    "character_designer": {
        "name": "人物设计师",
        "role": "character_designer",
        "description": "负责人物设定、性格塑造、关系设计",
        "model": "gpt-4o",
        "temperature": 0.8,
        "max_tokens": 4096,
        "enabled": True,
        "system_prompt": "",
        "rules": {
            "consistency_check": True,
            "relation_validation": True,
        },
    },
    "plot_writer": {
        "name": "剧情撰写员",
        "role": "plot_writer",
        "description": "负责剧情创作、章节撰写",
        "model": "gpt-4o",
        "temperature": 0.9,
        "max_tokens": 8192,
        "enabled": True,
        "system_prompt": "",
        "rules": {
            "min_words": 2000,
            "max_words": 5000,
            "foreshadowing_required": True,
        },
    },
    "proofreader": {
        "name": "资深校对",
        "role": "proofreader",
        "description": "负责内容校对、一致性检查、质量把关",
        "model": "gpt-4o",
        "temperature": 0.3,
        "max_tokens": 4096,
        "enabled": True,
        "system_prompt": "",
        "rules": {
            "check_consistency": True,
            "check_grammar": True,
            "check_foreshadowing": True,
            "auto_fix": False,
        },
    },
}


def _get_agent_config_path() -> Path:
    """获取 Agent 配置文件路径（系统级，独立于工作空间）。"""
    return get_system_config_dir() / "agent_config.yaml"


def _load_agent_config() -> dict:
    """加载 Agent 配置。"""
    path = _get_agent_config_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_agent_config(data: dict):
    """保存 Agent 配置。"""
    path = _get_agent_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def _get_merged_config() -> dict:
    """获取合并后的 Agent 配置（默认 + 用户自定义）。"""
    default = DEFAULT_AGENTS.copy()
    user_config = _load_agent_config()
    for key in user_config:
        if key in default:
            default[key].update(user_config[key])
        else:
            default[key] = user_config[key]
    return default


# ============================================================
# Pydantic 模型
# ============================================================

class AgentConfigUpdate(BaseModel):
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    enabled: Optional[bool] = None
    system_prompt: Optional[str] = None
    rules: Optional[dict] = None


class AgentToggle(BaseModel):
    enabled: bool


# ============================================================
# API 端点
# ============================================================

@router.get("/")
async def get_agents():
    """获取所有 Agent 配置。"""
    return _get_merged_config()


@router.get("/models")
async def get_agent_models():
    """获取可用的模型供应商列表（供 Agent 配置页使用）。"""
    return load_model_providers()


@router.get("/{name}")
async def get_agent(name: str):
    """获取指定 Agent 配置。"""
    config = _get_merged_config()
    if name not in config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' 不存在")
    return config[name]


@router.put("/{name}")
async def update_agent(name: str, update: AgentConfigUpdate):
    """更新指定 Agent 配置。"""
    config = _get_merged_config()
    if name not in config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' 不存在")

    # 合并更新
    user_config = _load_agent_config()
    if name not in user_config:
        user_config[name] = {}

    update_dict = update.model_dump(exclude_none=True)
    user_config[name].update(update_dict)
    _save_agent_config(user_config)

    return {"name": name, "status": "updated", "config": _get_merged_config()[name]}


@router.put("/{name}/toggle")
async def toggle_agent(name: str, toggle: AgentToggle):
    """启用/禁用 Agent。"""
    config = _get_merged_config()
    if name not in config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' 不存在")

    user_config = _load_agent_config()
    if name not in user_config:
        user_config[name] = {}
    user_config[name]["enabled"] = toggle.enabled
    _save_agent_config(user_config)

    return {"name": name, "enabled": toggle.enabled}


@router.get("/{name}/status")
async def get_agent_status(name: str):
    """获取 Agent 运行状态。"""
    config = _get_merged_config()
    if name not in config:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' 不存在")

    agent = config[name]
    return {
        "name": name,
        "enabled": agent.get("enabled", True),
        "model": agent.get("model", "unknown"),
        "temperature": agent.get("temperature", 0.7),
        "status": "ready" if agent.get("enabled", True) else "disabled",
    }