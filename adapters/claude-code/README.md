# Claude Code Adapter

这个目录放的是给 `Claude Code` 使用的 subagent 包装。

官方参考：

- [Claude Code settings](https://docs.anthropic.com/en/docs/claude-code/settings)
- [Claude Code subagents](https://docs.anthropic.com/en/docs/claude-code/sub-agents)

## 推荐接法

对 Claude Code，不建议强行照搬 `SKILL.md` 形式。更自然的适配方式是：

- 把 [subagent.md](subagent.md) 转成 `.claude/agents/` 下的项目级或用户级 subagent

例如：

- 项目级：`.claude/agents/prd-requirement-decomposer.md`
- 用户级：`~/.claude/agents/prd-requirement-decomposer.md`

如果 subagent 不和工具仓库放在同一个工作区，建议先配置：

```bash
export PRD_TOOL_HOME=/absolute/path/to/prd-requirement-decomposer
```

之后统一通过：

- `$PRD_TOOL_HOME/scripts/extract_prd_pages.sh`

调用核心脚本，而不是假设当前工作目录里存在 `scripts/`。

## 设计原则

- 只包装 Claude Code 的触发和使用方式
- 不复制核心脚本
- 输出契约以 `understanding-input.json` 为准
- 默认优先 `--output-mode concise`，只有明确需要页面结构回溯或调试时才提升到 `standard / rich`

## 最小验证

完成安装后，建议直接在工具仓库根目录执行：

- `python3 scripts/run_regression_checks.py`
- `scripts/run_real_smoke_tests.sh axhub-page`
