"""
Memory Config API - 分层记忆配置管理

提供各 Agent 的 MemoryConfig 查询、修改、重置功能。
配置文件位于工作空间级: {project_root}/config/memory_config.yaml
"""
from __future__ import annotations

import yaml
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..project_config import get_config_dir
from ..memory.memory_config import MemoryConfig
from ..memory.memory_config_bundle import MemoryConfigBundle

router = APIRouter()


class AgentMemoryConfigRequest(BaseModel):
    """更新 agent 内存配置的请求体。"""
    config: dict = Field(..., description="MemoryConfig 字段的子集")


def _get_memory_config_path() -> Path:
    """获取 memory_config.yaml 路径（工作空间级）。"""
    return get_config_dir() / "memory_config.yaml"


def _load_bundle() -> MemoryConfigBundle:
    """加载配置包。"""
    path = _get_memory_config_path()
    return MemoryConfigBundle.load_from_yaml(path)


def _save_bundle(bundle: MemoryConfigBundle):
    """保存配置包到 YAML。"""
    path = _get_memory_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # 重建 YAML 结构
    data: dict = {}
    # global
    global_dict = bundle.global_config.__dict__.copy()
    # 只保存非默认值
    default_global = MemoryConfig()
    data["global"] = {
        k: v for k, v in global_dict.items() if v != getattr(default_global, k)
    }
    # agents
    if bundle.agent_configs:
        data["agents"] = {}
        for agent_name, agent_cfg in bundle.agent_configs.items():
            agent_dict = agent_cfg.__dict__.copy()
            data["agents"][agent_name] = {
                k: v for k, v in agent_dict.items() if v != getattr(default_global, k)
            }

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _validate_agent_config(agent_id: str, cfg: MemoryConfig):
    """校验 agent 配置，非法时抛出 400。"""
    errors = cfg.validate()
    if errors:
        detail = "; ".join(errors)
        raise HTTPException(status_code=400, detail=f"{agent_id} 配置验证失败: {detail}")


@router.get("/api/memory-config/agents/{agent_id}")
async def get_memory_config(agent_id: str):
    """获取指定 agent 的合并后内存配置。

    返回:
    - config: agent 的最终配置（global + agent 覆盖）
    - global_config: 全局默认配置
    - has_override: 该 agent 是否有显式配置
    """
    bundle = _load_bundle()
    resolved = bundle.get_resolved(agent_id)
    has_override = agent_id in bundle.agent_configs

    return {
        "agent_id": agent_id,
        "config": resolved.__dict__,
        "global_config": bundle.global_config.__dict__,
        "has_override": has_override,
    }


@router.put("/api/memory-config/agents/{agent_id}")
async def put_memory_config(agent_id: str, body: AgentMemoryConfigRequest):
    """更新指定 agent 的内存配置（深合并到 YAML）。

    请求体示例:
    {
      "config": {
        "max_summary_blocks": 5,
        "dialogue_compression_threshold": 0.75
      }
    }

    返回更新后的配置。
    """
    bundle = _load_bundle()

    # 仅允许已知字段
    valid_fields = set(MemoryConfig.__dataclass_fields__.keys())
    filtered = {k: v for k, v in body.config.items() if k in valid_fields}

    if not filtered:
        raise HTTPException(status_code=400, detail="未提供任何有效 MemoryConfig 字段")

    # 获取现有 agent 配置（或创建新）
    existing = bundle.agent_configs.get(agent_id, MemoryConfig())
    merged_dict = existing.__dict__.copy()
    merged_dict.update(filtered)
    new_agent_cfg = MemoryConfig(**merged_dict)

    # 验证配置合法性
    _validate_agent_config(agent_id, new_agent_cfg)

    # 更新并保存
    bundle.agent_configs[agent_id] = new_agent_cfg
    # 同步更新 resolved
    bundle.resolved[agent_id] = MemoryConfig.merge(bundle.global_config, new_agent_cfg)

    _save_bundle(bundle)

    return {
        "agent_id": agent_id,
        "config": new_agent_cfg.__dict__,
        "status": "updated",
    }


@router.post("/api/memory-config/agents/{agent_id}/reset")
async def reset_memory_config(agent_id: str):
    """重置指定 agent 的内存配置为全局默认（删除 agent 覆盖层）。

    返回重置后的配置（即 global_config）。
    """
    bundle = _load_bundle()

    if agent_id not in bundle.agent_configs:
        return {
            "agent_id": agent_id,
            "config": bundle.global_config.__dict__,
            "status": "already_default",
        }

    # 删除 agent 覆盖
    del bundle.agent_configs[agent_id]
    del bundle.resolved[agent_id]

    _save_bundle(bundle)

    return {
        "agent_id": agent_id,
        "config": bundle.global_config.__dict__,
        "status": "reset",
    }


@router.get("/api/memory-config/agents")
async def list_agent_configs():
    """列出所有已配置 agent 的配置摘要。"""
    bundle = _load_bundle()

    return {
        "global_config": bundle.global_config.__dict__,
        "agents": {
            agent_id: cfg.__dict__
            for agent_id, cfg in bundle.agent_configs.items()
        },
    }
