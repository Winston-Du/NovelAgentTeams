"""
迭代写作控制器 - 管理多轮写作-校对迭代
"""
import yaml
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class IterationStatus(Enum):
    """迭代状态"""
    CONTINUE = "continue"      # 需要继续迭代
    ACCEPT = "accept"          # 质量达标，接受
    MAX_ITER = "max_iter"      # 达到最大迭代次数


@dataclass
class IterationResult:
    """单次迭代结果"""
    iteration: int
    draft: str                          # 初稿内容
    review_issues: List[Dict]           # 校对发现的问题
    quality_score: int                  # 质量评分 (1-10)
    status: IterationStatus             # 状态
    feedback: str = ""                  # 给撰写员的反馈


@dataclass
class IterationSession:
    """迭代会话"""
    chapter_id: int
    max_iterations: int = 3
    quality_threshold: int = 7          # 质量阈值，达到此分数则接受
    iterations: List[IterationResult] = field(default_factory=list)
    
    def current_iteration(self) -> int:
        return len(self.iterations)
    
    def should_continue(self, quality_score: int) -> IterationStatus:
        """判断是否需要继续迭代"""
        current = self.current_iteration()
        
        if quality_score >= self.quality_threshold:
            return IterationStatus.ACCEPT
        
        if current >= self.max_iterations:
            return IterationStatus.MAX_ITER
        
        return IterationStatus.CONTINUE
    
    def add_iteration(self, result: IterationResult):
        """添加一次迭代结果"""
        self.iterations.append(result)
    
    def get_best_draft(self) -> Tuple[str, int]:
        """获取最佳草稿"""
        if not self.iterations:
            return "", 0
        
        best = max(self.iterations, key=lambda x: x.quality_score)
        return best.draft, best.quality_score
    
    def get_summary(self) -> Dict[str, Any]:
        """获取迭代摘要"""
        best_draft, best_score = self.get_best_draft()
        
        return {
            "chapter_id": self.chapter_id,
            "total_iterations": self.current_iteration(),
            "max_iterations": self.max_iterations,
            "best_quality_score": best_score,
            "quality_threshold": self.quality_threshold,
            "final_status": self.iterations[-1].status.value if self.iterations else None,
            "improvement_history": [
                {"iteration": i.iteration, "score": i.quality_score, "issues_count": len(i.review_issues)}
                for i in self.iterations
            ]
        }


class IterationController:
    """迭代控制器"""
    
    def __init__(self, max_iterations: int = 3, quality_threshold: int = 7):
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.sessions: Dict[int, IterationSession] = {}
    
    def start_session(self, chapter_id: int) -> IterationSession:
        """开始一个新的迭代会话"""
        session = IterationSession(
            chapter_id=chapter_id,
            max_iterations=self.max_iterations,
            quality_threshold=self.quality_threshold
        )
        self.sessions[chapter_id] = session
        return session
    
    def get_session(self, chapter_id: int) -> Optional[IterationSession]:
        """获取现有会话"""
        return self.sessions.get(chapter_id)
    
    def parse_review_output(self, review_output: str) -> Tuple[List[Dict], int, str]:
        """
        解析校对输出，提取问题列表、质量评分和反馈
        
        Returns:
            (issues, quality_score, feedback)
        """
        issues = []
        quality_score = 5  # 默认分数
        feedback = ""
        
        try:
            # 尝试解析 YAML
            # 清理可能的 markdown 代码块标记
            clean_output = review_output.strip()
            if clean_output.startswith("```"):
                # 移除代码块标记
                lines = clean_output.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_output = "\n".join(lines)
            
            data = yaml.safe_load(clean_output)
            
            if isinstance(data, dict):
                # 提取问题列表
                chapter_final = data.get("chapter_final", {})
                proofreading_log = chapter_final.get("proofreading_log", {})
                issues = proofreading_log.get("issues_found_and_fixed", [])
                
                # 提取质量评分
                self_check = data.get("self_check_report", {})
                quality_score = self_check.get("quality_after", 5)
                
                # 提取反馈（用于给撰写员）
                feedback = self._generate_feedback(issues, quality_score)
                
        except Exception as e:
            # 解析失败，使用默认值
            feedback = f"校对输出解析失败: {str(e)}\n\n原始输出:\n{review_output[:500]}"
        
        return issues, quality_score, feedback
    
    def _generate_feedback(self, issues: List[Dict], quality_score: int) -> str:
        """生成给撰写员的反馈"""
        if not issues:
            return "校对未发现明显问题，质量良好。"
        
        feedback_parts = [
            f"📊 质量评分: {quality_score}/10",
            "",
            f"📝 发现 {len(issues)} 个问题需要修正:",
            ""
        ]
        
        # 按严重程度分组
        high_issues = [i for i in issues if i.get("severity") == "high"]
        medium_issues = [i for i in issues if i.get("severity") == "medium"]
        low_issues = [i for i in issues if i.get("severity") == "low"]
        
        if high_issues:
            feedback_parts.append("🔴 高优先级问题:")
            for i, issue in enumerate(high_issues[:5], 1):
                feedback_parts.append(f"  {i}. [{issue.get('issue_type', '未知')}]")
                feedback_parts.append(f"     原文: \"{issue.get('original_text', '')[:50]}...\"")
                feedback_parts.append(f"     问题: {issue.get('problem', '')}")
                feedback_parts.append(f"     修正: {issue.get('fix_applied', '')}")
            feedback_parts.append("")
        
        if medium_issues:
            feedback_parts.append(f"🟡 中优先级问题: {len(medium_issues)} 个")
            feedback_parts.append("")
        
        if low_issues:
            feedback_parts.append(f"🟢 低优先级问题: {len(low_issues)} 个")
            feedback_parts.append("")
        
        feedback_parts.append("请根据以上反馈修改章节内容，重点关注高优先级问题。")
        
        return "\n".join(feedback_parts)
    
    def create_revision_prompt(self, 
                               original_draft: str,
                               feedback: str,
                               issues: List[Dict],
                               iteration: int) -> str:
        """
        创建修改提示词
        
        Args:
            original_draft: 原始草稿
            feedback: 校对反馈
            issues: 问题列表
            iteration: 当前迭代次数
        
        Returns:
            修改提示词
        """
        prompt = f"""# 章节修改任务（第 {iteration} 次迭代）

## 校对反馈

{feedback}

## 修改要求

1. **重点修正高优先级问题**：对话风格偏离、逻辑漏洞等
2. **保持原有风格**：不要过度修改，保持文笔一致性
3. **输出格式不变**：仍然使用 YAML 格式输出

## 原始草稿（供参考）

```
{original_draft[:2000]}...
```

## 输出要求

请输出修改后的章节内容，格式与之前相同：
- content: 修改后的章节内容
- revision_notes: 修改说明（简述修改了哪些内容）

请开始修改：
"""
        return prompt


# 全局控制器实例
_controller = None


def get_iteration_controller(max_iterations: int = 3,
                             quality_threshold: int = 7) -> IterationController:
    """获取迭代控制器单例，参数变化时只更新配置，不重建实例"""
    global _controller
    if _controller is None:
        _controller = IterationController(
            max_iterations=max_iterations,
            quality_threshold=quality_threshold
        )
    else:
        # 只更新配置参数，不重建实例，保留已有 sessions
        _controller.max_iterations = max_iterations
        _controller.quality_threshold = quality_threshold
    return _controller
