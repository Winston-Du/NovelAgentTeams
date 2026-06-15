"""
综合集成测试：验证图谱记忆系统完整功能

测试覆盖：
1. 关键操作节点的日志记录
2. /graph search 伏笔 查询功能
3. 角色关系变更 + 增量同步数据一致性
4. 自动同步配置参数生效
"""
import sys
import os
import tempfile
import yaml
import shutil
import logging
import io
import json
from pathlib import Path

# ---- Setup ----
tmpdir = tempfile.mkdtemp()
project = os.path.join(tmpdir, "novel_output")
os.makedirs(project + "/config", exist_ok=True)
os.makedirs(project + "/output/chapters", exist_ok=True)
os.makedirs(project + "/graph", exist_ok=True)

# ---- 创建丰富的测试数据（含伏笔）----
character_cards = {
    "s_tier": {
        "tier_name": "core",
        "characters": {
            "Hero": {
                "role": "hero",
                "brief": "天命之子，身怀上古血脉",
                "relationships": {"Villain": "enemy", "Mentor": "mentor", "Ally": "friend"},
                "core_personality": ["正直", "勇敢", "重情义"],
            },
            "Villain": {
                "role": "villain",
                "brief": "暗影组织的首领",
                "relationships": {"Hero": "enemy", "Spy": "subordinate"},
                "core_personality": ["阴险", "野心勃勃"],
            },
            "Mentor": {
                "role": "mentor",
                "brief": "退隐的绝世高手",
                "relationships": {"Hero": "mentor", "Villain": "enemy"},
            },
            "Ally": {
                "role": "ally",
                "brief": "Hero的挚友",
                "relationships": {"Hero": "friend"},
            },
            "Spy": {
                "role": "spy",
                "brief": "Villain安插的卧底",
                "relationships": {"Villain": "subordinate"},
            },
        },
    }
}

with open(project + "/config/character_base_cards.yaml", "w") as f:
    yaml.dump(character_cards, f)

# 章节内容（含伏笔信息）
chapter_1_content = """
Hero在拍卖会上首次遭遇Villain。Villain展示了一件神秘的古物——传说中的陨星碎片，
据说其中蕴含着足以颠覆世界的秘密。Hero隐约感觉到这件古物与自己体内的血脉产生了共鸣。
Mentor后来告诉Hero，这绝非巧合，陨星碎片与Hero的命运密切相关。
"""

chapter_2_content = """
Hero拜入Mentor门下修炼。Ally前来传递情报，告知Villain正在暗中收集各地的上古遗物。
Spy伪装成商贩混入Hero的队伍，但Hero的直觉告诉他此人来意不善。
陨星碎片的秘密逐渐浮出水面——据传完整的上古神器能够扭转时间。
"""

with open(project + "/output/chapters/chapter_1_final.md", "w") as f:
    f.write(chapter_1_content)
with open(project + "/output/chapters/chapter_2_final.md", "w") as f:
    f.write(chapter_2_content)

# ---- 环境配置 ----
os.environ["NOVEL_PROJECT_ROOT"] = project
os.environ["COMPANY_API_KEY"] = "test-api-key"

sys.path.insert(0, "src")
from pathlib import Path
from novels_project.project_config import set_project_root, get_project_root
set_project_root()
assert Path(get_project_root()).resolve() == Path(project).resolve()

# ---- 启用详细日志 ----
log_stream = io.StringIO()
log_handler = logging.StreamHandler(log_stream)
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))

for logger_name in [
    "novels_project.memory",
    "novels_project.memory.integrator",
    "novels_project.memory.sync_manager",
    "novels_project.memory.entity_extractor",
]:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(log_handler)

from novels_project.memory import AutoSyncConfig, GraphStore, GraphQuery, SyncManager, GraphMemoryIntegrator
from novels_project.cli import _build_runtime, _shutdown_graph

errors = []
results = {}

def test(name):
    def decorator(fn):
        try:
            result = fn()
            results[name] = result
            print(f"  {name}: PASSED")
        except Exception as e:
            errors.append((name, e))
            print(f"  {name}: FAILED - {e}")
            import traceback; traceback.print_exc()
    return decorator


# ============================================================
# Phase 1: 系统初始化 + 日志验证
# ============================================================
print("=" * 60)
print("Phase 1: 系统初始化 + 日志验证")
print("=" * 60)

@test("系统正常初始化")
def _():
    config = AutoSyncConfig(enabled=True, event_triggered=True, threshold_chapters=1,
                            max_retries=3, retry_delay_seconds=10, persist_on_sync=True)
    runtime, sid, integrator = _build_runtime(
        model="gemini-3-pro",
        auto_sync_config=config,
        force_build_graph=True,
    )
    assert integrator.is_initialized()
    status = integrator.sync_manager.get_sync_status()
    assert status["graph_nodes"] >= 5, f"Expected >=5 nodes after init, got {status['graph_nodes']}"
    assert status["graph_edges"] >= 4, f"Expected >=4 edges, got {status['graph_edges']}"
    return integrator

integrator = results["系统正常初始化"]
store = integrator.graph_store
query = integrator.graph_query
sync_mgr = integrator.sync_manager


# ============================================================
# Phase 2: 伏笔数据构建与查询验证
# ============================================================
print("\n" + "=" * 60)
print("Phase 2: 伏笔数据构建与 /graph search 查询验证")
print("=" * 60)

@test("手动构建伏笔概念节点")
def _():
    # 添加伏笔概念节点
    store.add_entity("陨星碎片的秘密", "concept", {
        "brief": "上古神器陨星碎片能够扭曲时空，是贯穿全篇的核心暗线",
        "importance": "high",
        "introduced_chapter": 1,
    })
    store.add_entity("Spy的真实身份", "concept", {
        "brief": "Spy伪装成商贩混入队伍，其真实目的尚未揭露",
        "importance": "medium",
        "introduced_chapter": 2,
    })
    store.add_entity("上古神器", "concept", {
        "brief": "完整的上古神器能够扭转时间，Villain正在收集碎片",
        "importance": "high",
        "introduced_chapter": 1,
        "resolved": False,
    })

    # 伏笔预示关系：概念 -> 未来事件
    store.add_entity("最终决战", "event", {
        "brief": "Hero与Villain的终极对决",
        "chapter_id": 10,
        "resolved": False,
    })
    store.add_entity("神器觉醒", "event", {
        "brief": "上古神器碎片聚合，时空扭曲之力苏醒",
        "chapter_id": 8,
        "resolved": False,
    })
    store.add_entity("Spy叛变", "event", {
        "brief": "Spy在关键时刻暴露真实身份",
        "chapter_id": 5,
        "resolved": True,
    })

    store.add_relation("陨星碎片的秘密", "最终决战", "foreshadows", {"chapter_id": 1})
    store.add_relation("陨星碎片的秘密", "神器觉醒", "foreshadows", {"chapter_id": 1})
    store.add_relation("Spy的真实身份", "Spy叛变", "foreshadows", {"chapter_id": 2})
    store.add_relation("上古神器", "最终决战", "foreshadows", {"chapter_id": 1})

    # 验证节点已添加
    assert store.has_entity("陨星碎片的秘密")
    assert store.has_entity("Spy的真实身份")
    assert store.has_entity("最终决战")
    assert store.get_entity("最终决战")["type"] == "event"
    return {"foreshadow_count": 3}

print(f"  伏笔概念节点: 3 个已创建")

@test("search_graph 搜索'陨星'关键字")
def _():
    from novels_project.memory.graph_memory_tool import search_graph

    # 绑定全局实例
    import novels_project.memory.graph_memory_tool as gmt
    gmt._global_graph_store = store
    gmt._global_graph_query = query

    # 搜索"陨星"（实体名称中包含）
    result = search_graph("陨星")
    print(f"  search_graph('陨星') 输出:\n    {result.replace(chr(10), chr(10)+'    ')}")
    assert "陨星" in result, "Should find 陨星相关节点"
    assert "陨星碎片" in result, "Should find 陨星碎片 item"
    return {"search_result": result}

@test("search_graph 搜索'Spy'关键字")
def _():
    from novels_project.memory.graph_memory_tool import search_graph
    result = search_graph("Spy")
    print(f"  search_graph('Spy') 输出:\n    {result.replace(chr(10), chr(10)+'    ')}")
    assert "Spy" in result, "Should find Spy相关节点"
    # Spy相关节点应包含: Spy(character), Spy的真实身份(concept), Spy叛变(event)
    assert result.count("Spy") >= 2, f"Expected >=2 Spy matches, got {result.count('Spy')}"
    return {"search_result": result}

@test("搜索不存在的关键词返回友好提示")
def _():
    from novels_project.memory.graph_memory_tool import search_graph
    result = search_graph("xyz_not_found_keyword")
    print(f"  search_graph('xyz_not_found_keyword') 输出: {result}")
    assert "未找到" in result, "Should return friendly 'not found' message"
    return {"search_result": result}

@test("find_unresolved_foreshadowing 查询未回收伏笔")
def _():
    unresolved = query.find_unresolved_foreshadowing()
    print(f"  未回收伏笔 ({len(unresolved)} 个):")
    for u in unresolved:
        targets = ", ".join(t["name"] for t in u.get("unresolved_targets", []))
        print(f"    - [{u['concept']}] -> {targets}")
        print(f"      简述: {u.get('brief', 'N/A')[:60]}")

    # Spy的真实身份 -> Spy叛变 (resolved=True)，应该不在未回收列表中
    # 陨星碎片的秘密 -> 最终决战(resolved=False) + 神器觉醒(resolved=False)
    # 上古神器 -> 最终决战(resolved=False)
    assert len(unresolved) >= 2, f"Expected >=2 unresolved, got {len(unresolved)}"

    # 验证已回收的伏笔不在列表中
    unresolved_names = {u["concept"] for u in unresolved}
    assert "Spy的真实身份" not in unresolved_names, "Spy叛变已回收，不应在未回收列表中"

    return {"unresolved": unresolved}

@test("trace_foreshadowing 追踪特定伏笔脉络")
def _():
    from novels_project.memory.graph_memory_tool import trace_foreshadowing
    result = trace_foreshadowing("陨星碎片的秘密")
    print(f"  trace_foreshadowing('陨星碎片的秘密'):\n    {result.replace(chr(10), chr(10)+'    ')}")
    assert "最终决战" in result
    assert "神器觉醒" in result
    return {"trace_result": result}

@test("search_graph 按concept类型过滤搜索")
def _():
    from novels_project.memory.graph_memory_tool import search_graph
    # "陨星碎片的秘密" 是 concept 类型，搜索 "陨星" 按 concept 过滤
    result = search_graph("陨星", entity_type="concept")
    print(f"  search_graph('陨星', entity_type='concept'):\n    {result.replace(chr(10), chr(10)+'    ')}")
    assert "陨星碎片的秘密" in result
    # concept 过滤结果中，实体 type 应为 concept（简介中提到 item 名是正常的）
    assert "[concept]" in result, "Filtered result should contain concept type label"
    return {"filtered_search": result}


# ============================================================
# Phase 3: 角色关系变更 + 增量同步数据一致性
# ============================================================
print("\n" + "=" * 60)
print("Phase 3: 角色关系变更 + 增量同步数据一致性验证")
print("=" * 60)

# 记录变更前状态
@test("记录变更前状态快照")
def _():
    pre_snapshot = {
        "nodes": store.entity_count(),
        "edges": store.relation_count(),
        "hero_relations": store.get_relations(source="Hero"),
        "villain_relations": store.get_relations(source="Villain"),
        "ally_relations": store.get_relations(source="Ally"),
        "spy_relations": store.get_relations(source="Spy"),
        "statistics": store.get_statistics(),
    }
    print(f"  变更前: 节点={pre_snapshot['nodes']} 边={pre_snapshot['edges']}")
    print(f"  Hero关系: {[(r['target'], r['type']) for r in pre_snapshot['hero_relations']]}")
    return pre_snapshot

pre_snapshot = results["记录变更前状态快照"]

@test("新增关系: Hero--betrayed_by-->Spy")
def _():
    # Hero 添加被Spy背叛的关系
    store.add_relation("Hero", "Spy", "enemy", {
        "reason": "betrayal",
        "since_chapter": 2,
        "strength": "intense",
    })
    relations = store.get_relations(source="Hero", target="Spy")
    assert len(relations) >= 1, f"New relation not found: {relations}"
    assert relations[0]["type"] == "enemy"
    return {"new_relations": relations}

@test("删除关系: Spy--subordinate-->Villain")
def _():
    # Spy 脱离 Villain 控制
    removed = store.remove_relation("Spy", "Villain", "subordinate")
    assert removed, "Relation should have been removed"
    relations_after = store.get_relations(source="Spy", target="Villain")
    print(f"  Spy->Villain 删除后关系: {relations_after}")
    return {"removed": True}

@test("新增关系: Ally--knows-->Spy")
def _():
    # Ally 认识了 Spy
    store.add_relation("Ally", "Spy", "knows", {
        "since_chapter": 2,
        "trust_level": "suspicious",
    })
    relations = store.get_relations(source="Ally", target="Spy")
    assert len(relations) >= 1
    return {"new_relations": relations}

@test("新增关系: Hero--friend-->Ally（双向强化）")
def _():
    # 已存在 Hero->Ally friend，添加 Ally->Hero friend
    store.add_relation("Ally", "Hero", "friend", {
        "since_chapter": 1,
        "strength": "strong",
        "note": "生死之交",
    })
    relations = store.get_relations(source="Ally", target="Hero")
    assert len(relations) >= 1
    return {"bidirectional": relations}

@test("修改角色属性: Spy的role和brief更新")
def _():
    # Spy 身份暴露后更新属性
    updated = store.update_entity("Spy", {
        "role": "double_agent",
        "brief": "原Villain的卧底，后背叛Villain转而协助Hero",
        "betrayed_villain": True,
    })
    assert updated
    entity = store.get_entity("Spy")
    assert entity["role"] == "double_agent"
    assert "betrayed_villain" in entity
    print(f"  Spy更新后: role={entity['role']}, brief={entity['brief']}")
    return {"updated_entity": entity}

@test("新增地点和物品节点")
def _():
    store.add_entity("拍卖会场", "location", {"brief": "地下黑市拍卖场，Villain的势力范围"})
    store.add_entity("陨星碎片", "item", {"brief": "上古神器碎片，蕴含时空之力"})
    store.add_relation("Hero", "陨星碎片", "owns", {"since_chapter": 1})
    store.add_relation("陨星碎片", "拍卖会场", "located_at", {"since_chapter": 1})
    assert store.has_entity("拍卖会场")
    assert store.has_entity("陨星碎片")
    return {"new_nodes": 2}

@test("变更后状态对比")
def _():
    post_snapshot = {
        "nodes": store.entity_count(),
        "edges": store.relation_count(),
        "hero_relations": store.get_relations(source="Hero"),
        "villain_relations": store.get_relations(source="Villain"),
        "ally_relations": store.get_relations(source="Ally"),
        "spy_relations": store.get_relations(source="Spy"),
    }
    print(f"  变更后: 节点={post_snapshot['nodes']} 边={post_snapshot['edges']}")

    # 验证节点增量
    nodes_added = post_snapshot["nodes"] - pre_snapshot["nodes"]
    edges_added = post_snapshot["edges"] - pre_snapshot["edges"]
    edges_removed = 1  # 删除了 Spy-subordinate-Villain
    print(f"  节点变化: +{nodes_added}, 边变化: +{edges_added} (删除{edges_removed})")

    # 验证 Spry 关系变更
    spy_targets_after = {r["target"] for r in post_snapshot["spy_relations"]}
    assert "Villain" not in spy_targets_after, "Spy->Villain relation should be deleted"

    # 验证 Hero 新增关系
    hero_targets_after = {r["target"] for r in post_snapshot["hero_relations"]}
    assert "Spy" in hero_targets_after, "Hero->Spy enemy relation should exist"
    assert "陨星碎片" in hero_targets_after, "Hero->陨星碎片 owns should exist"

    # 验证 Ally 新增关系
    ally_targets_after = {r["target"] for r in post_snapshot["ally_relations"]}
    assert "Spy" in ally_targets_after, "Ally->Spy knows should exist"

    return post_snapshot

post_snapshot = results["变更后状态对比"]


# ============================================================
# Phase 4: 手动触发增量同步 + 数据一致性
# ============================================================
print("\n" + "=" * 60)
print("Phase 4: 增量同步验证数据一致性")
print("=" * 60)

@test("手动触发增量同步 /graph sync")
def _():
    nodes_before_sync = store.entity_count()
    edges_before_sync = store.relation_count()

    # force=False: 只处理文件内容有变化的章节，不重复同步人物卡
    result = sync_mgr.sync(mode="incremental", force=False)
    print(f"  同步结果: entities_added={result.get('entities_added', 0)}, "
          f"relations_added={result.get('relations_added', 0)}, "
          f"skipped={result.get('skipped', 0)}")

    nodes_after_sync = store.entity_count()
    edges_after_sync = store.relation_count()
    print(f"  同步后: 节点={nodes_after_sync} 边={edges_after_sync}")

    # 增量同步不应删除已存在的节点
    assert nodes_after_sync >= nodes_before_sync, \
        f"Sync should not delete nodes: {nodes_before_sync} -> {nodes_after_sync}"
    return result

@test("同步后伏笔数据完整性")
def _():
    # 验证伏笔概念节点未被增量同步影响
    assert store.has_entity("陨星碎片的秘密"), "Foreshadow concept should persist"
    assert store.has_entity("Spy的真实身份"), "Foreshadow concept should persist"
    assert store.has_entity("上古神器"), "Foreshadow concept should persist"

    # 验证 foreshadows 关系仍然存在
    foreshadow_rels = store.get_relations(rel_type="foreshadows")
    assert len(foreshadow_rels) >= 3, f"Expected >=3 foreshadows edges, got {len(foreshadow_rels)}"

    return {"foreshadow_edges": len(foreshadow_rels)}

@test("同步后新增关系保留")
def _():
    # 验证手动添加的关系在同步后依然存在
    hero_spy_rel = store.get_relations(source="Hero", target="Spy")
    assert len(hero_spy_rel) >= 1, "Hero->Spy enemy should persist after sync"

    ally_spy_rel = store.get_relations(source="Ally", target="Spy")
    assert len(ally_spy_rel) >= 1, "Ally->Spy knows should persist after sync"

    hero_item_rel = store.get_relations(source="Hero", target="陨星碎片")
    assert len(hero_item_rel) >= 1, "Hero->陨星碎片 owns should persist after sync"

    return {"persisted": True}

@test("同步后角色属性保留")
def _():
    spy = store.get_entity("Spy")
    assert spy["role"] == "double_agent", f"Spy role changed to {spy['role']}"
    assert spy.get("betrayed_villain") is True, "Spy betrayed_villain flag missing"
    return {"spy": spy}

@test("同步后已删除的关系未恢复")
def _():
    spy_villain_rels = store.get_relations(source="Spy", target="Villain")
    # 基本关系可能来自其他路径，但不应该有 subordinate 类型
    subordinate_rels = [r for r in spy_villain_rels if r.get("type") == "subordinate"]
    assert len(subordinate_rels) == 0, \
        f"Deleted subordinate relation should not reappear: {subordinate_rels}"
    return {"no_subordinate_rels": True}

@test("未修改的关系保持不变 (数据一致性)")
def _():
    # 验证未修改的关系（Hero->Mentor, Hero->Villain）仍存在
    hero_mentor = store.get_relations(source="Hero", target="Mentor")
    assert len(hero_mentor) >= 1, "Hero->Mentor should be unchanged"

    hero_villain = store.get_relations(source="Hero", target="Villain")
    assert len(hero_villain) >= 1, "Hero->Villain should be unchanged"

    # Mentor 关系不应被影响
    mentor_relations = store.get_relations(source="Mentor")
    mentor_targets = {r["target"] for r in mentor_relations}
    assert "Hero" in mentor_targets, "Mentor->Hero should be unchanged"
    assert "Villain" in mentor_targets, "Mentor->Villain should be unchanged"

    return {"unchanged_relations": True}


# ============================================================
# Phase 5: 日志输出验证
# ============================================================
print("\n" + "=" * 60)
print("Phase 5: 关键操作节点日志验证")
print("=" * 60)

@test("提取并验证日志内容")
def _():
    log_output = log_stream.getvalue()
    log_lines = log_output.split("\n")

    checks = {
        "GraphMemoryIntegrator 创建": ["[GraphMemoryIntegrator] 创建集成器"],
        "SyncManager 初始化": ["[SyncManager] 初始化完成"],
        "SyncManager 配置": ["[SyncManager] 监控路径已配置", "[SyncManager] 自动同步配置"],
        "全量同步开始": ["[SyncManager] 同步开始 | mode=SyncMode.FULL"],
        "人物卡同步": ["[SyncManager] 全量同步：处理人物卡", "[SyncManager] 全量同步：人物卡完成"],
        "章节同步": ["[SyncManager] 全量同步：处理章节"],
        "同步完成": ["[SyncManager] 同步完成"],
        "增量同步": ["[SyncManager] 增量同步开始"],
        "图谱持久化": ["[SyncManager] 图谱已持久化"],
        "EntityExtractor操作": ["[EntityExtractor]"],
        "GraphMemoryIntegrator初始化": ["[GraphMemoryIntegrator] 初始化完成"],
        "结构化的key=value格式": ["|", "="],
    }

    passed_checks = []
    failed_checks = []

    for check_name, keywords in checks.items():
        found = []
        for kw in keywords:
            for line in log_lines:
                if kw in line:
                    found.append(line.strip()[:150])
                    break
        if len(found) == len(keywords):
            passed_checks.append(check_name)
        else:
            failed_checks.append((check_name, keywords, found))

    print(f"  通过: {len(passed_checks)}/{len(checks)}")
    for c in passed_checks:
        print(f"    [OK] {c}")

    if failed_checks:
        print(f"  未通过: {len(failed_checks)}")
        for name, kw, found in failed_checks:
            print(f"    [FAIL] {name}: expected {kw}, found {found}")

    # 输出关键日志行
    print(f"\n  --- 关键日志摘录 (共 {len(log_lines)} 行) ---")
    key_patterns = [
        "[GraphMemoryIntegrator]", "[SyncManager]", "entity_extractor",
        "nodes=", "edges=", "同步", "extract",
    ]
    shown = 0
    for line in log_lines:
        if any(p in line for p in key_patterns):
            print(f"    {line[:200]}")
            shown += 1
        if shown >= 40:
            break

    # 验证结构化日志格式: key=value pairs
    kv_format_count = 0
    for line in log_lines:
        if " | " in line and "=" in line.split(" | ", 2)[-1] if " | " in line else False:
            kv_format_count += 1
        elif " | " in line:
            kv_format_count += 1

    print(f"\n  结构化日志行数: {kv_format_count}")

    assert len(passed_checks) >= len(checks) - 1, \
        f"Too many failed log checks: {failed_checks}"

    return {
        "total_lines": len(log_lines),
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "structured_log_lines": kv_format_count,
    }


# ============================================================
# Phase 6: 系统关闭 + 持久化验证
# ============================================================
print("\n" + "=" * 60)
print("Phase 6: 关闭与持久化")
print("=" * 60)

@test("安全关闭图谱系统")
def _():
    result = _shutdown_graph(integrator)
    assert result is not None
    assert result["status"] == "shutdown"
    assert result["final_nodes"] >= 8, f"Expected >=8 final nodes, got {result['final_nodes']}"
    print(f"  关闭结果: nodes={result['final_nodes']} edges={result['final_edges']}")
    return result

@test("图谱文件持久化验证")
def _():
    graph_path = Path(project) / "graph" / "knowledge_graph.json"
    assert graph_path.exists(), f"Graph file not found: {graph_path}"
    assert graph_path.stat().st_size > 0, "Graph file is empty"

    # 验证 JSON 可解析
    with open(graph_path, "r") as f:
        data = json.load(f)
    assert "nodes" in data
    assert "links" in data

    # 验证伏笔数据在持久化文件中
    concept_nodes = [n for n in data["nodes"] if n.get("type") == "concept"]
    foreshadow_links = [l for l in data["links"] if l.get("type") == "foreshadows"]

    print(f"  持久化文件: {graph_path.stat().st_size} bytes")
    print(f"  concept 节点: {len(concept_nodes)} 个")
    print(f"  foreshadows 边: {len(foreshadow_links)} 条")

    assert len(concept_nodes) >= 3, f"Expected >=3 concept nodes in persisted file"
    assert len(foreshadow_links) >= 3, f"Expected >=3 foreshadows links in persisted file"

    return {"file_size": graph_path.stat().st_size, "concept_nodes": len(concept_nodes)}


# ---- 清理 ----
shutil.rmtree(tmpdir)
del os.environ["NOVEL_PROJECT_ROOT"]
del os.environ["COMPANY_API_KEY"]

# ---- 汇总 ----
print("\n" + "=" * 60)
print("测试结果汇总")
print("=" * 60)
print(f"  通过: {len(results)} 个测试")
print(f"  失败: {len(errors)} 个测试")

if errors:
    print(f"\n失败详情:")
    for name, e in errors:
        print(f"  - {name}: {e}")
    sys.exit(1)
else:
    print(f"\nALL {len(results)} COMPREHENSIVE INTEGRATION TESTS PASSED")
    sys.exit(0)