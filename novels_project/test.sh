#!/bin/bash
# 自动测试脚本

echo "=========================================="
echo "🧪 CrewAI 小说创作系统 - 自动测试"
echo "=========================================="
echo ""

# 检查环境变量
echo "📋 步骤 1: 检查环境变量"
if [ -z "$COMPANY_API_KEY" ]; then
    echo "   ❌ COMPANY_API_KEY 未设置"
    echo "   请运行: export COMPANY_API_KEY=your_app_id:your_app_key"
    exit 1
else
    echo "   ✅ COMPANY_API_KEY 已设置"
fi

# 运行初始化检查
echo ""
echo "📋 步骤 2: 运行初始化检查"
python src/novels_project/initialize.py
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 初始化检查失败"
    echo "请参考 MVP_QUICKSTART.md 准备数据"
    exit 1
fi

# 运行单元测试
echo ""
echo "📋 步骤 3: 运行单元测试"
python tests/test_system.py
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 单元测试失败"
    exit 1
fi

# 可选：运行第 1 章模拟测试
echo ""
echo "📋 步骤 4: 第 1 章模拟运行（dry-run）"
python run.py --chapter 1 --dry-run

echo ""
echo "=========================================="
echo "✅ 所有测试通过！"
echo "=========================================="
echo ""
echo "🚀 准备运行第 1 章："
echo "   python run.py --chapter 1"
echo ""
