#!/usr/bin/env node

const path = require("path");

function emitJson(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

function requirePlaywrightCore(cliPath = "") {
  try {
    return require("playwright-core");
  } catch (directError) {
    if (cliPath) {
      try {
        const nodeModules = path.dirname(path.dirname(path.dirname(cliPath)));
        return require(path.join(nodeModules, "playwright-core"));
      } catch {
        // Fall through to the original error below.
      }
    }
    throw directError;
  }
}

async function launchChromiumBrowser(chromium, launchOptions = {}) {
  const baseOptions = { headless: true, ...launchOptions };
  try {
    return await chromium.launch({
      ...baseOptions,
      channel: "chrome",
    });
  } catch (chromeError) {
    try {
      return await chromium.launch(baseOptions);
    } catch {
      throw chromeError;
    }
  }
}

function registerSignalCleanup(cleanup, signalExitCodes = { SIGINT: 130, SIGTERM: 143 }) {
  let cleaning = false;
  const handlers = [];

  const runCleanup = async (exitCode) => {
    if (cleaning) {
      return;
    }
    cleaning = true;
    try {
      await cleanup();
    } finally {
      process.exit(exitCode);
    }
  };

  for (const [signal, exitCode] of Object.entries(signalExitCodes)) {
    const handler = () => {
      void runCleanup(exitCode);
    };
    handlers.push([signal, handler]);
    process.once(signal, handler);
  }

  return () => {
    for (const [signal, handler] of handlers) {
      process.removeListener(signal, handler);
    }
  };
}

function buildBlocked(reason, details = {}, extraRetryableReasons = []) {
  const retryableReasons = new Set([
    "content_frame_unavailable",
    "empty_page_text",
    "launch_failed",
    ...extraRetryableReasons,
  ]);
  return {
    status: "blocked",
    reason,
    retryable: retryableReasons.has(reason),
    ...details,
  };
}

async function dismissAxhubNotice(page) {
  const noticeButton = page.getByRole("button", { name: "知道了" });
  try {
    if (await noticeButton.isVisible({ timeout: 2000 })) {
      await noticeButton.click();
      await page.waitForTimeout(800);
    }
  } catch {
    // Reminder is optional; ignore if absent.
  }
}

async function resolveHtmlContentFrame(page, timeoutMs = 15000, preferredNeedle = "") {
  const deadline = Date.now() + timeoutMs;
  const validHtmlFrame = (frame) => /^https?:/.test(frame.url()) && /\.html(?:[?#]|$)/.test(frame.url());

  while (Date.now() < deadline) {
    const frames = page.frames().filter(validHtmlFrame);
    const matchesPreferred = (frame) => !preferredNeedle || frame.url().includes(preferredNeedle);
    const contentFrame =
      frames.find((frame) => frame.name() === "mainFrame" && matchesPreferred(frame)) ||
      frames.find((frame) => matchesPreferred(frame)) ||
      frames.find((frame) => frame.name() === "mainFrame") ||
      frames[0];
    if (contentFrame) {
      return contentFrame;
    }
    await page.waitForTimeout(500);
  }

  return null;
}

async function extractDomSemanticSnapshot(page) {
  return page.evaluate(() => {
    const textOf = (value) => String(value || "").trim();
    const headings = Array.from(document.querySelectorAll("h1, h2, h3, h4, [role='heading']"))
      .map((el) => ({
        role: "heading",
        name: textOf(el.textContent),
        level: Number(el.getAttribute("aria-level") || el.tagName.replace(/[^1-6]/g, "")) || null,
      }))
      .filter((item) => item.name);

    const controls = Array.from(
      document.querySelectorAll(
        "button, a[href], input, textarea, select, [role='button'], [role='link'], [role='textbox'], [role='searchbox'], [role='combobox'], [role='listbox'], [role='option'], [role='checkbox'], [role='radio'], [role='switch'], [role='tab'], [role='menuitem'], [role='slider'], [role='spinbutton']",
      ),
    )
      .map((el) => {
        const role =
          textOf(el.getAttribute("role")) ||
          (el.tagName === "BUTTON"
            ? "button"
            : el.tagName === "A"
              ? "link"
              : el.tagName === "SELECT"
                ? "combobox"
                : el.tagName === "TEXTAREA"
                  ? "textbox"
                  : el.tagName === "INPUT"
                    ? (el.getAttribute("type") || "textbox")
                    : "");
        const input = el instanceof HTMLInputElement ? el : null;
        const option = el instanceof HTMLOptionElement ? el : null;
        return {
          role,
          name:
            textOf(el.getAttribute("aria-label")) ||
            textOf(el.textContent) ||
            textOf(el.getAttribute("placeholder")) ||
            textOf(el.getAttribute("value")),
          value: input ? input.value || null : null,
          checked: input && ["checkbox", "radio"].includes(input.type) ? input.checked : null,
          selected: option ? option.selected : null,
          expanded: el.getAttribute("aria-expanded"),
          disabled: "disabled" in el ? Boolean(el.disabled) : null,
        };
      })
      .filter((item) => item.role && item.name);

    const tableLike = Array.from(
      document.querySelectorAll("table, th, td, [role='table'], [role='grid'], [role='row'], [role='cell'], [role='columnheader'], [role='rowheader']"),
    )
      .map((el) => ({
        role: textOf(el.getAttribute("role")) || el.tagName.toLowerCase(),
        name: textOf(el.textContent),
      }))
      .filter((item) => item.name || item.role !== "row");

    return {
      available: true,
      source: "dom",
      headings: headings.slice(0, 20),
      controls: controls.slice(0, 40),
      tableLike: tableLike.slice(0, 40),
    };
  });
}

function flattenA11yNodes(node, out = []) {
  if (!node || typeof node !== "object") {
    return out;
  }
  out.push(node);
  for (const child of node.children || []) {
    flattenA11yNodes(child, out);
  }
  return out;
}

async function extractSemanticSnapshot(page) {
  const emptySnapshot = { available: false, headings: [], controls: [], tableLike: [] };
  if (!page.accessibility || typeof page.accessibility.snapshot !== "function") {
    return extractDomSemanticSnapshot(page).catch(() => emptySnapshot);
  }

  const snapshot = await page.accessibility.snapshot({ interestingOnly: false }).catch(() => null);
  if (!snapshot) {
    return extractDomSemanticSnapshot(page).catch(() => emptySnapshot);
  }

  const nodes = flattenA11yNodes(snapshot, []);
  const headingRoles = new Set(["heading"]);
  const controlRoles = new Set([
    "button",
    "link",
    "textbox",
    "searchbox",
    "combobox",
    "listbox",
    "option",
    "checkbox",
    "radio",
    "switch",
    "tab",
    "menuitem",
    "slider",
    "spinbutton",
  ]);
  const tableRoles = new Set(["table", "grid", "row", "cell", "columnheader", "rowheader"]);

  const headings = [];
  const controls = [];
  const tableLike = [];

  for (const node of nodes) {
    const role = String(node.role || "").trim();
    const name = String(node.name || "").trim();
    if (!role) continue;

    if (headingRoles.has(role) && name) {
      headings.push({
        role,
        name,
        level: node.level ?? null,
      });
      continue;
    }

    if (controlRoles.has(role)) {
      controls.push({
        role,
        name,
        value: node.value ?? null,
        checked: node.checked ?? null,
        selected: node.selected ?? null,
        expanded: node.expanded ?? null,
        disabled: node.disabled ?? null,
      });
      continue;
    }

    if (tableRoles.has(role) && (name || role !== "row")) {
      tableLike.push({
        role,
        name,
      });
    }
  }

  return {
    available: true,
    source: "a11y",
    headings: headings.slice(0, 20),
    controls: controls.slice(0, 40),
    tableLike: tableLike.slice(0, 40),
  };
}

module.exports = {
  buildBlocked,
  dismissAxhubNotice,
  emitJson,
  extractSemanticSnapshot,
  launchChromiumBrowser,
  requirePlaywrightCore,
  registerSignalCleanup,
  resolveHtmlContentFrame,
};
