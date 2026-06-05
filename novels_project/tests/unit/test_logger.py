"""
单元测试：日志管理模块

测试范围：
1. ExecutionLogger 类的所有方法
2. MetricsCollector 类的所有方法
"""
import json
from pathlib import Path
from unittest.mock import patch

from novels_project.logger import ExecutionLogger, MetricsCollector


class TestExecutionLoggerInit:
    """测试 ExecutionLogger 初始化"""

    def test_init_creates_directory(self, tmp_path):
        """初始化创建目录"""
        log_dir = tmp_path / "logs" / "execution_logs"
        assert not log_dir.exists()
        logger = ExecutionLogger(log_dir=str(log_dir))
        assert logger.log_dir == log_dir
        assert log_dir.exists()

    def test_init_default_dir(self, tmp_path):
        """默认目录"""
        import os
        cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            logger = ExecutionLogger()
            # 相对路径被转换为 Path 对象，不 resolve
            assert logger.log_dir == Path("logs/execution_logs")
            assert logger.log_dir.exists()
        finally:
            os.chdir(cwd)

    def test_init_initial_state(self, tmp_path):
        """初始状态"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        assert logger.current_chapter is None
        assert logger.log_file is None
        assert logger.start_time is None


class TestStartChapter:
    """测试 start_chapter"""

    def test_creates_log_file(self, tmp_path):
        """创建日志文件"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        expected_file = tmp_path / "chapter_1_execution.md"
        assert expected_file.exists()
        assert logger.current_chapter == 1
        assert logger.log_file == expected_file
        assert logger.start_time is not None

        # 验证文件内容
        with open(expected_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "# 第 1 章执行日志" in content
        assert "开始时间:" in content

    def test_overwrites_existing_file(self, tmp_path):
        """覆盖已存在的日志文件"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        file_path = tmp_path / "chapter_2_execution.md"
        file_path.write_text("old content")

        logger.start_chapter(2)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "# 第 2 章执行日志" in content


class TestLog:
    """测试 log"""

    def test_log_info(self, tmp_path):
        """INFO 级别日志"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        logger.log("这是一条信息", level="INFO")
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "这是一条信息" in content

    def test_log_start(self, tmp_path):
        """START 级别"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        logger.log("开始处理", level="START")
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "开始处理" in content

    def test_log_success(self, tmp_path):
        """SUCCESS 级别"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        logger.log("操作成功", level="SUCCESS")
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "操作成功" in content

    def test_log_error(self, tmp_path):
        """ERROR 级别"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        logger.log("发生错误", level="ERROR")
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "发生错误" in content

    def test_log_decision(self, tmp_path):
        """DECISION 级别"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        logger.log("做出决定", level="DECISION")
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "做出决定" in content

    def test_log_agent(self, tmp_path):
        """AGENT 级别"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        logger.log("Agent 操作", level="AGENT")
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Agent 操作" in content

    def test_log_unknown_level(self, tmp_path):
        """未知级别（无emoji）"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        logger.log("自定义级别", level="CUSTOM")
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "自定义级别" in content

    def test_log_when_file_is_none(self, tmp_path):
        """log_file 为 None 时不崩溃（只打印到控制台）"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        # 不调用 start_chapter，log_file 为 None
        logger.log("这条不应崩溃", level="INFO")
        # 没有崩溃就是通过

    def test_log_default_level(self, tmp_path):
        """默认级别为 INFO"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        logger.log("默认级别")
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "默认级别" in content

    def test_log_appends_to_file(self, tmp_path):
        """日志追加到文件"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        logger.log("第一条")
        logger.log("第二条")
        logger.log("第三条")
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        # 应该有 header 2行 + 分隔符 + 3条日志行
        assert "第一条" in content
        assert "第二条" in content
        assert "第三条" in content

    def test_log_includes_timestamp(self, tmp_path):
        """日志包含时间戳"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        with patch("novels_project.logger.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "12:00:00"
            logger.log("测试时间戳")
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "[12:00:00]" in content


class TestEndChapter:
    """测试 end_chapter"""

    def test_end_chapter_with_start_time(self, tmp_path):
        """start_time 存在"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(3)
        logger.end_chapter()
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "第 3 章完成" in content
        assert "总耗时" in content
        assert "结束时间:" in content

    def test_end_chapter_without_start_time(self, tmp_path):
        """start_time 为 None"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(1)
        logger.start_time = None
        logger.end_chapter()
        # 不应该崩溃
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "结束时间:" in content

    def test_end_chapter_with_log_file_none(self, tmp_path):
        """log_file 为 None"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        # 不调用 start_chapter
        logger.end_chapter()
        # 不应该崩溃

    def test_end_chapter_adds_footer(self, tmp_path):
        """末尾添加 footer"""
        logger = ExecutionLogger(log_dir=str(tmp_path))
        logger.start_chapter(5)
        logger.log("中间日志")
        logger.end_chapter()
        with open(logger.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "---" in content
        assert "结束时间:" in content


class TestMetricsCollectorInit:
    """测试 MetricsCollector 初始化"""

    def test_init_creates_directory(self, tmp_path):
        """初始化创建目录"""
        metrics_dir = tmp_path / "logs" / "performance_metrics"
        assert not metrics_dir.exists()
        collector = MetricsCollector(metrics_dir=str(metrics_dir))
        assert collector.metrics_dir == metrics_dir
        assert metrics_dir.exists()

    def test_init_initial_state(self, tmp_path):
        """初始状态"""
        collector = MetricsCollector(metrics_dir=str(tmp_path))
        assert collector.current_chapter is None
        assert collector.chapter_metrics == {}


class TestStartChapterMetrics:
    """测试 MetricsCollector.start_chapter"""

    def test_start_chapter(self, tmp_path):
        """开始记录章节指标"""
        collector = MetricsCollector(metrics_dir=str(tmp_path))
        collector.start_chapter(1)
        assert collector.current_chapter == 1
        assert collector.chapter_metrics["chapter_id"] == 1
        assert collector.chapter_metrics["agents"] == {}
        assert "chapter_summary" in collector.chapter_metrics


class TestStartAgent:
    """测试 MetricsCollector.start_agent"""

    def test_start_agent(self):
        """开始记录 Agent"""
        collector = MetricsCollector(metrics_dir="/tmp/test")
        agent_data = collector.start_agent("test_agent")
        assert agent_data["agent_name"] == "test_agent"
        assert "start_time" in agent_data
        assert "start_datetime" in agent_data

    def test_start_agent_returns_dict(self):
        """返回字典"""
        collector = MetricsCollector(metrics_dir="/tmp/test")
        result = collector.start_agent("writer")
        assert isinstance(result, dict)


class TestEndAgent:
    """测试 MetricsCollector.end_agent"""

    def test_end_agent_basic(self):
        """基本结束 Agent"""
        collector = MetricsCollector(metrics_dir="/tmp/test")
        collector.start_chapter(1)
        agent_data = collector.start_agent("writer_agent")
        collector.end_agent("writer_agent", agent_data)

        metrics = collector.chapter_metrics["agents"]["writer_agent"]
        assert "start_time" in metrics
        assert "end_time" in metrics
        assert "duration_seconds" in metrics
        assert metrics["status"] == "success"

    def test_end_agent_with_tokens(self):
        """带 token 统计"""
        collector = MetricsCollector(metrics_dir="/tmp/test")
        collector.start_chapter(1)
        agent_data = collector.start_agent("writer_agent")
        tokens = {"input": 100, "output": 200, "total": 300}
        collector.end_agent("writer_agent", agent_data, tokens_used=tokens)

        metrics = collector.chapter_metrics["agents"]["writer_agent"]
        assert metrics["tokens_used"] == tokens

    def test_end_agent_with_output_size(self):
        """带输出大小"""
        collector = MetricsCollector(metrics_dir="/tmp/test")
        collector.start_chapter(1)
        agent_data = collector.start_agent("writer_agent")
        collector.end_agent("writer_agent", agent_data, output_size=1024)

        metrics = collector.chapter_metrics["agents"]["writer_agent"]
        assert metrics["output_size_bytes"] == 1024

    def test_end_agent_with_status(self):
        """自定义状态"""
        collector = MetricsCollector(metrics_dir="/tmp/test")
        collector.start_chapter(1)
        agent_data = collector.start_agent("writer_agent")
        collector.end_agent("writer_agent", agent_data, status="failed")

        metrics = collector.chapter_metrics["agents"]["writer_agent"]
        assert metrics["status"] == "failed"

    def test_end_agent_with_additional_info(self):
        """附加信息"""
        collector = MetricsCollector(metrics_dir="/tmp/test")
        collector.start_chapter(1)
        agent_data = collector.start_agent("writer_agent")
        additional = {"retry_count": 2, "model": "gpt-4"}
        collector.end_agent("writer_agent", agent_data, additional_info=additional)

        metrics = collector.chapter_metrics["agents"]["writer_agent"]
        assert metrics["retry_count"] == 2
        assert metrics["model"] == "gpt-4"

    def test_end_agent_without_tokens(self):
        """无 token 时不留 tokens_used 字段"""
        collector = MetricsCollector(metrics_dir="/tmp/test")
        collector.start_chapter(1)
        agent_data = collector.start_agent("writer_agent")
        collector.end_agent("writer_agent", agent_data)

        metrics = collector.chapter_metrics["agents"]["writer_agent"]
        assert "tokens_used" not in metrics


class TestEndChapterMetrics:
    """测试 MetricsCollector.end_chapter"""

    def test_end_chapter_saves_file(self, tmp_path):
        """结束章节保存文件"""
        collector = MetricsCollector(metrics_dir=str(tmp_path))
        collector.start_chapter(1)
        agent_data = collector.start_agent("writer_agent")
        collector.end_agent("writer_agent", agent_data,
                            tokens_used={"total": 100})
        result = collector.end_chapter()

        expected_file = tmp_path / "chapter_1_metrics.json"
        assert expected_file.exists()
        assert result == collector.chapter_metrics

    def test_end_chapter_summary(self, tmp_path):
        """章节摘要计算"""
        collector = MetricsCollector(metrics_dir=str(tmp_path))
        collector.start_chapter(2)
        agent1 = collector.start_agent("writer")
        collector.end_agent("writer", agent1, tokens_used={"total": 100})
        agent2 = collector.start_agent("editor")
        collector.end_agent("editor", agent2, tokens_used={"total": 200})

        result = collector.end_chapter()
        summary = result["chapter_summary"]
        assert "total_duration_seconds" in summary
        assert summary["total_tokens"] == 300

    def test_end_chapter_mixed_tokens(self, tmp_path):
        """部分 agent 有 tokens，部分没有"""
        collector = MetricsCollector(metrics_dir=str(tmp_path))
        collector.start_chapter(3)
        agent1 = collector.start_agent("writer")
        collector.end_agent("writer", agent1, tokens_used={"total": 100})
        agent2 = collector.start_agent("editor")
        collector.end_agent("editor", agent2)  # 无 tokens
        agent3 = collector.start_agent("reviewer")
        collector.end_agent("reviewer", agent3, tokens_used={"total": 50})

        result = collector.end_chapter()
        summary = result["chapter_summary"]
        assert summary["total_tokens"] == 150
        assert "timestamp" in summary

    def test_end_chapter_without_agents(self, tmp_path):
        """没有 agent 的章节"""
        collector = MetricsCollector(metrics_dir=str(tmp_path))
        collector.start_chapter(3)
        result = collector.end_chapter()
        assert result["chapter_summary"]["total_tokens"] == 0
        assert result["chapter_summary"]["total_duration_seconds"] == 0

    def test_end_chapter_file_content(self, tmp_path):
        """验证文件内容"""
        collector = MetricsCollector(metrics_dir=str(tmp_path))
        collector.start_chapter(4)
        collector.end_chapter()

        expected_file = tmp_path / "chapter_4_metrics.json"
        with open(expected_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["chapter_id"] == 4
        assert saved["agents"] == {}
        assert "chapter_summary" in saved