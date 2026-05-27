# Environment Requirements

这个工具的核心实现是：

- Bash
- Node.js
- Python
- Playwright browser automation

## 初始化

推荐先在仓库根目录执行：

```bash
npm install
```

如果环境里没有可用的 Chrome，或者希望使用 Playwright 自带 Chromium，再执行：

```bash
npx playwright install chromium
```

## 必需依赖

脚本当前会直接检查这些命令：

- `npx`
- `node`
- `jq`
- `grep`
- `sed`
- `cp`
- `cmp`
- `python3`

## 浏览器能力

当前主采集链路是 Node Playwright collector，因此运行环境还需要：

- 可用的 Chrome / Chromium 启动能力
- 本地可用的 `@playwright/cli` / `playwright-core` 链路

当前脚本会优先：

- 使用仓库内 `node_modules/@playwright/cli`
- 找不到时，再复用已有的 `npx` 缓存
- 最后才尝试 `npx --yes @playwright/cli --json`

浏览器启动时会优先尝试：

- 本机 Chrome

如果 Chrome 不可用，则回退到：

- 已安装的 Playwright Chromium

## 网络与访问

运行环境需要能访问：

- `modao.cc`
- `axhub.im`

如果分享链接本身需要：

- 登录
- 密码
- 验证码
- 公司内网

则工具不会绕过这些限制，只会把它识别成 `blocked` 或其他结构化失败。

## 临时目录

当前会优先使用：

- `${TMPDIR}`
- 或 `/tmp`

## 路径约定

如果是在仓库根目录里直接运行脚本，可以使用相对路径：

- `scripts/extract_prd_pages.sh`

如果是把平台适配层单独安装到全局目录，例如：

- `~/.kimi/skills/`
- `~/.claude/agents/`

则不应再依赖相对路径。建议先配置一个环境变量：

```bash
export PRD_TOOL_HOME=/absolute/path/to/prd-requirement-decomposer
```

之后统一通过：

- `$PRD_TOOL_HOME/scripts/extract_prd_pages.sh`

来调用核心脚本。

## 运行环境建议

更适合的环境：

- macOS
- Linux
- 能正常启动 Playwright 浏览器的开发机

不建议：

- 完全受限、无法启动浏览器的会话
- 无法访问 `Modao / Axhub` 的离线环境

## 常见卡点

最常见的问题通常是：

1. 没有 `jq`
2. `node / npx` 可用，但浏览器拉起失败
3. 网络能跑脚本，但访问不到 `Modao / Axhub`
4. 链接本身需要认证或额外权限
5. 环境限制了浏览器启动或临时目录写入
