#!/usr/bin/env python
"""
模型配置验证脚本
用来测试自定义模型提供商是否正确配置
"""
import os
import sys

def test_environment_variables():
    """测试环境变量是否正确设置"""
    print("📋 检查环境变量...")

    required_vars = {
        'COMPANY_API_KEY': '公司 API 密钥',
        'API_BASE_URL': '(可选) API 基础 URL',
        'MODEL_NAME': '(可选) 模型名称'
    }

    for var, description in required_vars.items():
        value = os.getenv(var)
        if var == 'COMPANY_API_KEY' and not value:
            print(f"❌ {var}: 未设置 ({description})")
            return False
        elif value:
            # 隐藏敏感信息
            masked_value = value[:5] + '***' + value[-2:] if len(value) > 10 else '***'
            print(f"✅ {var}: 已设置 ({description})")
        else:
            print(f"⚠️  {var}: 未设置，将使用默认值")

    return True

def test_imports():
    """测试必要的包是否已安装"""
    print("\n📦 检查依赖包...")

    required_packages = [
        ('crewai', 'CrewAI'),
        ('dotenv', 'python-dotenv')
    ]

    for package, display_name in required_packages:
        try:
            __import__(package)
            print(f"✅ {display_name}: 已安装")
        except ImportError:
            print(f"❌ {display_name}: 未安装")
            return False

    return True

def test_llm_initialization():
    """测试 LLM 初始化"""
    print("\n🤖 测试 LLM 初始化...")

    try:
        from novels_project.crew import NovelsProject

        # 测试默认模型
        print("  尝试初始化默认模型 (gemini-3-pro)...")
        crew1 = NovelsProject()
        print(f"  ✅ 默认模型初始化成功 (模型: {crew1.model_name})")

        # 测试指定模型
        print("  尝试初始化 gpt-5.2 模型...")
        crew2 = NovelsProject(model_name='gpt-5.2')
        print(f"  ✅ 指定模型初始化成功 (模型: {crew2.model_name})")

        return True
    except Exception as e:
        print(f"  ❌ LLM 初始化失败: {e}")
        return False

def test_supported_models():
    """显示支持的模型列表"""
    print("\n📊 支持的模型列表:")

    from novels_project.main import SUPPORTED_MODELS
    for model in SUPPORTED_MODELS:
        print(f"  • {model}")

def main():
    """运行所有测试"""
    print("=" * 50)
    print("🔧 CrewAI 自定义模型配置验证")
    print("=" * 50)

    tests = [
        test_environment_variables,
        test_imports,
        test_supported_models,
        test_llm_initialization
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append(False)

    print("\n" + "=" * 50)
    if all(results):
        print("✅ 所有测试通过！配置正确。")
        print("\n快速开始:")
        print("  crewai run")
        print("  或")
        print("  python -m novels_project.main run --model gpt-5.2")
        return 0
    else:
        print("❌ 部分测试失败，请检查配置。")
        return 1

if __name__ == '__main__':
    sys.exit(main())
