"""
分层异常体系 - 统一异常处理框架

提供项目级的异常基类和分类，确保异常传播路径可控，
消除裸 except Exception 导致的静默错误吞没问题。
"""
from __future__ import annotations


class NovelAgentError(Exception):
    """项目所有异常的基类。"""
    pass


class ConfigError(NovelAgentError):
    """配置相关错误：配置缺失、格式错误、路径无效。"""
    pass


class LLMError(NovelAgentError):
    """LLM 调用相关错误：API Key 过期、网络超时、速率限制。
    
    不可恢复，必须向上传播，禁止静默吞掉。
    """
    pass


class EntityExtractionError(NovelAgentError):
    """实体提取错误：LLM 输出解析失败、人物卡格式异常。
    
    可降级，在 LLM 输出格式异常时回退到规则模式。
    """
    pass


class CharacterCardsError(NovelAgentError):
    """人物卡相关错误：文件未找到、YAML 解析失败、格式不符合预期。"""
    pass


# ---------------------------------------------------------------------------
# 可降级异常白名单
# 当 LLM 调用成功但输出无法解析时，不应崩溃，而应降级为规则模式
# ---------------------------------------------------------------------------
import json

FALLBACK_EXCEPTIONS = (
    json.JSONDecodeError,
    ValueError,
    KeyError,
    TypeError,
    EntityExtractionError,
)
