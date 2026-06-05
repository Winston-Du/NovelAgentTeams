"""
实体识别与关系抽取模块

利用 AI 模型从人物卡、剧情文本等内容中自动提取实体（节点）和关系（边），
并更新到图存储中。

核心功能：
1. 从人物卡 YAML 中提取实体和关系
2. 从章节文本中提取实体和关系
3. 使用 LLM 进行实体链接和消歧
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

import yaml

from .graph_store import (
    GraphStore,
    NODE_TYPE_CHARACTER,
    NODE_TYPE_EVENT,
    NODE_TYPE_ITEM,
    NODE_TYPE_LOCATION,
    NODE_TYPE_ORGANIZATION,
    NODE_TYPE_CONCEPT,
    REL_TYPE_ALLY,
    REL_TYPE_ENEMY,
    REL_TYPE_FAMILY,
    REL_TYPE_MENTOR,
    REL_TYPE_FRIEND,
    REL_TYPE_LOVER,
    REL_TYPE_SUBORDINATE,
    REL_TYPE_KNOWS,
    REL_TYPE_PARTICIPATED_IN,
    REL_TYPE_CAUSED,
    REL_TYPE_OWNS,
    REL_TYPE_LOCATED_AT,
    REL_TYPE_BELONGS_TO,
    REL_TYPE_REFERS_TO,
    REL_TYPE_FORESHAODWS,
)

# 模块级 Logger
logger = logging.getLogger("novels_project.memory.entity_extractor")

# LLM 实体抽取的 System Prompt
ENTITY_EXTRACTION_PROMPT = """你是一个小说剧情知识图谱构建专家。请从给定的文本中提取实体和关系。

## 实体类型
- character: 人物角色
- event: 事件（具体发生的事情）
- item: 物品/道具（重要的物品、秘籍、法宝等）
- location: 地点
- organization: 组织/势力
- concept: 概念/设定（暗线、伏笔、阴谋计划等）

## 关系类型
- ally: 同盟
- enemy: 敌对
- family: 亲属
- mentor: 师徒
- friend: 朋友
- lover: 恋人
- subordinate: 上下级
- knows: 认识
- participated_in: 参与事件
- caused: 引发/导致
- owns: 拥有
- located_at: 位于
- belongs_to: 属于（组织）
- refers_to: 引用/提及（暗线关联）
- foreshadows: 伏笔预示

## 规则
1. 只提取文本中明确提到的实体和关系，不要臆造
2. 实体名称使用原文中的确切名称
3. 对每个实体提供 brief 属性（简短描述，不超过50字）
4. 对关系可附加 chapter 属性表示首次出现的章节

## 输出格式
请严格输出以下 JSON 格式：
{
  "entities": [
    {"name": "实体名", "type": "实体类型", "properties": {"brief": "简短描述"}}
  ],
  "relations": [
    {"source": "源实体", "target": "目标实体", "type": "关系类型", "properties": {"chapter": 1}}
  ]
}
"""

# LLM 人物卡解析的 System Prompt
CHARACTER_CARD_EXTRACTION_PROMPT = """你是一个小说人物关系图谱构建专家。请从给定的人物卡数据中提取所有角色及其关系类型。

## 输入格式
你会收到一份结构化的角色数据，每个角色包含以下字段：
- role: 角色定位（如 hero/villain/mentor/ally/spy 等）
- brief: 角色简介（如有）
- relationships: 与其他角色的关系，值可能是中文描述或英文关键词
- core_personality: 核心性格特征
- organization: 所属组织（如有）

## 关系类型（必须在以下选项中）
- ally: 同盟
- enemy: 敌对
- family: 亲属
- mentor: 师徒
- friend: 朋友
- lover: 恋人
- subordinate: 上下级
- knows: 认识

## 任务
1. 将每个角色的 relationships 中的关系描述准确映射到标准关系类型
   - "enemy" / "敌对" / "仇人" / "对手" → enemy
   - "mentor" / "师父" / "师傅" → mentor  
   - "friend" / "朋友" / "好友" → friend
   - "subordinate" / "下属" / "手下" → subordinate
   - "ally" / "同盟" / "盟友" → ally
   - "family" / "亲属" / "兄弟" → family
   - "lover" / "恋人" → lover
   - "knows" / "认识" → knows
2. 为每个角色生成简短的 brief 描述（综合 role 和 core_personality）
3. 如果角色有 organization 字段，添加 belongs_to 关系

## 输出格式
请严格输出以下 JSON 格式：
{
  "entities": [
    {"name": "角色名", "type": "character", "properties": {"brief": "角色简述", "role": "角色定位", "tier": "层级"}}
  ],
  "relations": [
    {"source": "源角色", "target": "目标角色", "type": "关系类型", "properties": {}}
  ]
}
"""


class EntityExtractor:
    """
    实体提取器。支持从 YAML 和纯文本中提取实体和关系。

    用法:
        extractor = EntityExtractor(graph_store)
        extractor.extract_from_character_cards("config/character_base_cards.yaml")
        extractor.extract_from_chapter_text(chapter_text, chapter_id=1)
    """

    # 关系关键词映射（用于规则抽取）
    RELATION_KEYWORDS: dict[str, str] = {
        # 中文关键词
        "同盟": REL_TYPE_ALLY,
        "盟友": REL_TYPE_ALLY,
        "敌对": REL_TYPE_ENEMY,
        "敌人": REL_TYPE_ENEMY,
        "仇人": REL_TYPE_ENEMY,
        "父亲": REL_TYPE_FAMILY,
        "母亲": REL_TYPE_FAMILY,
        "兄弟": REL_TYPE_FAMILY,
        "姐妹": REL_TYPE_FAMILY,
        "师父": REL_TYPE_MENTOR,
        "师傅": REL_TYPE_MENTOR,
        "弟子": REL_TYPE_MENTOR,
        "徒弟": REL_TYPE_MENTOR,
        "朋友": REL_TYPE_FRIEND,
        "好友": REL_TYPE_FRIEND,
        "恋人": REL_TYPE_LOVER,
        "下属": REL_TYPE_SUBORDINATE,
        "上级": REL_TYPE_SUBORDINATE,
        "手下": REL_TYPE_SUBORDINATE,
        "认识": REL_TYPE_KNOWS,
        # 英文关键词（直接映射到关系类型常量）
        "ally": REL_TYPE_ALLY,
        "enemy": REL_TYPE_ENEMY,
        "family": REL_TYPE_FAMILY,
        "mentor": REL_TYPE_MENTOR,
        "friend": REL_TYPE_FRIEND,
        "lover": REL_TYPE_LOVER,
        "subordinate": REL_TYPE_SUBORDINATE,
        "knows": REL_TYPE_KNOWS,
        "participated_in": REL_TYPE_PARTICIPATED_IN,
        "caused": REL_TYPE_CAUSED,
        "owns": REL_TYPE_OWNS,
        "located_at": REL_TYPE_LOCATED_AT,
        "belongs_to": REL_TYPE_BELONGS_TO,
        "refers_to": REL_TYPE_REFERS_TO,
        "foreshadows": REL_TYPE_FORESHAODWS,
    }

    def __init__(self, graph_store: GraphStore):
        self._graph = graph_store
        self._stats: dict[str, int] = {"entities_added": 0, "relations_added": 0, "extractions": 0}
        logger.info(
            "[EntityExtractor] 初始化完成 | graph_nodes=%d graph_edges=%d",
            graph_store.entity_count(),
            graph_store.relation_count(),
        )

    def _log_step(self, step: str, **kwargs):
        """输出结构化日志。"""
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.debug("[EntityExtractor] %s | %s", step, extra)

    # ============================================================
    # 从 YAML 人物卡提取
    # ============================================================

    def extract_from_character_cards(
        self,
        yaml_path: str | Path,
        llm_client: Any = None,
    ) -> int:
        """
        从人物卡 YAML 文件中提取实体和关系。

        优先使用 LLM 进行关系类型推断，当 LLM 不可用时降级为规则关键词匹配。

        Args:
            yaml_path: 人物卡 YAML 文件路径
            llm_client: LLM 客户端（可选，传入后使用 LLM 提取）

        Returns:
            新添加的实体数量
        """
        start_time = time.time()
        path = Path(yaml_path)
        mode = "llm" if llm_client else "rules"

        logger.info(
            "[EntityExtractor] 开始从人物卡提取实体 | path=%s mode=%s",
            path.name, mode,
        )

        if not path.exists():
            logger.error("[EntityExtractor] 人物卡文件不存在 | path=%s", path)
            raise FileNotFoundError(f"人物卡文件不存在: {path}")

        # 读取 YAML
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
            data = yaml.safe_load(raw) or {}
            logger.debug(
                "[EntityExtractor] YAML 加载完成 | size=%dkb tiers=%s",
                round(len(raw) / 1024, 1),
                [t for t in ["s_tier", "a_tier", "b_tier"] if t in data],
            )
        except yaml.YAMLError as e:
            logger.error("[EntityExtractor] YAML 解析失败 | path=%s error=%s", path, e)
            raise

        # 选择提取模式
        if llm_client:
            try:
                result = self._extract_character_cards_with_llm(data, llm_client)
                added_count = result["entities_added"]
                relation_count = result["relations_added"]
                tier_stats = result.get("tier_stats", {})
            except Exception as e:
                logger.warning(
                    "[EntityExtractor] LLM 人物卡提取失败，回退到规则模式 | error=%s", e,
                )
                result = self._extract_character_cards_with_rules(data)
                added_count = result["entities_added"]
                relation_count = result["relations_added"]
                tier_stats = result.get("tier_stats", {})
                mode = "rules (fallback)"
        else:
            result = self._extract_character_cards_with_rules(data)
            added_count = result["entities_added"]
            relation_count = result["relations_added"]
            tier_stats = result.get("tier_stats", {})

        elapsed = round(time.time() - start_time, 2)

        self._stats["entities_added"] += added_count
        self._stats["extractions"] += 1

        logger.info(
            "[EntityExtractor] 人物卡提取完成 | mode=%s new_entities=%d new_relations=%d "
            "total_nodes=%d total_edges=%d elapsed=%.2fs tier_stats=%s",
            mode, added_count, relation_count,
            self._graph.entity_count(), self._graph.relation_count(),
            elapsed, tier_stats,
        )

        return added_count

    def _extract_character_cards_with_llm(
        self,
        data: dict,
        llm_client: Any,
    ) -> dict[str, Any]:
        """使用 LLM 从人物卡数据中提取实体和关系。"""
        from ..api_client import ApiRequest

        # 构建用户消息：将人物卡数据序列化为结构化文本
        user_message = self._build_character_cards_user_message(data)
        text_preview = self._truncate_text(user_message, 150)

        logger.info(
            "[EntityExtractor] LLM 人物卡提取开始 | data_len=%d preview=%s",
            len(user_message), text_preview,
        )

        request = ApiRequest(
            system_prompt=CHARACTER_CARD_EXTRACTION_PROMPT,
            messages=[],
            tools=[],
            model=getattr(llm_client, "default_model", ""),
            max_tokens=4096,
        )

        llm_start = time.time()
        try:
            events = llm_client.stream(request, print_stream=False) if hasattr(llm_client, "stream") else []
            llm_elapsed = round(time.time() - llm_start, 2)
            logger.debug(
                "[EntityExtractor] LLM 调用完成 | elapsed=%.2fs event_count=%d",
                llm_elapsed, len(events),
            )
        except Exception as e:
            logger.warning(
                "[EntityExtractor] LLM 调用失败 | error=%s", e,
            )
            raise

        # 从 events 中提取文本
        full_text = ""
        from ..api_client import TextDelta
        for event in events:
            if isinstance(event, TextDelta):  # pragma: no branch
                full_text += event.text

        logger.debug("[EntityExtractor] LLM 响应文本 | len=%d", len(full_text))

        # 解析 LLM 输出的 JSON
        extracted = self._parse_llm_output(full_text)
        logger.info(
            "[EntityExtractor] LLM 人物卡输出解析 | entities=%d relations=%d",
            len(extracted.get("entities", [])),
            len(extracted.get("relations", [])),
        )

        return self._apply_character_card_extraction(extracted, data)

    def _build_character_cards_user_message(self, data: dict) -> str:
        """将人物卡数据构建为 LLM 可读的文本。"""
        lines = ["以下是一组小说角色数据，请提取所有角色及其关系：\n"]
        for tier in ["s_tier", "a_tier", "b_tier"]:
            if tier not in data or "characters" not in data[tier]:
                continue
            tier_info = data[tier]
            tier_name = tier_info.get("tier_name", "")
            lines.append(f"## 层级: {tier} ({tier_name})")
            for name, char_data in tier_info["characters"].items():
                lines.append(f"  - 角色: {name}")
                if char_data.get("role"):
                    lines.append(f"    定位: {char_data['role']}")
                if char_data.get("brief"):
                    lines.append(f"    简介: {char_data['brief']}")
                if char_data.get("core_personality"):
                    personality = char_data["core_personality"]
                    if isinstance(personality, list):
                        personality = ", ".join(personality)
                    lines.append(f"    性格: {personality}")
                relationships = char_data.get("relationships", {})
                if relationships:
                    rels = ", ".join(f"{k} -> {v}" for k, v in relationships.items())
                    lines.append(f"    关系: {rels}")
                if char_data.get("organization"):
                    lines.append(f"    组织: {char_data['organization']}")
            lines.append("")
        return "\n".join(lines)

    def _apply_character_card_extraction(
        self,
        extracted: dict,
        raw_data: dict,
    ) -> dict[str, Any]:
        """将 LLM 提取的人物卡结果应用到图存储。"""
        added_count = 0
        relation_count = 0
        tier_stats: dict[str, dict] = {}

        # 构建角色到层级的映射
        char_tier_map: dict[str, str] = {}
        char_tier_name_map: dict[str, str] = {}
        for tier in ["s_tier", "a_tier", "b_tier"]:
            if tier in raw_data and "characters" in raw_data[tier]:
                for name in raw_data[tier]["characters"]:
                    char_tier_map[name] = tier
                    char_tier_name_map[name] = raw_data[tier].get("tier_name", "")
                tier_stats[tier] = {"added": 0, "relations": 0}

        # 添加实体
        for entity in extracted.get("entities", []):
            name = entity.get("name", "")
            if not name:
                continue
            props = entity.get("properties", {})
            tier = char_tier_map.get(name, "s_tier")
            props["tier"] = tier
            props["tier_name"] = char_tier_name_map.get(name, "")

            if not self._graph.has_entity(name):
                self._graph.add_entity(name, NODE_TYPE_CHARACTER, props)
                added_count += 1
                tier_stats.setdefault(tier, {"added": 0, "relations": 0})["added"] += 1
                logger.debug(
                    "[EntityExtractor] LLM 新增实体 | name=%s role=%s tier=%s",
                    name, props.get("role", ""), tier,
                )
            else:
                self._graph.update_entity(name, props)
                logger.debug("[EntityExtractor] LLM 更新实体 | name=%s tier=%s", name, tier)

        # 添加 LLM 推断的关系
        for rel in extracted.get("relations", []):
            source = rel.get("source", "")
            target = rel.get("target", "")
            rel_type = rel.get("type", REL_TYPE_KNOWS)
            props = rel.get("properties", {})

            if not source or not target:
                continue

            self._graph.add_relation(source, target, rel_type,
                                     {"source": "character_cards_llm", **props})
            relation_count += 1
            src_tier = char_tier_map.get(source, "")
            if src_tier in tier_stats:
                tier_stats[src_tier]["relations"] += 1
            logger.debug(
                "[EntityExtractor] LLM 新增关系 | source=%s target=%s type=%s",
                source, target, rel_type,
            )

        # 处理 organization（如果 LLM 未覆盖）
        for tier in ["s_tier", "a_tier", "b_tier"]:
            if tier not in raw_data or "characters" not in raw_data[tier]:
                continue
            for name, char_data in raw_data[tier]["characters"].items():
                org = char_data.get("organization")
                if org:
                    org_name = org if isinstance(org, str) else org.get("name", str(org))
                    if not self._graph.has_entity(org_name):
                        self._graph.add_entity(org_name, NODE_TYPE_ORGANIZATION, {"brief": org_name})
                        added_count += 1
                    self._graph.add_relation(name, org_name, REL_TYPE_BELONGS_TO,
                                             {"source": "character_cards"})
                    relation_count += 1

        return {
            "entities_added": added_count,
            "relations_added": relation_count,
            "tier_stats": tier_stats,
        }

    def _extract_character_cards_with_rules(self, data: dict) -> dict[str, Any]:
        """使用规则（关键词匹配）从人物卡数据中提取实体和关系。"""
        added_count = 0
        relation_count = 0
        tier_stats: dict[str, dict] = {}

        for tier in ["s_tier", "a_tier", "b_tier"]:
            if tier not in data or "characters" not in data[tier]:
                logger.debug("[EntityExtractor] 跳过空层级 | tier=%s", tier)
                continue

            tier_info = data[tier]
            tier_name = tier_info.get("tier_name", "")
            characters = data[tier]["characters"]
            tier_added = 0
            tier_rels = 0

            logger.debug(
                "[EntityExtractor] 处理层级 | tier=%s name=%s char_count=%d",
                tier, tier_name, len(characters),
            )

            for name, char_data in characters.items():
                # 提取实体属性
                props = {
                    "brief": self._extract_brief(char_data),
                    "role": char_data.get("role", ""),
                    "tier": tier,
                    "tier_name": tier_name,
                }

                if not self._graph.has_entity(name):
                    self._graph.add_entity(name, NODE_TYPE_CHARACTER, props)
                    added_count += 1
                    tier_added += 1
                    logger.debug(
                        "[EntityExtractor] 新增实体 | name=%s type=character tier=%s role=%s",
                        name, tier, props.get("role", ""),
                    )
                else:
                    self._graph.update_entity(name, props)

                # 从 relationships 字段提取关系
                relationships = char_data.get("relationships", {})
                extracted_rels = self._extract_relations_from_dict(relationships)
                for rel_target, rel_info in extracted_rels:
                    rel_type = rel_info.get("type", REL_TYPE_KNOWS)
                    self._graph.add_relation(
                        name, rel_target,
                        rel_type=rel_type,
                        properties={"source": "character_cards", **rel_info},
                    )
                    relation_count += 1
                    tier_rels += 1
                    logger.debug(
                        "[EntityExtractor] 新增关系 | source=%s target=%s type=%s",
                        name, rel_target, rel_type,
                    )

                # 从关联组织中提取
                org = char_data.get("organization")
                if org:
                    org_name = org if isinstance(org, str) else org.get("name", str(org))
                    if not self._graph.has_entity(org_name):
                        self._graph.add_entity(org_name, NODE_TYPE_ORGANIZATION, {"brief": org_name})
                        added_count += 1
                    self._graph.add_relation(
                        name, org_name,
                        rel_type=REL_TYPE_BELONGS_TO,
                        properties={"source": "character_cards"},
                    )
                    relation_count += 1

            tier_stats[tier] = {"added": tier_added, "relations": tier_rels}

        return {
            "entities_added": added_count,
            "relations_added": relation_count,
            "tier_stats": tier_stats,
        }

    def _extract_brief(self, char_data: dict) -> str:
        """从人物卡数据中提取简短描述。"""
        parts = []

        role = char_data.get("role", "")
        if role:
            parts.append(role)

        personality = char_data.get("core_personality", [])
        if isinstance(personality, list) and personality:
            parts.append(", ".join(personality[:3]))
        elif isinstance(personality, str):
            parts.append(personality)

        goal = char_data.get("core_goal", "")
        if goal:
            parts.append(f"目标: {goal}")

        result = " | ".join(parts) if parts else ""
        logger.debug("[EntityExtractor] 提取简要描述 | len=%d", len(result))
        return result

    def _extract_relations_from_dict(self, relationships: dict) -> list[tuple[str, dict]]:
        """从关系字典中提取关系列表。"""
        result = []
        for target, info in relationships.items():
            if isinstance(info, str):
                # 尝试匹配关系类型
                rel_type = REL_TYPE_KNOWS
                for keyword, rtype in self.RELATION_KEYWORDS.items():
                    if keyword in info:
                        rel_type = rtype
                        break
                result.append((target, {"type": rel_type, "description": info}))
            elif isinstance(info, dict):
                rel_type = info.get("type", REL_TYPE_KNOWS)
                result.append((target, info))

        logger.debug(
            "[EntityExtractor] 关系字典解析 | input_count=%d output_count=%d",
            len(relationships), len(result),
        )
        return result

    # ============================================================
    # 从章节文本提取
    # ============================================================

    def extract_from_chapter_text(
        self,
        text: str,
        chapter_id: int = 1,
        llm_client: Any = None,
    ) -> dict[str, Any]:
        """
        从章节文本中提取实体和关系（支持 LLM 和规则两种模式）。

        Args:
            text: 章节文本
            chapter_id: 章节 ID
            llm_client: LLM 客户端（可选，不传则使用规则模式）

        Returns:
            {"added_entities": N, "added_relations": N, "extracted": [...]}
        """
        text_len = len(text)
        mode = "llm" if llm_client else "rules"

        logger.info(
            "[EntityExtractor] 开始从章节文本提取 | chapter=%d text_len=%d mode=%s",
            chapter_id, text_len, mode,
        )

        start_time = time.time()

        if llm_client:
            result = self._extract_with_llm(text, chapter_id, llm_client)
        else:
            result = self._extract_with_rules(text, chapter_id)

        elapsed = round(time.time() - start_time, 2)

        self._stats["entities_added"] += result.get("added_entities", 0)
        self._stats["relations_added"] += result.get("added_relations", 0)
        self._stats["extractions"] += 1

        logger.info(
            "[EntityExtractor] 章节文本提取完成 | chapter=%d mode=%s "
            "added_entities=%d added_relations=%d elapsed=%.2fs",
            chapter_id, mode,
            result.get("added_entities", 0),
            result.get("added_relations", 0),
            elapsed,
        )

        return result

    def _extract_with_llm(
        self,
        text: str,
        chapter_id: int,
        llm_client: Any,
    ) -> dict[str, Any]:
        """使用 LLM 提取实体和关系。"""
        from ..api_client import ApiRequest

        text_preview = self._truncate_text(text, 100)

        logger.info(
            "[EntityExtractor] LLM 实体提取开始 | chapter=%d text_len=%d preview=%s",
            chapter_id, len(text), text_preview,
        )

        request = ApiRequest(
            system_prompt=ENTITY_EXTRACTION_PROMPT,
            messages=[],
            tools=[],
            model=getattr(llm_client, "default_model", ""),
            max_tokens=4096,
        )

        llm_start = time.time()
        try:
            events = llm_client.stream(request, print_stream=False) if hasattr(llm_client, "stream") else []
            llm_elapsed = round(time.time() - llm_start, 2)
            logger.debug(
                "[EntityExtractor] LLM 调用完成 | elapsed=%.2fs event_count=%d",
                llm_elapsed, len(events),
            )
        except Exception as e:
            logger.warning(
                "[EntityExtractor] LLM 调用失败，回退到规则模式 | chapter=%d error=%s",
                chapter_id, e,
            )
            return self._extract_with_rules(text, chapter_id)

        # 从 events 中提取文本内容
        full_text = ""
        from ..api_client import TextDelta
        for event in events:
            if isinstance(event, TextDelta):
                full_text += event.text

        logger.debug(
            "[EntityExtractor] LLM 响应文本 | len=%d",
            len(full_text),
        )

        # 解析 JSON
        extracted = self._parse_llm_output(full_text)
        logger.debug(
            "[EntityExtractor] LLM 输出解析 | entities=%d relations=%d",
            len(extracted.get("entities", [])),
            len(extracted.get("relations", [])),
        )

        return self._apply_extraction(extracted, chapter_id)

    def _extract_with_rules(self, text: str, chapter_id: int) -> dict[str, Any]:
        """使用规则从章节文本中提取实体和关系。"""
        logger.debug(
            "[EntityExtractor] 规则模式提取 | chapter=%d text_len=%d",
            chapter_id, len(text),
        )

        extracted = {"entities": [], "relations": []}

        # 获取已知人物列表
        known_characters = {
            attrs.get("name", name): attrs
            for name, attrs in self._graph._graph.nodes(data=True)
            if attrs.get("type") == NODE_TYPE_CHARACTER
        }

        logger.debug(
            "[EntityExtractor] 已知人物列表 | count=%d",
            len(known_characters),
        )

        # 在文本中查找已知人物
        mentioned = set()
        for name in known_characters:
            if name in text:
                mentioned.add(name)

        logger.debug(
            "[EntityExtractor] 文本中检测到的人物 | count=%d names=%s",
            len(mentioned), list(mentioned)[:5],
        )

        # 记录人物在本章的出场
        for name in mentioned:
            extracted["entities"].append({
                "name": name,
                "type": NODE_TYPE_CHARACTER,
                "properties": {"appears_in_chapter": chapter_id},
            })

        result = self._apply_extraction(extracted, chapter_id)
        return result

    def _parse_llm_output(self, text: str) -> dict:
        """解析 LLM 输出的 JSON。"""
        # 尝试提取 JSON 块
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError as e:
                logger.warning(
                    "[EntityExtractor] LLM JSON 解析失败 | error=%s text_preview=%s",
                    e, self._truncate_text(text, 200),
                )

        logger.warning(
            "[EntityExtractor] LLM 输出中未找到有效 JSON | text_len=%d",
            len(text),
        )
        return {"entities": [], "relations": []}

    def _apply_extraction(
        self,
        extracted: dict,
        chapter_id: int,
    ) -> dict[str, Any]:
        """将提取结果应用到图存储。"""
        added_entities = 0
        added_relations = 0
        updated_entities = 0

        # 添加实体
        entities = extracted.get("entities", [])
        logger.debug(
            "[EntityExtractor] 应用提取结果 | chapter=%d entities=%d relations=%d",
            chapter_id, len(entities), len(extracted.get("relations", [])),
        )

        for entity in entities:
            name = entity.get("name", "")
            etype = entity.get("type", NODE_TYPE_CHARACTER)
            props = entity.get("properties", {})

            if not name:
                logger.warning("[EntityExtractor] 跳过空名称实体 | type=%s", etype)
                continue

            # 添加章节出场标记
            if "chapter_id" not in props:
                props["chapter_id"] = chapter_id

            if not self._graph.has_entity(name):
                self._graph.add_entity(name, etype, props)
                added_entities += 1
                logger.debug(
                    "[EntityExtractor] 新增实体 | name=%s type=%s chapter=%d",
                    name, etype, chapter_id,
                )
            else:
                # 更新已有实体的属性（合并 chapter 信息）
                existing = self._graph.get_entity(name) or {}
                existing_appear = existing.get("appears_in_chapters", [])
                if isinstance(existing_appear, (list, set)):  # pragma: no branch
                    if chapter_id not in existing_appear:
                        existing_appear = list(existing_appear) + [chapter_id]
                elif isinstance(existing_appear, int):
                    existing_appear = [existing_appear, chapter_id]
                else:
                    existing_appear = [chapter_id]
                self._graph.update_entity(name, {"appears_in_chapters": existing_appear})
                updated_entities += 1

        # 添加关系
        for rel in extracted.get("relations", []):
            source = rel.get("source", "")
            target = rel.get("target", "")
            rtype = rel.get("type", REL_TYPE_KNOWS)
            props = rel.get("properties", {})

            if not source or not target:
                logger.warning(
                    "[EntityExtractor] 跳过不完整关系 | source=%s target=%s",
                    source, target,
                )
                continue

            if "chapter_id" not in props:
                props["chapter_id"] = chapter_id

            self._graph.add_relation(source, target, rtype, props)
            added_relations += 1

        logger.debug(
            "[EntityExtractor] 提取结果应用完成 | added=%d updated=%d relations=%d",
            added_entities, updated_entities, added_relations,
        )

        return {
            "added_entities": added_entities,
            "added_relations": added_relations,
            "updated_entities": updated_entities,
            "extracted": extracted,
        }

    # ============================================================
    # 批量提取
    # ============================================================

    def build_knowledge_graph(
        self,
        character_cards_path: str | Path,
        chapter_texts: Optional[dict[int, str]] = None,
        llm_client: Any = None,
    ) -> dict[str, Any]:
        """
        构建完整知识图谱。

        Args:
            character_cards_path: 人物卡路径
            chapter_texts: {chapter_id: text} 字典
            llm_client: LLM 客户端

        Returns:
            构建统计信息
        """
        build_start = time.time()
        chapter_count = len(chapter_texts) if chapter_texts else 0

        logger.info(
            "[EntityExtractor] 开始构建知识图谱 | cards=%s chapters=%d",
            Path(character_cards_path).name, chapter_count,
        )

        stats = {
            "characters_extracted": 0,
            "chapters_processed": 0,
            "total_entities_added": 0,
            "total_relations_added": 0,
            "errors": [],
        }

        # 1. 提取人物卡
        try:
            stats["characters_extracted"] = self.extract_from_character_cards(character_cards_path)
        except Exception as e:
            logger.error("[EntityExtractor] 人物卡提取失败 | error=%s", e)
            stats["errors"].append(f"character_cards: {e}")

        # 2. 提取各章节
        if chapter_texts:
            for chapter_id, text in chapter_texts.items():
                try:
                    result = self.extract_from_chapter_text(text, chapter_id, llm_client)
                    stats["chapters_processed"] += 1
                    stats["total_entities_added"] += result["added_entities"]
                    stats["total_relations_added"] += result["added_relations"]
                except Exception as e:
                    logger.error(
                        "[EntityExtractor] 章节提取失败 | chapter=%d error=%s",
                        chapter_id, e,
                    )
                    stats["errors"].append(f"chapter_{chapter_id}: {e}")

        elapsed = round(time.time() - build_start, 2)
        logger.info(
            "[EntityExtractor] 知识图谱构建完成 | elapsed=%.2fs chars=%d chapters=%d "
            "entities=%d relations=%d errors=%d",
            elapsed,
            stats["characters_extracted"],
            stats["chapters_processed"],
            stats["total_entities_added"],
            stats["total_relations_added"],
            len(stats["errors"]),
        )

        return stats

    def get_stats(self) -> dict[str, int]:
        """获取提取器统计信息。"""
        return dict(self._stats)

    @staticmethod
    def _truncate_text(text: str, max_len: int = 100) -> str:
        """截断文本用于日志预览。"""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."