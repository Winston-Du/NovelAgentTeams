"""
内容管理 API

管理小说内容：人物卡、章节、暗线、全局搜索、内容批注与 Agent 修改。
"""
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..project_config import (
    get_project_root, get_character_cards_path,
    get_chapters_dir, get_summaries_dir, get_output_dir,
)

router = APIRouter()

# ============================================================
# Pydantic 模型
# ============================================================

class CharacterBase(BaseModel):
    name: str
    tier: Optional[str] = None
    role: Optional[str] = None
    brief: Optional[str] = None
    appearance: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    abilities: Optional[str] = None
    relationships: Optional[list[dict]] = None
    notes: Optional[list[str]] = None


class CharacterResponse(CharacterBase):
    pass


class ChapterSummary(BaseModel):
    chapter_id: int
    title: Optional[str] = None
    summary: Optional[str] = None
    key_events: Optional[list[str]] = None
    characters_appeared: Optional[list[str]] = None


class ChapterDetail(BaseModel):
    chapter_id: int
    title: Optional[str] = None
    content: str
    summary: Optional[ChapterSummary] = None


class PlotLine(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    status: str = "active"   # active, resolved, abandoned
    related_characters: Optional[list[str]] = None
    foreshadowing: Optional[list[str]] = None
    notes: Optional[str] = None


class AnnotationRequest(BaseModel):
    content_type: str  # character, chapter, plotline
    content_id: str
    note: str          # 批注内容
    instruction: Optional[str] = None  # 给 Agent 的修改指令


class SearchResult(BaseModel):
    type: str  # character, chapter, plotline, concept
    id: str
    title: str
    snippet: str
    highlight: Optional[str] = None


# ============================================================
# 人物卡管理
# ============================================================

def _load_character_cards() -> dict:
    """加载人物卡文件。"""
    path = get_character_cards_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_character_cards(data: dict):
    """保存人物卡文件。"""
    path = get_character_cards_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _flatten_characters(data: dict) -> list[dict]:
    """将层级结构的人物卡扁平化为列表。"""
    result = []
    for tier_key in ["s_tier", "a_tier", "b_tier", "c_tier"]:
        tier_data = data.get(tier_key, {})
        if isinstance(tier_data, dict):
            # 支持两种结构：
            # 1. 直接嵌套：{ name: { info } }
            # 2. characters 子键：{ characters: { name: { info } } }
            chars = tier_data.get("characters", tier_data)
            if isinstance(chars, dict):
                for name, info in chars.items():
                    if isinstance(info, dict) and not name.startswith("_"):
                        info["tier"] = tier_key
                        info["name"] = name
                        result.append(info)
    return result


@router.get("/characters")
async def get_characters():
    """获取所有人物卡。"""
    data = _load_character_cards()
    return _flatten_characters(data)


@router.get("/characters/{name}")
async def get_character(name: str):
    """获取单个人物卡详情。"""
    data = _load_character_cards()
    for tier_key in ["s_tier", "a_tier", "b_tier", "c_tier"]:
        tier_data = data.get(tier_key, {})
        if isinstance(tier_data, dict):
            # 支持两种结构：
            # 1. 直接嵌套：{ name: { info } }
            # 2. characters 子键：{ characters: { name: { info } } }
            chars = tier_data.get("characters", tier_data)
            if isinstance(chars, dict) and name in chars:
                info = chars[name]
                if isinstance(info, dict):
                    info["tier"] = tier_key
                    info["name"] = name
                    return info
    raise HTTPException(status_code=404, detail=f"人物 '{name}' 不存在")


@router.post("/characters")
async def create_character(char: CharacterBase):
    """添加新人物。"""
    data = _load_character_cards()
    tier = char.tier or "b_tier"
    if tier not in data:
        data[tier] = {}
    tier_data = data[tier]
    if not isinstance(tier_data, dict):
        tier_data = {}
        data[tier] = tier_data

    char_dict = char.model_dump(exclude={"name", "tier"}, exclude_none=True)
    # 如果该 tier 已有 characters 子键，保持结构一致
    if "characters" in tier_data and isinstance(tier_data["characters"], dict):
        tier_data["characters"][char.name] = char_dict
    else:
        tier_data[char.name] = char_dict
    _save_character_cards(data)
    return {"name": char.name, "tier": tier, "status": "created"}


@router.put("/characters/{name}")
async def update_character(name: str, char: CharacterBase):
    """更新人物信息。"""
    data = _load_character_cards()
    found = False
    for tier_key in ["s_tier", "a_tier", "b_tier", "c_tier"]:
        tier_data = data.get(tier_key, {})
        if isinstance(tier_data, dict):
            # 支持嵌套 characters 结构和直接结构
            chars = tier_data.get("characters", tier_data)
            if isinstance(chars, dict) and name in chars:
                char_dict = char.model_dump(exclude={"name", "tier"}, exclude_none=True)
                chars[name] = char_dict
                found = True
                break

    if not found:
        raise HTTPException(status_code=404, detail=f"人物 '{name}' 不存在")

    _save_character_cards(data)
    return {"name": name, "status": "updated"}


@router.delete("/characters/{name}")
async def delete_character(name: str):
    """删除人物。"""
    data = _load_character_cards()
    found = False
    for tier_key in ["s_tier", "a_tier", "b_tier", "c_tier"]:
        tier_data = data.get(tier_key, {})
        if isinstance(tier_data, dict):
            # 支持嵌套 characters 结构和直接结构
            chars = tier_data.get("characters", tier_data)
            if isinstance(chars, dict) and name in chars:
                del chars[name]
                found = True
                break

    if not found:
        raise HTTPException(status_code=404, detail=f"人物 '{name}' 不存在")

    _save_character_cards(data)
    return {"name": name, "status": "deleted"}


# ============================================================
# 章节管理
# ============================================================

@router.get("/chapters")
async def get_chapters():
    """获取章节列表（含摘要）。"""
    chapters_dir = get_chapters_dir()
    summaries_dir = get_summaries_dir()
    chapters = []

    if not chapters_dir.exists():
        return chapters

    chapter_files = sorted(chapters_dir.glob("chapter_*_final.md"))
    for cf in chapter_files:
        chapter_id = cf.stem.replace("chapter_", "").replace("_final", "")
        # 尝试读取摘要
        summary = None
        summary_file = summaries_dir / f"chapter_{chapter_id}_summary.yaml"
        if summary_file.exists():
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    summary = yaml.safe_load(f)
            except Exception:
                pass

        # 获取章节标题（取第一行）
        title = None
        try:
            with open(cf, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("#"):
                    title = first_line.lstrip("#").strip()
        except Exception:
            pass

        chapters.append({
            "chapter_id": chapter_id,
            "title": title,
            "file": cf.name,
            "summary": summary,
            "size": cf.stat().st_size,
        })

    return chapters


@router.get("/chapters/{chapter_id}")
async def get_chapter(chapter_id: str):
    """获取章节完整内容。"""
    chapters_dir = get_chapters_dir()
    chapter_file = chapters_dir / f"chapter_{chapter_id}_final.md"

    if not chapter_file.exists():
        # 尝试其他命名格式
        candidates = list(chapters_dir.glob(f"chapter_{chapter_id}*.md"))
        if not candidates:
            raise HTTPException(status_code=404, detail=f"章节 '{chapter_id}' 不存在")
        chapter_file = candidates[0]

    with open(chapter_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 读取摘要
    summary = None
    summary_file = get_summaries_dir() / f"chapter_{chapter_id}_summary.yaml"
    if summary_file.exists():
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                summary = yaml.safe_load(f)
        except Exception:
            pass

    # 获取标题
    title = None
    for line in content.split("\n"):
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            break

    return {
        "chapter_id": chapter_id,
        "title": title,
        "content": content,
        "summary": summary,
        "file": chapter_file.name,
    }


@router.get("/chapters/{chapter_id}/summary")
async def get_chapter_summary(chapter_id: str):
    """获取章节摘要。"""
    summary_file = get_summaries_dir() / f"chapter_{chapter_id}_summary.yaml"
    if not summary_file.exists():
        raise HTTPException(status_code=404, detail=f"章节 '{chapter_id}' 摘要不存在")

    with open(summary_file, "r", encoding="utf-8") as f:
        summary = yaml.safe_load(f)

    return summary


# ============================================================
# 暗线管理
# ============================================================

def _get_plotlines_path() -> Path:
    """获取暗线文件路径。"""
    return get_output_dir() / "plotlines.yaml"


def _load_plotlines() -> list[dict]:
    """加载暗线列表。"""
    path = _get_plotlines_path()
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, list) else []


def _save_plotlines(data: list[dict]):
    """保存暗线列表。"""
    path = _get_plotlines_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


@router.get("/plotlines")
async def get_plotlines():
    """获取暗线列表。"""
    return _load_plotlines()


@router.post("/plotlines")
async def create_plotline(plotline: PlotLine):
    """创建暗线。"""
    plotlines = _load_plotlines()
    import uuid
    new_id = plotline.id or str(uuid.uuid4())[:8]
    entry = plotline.model_dump(exclude_none=True)
    entry["id"] = new_id
    plotlines.append(entry)
    _save_plotlines(plotlines)
    return entry


@router.put("/plotlines/{plotline_id}")
async def update_plotline(plotline_id: str, plotline: PlotLine):
    """更新暗线。"""
    plotlines = _load_plotlines()
    for i, pl in enumerate(plotlines):
        if pl.get("id") == plotline_id:
            entry = plotline.model_dump(exclude_none=True)
            entry["id"] = plotline_id
            plotlines[i] = entry
            _save_plotlines(plotlines)
            return entry
    raise HTTPException(status_code=404, detail=f"暗线 '{plotline_id}' 不存在")


@router.delete("/plotlines/{plotline_id}")
async def delete_plotline(plotline_id: str):
    """删除暗线。"""
    plotlines = _load_plotlines()
    for i, pl in enumerate(plotlines):
        if pl.get("id") == plotline_id:
            del plotlines[i]
            _save_plotlines(plotlines)
            return {"id": plotline_id, "status": "deleted"}
    raise HTTPException(status_code=404, detail=f"暗线 '{plotline_id}' 不存在")


# ============================================================
# 全局搜索
# ============================================================

@router.get("/search")
async def global_search(q: str = Query(..., min_length=1)):
    """全局搜索：跨模块查询人物、章节、暗线。"""
    results = []

    # 搜索人物
    data = _load_character_cards()
    for tier_key in ["s_tier", "a_tier", "b_tier", "c_tier"]:
        tier_data = data.get(tier_key, {})
        if isinstance(tier_data, dict):
            # 支持嵌套 characters 结构和直接结构
            chars = tier_data.get("characters", tier_data)
            if isinstance(chars, dict):
                for name, info in chars.items():
                    if isinstance(info, dict) and not name.startswith("_"):
                        # 搜索名字和简介
                        brief = info.get("brief", "") or ""
                        search_text = f"{name} {brief} {info.get('role', '')} {info.get('personality', '')}"
                        if q.lower() in search_text.lower():
                            results.append({
                                "type": "character",
                                "id": name,
                                "title": name,
                                "snippet": brief[:200] if brief else "",
                                "tier": tier_key,
                            })

    # 搜索章节
    summaries_dir = get_summaries_dir()
    if summaries_dir.exists():
        for sf in sorted(summaries_dir.glob("chapter_*_summary.yaml")):
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    summary = yaml.safe_load(f)
                if summary and isinstance(summary, dict):
                    summary_text = str(summary.get("summary", "")) + " " + " ".join(
                        summary.get("key_events", []) or []
                    ) + " " + " ".join(summary.get("characters_appeared", []) or [])
                    if q.lower() in summary_text.lower():
                        cid = sf.stem.replace("chapter_", "").replace("_summary", "")
                        results.append({
                            "type": "chapter",
                            "id": cid,
                            "title": summary.get("title", f"第{cid}章"),
                            "snippet": (summary.get("summary", "") or "")[:200],
                        })
            except Exception:
                continue

    # 搜索暗线
    plotlines = _load_plotlines()
    for pl in plotlines:
        search_text = f"{pl.get('name', '')} {pl.get('description', '')} {' '.join(pl.get('related_characters', []) or [])}"
        if q.lower() in search_text.lower():
            results.append({
                "type": "plotline",
                "id": pl.get("id", ""),
                "title": pl.get("name", ""),
                "snippet": (pl.get("description", "") or "")[:200],
            })

    return {"query": q, "count": len(results), "results": results}


# ============================================================
# 内容批注与 Agent 修改
# ============================================================

class OptimizeRequest(BaseModel):
    """AI 优化请求。"""
    field: str            # 需要优化的字段名
    current_value: str    # 当前值
    character_name: str   # 人物名称（用于上下文）
    context: Optional[dict] = None  # 其他字段的值（用于提供上下文）


class OptimizeResponse(BaseModel):
    """AI 优化响应。"""
    field: str
    optimized_value: str
    explanation: Optional[str] = None


@router.post("/characters/optimize", response_model=OptimizeResponse)
async def optimize_character_content(req: OptimizeRequest):
    """
    使用 AI 模型优化人物卡片的某个字段内容。

    读取模型供应商配置，调用第一个可用的模型对内容进行智能优化，
    返回优化后的文本。
    """
    import os
    from ..api.settings import load_model_providers, _resolve_api_key
    from ..api_client import OpenAICompatibleClient

    # 加载模型供应商配置
    providers_data = load_model_providers()
    providers = providers_data.get("providers", {})

    if not providers:
        raise HTTPException(status_code=503, detail="没有配置任何模型供应商，请先在基础设置中配置")

    # 尝试找到第一个可用的供应商
    client = None
    model_name = None
    for provider_id, provider_info in providers.items():
        if not isinstance(provider_info, dict):
            continue
        base_url = provider_info.get("base_url", "")
        api_key = _resolve_api_key(provider_info.get("api_key", ""))
        models = provider_info.get("models", [])
        if not base_url or not api_key or not models:
            continue
        model_name = models[0].get("id", "") if isinstance(models[0], dict) else str(models[0])
        if not model_name:
            continue
        try:
            client = OpenAICompatibleClient(
                base_url=base_url,
                api_key=api_key,
                default_model=model_name,
            )
            break
        except Exception:
            continue

    if not client:
        raise HTTPException(status_code=503, detail="没有可用的模型供应商，请检查 API Key 配置")

    # 构建优化提示词
    field_label_map = {
        "name": "姓名",
        "brief": "简介",
        "appearance": "外貌描述",
        "personality": "性格描述",
        "character_flaw": "性格缺陷",
        "core_motivation": "核心动机",
        "bottom_line": "底线",
        "role": "角色定位",
        "identity": "身份",
        "unique_speaking_style": "对话风格",
        "background": "背景故事",
        "abilities": "能力特长",
    }
    field_label = field_label_map.get(req.field, req.field)

    # 构建上下文信息
    context_parts = [f"人物名称: {req.character_name}"]
    if req.context:
        for k, v in req.context.items():
            if v and k != req.field and k in field_label_map:
                context_parts.append(f"{field_label_map.get(k, k)}: {v}")
    context_text = "\n".join(context_parts)

    system_prompt = (
        "你是一位资深的小说编辑，擅长优化人物设定。"
        "请根据人物上下文信息，对指定的字段内容进行专业优化。"
        "优化要求：\n"
        "1. 保持原有风格和核心意思\n"
        "2. 增强文学性和表现力\n"
        "3. 使描述更加生动、具体、有画面感\n"
        "4. 确保与人物其他设定保持一致\n"
        "5. 只返回优化后的文本，不要添加任何解释或前缀"
    )

    user_prompt = (
        f"请优化以下人物的【{field_label}】字段：\n\n"
        f"{context_text}\n\n"
        f"当前【{field_label}】内容：\n{req.current_value}\n\n"
        f"请直接返回优化后的{field_label}内容。"
    )

    try:
        # 使用 OpenAI API 直接调用（非流式）
        import openai
        raw_client = client.client
        response = raw_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2048,
        )
        optimized = response.choices[0].message.content or ""
        optimized = optimized.strip()

        return OptimizeResponse(
            field=req.field,
            optimized_value=optimized,
            explanation=f"已通过 {provider_id} 的 {model_name} 模型优化",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"模型调用失败: {str(e)}")


@router.post("/annotate")
async def annotate_content(req: AnnotationRequest):
    """
    对内容进行批注并调用 Agent 进行修改。

    此接口将批注提交到后端，触发 Agent 对指定内容进行修改。
    """
    # 记录批注到文件
    feedback_dir = get_project_root() / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    import json
    from datetime import datetime

    annotation = {
        "content_type": req.content_type,
        "content_id": req.content_id,
        "note": req.note,
        "instruction": req.instruction,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",
    }

    annotation_file = feedback_dir / f"annotation_{req.content_type}_{req.content_id.replace('/', '_')}.json"
    with open(annotation_file, "w", encoding="utf-8") as f:
        json.dump(annotation, f, ensure_ascii=False, indent=2)

    return {
        "status": "submitted",
        "annotation_id": annotation_file.stem,
        "message": "批注已提交，Agent 将进行处理",
    }