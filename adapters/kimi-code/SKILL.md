---
name: prd-requirement-decomposer
description: Use when you need to parse Modao or Axhub PRD share links and produce structured requirement understanding input for downstream AI reasoning, scoped to a directory subtree or single page.
---

# PRD Requirement Decomposer

Use this skill when the input is a `Modao` or `Axhub` PRD share link and the goal is to produce structured AI-readable requirement input rather than a polished human document.

## When to use

Use this skill when:

- the user provides a `Modao` or `Axhub` PRD share link
- only a directory subtree or a single page needs to be parsed
- downstream AI needs stable requirement structure before planning or implementation
- raw PRD pages mix text, rules, examples, screenshots, and configuration semantics

Do not use this skill when:

- the user wants a final outward-facing requirement document
- the page itself is inaccessible and there is no export or raw text available
- the task is implementation design or code change planning instead of PRD understanding

## Primary artifact

The default primary artifact is:

- `understanding-input.json`

Read this file first. Then optionally inspect:

- `extraction-summary.json`
- `pages.json`
- `page-*/page.json`

## How to run

If the adapter is installed globally rather than used from the repository root, set:

```bash
export PRD_TOOL_HOME=/absolute/path/to/prd-requirement-decomposer
```

Preferred commands:

```bash
$PRD_TOOL_HOME/scripts/extract_prd_pages.sh --output-mode concise --scope-page '<page-label>' '<url>' '<output-dir>'
$PRD_TOOL_HOME/scripts/extract_prd_pages.sh --output-mode concise --scope-dir '<dir-label>' '<url>' '<output-dir>'
```

Optional flags:

- `--with-screenshot`
- `--output-mode concise|standard|rich`

Default recommendation:

- Always prefer `--output-mode concise` unless deep layout debugging is explicitly required.

## What to read in the output

Prioritize these fields from `understanding-input.json`:

- `goal`
- `pageSummary`
- `understandingOutline`
- `sections`
- `mainRequirements`
- `globalRules`
- `visualSignals`

Treat these as enhancement layers:

- `semanticSignals`
- `evidenceReferences`

## Reliability checks

Before trusting the extraction, inspect `extraction-summary.json`:

- `primary`
- `legacy-fallback`
- `blocked`

Prefer results where:

- `mode=primary`
- `fallbackUsed=false`

If the result is `blocked`, explain the failure using the structured reason instead of guessing.

## References

For the shared tool description and stable schema, read:

- [README.md](../../README.md)
- [docs/output-schema.md](../../docs/output-schema.md)
- [docs/environment.md](../../docs/environment.md)
- [docs/usage-examples.md](../../docs/usage-examples.md)
