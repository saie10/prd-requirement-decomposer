---
name: prd-requirement-decomposer
description: 当需要解析墨刀或 Axhub 的 PRD 分享链接，并按目录子树或单页范围输出供 AI 继续理解和推理的结构化需求输入时使用。
---

# PRD 需求拆解

把 `Modao / Axhub` 的 PRD 分享链接转换成更适合 AI 继续理解和推理的结构化输入。

共享说明优先参考：

- [README.md](README.md)
- [docs/output-schema.md](docs/output-schema.md)
- [docs/environment.md](docs/environment.md)
- [docs/usage-examples.md](docs/usage-examples.md)

## 什么时候用

在这些场景使用：

- 输入是 `Modao` 或 `Axhub` 的 PRD 分享链接
- 只需要解析一个目录子树或一个单页
- 当前目标是先让 AI 把需求读稳，再继续做分析、讨论或规划

不要用在这些事情上：

- 生成最终对外需求文档
- 直接提出实现方案或代码修改建议
- 在页面原文之外过度推断产品意图

## 怎么跑

优先运行：

```bash
scripts/extract_prd_pages.sh --scope-page '<page-label>' '<url>' '<output-dir>'
scripts/extract_prd_pages.sh --scope-dir '<dir-label>' '<url>' '<output-dir>'
```

常用附加参数：

- `--with-screenshot`
- `--output-mode concise|standard|rich`

推荐默认：

- 优先用 `--output-mode concise`
- 只有明确需要回溯页面结构或调试时，才提升到 `standard / rich`

如果用户没有指定输出目录，默认使用：

- `${TMPDIR:-/tmp}/prd-requirement-decomposer/...`

## 先看什么输出

先看：

- `extraction-summary.json`
- `understanding-input.json`

必要时再看：

- `pages.json`
- `page-*/page.json`

主理解字段优先级：

- `goal`
- `pageSummary`
- `understandingOutline`
- `sections`
- `mainRequirements`
- `globalRules`
- `visualSignals`

增强字段：

- `semanticSignals`
- `evidenceReferences`

默认最后一步：

- 由 AI 基于 `understanding-input.json` 在对话里输出一版详细、结构化的需求复述，供人工快速核对是否理解偏差
- 复述建议至少包含：
  - 需求总述
  - 主需求
  - 配套需求
  - 规则与约束
  - 示例与展示口径
  - 风险与待确认项

## 怎么判断结果是否可信

先看 `extraction-summary.json`：

- `primary`
- `legacy-fallback`
- `blocked`

优先信任：

- `mode=primary`
- `fallbackUsed=false`

如果结果是 `blocked`：

- 解释结构化失败原因
- 不要猜测页面内容

## 可靠性原则

- 主链路是 Node Playwright collector
- `extraction-summary.json` 会明确标记 `primary / legacy-fallback / blocked`
- `no_scope_match` 这类明确范围不命中的情况，不会自动 fallback
- 以正文文本为主输入，`semanticSignals` 和截图信号只做增强
- 页面是强视觉页时，可以结合截图核对，但不要让截图替代正文主干
