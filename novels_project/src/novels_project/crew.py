"""
CrewAI 小说创作系统 - 主 Crew 定义
集成 4 个 Agent：总编、人物设计师、剧情撰写员、资深校对
"""
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from typing import Dict, Any, Optional
import os
import yaml
from pathlib import Path

# 导入工具和日志
from .tools.sample_retriever import retrieve_writing_samples
from .tools.character_voice_checker import check_character_voice, get_character_voice_guide
from .tools.feedback_tools import retrieve_feedback, get_common_mistakes, record_feedback, record_batch_feedback
from .logger import ExecutionLogger, MetricsCollector


@CrewBase
class NovelsCrewAI():
    """小说创作 Crew - 4 个 Agent 协作"""

    def __init__(self, model_name: str = None):
        """
        初始化 Crew

        Args:
            model_name: 可选，全局覆盖模型名称（优先级最高）。
                - 传入时：4 个 Agent 都使用同一个模型
                - 未传入且环境变量 MODEL_NAME 未设置时：使用默认分组双模型
        """
        self.project_root = Path(__file__).parent.parent.parent

        # 全局覆盖（CLI 传参或环境变量）
        self.model_name = model_name or os.getenv('MODEL_NAME')

        if self.model_name:
            # 覆盖模式：4 个 Agent 统一使用同一个模型
            self.llm = self._create_llm(model_name=self.model_name)
            self.llm_gemini = self.llm
            self.llm_qwen = self.llm
        else:
            # 默认分组模式：总编+校对使用 gemini-3-pro；人物+剧情使用 qwen3-max
            self.llm_gemini = self._create_llm(model_name='gemini-3-pro')
            self.llm_qwen = self._create_llm(model_name='qwen3-max')
            # 向后兼容：保留 self.llm（默认指向总编/校对使用的 LLM）
            self.llm = self.llm_gemini

        # 加载设计文档
        self._load_design_docs()

        # 初始化日志和指标
        self.logger = ExecutionLogger()
        self.metrics = MetricsCollector()

    def _create_llm(self, model_name: str) -> LLM:
        """创建自定义 LLM 实例（同一套 OpenAI-compatible 接口，通过 model_name 区分模型）"""
        api_key = os.getenv('COMPANY_API_KEY')
        api_base_url = os.getenv(
            'API_BASE_URL',
            'http://ai-service.tal.com/openai-compatible/v1'
        )

        if not api_key:
            raise ValueError("COMPANY_API_KEY 环境变量未设置")

        return LLM(
            model=model_name,
            base_url=api_base_url,
            api_key=api_key
        )

    def _load_design_docs(self):
        """加载设计文档中的 Prompt 模板"""
        prompts_dir = self.project_root / "DESIGN" / "PROMPTS"

        self.prompts = {}
        prompt_files = {
            'chief_editor': 'chief_editor_prompt.md',
            'character_designer': 'character_designer_prompt.md',
            'plot_writer': 'plot_writer_prompt.md',
            'proofreader': 'proofreader_prompt.md',
        }

        for key, filename in prompt_files.items():
            prompt_file = prompts_dir / filename
            if prompt_file.exists():
                self.prompts[key] = prompt_file.read_text(encoding='utf-8')
            else:
                print(f"⚠️  警告：Prompt 文件不存在: {filename}")
                self.prompts[key] = ""

    # ========== 4 个 Agent 定义 ==========

    @agent
    def chief_editor(self) -> Agent:
        """总编 Agent"""
        return Agent(
            role="小说总编",
            goal="根据卷大纲和前章进展，制定本章的故事大纲，明确节奏、人物出场、冲突点、爽点、伏笔埋设",
            backstory="""你是一位资深小说编辑，拥有20年经验。
擅长宏观把控故事节奏、识别爽点、设置悬念。
你的大纲清晰、可执行、充满张力，能让团队准确理解创作意图。
你深谙东方玄幻小说的套路，理解"权谋经营流"的核心魅力。""",
            llm=self.llm_gemini,
            verbose=True,
            allow_delegation=False,
            max_iter=15,
        )

    @agent
    def character_designer(self) -> Agent:
        """人物设计师 Agent"""
        return Agent(
            role="人物策划设计师",
            goal="基于本章大纲和全局人物卡库，为本章涉及的核心人物生成'当前状态卡'，确保人物行为逻辑一致，保持独特的语言风格",
            backstory="""你是资深的人物塑造专家，深谙心理学、群体动力学、戏剧冲突。
你能让每个角色有血有肉，台词充满个性，行为符合逻辑。
你理解"Show, don't tell"原则，用行动和对话来表现人物性格。
你擅长设计人物间的张力，让对话和互动充满戏剧性。""",
            llm=self.llm_qwen,
            verbose=True,
            allow_delegation=False,
            max_iter=15,
        )

    @agent
    def plot_writer(self) -> Agent:
        """剧情撰写员 Agent"""
        return Agent(
            role="剧情撰写员",
            goal="根据章大纲、人物卡、前章摘要、参考样例，创作本章内容。追求细腻描写（Show, don't tell）、环境渲染、文学性，拒绝平铺直叙。目标字数：3000-5000字",
            backstory="""你是文学创意大师，拥有深厚的文字功底和敏锐的美学感知。
你擅长通过动作、对话、环境细节来表现人物和故事。
你的文字有节奏、有质感、有余韵，能让读者沉浸其中。
你熟悉东方玄幻的叙事语言，能驾驭权谋对话和战斗场面。
你拒绝"然后...接着...最后..."的流水账，每一句话都经过精心雕琢。
写作完成后，你会使用 check_character_voice 工具检查对话风格一致性。
你也会检索历史反馈，避免重复犯错。""",
            tools=[
                retrieve_writing_samples, 
                check_character_voice, 
                get_character_voice_guide,
                retrieve_feedback,
                get_common_mistakes
            ],
            llm=self.llm_qwen,
            verbose=True,
            allow_delegation=False,
            max_iter=20,
        )

    @agent
    def senior_proofreader(self) -> Agent:
        """资深校对 Agent"""
        return Agent(
            role="资深校对",
            goal="检查章节的逻辑一致性、节奏、文笔、人物口吻。优化文笔，指出并修正生硬转折，统一全文风格。最后生成'章节摘要卡'供下章参考",
            backstory="""你是文学质量把关官，有敏锐的编辑眼光和极高的专业标准。
你能发现微妙的逻辑漏洞、不和谐的节奏、飘忽的人物设定。
你深知"魔鬼藏在细节中"，任何不自然的表达都逃不过你的眼睛。
你不仅会指出问题，更会给出优化后的版本。
你的最终目标是让每一章都成为精品。
校对时，你会使用 check_character_voice 工具确保对话风格与人物卡库一致。
发现的问题会记录到反馈库，供后续创作参考。""",
            tools=[
                retrieve_writing_samples, 
                check_character_voice, 
                get_character_voice_guide,
                retrieve_feedback,
                get_common_mistakes,
                record_feedback,
                record_batch_feedback
            ],
            llm=self.llm_gemini,
            verbose=True,
            allow_delegation=False,
            max_iter=20,
        )

    # ========== 4 个 Task 定义 ==========

    @task
    def create_chapter_outline_task(self) -> Task:
        """总编生成章大纲"""
        return Task(
            description=self.prompts.get('chief_editor', '生成章大纲') + """

请根据输入数据生成章大纲。输出必须是纯 YAML 格式。
""",
            expected_output="""YAML 格式的章大纲，包含：
- story_structure（故事结构）
- characters_appearance（人物出场清单）
- climax_plan（爽点规划）
- atmosphere（环境氛围）
- foreshadowing（伏笔埋设）
- pacing_notes（节奏指导）""",
            agent=self.chief_editor(),
        )

    @task
    def design_character_states_task(self) -> Task:
        """人物设计师生成人物状态卡"""
        return Task(
            description=self.prompts.get('character_designer', '生成人物状态卡') + """

请根据章大纲和人物基础卡库生成本章人物状态卡。输出必须是纯 YAML 格式。
""",
            expected_output="""YAML 格式的人物状态卡，包含：
- 每个人物的 chapter_arc、behavior_this_chapter、dialogue_style_this_chapter
- character_tensions（人物间的张力）
- story_conflicts_and_turning_points（冲突与转折点）
- callbacks（Callback 内容）""",
            agent=self.character_designer(),
            context=[self.create_chapter_outline_task()],  # 依赖总编的输出
        )

    @task
    def write_chapter_draft_task(self) -> Task:
        """剧情撰写员创作初稿"""
        return Task(
            description=self.prompts.get('plot_writer', '创作章节初稿') + """

请根据章大纲和人物状态卡创作本章内容。输出必须是 YAML 格式。
""",
            expected_output="""YAML 格式的章节初稿，包含：
- content（完整的章节内容，3000-5000字）
- creation_notes（创作笔记）
- estimated_word_count（字数统计）""",
            agent=self.plot_writer(),
            context=[
                self.create_chapter_outline_task(),
                self.design_character_states_task()
            ],  # 依赖前两个 Agent 的输出
        )

    @task
    def proofread_and_summarize_task(self) -> Task:
        """资深校对优化并生成摘要"""
        return Task(
            description=self.prompts.get('proofreader', '校对并生成摘要') + """

请校对章节初稿，优化文笔，并生成章节摘要卡。输出必须是 YAML 格式。
""",
            expected_output="""YAML 格式的最终版章节和摘要卡，包含：
- chapter_final（最终版章节内容和校对日志）
- chapter_summary_card（章节摘要卡，供下章参考）""",
            agent=self.senior_proofreader(),
            context=[
                self.create_chapter_outline_task(),
                self.design_character_states_task(),
                self.write_chapter_draft_task()
            ],  # 依赖所有前面的输出
        )

    # ========== Crew 定义 ==========

    @crew
    def crew(self) -> Crew:
        """创建小说创作 Crew"""
        return Crew(
            agents=self.agents,  # 自动包含所有 @agent 装饰的 Agent
            tasks=self.tasks,    # 自动包含所有 @task 装饰的 Task
            process=Process.sequential,  # 串联执行
            verbose=True,
        )

    # ========== 辅助方法 ==========

    def run_chapter(self, chapter_id: int, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行一个完整的章节创作流程

        Args:
            chapter_id: 章节ID
            inputs: 输入数据（包含章大纲、人物卡库等）

        Returns:
            包含最终章节和摘要的字典
        """
        self.logger.start_chapter(chapter_id)
        self.metrics.start_chapter(chapter_id)

        self.logger.log(f"第 {chapter_id} 章开始执行", "START")

        try:
            # 执行 Crew
            result = self.crew().kickoff(inputs=inputs)

            self.logger.log(f"第 {chapter_id} 章执行完成", "SUCCESS")

            # 结束日志和指标
            self.logger.end_chapter()
            metrics_data = self.metrics.end_chapter()

            return {
                "success": True,
                "result": result,
                "metrics": metrics_data,
            }

        except Exception as e:
            self.logger.log(f"执行失败: {str(e)}", "ERROR")
            self.logger.end_chapter()

            return {
                "success": False,
                "error": str(e),
            }
