#!/usr/bin/env python
"""
初始化脚本 - 检查设计文档和配置完整性
"""
import os
import sys
from pathlib import Path
import yaml

class DesignValidator:
    """验证设计文档和配置的完整性"""

    def __init__(self, project_root: str = None):
        if project_root is None:
            # 假设脚本在 src/novels_project/ 下
            self.project_root = Path(__file__).parent.parent.parent
        else:
            self.project_root = Path(project_root)

        self.design_dir = self.project_root / "DESIGN"
        self.config_dir = self.project_root / "src" / "novels_project" / "config"
        self.samples_dir = self.project_root / "samples"

        self.errors = []
        self.warnings = []

    def validate_all(self) -> bool:
        """执行所有验证检查"""
        print("=" * 60)
        print("🔍 CrewAI 小说创作系统 - 初始化检查")
        print("=" * 60)
        print()

        checks = [
            ("设计文档完整性", self._check_design_documents),
            ("配置文件完整性", self._check_config_files),
            ("人物卡库检查", self._check_character_base_cards),
            ("样例库检查", self._check_samples),
            ("环境变量检查", self._check_environment_variables),
        ]

        for check_name, check_func in checks:
            print(f"检查 {check_name}...", end=" ")
            try:
                result = check_func()
                if result:
                    print("✅ 通过")
                else:
                    print("⚠️  警告")
            except Exception as e:
                print(f"❌ 失败")
                self.errors.append(f"{check_name}: {str(e)}")

        print()
        print("=" * 60)

        # 打印报告
        if self.errors:
            print("❌ 发现错误：")
            for error in self.errors:
                print(f"  • {error}")
            print()

        if self.warnings:
            print("⚠️  警告信息：")
            for warning in self.warnings:
                print(f"  • {warning}")
            print()

        if not self.errors and not self.warnings:
            print("✅ 所有检查通过！系统已就绪。")
            return True
        elif not self.errors:
            print("⚠️  所有检查通过（有警告），可以继续。")
            return True
        else:
            print("❌ 初始化失败，请修复上述错误后重试。")
            return False

    def _check_design_documents(self) -> bool:
        """检查设计文档是否完整"""
        required_files = [
            "BRAINSTORM_SUMMARY.md",
            "WORKFLOW.md",
            "AGENTS_DEFINITION.md",
            "DATA_STRUCTURES.md",
            "VALIDATION_CHECKLIST.md",
            "PROMPTS/chief_editor_prompt.md",
            "PROMPTS/character_designer_prompt.md",
            "PROMPTS/plot_writer_prompt.md",
            "PROMPTS/proofreader_prompt.md",
        ]

        missing = []
        for file in required_files:
            file_path = self.design_dir / file
            if not file_path.exists():
                missing.append(file)
            elif file_path.stat().st_size < 100:
                self.warnings.append(f"设计文档 {file} 内容过少（<100字节）")

        if missing:
            raise Exception(f"缺失设计文档: {', '.join(missing)}")

        return True

    def _check_config_files(self) -> bool:
        """检查配置文件是否存在且格式正确"""
        config_files = {
            "agents.yaml": False,  # 暂时可选
            "tasks.yaml": False,   # 暂时可选
            "character_base_cards.yaml": True,  # 必需
        }

        for file, required in config_files.items():
            file_path = self.config_dir / file
            if not file_path.exists():
                if required:
                    raise Exception(f"缺失必需配置文件: {file}")
                else:
                    self.warnings.append(f"配置文件 {file} 不存在（可选）")
            else:
                # 验证 YAML 格式
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        yaml.safe_load(f)
                except yaml.YAMLError as e:
                    raise Exception(f"配置文件 {file} YAML 格式错误: {e}")

        return True

    def _check_character_base_cards(self) -> bool:
        """检查人物卡库"""
        cards_file = self.config_dir / "character_base_cards.yaml"

        if not cards_file.exists():
            raise Exception("人物卡库文件不存在")

        with open(cards_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            raise Exception("人物卡库为空")

        # 检查 S 级人物
        s_tier = data.get('s_tier', {})
        s_count = len(s_tier.get('characters', {}))

        if s_count < 3:
            self.warnings.append(f"S级人物只有 {s_count} 个，建议至少 3-4 个（MVP可以接受）")

        # 检查必填字段
        for tier in ['s_tier', 'a_tier']:
            if tier in data:
                characters = data[tier].get('characters', {})
                for name, char in characters.items():
                    required_fields = ['name', 'role', 'core_personality', 'unique_speaking_style']
                    for field in required_fields:
                        if field not in char or not char[field]:
                            raise Exception(f"人物 {name} 缺少必填字段: {field}")

                    # 检查 example_dialogues
                    style = char.get('unique_speaking_style', {})
                    if isinstance(style, dict):
                        examples = style.get('example_dialogues', [])
                        if not examples or len(examples) < 2:
                            self.warnings.append(f"人物 {name} 的对话示例少于 2 条")

        return True

    def _check_samples(self) -> bool:
        """检查样例库"""
        if not self.samples_dir.exists():
            self.warnings.append("samples/ 目录不存在，将无法使用样例检索")
            return True

        # 统计样例数量
        sample_files = list(self.samples_dir.rglob("*.md"))
        sample_count = len(sample_files)

        if sample_count == 0:
            self.warnings.append("样例库为空，建议至少添加 1-2 个样例（MVP可以接受）")
        elif sample_count < 5:
            self.warnings.append(f"样例库只有 {sample_count} 个样例，建议至少 5 个")

        return True

    def _check_environment_variables(self) -> bool:
        """检查环境变量"""
        api_key = os.getenv('COMPANY_API_KEY')

        if not api_key:
            raise Exception("环境变量 COMPANY_API_KEY 未设置")

        if ':' not in api_key:
            self.warnings.append("COMPANY_API_KEY 格式可能不正确（应为 APP_ID:APP_KEY）")

        return True


def main():
    """主函数"""
    validator = DesignValidator()
    success = validator.validate_all()

    if success:
        print()
        print("🚀 可以开始执行：python run.py --chapter 1")
        sys.exit(0)
    else:
        print()
        print("📖 请参考 PROJECT_STATUS.md 了解如何准备数据")
        sys.exit(1)


if __name__ == "__main__":
    main()
