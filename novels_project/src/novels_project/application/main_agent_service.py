"""
主 Agent 统一服务 - 全局唯一入口

Web 与 CLI 唯一允许直接调用的主 Agent 服务，不允许端侧绕过它直接操作 runtime。
负责一次 turn 的完整生命周期：会话恢复 → 路由 → 执行 → 流式输出 → 收尾。
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional, AsyncIterator

from ..api_client import (
    AssistantEvent, TextDelta, ToolUseEvent, UsageEvent,
)
from ..session import Session
from ..tool_spec import ToolRegistry, build_builtin_tool_registry
from ..tool_executor import MainToolExecutor
from ..runtime import ConversationRuntime, TurnSummary
from ..agents import (
    AgentRunner, register_agent_tools,
    build_save_chapter_tool, build_load_chapter_data_tool,
)
from ..system_prompt import build_main_agent_system_prompt
from ..transport.llm_factory import create_llm_client, ConfigurationError

from .contracts import (
    CreateSessionRequest, HandleTurnRequest, SessionInfo,
    EventType,
)
from .trace_service import get_trace_service, TraceService
from .session_facade import get_session_facade, SessionFacade
from .capability_router import get_capability_router, CapabilityRouter
from .stream_bridge import StreamBridge, StreamingApiClient

logger = logging.getLogger("novels_project.main_agent_service")


class MainAgentService:
    """全局唯一主 Agent 服务入口。

    统一接收 Web/CLI 对话请求，标准化请求上下文，
    组织一次 turn 的完整生命周期。
    """

    def __init__(self):
        self._trace: TraceService = get_trace_service()
        self._sessions: SessionFacade = get_session_facade()
        self._router: CapabilityRouter = get_capability_router()
        # 默认模型（当没有配置时回退）
        self._model: str = os.getenv("MODEL_NAME", "gemini-3-pro")
        # 从 settings 加载的模型配置
        self._provider_id: Optional[str] = None
        self._provider_api_key: Optional[str] = None
        self._provider_base_url: Optional[str] = None

        # 运行时组件（惰性初始化）
        self._api_client: Optional[StreamingApiClient] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._agent_runner: Optional[AgentRunner] = None
        self._system_prompt: Optional[str] = None

    def _load_model_config(self):
        """从 settings 加载模型供应商配置。"""
        try:
            from ..api.settings import load_model_providers, _resolve_api_key
            providers_data = load_model_providers(resolve_keys=True)
            providers = providers_data.get("providers", {})

            logger.info("[MainAgentService] 加载模型配置，找到 %d 个供应商", len(providers))

            # 找到第一个有有效 api_key 的供应商
            for provider_id, info in providers.items():
                raw_key = info.get("api_key", "")
                api_key = _resolve_api_key(raw_key)
                has_key = bool(api_key and len(api_key) > 10)
                logger.info(
                    "[MainAgentService] 检查供应商 %s: base_url=%s, has_key=%s, key_prefix=%s",
                    provider_id, info.get("base_url", ""), has_key, raw_key[:20] if raw_key else "empty",
                )
                if has_key:
                    self._provider_id = provider_id
                    self._provider_api_key = api_key
                    self._provider_base_url = info.get("base_url", "")
                    models = info.get("models", [])
                    if models:
                        self._model = models[0].get("id", self._model)
                    logger.info(
                        "[MainAgentService] 使用配置供应商: %s, model=%s",
                        provider_id, self._model,
                    )
                    return

            # 没有有效配置，回退到环境变量
            logger.info("[MainAgentService] 无有效模型配置，回退到环境变量")
        except Exception as e:
            logger.warning("[MainAgentService] 加载模型配置失败: %s", e)

    def reload_model_config(self):
        """重新加载模型配置（支持热切换）。"""
        self._provider_id = None
        self._provider_api_key = None
        self._provider_base_url = None
        self._model = os.getenv("MODEL_NAME", "gemini-3-pro")
        if self._api_client is not None:
            self._api_client = None
        self._load_model_config()
        logger.info("[MainAgentService] 模型配置已重新加载")

    def _ensure_runtime(self):
        """确保运行时组件已初始化。"""
        if self._api_client is not None:
            return

        # 先尝试加载 settings 中的模型配置
        self._load_model_config()

        try:
            if self._provider_id and self._provider_api_key and self._provider_base_url:
                # 使用 settings 配置的供应商（直接传参，绕过 yaml 解析）
                logger.info(
                    "[MainAgentService] 使用显式参数创建 LLM 客户端 | provider=%s model=%s",
                    self._provider_id, self._model,
                )
                base_client = create_llm_client(
                    api_key=self._provider_api_key,
                    base_url=self._provider_base_url,
                    default_model=self._model,
                )
            else:
                # 回退到原有逻辑
                base_client = create_llm_client(default_model=self._model)
        except ConfigurationError as e:
            logger.warning("[MainAgentService] LLM 客户端创建失败: %s", e)
            raise

        self._api_client = StreamingApiClient(
            base_url=base_client.base_url,
            api_key=base_client.api_key,
            default_model=base_client.default_model or self._model,
        )
        self._system_prompt = build_main_agent_system_prompt()

        # 工具注册
        self._tool_registry = build_builtin_tool_registry()
        register_agent_tools(self._tool_registry)
        self._tool_registry.register(build_save_chapter_tool())
        self._tool_registry.register(build_load_chapter_data_tool())

        # Agent Runner
        self._agent_runner = AgentRunner(self._api_client)
        self._agent_runner.set_builtin_registry(self._tool_registry)

    def create_session(self, request: CreateSessionRequest) -> tuple[str, Session]:
        """创建新会话。"""
        session_id, session = self._sessions.create_session(
            client_type=request.client_type,
            scene=request.scene,
            user_id=request.user_id,
        )
        return session_id, session

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """获取会话信息。"""
        return self._sessions.get_session_info(session_id)

    def list_messages(self, session_id: str) -> list[dict]:
        """获取会话消息历史。"""
        return self._sessions.get_messages(session_id)

    async def handle_turn(
        self,
        session_id: str,
        request: HandleTurnRequest,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        """处理一次对话轮次，返回 SSE 事件流。

        这是 Web 端的主入口。CLI 端使用同步版本 handle_turn_sync()。
        """
        trace_id = self._trace.generate_trace_id()
        turn_id = self._trace.generate_turn_id()
        logger.info(
            "[MainAgentService] turn 接收 | session=%s trace=%s turn=%s stream=%s input_preview=%s",
            session_id, trace_id, turn_id, stream,
            (request.input or "")[:120],
        )

        # 确保运行时可用
        try:
            self._ensure_runtime()
        except Exception as e:
            logger.warning("[MainAgentService] 运行时初始化失败: %s", e)
            yield self._trace.build_event(
                EventType.TURN_FAILED, trace_id, session_id, turn_id,
                {"error": f"LLM 服务未配置: {str(e)}", "error_type": "CONFIGURATION_ERROR"},
            ).to_sse()
            return

        # 恢复会话
        session = self._sessions.load(session_id)
        if session is None:
            logger.warning("[MainAgentService] 会话不存在 | session=%s", session_id)
            yield self._trace.build_event(
                EventType.TURN_FAILED, trace_id, session_id, turn_id,
                {"error": f"会话不存在: {session_id}"},
            ).to_sse()
            return

        # 路由分类
        route_type = self._router.classify(request.input, request.context)
        logger.info(
            "[MainAgentService] 路由分类完成 | session=%s route=%s",
            session_id, route_type.value,
        )
        yield self._trace.build_event(
            EventType.ROUTE_SELECTED, trace_id, session_id, turn_id,
            {"route_type": route_type.value},
        ).to_sse()

        yield self._trace.build_event(
            EventType.TURN_STARTED, trace_id, session_id, turn_id,
            {"input": request.input[:200]},
        ).to_sse()

        # 创建流式桥接（每个 turn 独立，避免并发冲突）
        bridge = StreamBridge(self._trace)
        loop = asyncio.get_event_loop()

        # 设置事件回调，将 LLM 文本增量发送到 SSE
        # 使用闭包捕获当前 turn 的 bridge 和 loop，避免并发覆盖
        def on_event(event: AssistantEvent):
            if isinstance(event, TextDelta):
                asyncio.run_coroutine_threadsafe(
                    bridge.send_delta(event.text, trace_id, session_id, turn_id),
                    loop,
                )
            elif isinstance(event, ToolUseEvent):
                logger.info(
                    "[MainAgentService] 模型触发工具 | name=%s id=%s",
                    event.name, event.id,
                )
                asyncio.run_coroutine_threadsafe(
                    bridge.put_event(bridge.create_event(
                        EventType.TOOL_CALLED, trace_id, session_id, turn_id,
                        {"tool_name": event.name},
                    )),
                    loop,
                )
            elif isinstance(event, UsageEvent):
                logger.info(
                    "[MainAgentService] usage 事件 | in=%d out=%d total=%d",
                    event.usage.input_tokens, event.usage.output_tokens,
                    event.usage.total_tokens,
                )
                asyncio.run_coroutine_threadsafe(
                    bridge.put_event(bridge.create_event(
                        EventType.USAGE_UPDATED, trace_id, session_id, turn_id,
                        {"input_tokens": event.usage.input_tokens,
                         "output_tokens": event.usage.output_tokens},
                    )),
                    loop,
                )

        # 为当前 turn 创建独立的 API 客户端包装器，避免并发回调覆盖
        turn_client = StreamingApiClient(
            base_url=self._api_client.base_url,
            api_key=self._api_client.api_key,
            default_model=self._api_client.default_model or self._model,
        )
        turn_client.set_event_callback(on_event)

        # 构建运行时
        try:
            tool_executor = MainToolExecutor(self._tool_registry, self._agent_runner)
            runtime = ConversationRuntime(
                session=session,
                api_client=turn_client,
                tool_executor=tool_executor,
                tool_registry=self._tool_registry,
                system_prompt=self._system_prompt,
                model=self._model,
                max_iterations=50,
                print_stream=False,
            )
            logger.info(
                "[MainAgentService] 运行时构建完成 | session=%s tools=%d model=%s",
                session_id, len(self._tool_registry.all_specs()), self._model,
            )

            # 在线程池中运行（避免阻塞事件循环）
            summary: TurnSummary = await asyncio.get_event_loop().run_in_executor(
                None, runtime.run_turn, request.input,
            )
            logger.info(
                "[MainAgentService] run_turn 完成 | session=%s iter=%d tool_calls=%d",
                session_id, summary.iterations, len(summary.tool_results),
            )

            # 保存会话
            self._sessions.save(session, session_id)
            logger.info("[MainAgentService] 会话已保存 | session=%s", session_id)

            # 发送完成事件
            final_text = summary.get_final_text()
            if final_text:
                yield self._trace.build_event(
                    EventType.MESSAGE_COMPLETED, trace_id, session_id, turn_id,
                    {"text": final_text[:500], "full_length": len(final_text)},
                ).to_sse()

            usage = {
                "input_tokens": summary.usage.input_tokens,
                "output_tokens": summary.usage.output_tokens,
                "total_tokens": summary.usage.total_tokens,
                "iterations": summary.iterations,
            }
            yield self._trace.build_event(
                EventType.TURN_COMPLETED, trace_id, session_id, turn_id,
                {"usage": usage, "route_type": route_type.value},
            ).to_sse()

            # 同时从 bridge 发送完成事件
            await bridge.send_completed(trace_id, session_id, turn_id, usage)

            # 流式输出 bridge 中的 delta 事件
            async for sse in bridge.stream_sse():
                yield sse

        except Exception as e:
            logger.exception("[MainAgentService] turn failed: %s", e)
            yield self._trace.build_event(
                EventType.TURN_FAILED, trace_id, session_id, turn_id,
                {"error": str(e), "error_type": type(e).__name__},
            ).to_sse()

    def handle_turn_sync(self, session_id: str, user_input: str) -> TurnSummary:
        """同步处理对话轮次（CLI 端使用）。"""
        self._ensure_runtime()

        session = self._sessions.load(session_id)
        if session is None:
            raise ValueError(f"会话不存在: {session_id}")

        tool_executor = MainToolExecutor(self._tool_registry, self._agent_runner)
        runtime = ConversationRuntime(
            session=session,
            api_client=self._api_client,
            tool_executor=tool_executor,
            tool_registry=self._tool_registry,
            system_prompt=self._system_prompt,
            model=self._model,
            max_iterations=50,
            print_stream=False,
        )

        summary = runtime.run_turn(user_input)
        self._sessions.save(session, session_id)
        return summary


# 全局单例
_main_agent_service: Optional[MainAgentService] = None


def get_main_agent_service() -> MainAgentService:
    global _main_agent_service
    if _main_agent_service is None:
        _main_agent_service = MainAgentService()
    return _main_agent_service