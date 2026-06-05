#!/usr/bin/env python3
"""
OpenRouter (owl-alpha) 模型集成测试脚本

使用方法:
    python test_openrouter_integration.py

前置条件:
    1. 后端服务已启动 (http://localhost:8000)
    2. OpenRouter API Key 已配置在 model_providers.yaml
"""

import json
import time
import sys
from datetime import datetime
from pathlib import Path

import requests

# 配置
BASE_URL = "http://localhost:8000/api"
MODEL_ID = "openrouter/owl-alpha"

# 测试结果存储
test_results = []


class TestResult:
    def __init__(self, case_id: str, name: str):
        self.case_id = case_id
        self.name = name
        self.passed = False
        self.error = None
        self.response_time = 0
        self.response_data = None
        self.status_code = None


def log(msg: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    symbols = {"INFO": "📋", "PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "SKIP": "⏭️"}
    print(f"[{timestamp}] {symbols.get(level, '•')} {msg}")


def log_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check_server_health() -> bool:
    """检查服务健康状态"""
    try:
        resp = requests.get(f"{BASE_URL.rsplit('/api', 1)[0]}/api/health", timeout=5)
        if resp.status_code == 200:
            log(f"服务健康检查通过: {resp.json()}", "PASS")
            return True
        return False
    except Exception as e:
        log(f"服务健康检查失败: {e}", "FAIL")
        return False


def check_model_config() -> bool:
    """检查模型配置"""
    try:
        resp = requests.get(f"{BASE_URL}/settings/models", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            providers = data.get("providers", {})
            for pid, pdata in providers.items():
                models = pdata.get("models", [])
                for m in models:
                    if "owl" in m.get("id", "").lower():
                        log(f"找到 owl 模型: {pid}/{m.get('id')} - {m.get('name')}", "PASS")
                        return True
            log("未找到 owl 模型配置", "WARN")
            return True  # 不强制要求，因为可能用其他模型
        return False
    except Exception as e:
        log(f"模型配置检查失败: {e}", "FAIL")
        return False


# ============================================================
# Agent 配置测试
# ============================================================

def test_get_agents():
    """TC-AGENT-001: 获取所有 Agent 配置"""
    result = TestResult("TC-AGENT-001", "获取所有 Agent 配置")

    try:
        start = time.time()
        resp = requests.get(f"{BASE_URL}/agents/", timeout=10)
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            result.passed = len(data) >= 4
            result.response_data = data
            if result.passed:
                log(f"获取到 {len(data)} 个 Agent 配置", "PASS")
            else:
                log(f"Agent 数量不足，期望 >= 4，实际 {len(data)}", "FAIL")
        else:
            result.error = f"HTTP {resp.status_code}"

    except Exception as e:
        result.error = str(e)
        log(f"获取 Agent 配置失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


def test_update_agent_model():
    """TC-AGENT-002: 更新 Agent 模型配置"""
    result = TestResult("TC-AGENT-002", "更新 Agent 模型配置")

    try:
        # 更新 master agent 使用 owl-alpha
        start = time.time()
        resp = requests.put(
            f"{BASE_URL}/agents/master",
            json={"model": MODEL_ID},
            timeout=10
        )
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            config = data.get("config", {})
            result.passed = config.get("model") == MODEL_ID
            result.response_data = data
            if result.passed:
                log(f"Agent 模型已更新为 {MODEL_ID}", "PASS")
            else:
                result.error = f"模型未更新: {config.get('model')}"
                log(f"Agent 模型更新失败: {result.error}", "FAIL")
        else:
            result.error = f"HTTP {resp.status_code}"

    except Exception as e:
        result.error = str(e)
        log(f"更新 Agent 模型失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


def test_toggle_agent():
    """TC-AGENT-003: 启用/禁用 Agent"""
    result = TestResult("TC-AGENT-003", "启用/禁用 Agent")

    try:
        # 禁用 proofreader
        start = time.time()
        resp = requests.put(
            f"{BASE_URL}/agents/proofreader/toggle",
            json={"enabled": False},
            timeout=10
        )
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            disabled = data.get("enabled") == False

            # 重新启用
            resp2 = requests.put(
                f"{BASE_URL}/agents/proofreader/toggle",
                json={"enabled": True},
                timeout=10
            )
            result.passed = disabled and resp2.status_code == 200
            result.response_data = {"disabled": data, "enabled": resp2.json()}
            log("Agent 启用/禁用功能正常", "PASS")
        else:
            result.error = f"HTTP {resp.status_code}"

    except Exception as e:
        result.error = str(e)
        log(f"启用/禁用 Agent 失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


def test_get_agent_status():
    """TC-AGENT-004: 获取 Agent 运行状态"""
    result = TestResult("TC-AGENT-004", "获取 Agent 运行状态")

    try:
        start = time.time()
        resp = requests.get(f"{BASE_URL}/agents/master/status", timeout=10)
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["name", "enabled", "model", "status"]
            result.passed = all(f in data for f in required_fields)
            result.response_data = data
            if result.passed:
                log(f"Agent 状态: {data.get('status')}, 模型: {data.get('model')}", "PASS")
            else:
                result.error = f"缺少必要字段"
                log(f"Agent 状态响应缺少字段", "FAIL")
        else:
            result.error = f"HTTP {resp.status_code}"

    except Exception as e:
        result.error = str(e)
        log(f"获取 Agent 状态失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


# ============================================================
# 内容管理测试
# ============================================================

def test_get_characters():
    """TC-CONTENT-001: 获取人物卡列表"""
    result = TestResult("TC-CONTENT-001", "获取人物卡列表")

    try:
        start = time.time()
        resp = requests.get(f"{BASE_URL}/content/characters", timeout=10)
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            result.passed = isinstance(data, list)
            result.response_data = {"count": len(data), "items": data[:3] if data else []}
            log(f"获取到 {len(data)} 个人物卡", "PASS")
        else:
            result.error = f"HTTP {resp.status_code}"

    except Exception as e:
        result.error = str(e)
        log(f"获取人物卡列表失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


def test_create_character():
    """TC-CONTENT-002: 创建人物卡"""
    result = TestResult("TC-CONTENT-002", "创建人物卡")

    try:
        payload = {
            "name": "测试人物_OWL",
            "tier": "b_tier",
            "role": "测试角色",
            "brief": "这是一个用于测试的人物"
        }

        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/content/characters",
            json=payload,
            timeout=10
        )
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code in (200, 201):
            data = resp.json()
            result.passed = data.get("status") == "created"
            result.response_data = data
            if result.passed:
                log(f"人物卡创建成功: {payload['name']}", "PASS")
            else:
                result.error = f"状态异常: {data.get('status')}"
        else:
            result.error = f"HTTP {resp.status_code}"

    except Exception as e:
        result.error = str(e)
        log(f"创建人物卡失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


def test_ai_optimize():
    """TC-CONTENT-006: AI 优化人物内容 ⭐ 核心测试"""
    result = TestResult("TC-CONTENT-006", "AI 优化人物内容")

    try:
        payload = {
            "field": "brief",
            "current_value": "一个普通的商人",
            "character_name": "测试人物_OWL",
            "context": {
                "role": "商人",
                "personality": "精明、狡猾"
            }
        }

        log(f"开始 AI 优化测试 (使用 {MODEL_ID})...", "INFO")
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/content/characters/optimize",
            json=payload,
            timeout=60  # AI 调用可能需要更长时间
        )
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            result.passed = "optimized_value" in data
            result.response_data = {
                "field": data.get("field"),
                "optimized_value": data.get("optimized_value", "")[:100] + "...",
                "explanation": data.get("explanation")
            }
            if result.passed:
                log(f"AI 优化成功 (耗时: {result.response_time:.0f}ms)", "PASS")
                log(f"优化结果: {data.get('optimized_value', '')[:80]}...", "INFO")
            else:
                result.error = "响应缺少 optimized_value"
                log(f"AI 优化响应格式异常", "FAIL")
        else:
            result.error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            log(f"AI 优化失败: {result.error}", "FAIL")

    except requests.exceptions.Timeout:
        result.error = "请求超时 (60秒)"
        log(f"AI 优化超时", "FAIL")
    except Exception as e:
        result.error = str(e)
        log(f"AI 优化失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


def test_global_search():
    """TC-CONTENT-010: 全局搜索"""
    result = TestResult("TC-CONTENT-010", "全局搜索")

    try:
        start = time.time()
        resp = requests.get(
            f"{BASE_URL}/content/search",
            params={"q": "测试"},
            timeout=10
        )
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            result.passed = "results" in data
            result.response_data = {
                "query": data.get("query"),
                "count": data.get("count", 0),
                "results": data.get("results", [])[:3]
            }
            log(f"搜索完成，找到 {data.get('count', 0)} 个结果", "PASS")
        else:
            result.error = f"HTTP {resp.status_code}"

    except Exception as e:
        result.error = str(e)
        log(f"全局搜索失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


# ============================================================
# 记忆管理测试
# ============================================================

def test_get_entities():
    """TC-MEMORY-001: 获取实体列表"""
    result = TestResult("TC-MEMORY-001", "获取实体列表")

    try:
        start = time.time()
        resp = requests.get(f"{BASE_URL}/memory/entities", timeout=10)
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            result.passed = "entities" in data and "total" in data
            result.response_data = {
                "total": data.get("total", 0),
                "count": len(data.get("entities", []))
            }
            log(f"获取到 {data.get('total', 0)} 个实体", "PASS")
        else:
            result.error = f"HTTP {resp.status_code}"

    except Exception as e:
        result.error = str(e)
        log(f"获取实体列表失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


def test_memory_stats():
    """TC-MEMORY-010: 获取记忆统计"""
    result = TestResult("TC-MEMORY-010", "获取记忆统计")

    try:
        start = time.time()
        resp = requests.get(f"{BASE_URL}/memory/stats", timeout=10)
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            result.passed = isinstance(data, dict)
            result.response_data = data
            log(f"记忆统计: {json.dumps(data, ensure_ascii=False)[:100]}", "PASS")
        else:
            result.error = f"HTTP {resp.status_code}"

    except Exception as e:
        result.error = str(e)
        log(f"获取记忆统计失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


def test_memory_sync():
    """TC-MEMORY-012: 手动触发记忆同步"""
    result = TestResult("TC-MEMORY-012", "手动触发记忆同步")

    try:
        start = time.time()
        resp = requests.post(f"{BASE_URL}/memory/sync", timeout=30)
        result.response_time = (time.time() - start) * 1000
        result.status_code = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            result.passed = data.get("status") == "synced"
            result.response_data = data
            if result.passed:
                log(f"记忆同步成功", "PASS")
            else:
                result.error = f"同步状态异常: {data.get('status')}"
        else:
            result.error = f"HTTP {resp.status_code}"

    except Exception as e:
        result.error = str(e)
        log(f"记忆同步失败: {e}", "FAIL")

    test_results.append(result)
    return result.passed


# ============================================================
# 测试报告
# ============================================================

def print_summary():
    """打印测试结果汇总"""
    log_section("测试结果汇总")

    total = len(test_results)
    passed = sum(1 for r in test_results if r.passed)
    failed = total - passed

    print(f"\n总用例数: {total}")
    print(f"通过: {passed} ({passed/total*100:.1f}%)")
    print(f"失败: {failed} ({failed/total*100:.1f}%)")

    if failed > 0:
        log_section("失败用例")
        for r in test_results:
            if not r.passed:
                print(f"\n❌ {r.case_id} - {r.name}")
                print(f"   错误: {r.error}")
                print(f"   HTTP: {r.status_code}")
                print(f"   耗时: {r.response_time:.0f}ms")

    log_section("详细结果")
    for r in test_results:
        status = "✅" if r.passed else "❌"
        print(f"{status} {r.case_id} | {r.name:<30} | {r.response_time:>6.0f}ms | HTTP {r.status_code}")

    return passed == total


# ============================================================
# 主函数
# ============================================================

def main():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║     OpenRouter (owl-alpha) 模型集成测试                      ║
║     测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                            ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # 前置检查
    log_section("阶段1: 前置条件检查")
    if not check_server_health():
        log("服务不可用，请确保后端已启动 (http://localhost:8000)", "FAIL")
        sys.exit(1)

    check_model_config()

    # Agent 配置测试
    log_section("阶段2: Agent 配置测试")
    test_get_agents()
    test_update_agent_model()
    test_toggle_agent()
    test_get_agent_status()

    # 内容管理测试
    log_section("阶段3: 内容管理测试")
    test_get_characters()
    test_create_character()
    test_ai_optimize()  # 核心测试
    test_global_search()

    # 记忆管理测试
    log_section("阶段4: 记忆管理测试")
    test_get_entities()
    test_memory_stats()
    test_memory_sync()

    # 结果汇总
    success = print_summary()

    if success:
        log("\n🎉 所有测试通过！模型集成验证成功。", "PASS")
        sys.exit(0)
    else:
        log("\n⚠️ 部分测试失败，请检查上述失败用例。", "FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
