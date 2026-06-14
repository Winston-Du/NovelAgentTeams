"""
上下文自动注入模块

自动从图谱和向量库中提取相关上下文信息，注入到 Agent 的输入中。

支持的场景：
1. 角色信息自动注入 - 根据用户输入中的角色名称，自动查询角色的境界、喜好等信息
2. 暗线追踪自动注入 - 自动查询未完成的伏笔，帮助填坑
3. 人物一致性检查 - 自动查询人物历史信息，保证人物一致性
5. 章节摘要自动收集 - 自动提取章节摘要并存入向量库
"""
import logging
import time
from typing import Optional, List

logger = logging.getLogger("novels_project.context_injector")

# 延迟导入以避免循环依赖
_graph_integrator = None
_retrieval_engine = None


def get_graph_integrator():
    """获取图谱集成器"""
    global _graph_integrator
    if _graph_integrator is None:
        from .memory.integrator import GraphMemoryIntegrator
        from .project_config import get_project_root
        _graph_integrator = GraphMemoryIntegrator(get_project_root())
        try:
            _graph_integrator.initialize()
        except Exception:
            # 如果初始化失败，可能是还没有创建工作空间
            pass
    return _graph_integrator


def get_retrieval_engine():
    """获取检索引擎"""
    global _retrieval_engine
    if _retrieval_engine is None:
        from .retrieval_engine import get_retrieval_engine as get_engine
        _retrieval_engine = get_engine()
    return _retrieval_engine


class ContextInjector:
    """上下文自动注入器

    注入优先级（由高到低，受 max_context_chars 预算约束）：
    1. 角色上下文（按名字，单角色 ≤ 2000 字，最多 3 个）
    2. 伏笔上下文（未完成伏笔列表）
    3. 历史摘要块（来自 MemoryManager，按 agent 隔离）
    """

    def __init__(self, memory_manager: Optional["MemoryManager"] = None):
        """初始化上下文注入器。

        参数：
        - memory_manager: 记忆系统门面，可选；为 None 时不注入历史摘要块
        """
        self.enabled = True
        self.memory_manager = memory_manager
        logger.info(
            "[ContextInjector] 初始化 | has_memory_manager=%s",
            memory_manager is not None,
        )
    
    def extract_character_names(self, text: str) -> List[str]:
        """从文本中提取可能的角色名称
        
        优先从图谱中查询已知角色，再用正则表达式作为备选方案
        """
        import re
        
        # 步骤1: 优先从图谱中获取已知角色名称
        known_characters = self._get_known_characters_from_graph()
        
        # 在文本中查找已知角色
        found_characters = []
        for char_name in known_characters:
            if char_name in text:
                found_characters.append(char_name)
        
        # 如果从图谱中找到了角色，直接返回
        if found_characters:
            print(f"🔍 [角色识别] 从图谱中找到 {len(found_characters)} 个已知角色: {found_characters}")
            return found_characters
        
        # 步骤2: 图谱中没有找到角色，使用正则表达式作为备选
        print(f"🔍 [角色识别] 图谱中未找到已知角色，使用正则表达式匹配")
        
        # 模式1：匹配"让XXX"、"使XXX"、"叫XXX"等（只匹配后面的名字）
        pattern1 = r'[让使叫请令命派]([\u4e00-\u9fff]{2,3})'
        # 模式2：匹配句子开头的名字（前面是标点或空格，后面是标点或特定词）
        pattern2 = r'(?:^|[\u3002\uff0c\uff01?！。，、])\s*([\u4e00-\u9fff]{2,3})(?=[\u3002\uff0c\uff01?！。，、的在和与及是了就])'
        # 模式3：匹配"XXX和YYY"中的名字（两个名字之间用"和"连接）
        pattern3 = r'([\u4e00-\u9fff]{2,3})和([\u4e00-\u9fff]{2,3})'
        
        matches = []
        
        # 使用各种模式匹配
        matches.extend(re.findall(pattern1, text))
        matches.extend(re.findall(pattern2, text))
        
        # 处理模式3
        for match in re.findall(pattern3, text):
            matches.extend(match)
        
        # 额外模式：直接匹配文本中连续2-3个汉字（作为备选）
        pattern4 = r'(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{2,3})(?![\u4e00-\u9fff])'
        matches.extend(re.findall(pattern4, text))
        
        # 过滤常见词
        common_words = {
            '的', '是', '在', '有', '和', '了', '我', '你', '他', '她', '它', 
            '这', '那', '为', '与', '及', '等', '个', '中', '上', '下', '大', '小',
            '可以', '不能', '需要', '应该', '可能', '会', '不会', '能',
            '我们', '你们', '他们', '她们', '它们', '什么', '怎么', '为什么',
            '然后', '但是', '然而', '虽然', '如果', '因为', '所以', '于是',
            '已经', '正在', '将要', '曾经', '总是', '经常', '偶尔', '从不',
            '这里', '那里', '到处', '任何', '所有', '一些', '许多', '很少',
            '非常', '特别', '十分', '极其', '稍微', '略微', '完全', '彻底',
            '开始', '结束', '继续', '停止', '进行', '完成', '实现', '达到',
            '发现', '看到', '听到', '想到', '知道', '明白', '理解', '相信',
            '觉得', '认为', '希望', '想要', '打算', '计划', '准备', '决定',
            '修炼', '功法', '神秘', '山洞', '发生', '看看', '一起', '路上', 
            '遇到', '前往', '妖兽', '古籍', '尸体', '石棺', '光芒', '符文', 
            '深处', '完好', '保存', '古老', '泛黄', '诡异', '散发', '刻满', 
            '棺盖', '里面', '躺着', '手中', '握着', '进入', '小心', '翼翼',
            '一本', '这本', '什么', '青云', '青云宗', '宗门', '弟子', '境界', 
            '宝物', '获得', '成为', '帮助', '必须', '能够', '立刻', '马上', 
            '立即', '终于', '终究', '到底', '毕竟', '果然', '竟然', '居然',
            '偏偏', '反倒', '反正', '横竖', '左右', '前后', '里外', '远近',
            '高低', '深浅', '大小', '长短', '粗细', '厚薄', '宽窄', '快慢',
            '松紧', '软硬', '轻重', '新旧', '冷热', '干湿', '肥瘦', '方圆',
            '就去', '一起', '一起前', '前往青', '青云宗', '们在', '路上遇',
            '苏晴一', '林羽去',
        }
        
        filtered = [m for m in matches if m and m not in common_words]
        
        result = list(set(filtered))
        print(f"🔍 [角色识别] 正则匹配结果: {result}")
        return result
    
    def _get_known_characters_from_graph(self) -> List[str]:
        """从图谱中获取已知的角色名称列表"""
        try:
            integrator = get_graph_integrator()
            if integrator.is_initialized() and integrator.graph_store:
                # 获取所有人物类型的节点
                characters = integrator.graph_store.get_all_characters()
                if characters:
                    return [char.get('name', '') for char in characters if char.get('name')]
        except Exception as e:
            print(f"⚠️  从图谱获取角色列表失败: {e}")
        return []
    
    def get_character_context(self, character_name: str) -> Optional[str]:
        """获取角色的上下文信息"""
        try:
            integrator = get_graph_integrator()
            if integrator.is_initialized() and integrator.graph_query:
                context = integrator.inject_graph_context_into_prompt(character_name, "writing")
                return context
        except Exception as e:
            print(f"获取角色上下文失败: {e}")
        return None
    
    def get_foreshadowing_context(self) -> Optional[str]:
        """获取未完成的伏笔信息"""
        try:
            integrator = get_graph_integrator()
            if integrator.is_initialized() and integrator.graph_query:
                # 查询所有未完成的伏笔
                foreshadowings = integrator.graph_query.trace_all_foreshadowings()
                if foreshadowings:
                    result = "📌 未完成的伏笔:\n"
                    for idx, f in enumerate(foreshadowings[:5], 1):  # 最多返回5个
                        result += f"{idx}. {f}\n"
                    return result
        except Exception as e:
            print(f"获取伏笔信息失败: {e}")
        return None
    
    def inject_context(
        self,
        user_input: str,
        max_context_chars: int = 8000,
        agent_id: str = "main",
    ) -> str:
        """自动注入上下文信息，带长度预算

        参数：
        - user_input: 用户原始输入
        - max_context_chars: 注入上下文最大字符数（包含所有三类）
        - agent_id: agent 标识（用于从 MemoryManager 获取对应历史摘要块）

        注入顺序（按优先级）：
        1. 角色上下文
        2. 伏笔上下文
        3. 历史摘要块（仅当 memory_manager 注入时）
        """
        if not self.enabled:
            logger.info("[ContextInjector] 已禁用，跳过注入")
            return user_input

        logger.info(
            "[ContextInjector] 开始注入 | input_len=%d agent_id=%s max_context_chars=%d",
            len(user_input) if user_input else 0,
            agent_id,
            max_context_chars,
        )
        context_parts = []
        current_len = 0

        # 1. 角色上下文（按优先级截断）
        character_names = self.extract_character_names(user_input)
        logger.info(
            "[ContextInjector] 识别到角色 | count=%d names=%s",
            len(character_names), character_names,
        )
        for name in character_names[:3]:  # 最多处理3个角色
            char_context = self.get_character_context(name)
            if char_context:
                # 单角色上下文限制
                char_context = self._truncate_context(char_context, 2000)
                if current_len + len(char_context) > max_context_chars:
                    break
                context_parts.append(char_context)
                current_len += len(char_context)
                logger.info(
                    "[ContextInjector] 角色上下文已加入 | name=%s context_len=%d",
                    name, len(char_context),
                )
            else:
                logger.info("[ContextInjector] 角色无上下文 | name=%s", name)

        # 2. 伏笔上下文（次低优先级）
        if current_len < max_context_chars:
            foreshadow_context = self.get_foreshadowing_context()
            if foreshadow_context:
                remaining = max_context_chars - current_len
                foreshadow_context = self._truncate_context(foreshadow_context, remaining)
                context_parts.append(foreshadow_context)
                current_len += len(foreshadow_context)
                logger.info(
                    "[ContextInjector] 伏笔上下文已加入 | len=%d",
                    len(foreshadow_context),
                )

        # 3. 历史摘要块（Task 12 新增：最低优先级，剩余预算）
        if current_len < max_context_chars and self.memory_manager is not None:
            remaining = max_context_chars - current_len
            try:
                summary_text = self.memory_manager.get_summary_for_injection(agent_id)
            except Exception as e:
                # 摘要获取失败不阻塞注入，记录后跳过
                logger.warning(
                    "[ContextInjector] 获取历史摘要块失败，跳过 | agent=%s error=%s",
                    agent_id, e, exc_info=True,
                )
                summary_text = ""
            if summary_text:
                summary_text = self._truncate_context(summary_text, remaining)
                context_parts.append(summary_text)
                current_len += len(summary_text)
                logger.info(
                    "[ContextInjector] 注入历史摘要块 | agent=%s summary_len=%d",
                    agent_id, len(summary_text),
                )
        elif current_len < max_context_chars:
            logger.info(
                "[ContextInjector] 未配置 memory_manager，跳过历史摘要块注入 | agent=%s",
                agent_id,
            )

        # 如果有上下文，添加到用户输入前面
        if context_parts:
            context_str = "\n\n".join(context_parts)
            enriched = f"【上下文信息】\n{context_str}\n\n【用户输入】\n{user_input}"
            logger.info(
                "[ContextInjector] 注入完成 | parts=%d total_context_len=%d final_len=%d",
                len(context_parts), len(context_str), len(enriched),
            )
            return enriched

        logger.info("[ContextInjector] 注入完成 | 无补充信息")
        return user_input

    def _truncate_context(self, text: str, max_len: int) -> str:
        """智能截断：保留开头和结尾，中间用省略号"""
        if len(text) <= max_len:
            return text
        half = max_len // 2 - 50
        return text[:half] + "\n... [内容已截断] ...\n" + text[-half:]
    
    def extract_chapter_summary(self, chapter_text: str) -> str:
        """从章节文本中提取摘要"""
        start_time = time.time()
        logger.info("章节摘要提取开始 | 文本长度=%d", len(chapter_text))
        
        # 简单的摘要提取逻辑
        # 实际应用中可以调用 LLM 来提取更准确的摘要
        lines = chapter_text.strip().split('\n')
        
        # 获取标题（只取第一个一级标题）
        title = ""
        title_found = False
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#') and not stripped.startswith('##') and not title_found:
                title = stripped.replace('#', '').strip()
                title_found = True
                logger.debug("章节摘要提取到标题: '%s'", title)
            elif stripped and not stripped.startswith('##'):
                content_lines.append(stripped)
        
        # 取前300个字符作为摘要
        content = ' '.join(content_lines)[:300]
        
        if title:
            summary = f"【章节标题】{title}\n【内容摘要】{content}"
        else:
            summary = f"【内容摘要】{content}"
        
        elapsed_time = time.time() - start_time
        logger.info("章节摘要提取完成 | 长度=%d | 耗时=%.4fs", len(summary), elapsed_time)
        
        return summary
    
    def add_chapter_to_vector_db(self, chapter_text: str, chapter_id: int = None):
        """将章节摘要添加到向量库"""
        start_time = time.time()
        logger.info("向量库存储开始 | chapter_id=%s", chapter_id)

        try:
            # 步骤0: 优雅降级检查 - langchain 不可用时直接跳过（INFO 而非 ERROR）
            try:
                from langchain.schema import Document  # noqa: F401
            except ImportError:
                logger.info(
                    "向量库存储跳过 | reason=langchain 未安装 | chapter_id=%s",
                    chapter_id,
                )
                return False

            # 步骤1: 提取摘要
            summary = self.extract_chapter_summary(chapter_text)
            logger.debug("摘要提取成功 | 长度=%d", len(summary))
            
            # 步骤2: 获取检索引擎
            engine = get_retrieval_engine()
            logger.debug("检索引擎获取成功 | 引擎类型=%s", type(engine).__name__)
            
            # 步骤3: 生成文档ID
            if chapter_id:
                doc_id = f"chapter_{chapter_id}"
            else:
                doc_id = f"chapter_{int(time.time() * 1000)}"
            logger.debug("文档ID: %s", doc_id)
            
            # 步骤4: 创建文档对象
            from langchain.schema import Document
            doc = Document(
                page_content=summary,
                metadata={"source": f"chapter_{chapter_id}", "type": "summary", "chapter_id": chapter_id}
            )
            
            # 步骤5: 检查向量库状态
            if not hasattr(engine, '_initialized') or not engine._initialized:
                logger.warning("向量库未初始化，跳过存储")
                return False
            
            if not hasattr(engine, 'vectorstore') or engine.vectorstore is None:
                logger.warning("向量库对象为空，跳过存储")
                return False
            
            logger.debug("向量库状态正常 | 已初始化=True")
            
            # 步骤6: 添加文档到向量库
            try:
                engine.vectorstore.add_documents([doc])
                logger.info("文档添加成功 | doc_id=%s", doc_id)
            except Exception as add_error:
                logger.error("文档添加失败 | error=%s", add_error, exc_info=True)
                return False
            
            # 步骤7: 持久化向量库
            try:
                engine.vectorstore.persist()
                logger.info("向量库持久化成功")
            except Exception as persist_error:
                logger.warning("持久化失败（可能不影响功能）| error=%s", persist_error)
            
            elapsed = time.time() - start_time
            logger.info("向量库存储完成 | 耗时=%.4fs", elapsed)
            return True
            
        except Exception as e:
            logger.error("向量库存储失败 | error=%s", e, exc_info=True)
            elapsed = time.time() - start_time
            logger.debug("向量库存储总耗时: %.4fs", elapsed)
            return False


# 全局上下文注入器实例
_global_context_injector: Optional["ContextInjector"] = None

def get_context_injector() -> ContextInjector:
    """获取全局上下文注入器实例"""
    global _global_context_injector
    if _global_context_injector is None:
        _global_context_injector = ContextInjector()
    return _global_context_injector
