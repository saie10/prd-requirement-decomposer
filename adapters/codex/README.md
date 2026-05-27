# Codex Adapter

仓库根目录的 [SKILL.md](../../SKILL.md) 是 Codex 直接安装使用的入口。

这个目录的作用是：

- 说明 Codex 侧如何理解这个工具
- 补充 Codex 侧的适配说明

## 当前策略

- 核心能力仍以根目录 `scripts/` 为唯一真源
- 根目录 `SKILL.md` 继续服务 Codex
- 通用说明优先看：
  - [README.md](../../README.md)
  - [docs/output-schema.md](../../docs/output-schema.md)
  - [docs/environment.md](../../docs/environment.md)

## 最小验证

完成安装后，建议至少跑一次：

- `python3 scripts/run_regression_checks.py`
- `scripts/run_real_smoke_tests.sh axhub-page`
