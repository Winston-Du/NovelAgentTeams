"""
日志管理系统 - 执行轨迹和性能指标
"""
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

class ExecutionLogger:
    """执行轨迹日志"""

    def __init__(self, log_dir: str = "logs/execution_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_chapter = None
        self.log_file = None
        self.start_time = None

    def start_chapter(self, chapter_id: int):
        """开始记录某一章"""
        self.current_chapter = chapter_id
        self.log_file = self.log_dir / f"chapter_{chapter_id}_execution.md"
        self.start_time = datetime.now()

        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"# 第 {chapter_id} 章执行日志\n\n")
            f.write(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")

    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')

        emoji_map = {
            "INFO": "ℹ️ ",
            "START": "🚀",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "DECISION": "🤔",
            "AGENT": "🤖",
        }

        emoji = emoji_map.get(level, "")
        log_line = f"[{timestamp}] {emoji} {message}\n"

        print(log_line.strip())  # 也打印到控制台

        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)

    def end_chapter(self):
        """结束章节记录"""
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            self.log(f"第 {self.current_chapter} 章完成 - 总耗时 {duration:.1f} 秒", "SUCCESS")

        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write("\n---\n")
                f.write(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


class MetricsCollector:
    """性能指标收集"""

    def __init__(self, metrics_dir: str = "logs/performance_metrics"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.current_chapter = None
        self.chapter_metrics = {}

    def start_chapter(self, chapter_id: int):
        """开始记录某一章的指标"""
        self.current_chapter = chapter_id
        self.chapter_metrics = {
            "chapter_id": chapter_id,
            "agents": {},
            "chapter_summary": {}
        }

    def start_agent(self, agent_name: str) -> Dict[str, Any]:
        """开始记录某个 Agent 的执行"""
        agent_data = {
            "agent_name": agent_name,
            "start_time": time.time(),
            "start_datetime": datetime.now().isoformat(),
        }
        return agent_data

    def end_agent(self, agent_name: str, agent_data: Dict[str, Any],
                  tokens_used: Optional[Dict[str, int]] = None,
                  output_size: Optional[int] = None,
                  status: str = "success",
                  additional_info: Optional[Dict] = None):
        """结束记录某个 Agent 的执行"""
        end_time = time.time()
        duration = end_time - agent_data["start_time"]

        metrics = {
            "start_time": agent_data["start_datetime"],
            "end_time": datetime.now().isoformat(),
            "duration_seconds": round(duration, 2),
            "status": status,
        }

        if tokens_used:
            metrics["tokens_used"] = tokens_used

        if output_size:
            metrics["output_size_bytes"] = output_size

        if additional_info:
            metrics.update(additional_info)

        self.chapter_metrics["agents"][agent_name] = metrics

    def end_chapter(self):
        """结束章节指标记录并保存"""
        # 计算总计
        total_tokens = 0
        total_duration = 0

        for agent, metrics in self.chapter_metrics["agents"].items():
            total_duration += metrics.get("duration_seconds", 0)
            if "tokens_used" in metrics:
                total_tokens += metrics["tokens_used"].get("total", 0)

        self.chapter_metrics["chapter_summary"] = {
            "total_duration_seconds": round(total_duration, 2),
            "total_tokens": total_tokens,
            "timestamp": datetime.now().isoformat(),
        }

        # 保存到文件
        output_file = self.metrics_dir / f"chapter_{self.current_chapter}_metrics.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.chapter_metrics, f, indent=2, ensure_ascii=False)

        return self.chapter_metrics
