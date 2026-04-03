"""
Layer 5: Orchestrator - CLI / REPL

Interactive conversation interface and CLI entry point.
Supports both REPL mode and single-shot command mode.
"""
import os
import sys
import argparse
import readline  # Enable arrow keys and history in input()
from pathlib import Path
from typing import Optional

from .api_client import OpenAICompatibleClient
from .session import Session
from .session_store import SessionStore, generate_session_id
from .tool_spec import ToolRegistry, build_builtin_tool_registry
from .tool_executor import MainToolExecutor
from .runtime import ConversationRuntime
from .agents import (
    AgentRunner, register_agent_tools,
    build_save_chapter_tool, build_load_chapter_data_tool,
)
from .system_prompt import build_main_agent_system_prompt


def _build_runtime(
    model: Optional[str] = None,
    session: Optional[Session] = None,
) -> tuple[ConversationRuntime, str]:
    """
    Bootstrap the full runtime stack.
    Returns (runtime, session_id).
    """
    # Load config from environment
    api_key = os.getenv("COMPANY_API_KEY")
    if not api_key:
        print("Error: COMPANY_API_KEY environment variable not set")
        sys.exit(1)

    base_url = os.getenv(
        "API_BASE_URL",
        "http://ai-service.tal.com/openai-compatible/v1"
    )
    default_model = model or os.getenv("MODEL_NAME", "gemini-3-pro")

    # Layer 1: API Client
    api_client = OpenAICompatibleClient(
        base_url=base_url,
        api_key=api_key,
        default_model=default_model,
    )

    # Layer 3: Tool Registry
    builtin_registry = build_builtin_tool_registry()

    # Agent Runner (sub-agent execution)
    agent_runner = AgentRunner(api_client=api_client)
    agent_runner.set_builtin_registry(builtin_registry)

    # Register agent tools + utility tools in main registry
    main_registry = ToolRegistry()
    # Copy built-in tools
    for spec in builtin_registry.all_specs():
        main_registry.register(spec)
    # Add agent tools (chief_editor, character_designer, plot_writer, proofreader)
    register_agent_tools(main_registry)
    # Add utility tools
    main_registry.register(build_save_chapter_tool())
    main_registry.register(build_load_chapter_data_tool())

    # Layer 5: System Prompt
    system_prompt = build_main_agent_system_prompt()

    # Tool Executor
    tool_executor = MainToolExecutor(
        registry=main_registry,
        agent_runner=agent_runner,
    )

    # Layer 4: Runtime
    if session is None:
        session = Session()

    session_id = generate_session_id()

    runtime = ConversationRuntime(
        session=session,
        api_client=api_client,
        tool_executor=tool_executor,
        tool_registry=main_registry,
        system_prompt=system_prompt,
        model=default_model,
    )

    return runtime, session_id


def _run_repl(runtime: ConversationRuntime, session_id: str, session_store: SessionStore):
    """Run the interactive REPL loop."""
    print("=" * 60)
    print("  novels_project - AI 小说创作系统")
    print("  输入自然语言与Agent对话，输入 /help 查看命令")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("novels> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        # Handle slash commands
        if user_input.startswith("/"):
            should_quit = _handle_slash_command(
                user_input, runtime, session_id, session_store
            )
            if should_quit:
                break
            continue

        # Regular conversation
        try:
            summary = runtime.run_turn(user_input)
            # Auto-save session
            session_store.save(runtime.session, session_id)
        except KeyboardInterrupt:
            print("\n[Interrupted]")
        except Exception as e:
            print(f"\nError: {e}")


def _handle_slash_command(
    cmd: str,
    runtime: ConversationRuntime,
    session_id: str,
    session_store: SessionStore,
) -> bool:
    """Handle a slash command. Returns True if the REPL should quit."""
    parts = cmd[1:].split(maxsplit=1)
    cmd_name = parts[0].lower() if parts else ""
    cmd_args = parts[1] if len(parts) > 1 else ""

    if cmd_name == "help":
        print("""
可用命令:
  /help                 显示帮助
  /chapter <N>          快速创作第N章（自动加载数据并调用完整流程）
  /cost                 显示 Token 使用统计
  /session              显示当前会话信息
  /sessions             列出所有保存的会话
  /resume <session_id>  恢复一个已保存的会话
  /compact              手动压缩上下文
  /clear                清空当前对话
  /quit                 退出
""")

    elif cmd_name == "chapter":
        if not cmd_args:
            print("用法: /chapter <章节ID>")
            return False
        try:
            chapter_id = int(cmd_args.strip())
            prompt = (
                f"请创作第{chapter_id}章。先使用 load_chapter_data 加载章节数据，"
                f"然后按照标准流程依次调用总编、人物设计师、剧情撰写员、资深校对。"
                f"完成后使用 save_chapter 保存结果。"
            )
            summary = runtime.run_turn(prompt)
            session_store.save(runtime.session, session_id)
        except ValueError:
            print("错误: 章节ID必须是数字")
        except Exception as e:
            print(f"Error: {e}")

    elif cmd_name == "cost":
        print(runtime.usage_tracker.format_cost_report())

    elif cmd_name == "session":
        print(f"Session ID: {session_id}")
        print(f"Messages: {runtime.session.message_count()}")
        print(f"Estimated tokens: {runtime.session.total_estimated_tokens():,}")

    elif cmd_name == "sessions":
        sessions = session_store.list_sessions()
        if not sessions:
            print("没有保存的会话")
        else:
            print(f"保存的会话 ({len(sessions)} 个):")
            for s in sessions[:10]:
                print(f"  {s['session_id']}  ({s['message_count']} messages, {s['saved_at']})")

    elif cmd_name == "resume":
        if not cmd_args:
            print("用法: /resume <session_id>")
            return False
        loaded = session_store.load(cmd_args.strip())
        if loaded:
            runtime.session = loaded
            runtime.usage_tracker = runtime.usage_tracker.from_session(loaded)
            print(f"已恢复会话: {cmd_args.strip()} ({loaded.message_count()} messages)")
        else:
            print(f"未找到会话: {cmd_args.strip()}")

    elif cmd_name == "compact":
        from .compaction import compact_session
        result = compact_session(runtime.session)
        if result.removed_message_count > 0:
            runtime.session = result.compacted_session
            print(f"已压缩 {result.removed_message_count} 条消息")
        else:
            print("无需压缩")

    elif cmd_name == "clear":
        runtime.session = Session()
        print("对话已清空")

    elif cmd_name in ("quit", "exit", "q"):
        session_store.save(runtime.session, session_id)
        print("会话已保存，再见！")
        return True

    else:
        print(f"未知命令: /{cmd_name}  (输入 /help 查看可用命令)")

    return False


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="AI 小说创作系统")
    parser.add_argument("--prompt", type=str, help="单次对话模式（非交互）")
    parser.add_argument("--chapter", type=int, help="快速创作指定章节")
    parser.add_argument("--model", type=str, help="覆盖主Agent模型名称")
    parser.add_argument("--resume", type=str, help="恢复指定会话")
    parser.add_argument("--init-vectordb", action="store_true", help="初始化向量库")

    args = parser.parse_args()

    # Vector DB initialization mode
    if args.init_vectordb:
        print("初始化向量库...")
        from .retrieval_engine import get_retrieval_engine
        engine = get_retrieval_engine()
        engine._ensure_initialized()
        if engine.vectorstore:
            print("向量库初始化完成")
        else:
            print("向量库初始化失败，请检查样例目录和 API 配置")
        return

    # Build runtime
    session = None
    session_store = SessionStore(Path("sessions"))

    if args.resume:
        session = session_store.load(args.resume)
        if session is None:
            print(f"未找到会话: {args.resume}")
            sys.exit(1)
        print(f"已恢复会话: {args.resume}")

    runtime, session_id = _build_runtime(model=args.model, session=session)

    if args.resume:
        session_id = args.resume

    # Single-shot prompt mode
    if args.prompt:
        summary = runtime.run_turn(args.prompt)
        session_store.save(runtime.session, session_id)
        return

    # Chapter generation mode
    if args.chapter:
        prompt = (
            f"请创作第{args.chapter}章。先使用 load_chapter_data 加载章节数据，"
            f"然后按照标准流程依次调用总编、人物设计师、剧情撰写员、资深校对。"
            f"完成后使用 save_chapter 保存结果。"
        )
        summary = runtime.run_turn(prompt)
        session_store.save(runtime.session, session_id)
        return

    # Interactive REPL mode (default)
    _run_repl(runtime, session_id, session_store)


if __name__ == "__main__":
    main()
