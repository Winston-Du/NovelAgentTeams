"""
Layer 5: Orchestrator - CLI / REPL

Interactive conversation interface and CLI entry point.
Supports both REPL mode and single-shot command mode.

All paths are based on the current working directory (project root).
Run from different directories to work on different stories.
"""
import os
import sys
import argparse
import readline  # Enable arrow keys and history in input()
from pathlib import Path
from typing import Optional

from .project_config import (
    set_project_root, get_project_root, get_sessions_dir,
    ensure_directories, format_project_status, check_project_ready,
)
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
from .memory.integrator import GraphMemoryIntegrator
from .memory.sync_manager import AutoSyncConfig


def _build_runtime(
    model: Optional[str] = None,
    session: Optional[Session] = None,
    auto_sync_config: Optional[AutoSyncConfig] = None,
    force_build_graph: bool = False,
) -> tuple[ConversationRuntime, str, Optional[GraphMemoryIntegrator]]:
    """
    Bootstrap the full runtime stack.
    Returns (runtime, session_id, graph_integrator).
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

    # Graph Memory Integration
    project_root = get_project_root()
    graph_integrator = None

    try:
        auto_sync_config = auto_sync_config or AutoSyncConfig(
            enabled=True,
            event_triggered=True,
            threshold_chapters=1,
            max_retries=3,
            retry_delay_seconds=10,
            persist_on_sync=True,
        )
        graph_integrator = GraphMemoryIntegrator(
            project_root=project_root,
            auto_sync_config=auto_sync_config,
        )
        init_result = graph_integrator.initialize(force_full_sync=force_build_graph)
        print(f"[图谱记忆] 已初始化 | 节点={init_result['node_count']} 边={init_result['edge_count']}")
    except Exception as e:
        print(f"[图谱记忆] 初始化失败（非致命）: {e}")

    return runtime, session_id, graph_integrator


def _run_repl(
    runtime: ConversationRuntime,
    session_id: str,
    session_store: SessionStore,
    graph_integrator: Optional[GraphMemoryIntegrator] = None,
):
    """Run the interactive REPL loop."""
    # Show project status
    print(format_project_status())
    if graph_integrator and graph_integrator.is_initialized():
        status = graph_integrator.sync_manager.get_sync_status()
        print(f"[图谱记忆] 节点={status['graph_nodes']} 边={status['graph_edges']} 状态={status['status']}")
    print()

    # Check if project is ready
    is_ready, missing = check_project_ready()
    if not is_ready:
        print("需要准备以下文件:")
        for item in missing:
            print(f"  - {item}")
        print()
        print("创建最小配置: config/character_base_cards.yaml")
        print()

    print("输入自然语言与Agent对话，输入 /help 查看命令")
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
                user_input, runtime, session_id, session_store, graph_integrator
            )
            if should_quit:
                break
            continue

        # Regular conversation
        try:
            summary = runtime.run_turn(user_input)
            # Auto-save session
            session_store.save(runtime.session, session_id)
            # Post-turn graph sync check
            if graph_integrator and graph_integrator.is_initialized():
                graph_integrator._check_and_sync()
        except KeyboardInterrupt:
            print("\n[Interrupted]")
        except Exception as e:
            print(f"\nError: {e}")


def _handle_slash_command(
    cmd: str,
    runtime: ConversationRuntime,
    session_id: str,
    session_store: SessionStore,
    graph_integrator: Optional[GraphMemoryIntegrator] = None,
) -> bool:
    """Handle a slash command. Returns True if the REPL should quit."""
    parts = cmd[1:].split(maxsplit=1)
    cmd_name = parts[0].lower() if parts else ""
    cmd_args = parts[1] if len(parts) > 1 else ""

    if cmd_name == "help":
        graph_help = ""
        if graph_integrator and graph_integrator.is_initialized():
            graph_help = """
图谱记忆:
  /graph                 查看图谱记忆系统状态
  /graph health          查看图谱同步健康报告
  /graph sync            手动触发增量同步
  /graph network <人物>  查询人物关系网络
  /graph search <关键词> 搜索图谱实体
  /graph foreshadow      查看未回收的伏笔
"""
        print(f"""
可用命令:
  /help                 显示帮助
  /status               显示当前项目状态
  /chapter <N>          快速创作第N章
  /cost                 显示 Token 使用统计
  /session              显示当前会话信息
  /sessions             列出所有保存的会话
  /resume <session_id>  恢复一个已保存的会话
  /compact              手动压缩上下文
  /clear                清空当前对话
  /quit                 退出
{graph_help}
项目配置:
  在当前目录创建 config/character_base_cards.yaml 即可开始新故事
  运行: cd /path/to/your/story && python run.py
""")

    elif cmd_name == "status":
        print(format_project_status())

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
        print(f"Project: {get_project_root()}")
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

    elif cmd_name == "graph":
        if not graph_integrator or not graph_integrator.is_initialized():
            print("图谱记忆系统未初始化")
            return False

        sub = cmd_args.strip().lower() if cmd_args else ""

        if sub == "":
            # 显示状态
            status = graph_integrator.sync_manager.get_sync_status()
            print(f"图谱记忆状态: {status['status']}")
            print(f"  节点: {status['graph_nodes']}, 边: {status['graph_edges']}")
            print(f"  上次同步: {status['last_sync_time'] or '从未'}")
            print(f"  同步次数: {status['sync_count']}")
            print(f"  连续失败: {status['consecutive_failures']}")
            print(f"  自动同步: {'启用' if status['auto_sync_enabled'] else '禁用'}")

        elif sub == "health":
            print(graph_integrator.sync_manager.get_health_report())

        elif sub == "sync":
            print("正在执行增量同步...")
            result = graph_integrator.sync_manager.sync(mode="incremental", force=False)
            print(f"同步完成: entities={result.get('entities_added', 0)} "
                  f"relations={result.get('relations_added', 0)} "
                  f"skipped={result.get('skipped', 0)}")

        elif sub.startswith("network"):
            char_name = sub[len("network"):].strip() or cmd_args.split(maxsplit=1)[1] if " " in cmd_args else ""
            if not char_name:
                print("用法: /graph network <人物名>")
                return False
            from .memory.graph_memory_tool import query_character_network
            print(query_character_network(char_name))

        elif sub.startswith("search"):
            keyword = sub[len("search"):].strip() or cmd_args.split(maxsplit=1)[1] if " " in cmd_args else ""
            if not keyword:
                print("用法: /graph search <关键词>")
                return False
            from .memory.graph_memory_tool import search_graph
            print(search_graph(keyword))

        elif sub == "foreshadow":
            from .memory.graph_memory_tool import get_graph_query as _get_gq
            query = _get_gq()
            unresolved = query.find_unresolved_foreshadowing()
            if unresolved:
                print(f"未回收的伏笔 ({len(unresolved)} 个):")
                for u in unresolved:
                    targets = ", ".join(t["name"] for t in u.get("unresolved_targets", []))
                    print(f"  - {u['concept']}: {u.get('brief', '')}")
                    print(f"    未回收: {targets}")
            else:
                print("暂未发现未回收的伏笔（或伏笔已全部回收）")

        else:
            print(f"未知的 graph 子命令: {sub}")
            print("可用: /graph [health|sync|network <人物>|search <关键词>|foreshadow]")

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
    parser.add_argument("--build-graph", action="store_true",
                        help="启动时强制重建知识图谱")
    parser.add_argument("--no-graph", action="store_true",
                        help="禁用图谱记忆功能")

    args = parser.parse_args()

    # Set project root to current working directory
    set_project_root()

    # Ensure directories exist
    ensure_directories()

    # Vector DB initialization mode
    if args.init_vectordb:
        print("初始化向量库...")
        from .retrieval_engine import get_retrieval_engine
        from .project_config import get_samples_dir, get_vector_db_dir

        engine = get_retrieval_engine(
            sample_dir=str(get_samples_dir()),
            persist_dir=str(get_vector_db_dir()),
        )
        engine._ensure_initialized()
        if engine.vectorstore:
            print("向量库初始化完成")
        else:
            print("向量库初始化失败，请检查样例目录和 API 配置")
        return

    # Build session store with project-specific path
    session_store = SessionStore(get_sessions_dir())

    # Load session if resuming
    session = None
    if args.resume:
        session = session_store.load(args.resume)
        if session is None:
            print(f"未找到会话: {args.resume}")
            sys.exit(1)
        print(f"已恢复会话: {args.resume}")

    # Graph memory auto-sync config
    auto_sync_config = None
    if args.no_graph:
        auto_sync_config = AutoSyncConfig(enabled=False, event_triggered=False)

    runtime, session_id, graph_integrator = _build_runtime(
        model=args.model,
        session=session,
        auto_sync_config=auto_sync_config,
        force_build_graph=args.build_graph,
    )

    if args.resume:
        session_id = args.resume

    # Single-shot prompt mode
    if args.prompt:
        try:
            summary = runtime.run_turn(args.prompt)
            session_store.save(runtime.session, session_id)
        finally:
            _shutdown_graph(graph_integrator)
        return

    # Chapter generation mode
    if args.chapter:
        try:
            prompt = (
                f"请创作第{args.chapter}章。先使用 load_chapter_data 加载章节数据，"
                f"然后按照标准流程依次调用总编、人物设计师、剧情撰写员、资深校对。"
                f"完成后使用 save_chapter 保存结果。"
            )
            summary = runtime.run_turn(prompt)
            session_store.save(runtime.session, session_id)
        finally:
            _shutdown_graph(graph_integrator)
        return

    # Interactive REPL mode (default)
    try:
        _run_repl(runtime, session_id, session_store, graph_integrator)
    finally:
        _shutdown_graph(graph_integrator)


def _shutdown_graph(graph_integrator: Optional[GraphMemoryIntegrator]) -> Optional[dict]:
    """安全关闭图谱记忆系统。"""
    if graph_integrator and graph_integrator.is_initialized():
        try:
            result = graph_integrator.shutdown()
            print(f"[图谱记忆] 已关闭 | 节点={result['final_nodes']} 图谱已保存")
            return result
        except Exception as e:
            print(f"[图谱记忆] 关闭时出错: {e}")
    return None


if __name__ == "__main__":
    main()
