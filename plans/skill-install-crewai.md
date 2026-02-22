# 项目级 Skill 安装记录：crewai

## 目标

将下载的 Kilo Code skill 从 [`../../../../Downloads/crewai/SKILL.md`](../../../../Downloads/crewai/SKILL.md:1) 安装为 **当前工作区项目级 skill**，使其在本仓库内优先生效。

## 落地路径

- 已创建：[`skills/crewai/SKILL.md`](../skills/crewai/SKILL.md)
- 回退路径已准备：[`skills-architect/crewai/SKILL.md`](../skills-architect/crewai/SKILL.md)

## 迁移与规范化

来源文件的 frontmatter 含额外字段 `source`/`risk`，为避免 skill 解析器不兼容，已在项目文件中做如下调整：

- frontmatter 仅保留：`name`、`description`
- 将 `source`/`risk` 移入正文 `Metadata` 小节
- 将 `description` 改为以 `Use when` 开头、强调触发条件（便于技能检索与加载）

## 验证步骤（手工）

1. 关闭并重新打开 VS Code（或重启 Kilo Code 会话）
2. 进入任意模式（Architect/Code/Ask 等），确认系统输出的 `available_skills` 列表中出现 `crewai`
3. 用一句明确请求触发：例如让助手设计 CrewAI 多 Agent 结构；确认它选择并加载 `crewai` skill

## 回退与排障策略

若 `available_skills` 中仍未出现 `crewai`：

1. 保持内容不变，将同样的 skill 复制到 mode 专用目录（优先 Architect）：
   - 备选路径：[`skills-architect/crewai/SKILL.md`](../skills-architect/crewai/SKILL.md)
2. 若仍不识别，使用工作区内 Kilo Code 默认目录兜底：
   - 兜底路径：[`.kilocode/skills/crewai/SKILL.md`](../.kilocode/skills/crewai/SKILL.md)
3. 仍不识别则说明当前 Kilo Code 版本**不从工作区加载 skills**（仅加载全局 `~/.kilocode/skills`）。此时需要改为全局安装，或查阅 Kilo Code 的项目级 skills 搜索路径配置。
4. 每次移动/复制后重复“验证步骤（手工）”

## 备注

- 当前仓库是 CrewAI Python 项目（见 [`novels_project/pyproject.toml`](../novels_project/pyproject.toml)），但本次安装的是 **Kilo Code skill**，与 Python 依赖安装无关。
