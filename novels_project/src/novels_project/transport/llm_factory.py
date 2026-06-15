"""
统一 LLM 客户端工厂 - 消除 CLI 与 Web API 双路径创建的重复

为 CLI 和 Web API 提供统一的 OpenAICompatibleClient 创建入口，
优先级：显式参数 → model_providers.yaml → 环境变量 → ConfigurationError

Usage:
    from ..transport.llm_factory import LLMClientFactory
    client = LLMClientFactory.create(provider_id="gemini", api_key="...")
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("novels_project.transport.llm_factory")

# 模块级客户端缓存，按 provider_id 隔离
_instances: dict[str, Any] = {}


class ConfigurationError(Exception):
    """LLM 客户端配置错误。"""
    pass


def create_llm_client(
    provider_id: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    default_model: Optional[str] = None,
) -> Any:
    """
    创建统一的 LLM 客户端。

    优先级（从高到低）：
    1. 显式参数（api_key / base_url / default_model）
    2. model_providers.yaml 中的供应商配置（通过 provider_id 匹配）
    3. 环境变量：COMPANY_API_KEY + API_BASE_URL + MODEL_NAME
    4. 抛出 ConfigurationError

    Args:
        provider_id: 模型供应商 ID（如 "gemini", "openai"），用于匹配 yaml 配置
        api_key: 显式 API Key（优先级最高）
        base_url: 显式 Base URL
        default_model: 显式默认模型名

    Returns:
        OpenAICompatibleClient 实例

    Raises:
        ConfigurationError: 所有配置来源均不可用时抛出
    """
    from ..api_client import OpenAICompatibleClient

    # ---- 1. 显式参数 ----
    if api_key and base_url:
        model = default_model or "gemini-3-pro"
        logger.info("[LLMClientFactory] 使用显式参数创建客户端 | model=%s", model)
        return OpenAICompatibleClient(
            base_url=base_url, api_key=api_key, default_model=model,
        )

    # ---- 2. model_providers.yaml ----
    if provider_id:
        try:
            from ..api.settings import load_model_providers, _resolve_api_key

            providers_data = load_model_providers()
            providers = providers_data.get("providers", {})
            if provider_id in providers:
                info = providers[provider_id]
                resolved_key = _resolve_api_key(info.get("api_key", ""))
                if resolved_key:
                    models = info.get("models", [])
                    model = default_model or (models[0] if models else "gemini-3-pro")
                    client = OpenAICompatibleClient(
                        base_url=info.get("base_url", ""),
                        api_key=resolved_key,
                        default_model=model,
                    )
                    logger.info(
                        "[LLMClientFactory] 使用 yaml 供应商配置 | provider=%s model=%s",
                        provider_id, model,
                    )
                    return client
        except ImportError:
            logger.debug("[LLMClientFactory] 无法导入 api.settings，跳过 yaml 配置")

    # ---- 3. 环境变量 ----
    env_key = os.getenv("COMPANY_API_KEY")
    if env_key:
        env_url = os.getenv(
            "API_BASE_URL", "http://ai-service.tal.com/openai-compatible/v1"
        )
        env_model = default_model or os.getenv("MODEL_NAME", "gemini-3-pro")
        logger.info("[LLMClientFactory] 使用环境变量创建客户端 | model=%s", env_model)
        return OpenAICompatibleClient(
            base_url=env_url, api_key=env_key, default_model=env_model,
        )

    # ---- 4. 不可配置 ----
    raise ConfigurationError(
        "无法创建 LLM 客户端：未提供 api_key、provider_id 匹配失败、"
        "且 COMPANY_API_KEY 环境变量未设置"
    )


def get_cached_client(provider_id: str) -> Optional[Any]:
    """获取缓存的 LLM 客户端实例。"""
    return _instances.get(provider_id)


def invalidate_cache(provider_id: Optional[str] = None):
    """清除客户端缓存，支持模型热切换。"""
    global _instances
    if provider_id:
        _instances.pop(provider_id, None)
        logger.info("[LLMClientFactory] 缓存已清除 | provider=%s", provider_id)
    else:
        _instances.clear()
        logger.info("[LLMClientFactory] 全部缓存已清除")
