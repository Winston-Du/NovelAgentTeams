#!/usr/bin/env python
"""
向量库初始化脚本
用于预先构建样例检索的向量库
"""
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    print("=" * 60)
    print("📚 向量库初始化脚本")
    print("=" * 60)
    print()

    # 检查样例目录
    sample_dir = Path("samples")
    if not sample_dir.exists():
        print(f"❌ 样例目录不存在: {sample_dir}")
        print("   请先创建样例目录并添加 Markdown 文件")
        return

    # 检查样例文件
    sample_files = list(sample_dir.glob("**/*.md"))
    if not sample_files:
        print(f"❌ 样例目录中没有 Markdown 文件: {sample_dir}")
        print("   请先添加写作样例")
        return

    print(f"📄 找到 {len(sample_files)} 个样例文件:")
    for f in sample_files:
        print(f"   - {f}")
    print()

    # 初始化向量库
    print("🔨 开始构建向量库...")
    print()

    try:
        from novels_project.retrieval_engine import get_retrieval_engine
        engine = get_retrieval_engine()
        engine._ensure_initialized()

        if engine.vectorstore:
            count = engine.vectorstore._collection.count()
            print()
            print("=" * 60)
            print(f"✅ 向量库初始化完成！")
            print(f"   文档块数量: {count}")
            print("=" * 60)
        else:
            print()
            print("=" * 60)
            print("⚠️  向量库初始化失败")
            print("   可能原因：")
            print("   1. SILICONFLOW_API_KEY 环境变量未设置")
            print("   2. SiliconFlow Embedding API 不可用")
            print("   3. 网络连接问题")
            print("=" * 60)

    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ 初始化失败: {e}")
        print("=" * 60)


if __name__ == "__main__":
    main()
