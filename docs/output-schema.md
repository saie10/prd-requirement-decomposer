# Output Schema

这个文档只描述当前主产物的字段契约，不描述平台如何触发 skill。

默认主产物：

- `understanding-input.json`
- `extraction-summary.json`

## understanding-input.json

### 根层稳定主字段

- `artifactType`
- `formatVersion`
- `sourceUrl`
- `scopeType`
- `scopeValue`
- `pageCount`
- `pages`

### 页面层稳定主字段

- `label`
- `pageSummary`
- `goal`
- `sections`
- `mainRequirements`
- `supportingRequirements`
- `globalRules`
- `exampleDisplay`
- `suspectedIssues`
- `visualSignals`
- `understandingOutline`

### section 层稳定主字段

- `title`
- `summary`
- `mainRequirements`
- `supportingRequirements`
- `rulesAndConstraints`
- `exampleDisplay`

### 增强字段

这些字段有值时应优先利用，但不应该被当作每页必有：

- `semanticSignals`
- `evidenceReferences`

### 允许为空或缺失

下面这些字段在真实页面里允许为空，不应被当作抽取失败：

- `goal`
- `supportingRequirements`
- `globalRules`
- `exampleDisplay`
- `suspectedIssues`
- `semanticSignals`
- `evidenceReferences`

### 推荐消费顺序

后续 AI 或脚本建议按下面顺序理解：

1. `goal`
2. `pageSummary`
3. `understandingOutline`
4. `sections`
5. `mainRequirements`
6. `globalRules`
7. `visualSignals`
8. `semanticSignals`
9. `evidenceReferences`

## extraction-summary.json

这个文件用于判断本次抽取跑在哪条链路上。

稳定主字段：

- `mode`
  - `primary`
  - `legacy-fallback`
  - `blocked`
- `fallbackUsed`
- `collectorKind`
  - `single-page-node`
  - `multi-page-node`
  - `legacy-bash`
- `sourceUrl`
- `scopeType`
- `scopeValue`

可选字段：

- `fallbackReason`

推荐使用方式：

- 先看 `mode`
- 再看 `collectorKind`
- 最后判断 `fallbackUsed`

不要只看“文件有没有产出”，要先确认是不是命中了主链路。
