# Kimi Code CLI Adapter

这个目录放的是给 `Kimi Code CLI` 使用的 skill 包装。

官方参考：

- [Kimi Code Docs: Skills](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html)
- [Using Skills in Kimi Code](https://www.kimi.com/help/agent/use-skills-in-code)

## 使用方式

把 [SKILL.md](SKILL.md) 放到 Kimi Code CLI 的 skills 目录下即可。

如果这个 skill 目录本身不在当前项目工作区里，建议先配置：

```bash
export PRD_TOOL_HOME=/absolute/path/to/prd-requirement-decomposer
```

之后由 skill 统一通过：

- `$PRD_TOOL_HOME/scripts/extract_prd_pages.sh`

调用核心脚本，而不是假设当前工作目录里一定有 `scripts/`。

更推荐的平台无关目录：

- `~/.config/agents/skills/`

Kimi Code CLI 也支持搜索：

- `~/.kimi/skills/`
- `~/.claude/skills/`
- `~/.codex/skills/`

## 设计原则

- 只适配 skill 文案，不改核心脚本
- 输出契约以 `understanding-input.json` 为准
- 详细字段和环境说明继续复用根目录文档
- 默认优先 `--output-mode concise`，减少上下文污染；只有明确需要回溯页面结构或调试时，才使用 `standard` 或 `rich`

## 最小验证

完成安装后，建议直接在工具仓库根目录执行：

- `python3 scripts/run_regression_checks.py`
- `scripts/run_real_smoke_tests.sh axhub-page`
