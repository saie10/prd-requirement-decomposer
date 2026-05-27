# PRD Requirement Decomposer

把 `Modao / Axhub` 的 PRD 分享链接转换成更适合 AI 继续理解、推理和后续处理的结构化输入。

默认主产物：

- `understanding-input.json`

它不是最终文档生成器，而是一个：

**PRD -> AI 可消费理解输入**

的前处理器。

## Highlights

- 支持 `Modao` 和 `Axhub`
- 支持单页和目录子树范围抽取
- 主链路使用 Node Playwright collector
- 输出 `understanding-input.json` 和 `extraction-summary.json`
- 支持 `Codex`、`Kimi Code CLI`、`Claude Code` 三种适配层

## Quick Start

在仓库根目录执行：

```bash
npm install
```

如果本机没有可用的 Chrome，或者希望让工具回退到 Playwright 自带 Chromium，再执行：

```bash
npx playwright install chromium
```

快速自检建议：

```bash
python3 scripts/run_regression_checks.py
scripts/run_real_smoke_tests.sh axhub-page
```

如果主链路正常，smoke 输出里应看到：

- `mode=primary`
- `fallbackUsed=false`

最常用的单页抽取：

```bash
scripts/extract_prd_pages.sh \
  --scope-page '15899·指标卡支持选择时间范围、适配查询粒度、自定义数值格式' \
  'https://axhub.im/ax9/88a869475d1591b8/#id=4o2e14&p=15899%C2%B7%E6%8C%87%E6%A0%87%E5%8D%A1%E6%94%AF%E6%8C%81%E9%80%89%E6%8B%A9%E6%97%B6%E9%97%B4%E8%8C%83%E5%9B%B4%E3%80%81%E9%80%82%E9%85%8D%E6%9F%A5%E8%AF%A2%E7%B2%92%E5%BA%A6%E3%80%81%E8%87%AA%E5%AE%9A%E4%B9%89%E6%95%B0%E5%80%BC%E6%A0%BC%E5%BC%8F&g=1'
```

核心脚本会优先尝试本机 Chrome；如果 Chrome 不可用，再回退到已安装的 Playwright Chromium。

## When To Use

适合这些场景：

- 需要让 AI 先把 PRD 读稳，再继续做讨论、规划或实现分析
- PRD 很大，但当前只关心某个目录或某个单页
- 原始页面里混着正文、规则、配置块、示例口径、截图信息，直接喂给 AI 不够稳
- 需要把页面截图信号、控件语义和规则块一起交给下游 AI

不适合这些场景：

- 直接生成最终对外需求文档
- 让工具代替人工做实现方案或代码修改建议
- 页面本身不可访问，且无法提供导出文档或正文

## Outputs

默认主产物：

- `understanding-input.json`
- `extraction-summary.json`

辅助产物：

- `pages.json`
- 每页精简后的 `page.json`
- 显式开启截图时保留 `page.png`

默认交互方式：

- 工具负责生成 `understanding-input.json`
- AI 读取这个 JSON 后，在对话里输出一版详细、结构化的需求复述，供人工快速核对理解是否有偏差
- 如果最后一环解析失败，工具也会尽量输出结构化的 `blocked` JSON，而不是只留下 traceback 或空结果

更多字段和输出细节见：

- [docs/output-schema.md](docs/output-schema.md)

## Installation Notes

环境依赖和初始化说明见：

- [docs/environment.md](docs/environment.md)

安装完成后，建议至少跑一次：

- `python3 scripts/run_regression_checks.py`
- `scripts/run_real_smoke_tests.sh axhub-page`

更多命令示例见：

- [docs/usage-examples.md](docs/usage-examples.md)

## Repository Layout

- [scripts](scripts)
  - 核心脚本
- [tests](tests)
  - 基础夹具
- [docs](docs)
  - 平台中立说明
- [adapters](adapters)
  - `codex`
  - `kimi-code`
  - `claude-code`

## Platform Adapters

- `Codex`
  - 根目录 [SKILL.md](SKILL.md) 是当前可直接安装使用的入口
  - 额外说明在 [adapters/codex/README.md](adapters/codex/README.md)
- `Kimi Code CLI`
  - 使用 [adapters/kimi-code/SKILL.md](adapters/kimi-code/SKILL.md)
- `Claude Code`
  - 使用 [adapters/claude-code/subagent.md](adapters/claude-code/subagent.md)

这些适配层只包装“如何触发、如何解释输出”，不会改核心脚本和输出契约。

## Implementation Notes

- 主采集链路是 Node Playwright collector
- `extraction-summary.json` 会明确标记 `primary / legacy-fallback / blocked`
- 输出重点放在：
  - `goal`
  - `sections`
  - `mainRequirements`
  - `globalRules`
  - `exampleDisplay`
  - `visualSignals`
  - `semanticSignals`
  - `evidenceReferences`

## Maintenance Principles

- 核心脚本只维护一份
- 三端适配层不各自发明新的输出格式
- 输出契约只以 `understanding-input.json` 为准
- 新增平台适配时，优先补包装层，不先改核心能力层
