#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const {
  buildBlocked,
  dismissAxhubNotice,
  emitJson,
  extractSemanticSnapshot,
  launchChromiumBrowser,
  requirePlaywrightCore,
  registerSignalCleanup,
  resolveHtmlContentFrame,
} = require("./playwright_helpers");

function buildFrameUrl(baseFrameUrl, pageLabel) {
  const baseFrame = new URL(baseFrameUrl);
  const targetPath = `${baseFrame.pathname.replace(/\/[^/]*$/, "")}/${encodeURIComponent(pageLabel)}.html`;
  return `${baseFrame.origin}${targetPath}`;
}

async function captureDebugScreenshot(page, outDir, name) {
  try {
    fs.mkdirSync(outDir, { recursive: true });
    const target = path.join(outDir, name);
    await page.screenshot({ path: target, fullPage: true });
    return target;
  } catch {
    return null;
  }
}

async function waitForReadableBody(page, timeoutMs = 10000) {
  await page.waitForFunction(() => {
    const body = document.body;
    if (!body) return false;
    const text = (body.innerText || "").trim();
    return text.length > 0;
  }, { timeout: timeoutMs });
}

async function readVisibleTreeItems(context) {
  return context.evaluate(() => {
    const items = [];
    const containers = Array.from(document.querySelectorAll(".sitemapPageLinkContainer"));

    for (const container of containers) {
      const rect = container.getBoundingClientRect();
      const style = window.getComputedStyle(container);
      if (style.display === "none" || style.visibility === "hidden" || rect.width === 0 || rect.height === 0) {
        continue;
      }

      const nameEl = container.querySelector(".sitemapPageName");
      const linkEl = container.querySelector(".sitemapPageLink");
      const text = (nameEl?.textContent || container.textContent || "").trim().replace(/\s+/g, " ");
      if (!text) {
        continue;
      }

      const nameRect = (nameEl || container).getBoundingClientRect();
      items.push({
        text,
        x: Math.round(nameRect.x),
        y: Math.round(nameRect.y),
        hasLink: Boolean(linkEl),
      });
    }

    items.sort((a, b) => {
      if (a.y !== b.y) return a.y - b.y;
      if (a.x !== b.x) return a.x - b.x;
      return a.text.localeCompare(b.text);
    });

    return items;
  });
}

async function expandTree(context) {
  let previousCount = 0;

  for (let pass = 0; pass < 24; pass += 1) {
    const beforeCount = (await readVisibleTreeItems(context)).length;
    const clickedCount = await context.evaluate(() => {
      const isVisible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      };

      const candidates = Array.from(document.querySelectorAll(".sitemapPlusMinusLink:not(.is-expand)"))
        .filter((el) => isVisible(el))
        .sort((a, b) => a.getBoundingClientRect().y - b.getBoundingClientRect().y);

      if (!candidates.length) {
        return 0;
      }

      for (const target of candidates.slice(0, 6)) {
        target.click();
      }
      return Math.min(candidates.length, 6);
    });

    if (!clickedCount) {
      break;
    }

    await context.waitForTimeout(180);
    const afterCount = (await readVisibleTreeItems(context)).length;
    if (afterCount <= previousCount && afterCount === beforeCount) {
      // Nothing new became visible after expanding the next collapsed node.
      continue;
    }
    previousCount = afterCount;
  }
}

async function countExpandableNodes(context) {
  return context.evaluate(() => {
    const isVisible = (el) => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    };

    return Array.from(document.querySelectorAll(".sitemapPlusMinusLink:not(.is-expand)")).filter((el) => isVisible(el)).length;
  });
}

async function waitForTreeReady(context, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const visibleCount = await context.evaluate(() => {
      const isVisible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      };

      return Array.from(document.querySelectorAll(".sitemapPageLinkContainer, .sitemapPageName")).filter((el) => isVisible(el)).length;
    }).catch(() => 0);

    if (visibleCount > 0) {
      return true;
    }

    await context.waitForTimeout(500);
  }

  return false;
}

function buildPagesFromTreeItems(items) {
  const pages = [];
  const stack = [];

  for (const item of items) {
    while (stack.length && item.x <= stack[stack.length - 1].x) {
      stack.pop();
    }

    const ancestors = stack.map((entry) => entry.text);
    if (item.hasLink) {
      pages.push({
        label: item.text,
        ancestors,
        path: [...ancestors, item.text],
      });
    }

    stack.push(item);
  }

  return pages;
}

function applyScope(pages, scopeType, scopeValue) {
  if (!scopeValue || scopeType === "all") {
    return pages;
  }
  if (scopeType === "page") {
    return pages.filter((page) => page.label === scopeValue);
  }
  if (scopeType === "directory") {
    return pages.filter((page) => page.ancestors.includes(scopeValue));
  }
  return pages;
}

async function collectScopedPages(context, scopeType, scopeValue) {
  let bestPages = [];
  let bestMatchedPages = [];

  for (let attempt = 0; attempt < 4; attempt += 1) {
    await expandTree(context);
    const treeItems = await readVisibleTreeItems(context);
    const pages = buildPagesFromTreeItems(treeItems);
    const matchedPages = applyScope(pages, scopeType, scopeValue);

    if (pages.length > bestPages.length) {
      bestPages = pages;
    }
    if (matchedPages.length > bestMatchedPages.length) {
      bestMatchedPages = matchedPages;
    }

    if (scopeType === "all" || matchedPages.length > 0) {
      return { pages, matchedPages };
    }

    const expandableCount = await countExpandableNodes(context);
    if (!expandableCount) {
      break;
    }

    // Modao 树有时在首轮展开后会延迟渲染更深层节点，再做一轮补偿采集比直接回退旧链路更划算。
    await context.waitForTimeout(300 + attempt * 120);
  }

  return { pages: bestPages, matchedPages: bestMatchedPages };
}

async function extractBodyText(browser, frameUrl, outDir, index, label) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  try {
    await page.goto(frameUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitForReadableBody(page, 10000);
    await page.waitForTimeout(120);

    const payload = await page.evaluate(() => {
      const body = document.body;
      if (!body) {
        return { lines: [], rawText: "", headings: [] };
      }

      const lines = (body.innerText || "")
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);

      const headings = Array.from(document.querySelectorAll("h1, h2, h3, h4, [role='heading']"))
        .map((el) => (el.textContent || "").trim())
        .filter(Boolean);

      return {
        lines,
        rawText: lines.join("\n"),
        headings,
      };
    });
    const semanticSnapshot = await extractSemanticSnapshot(page);

    if (!payload.lines.length) {
      const debugScreenshot = await captureDebugScreenshot(page, outDir, `page-${String(index).padStart(3, "0")}-empty.png`);
      return {
        status: "blocked",
        reason: "empty_page_text",
        label,
        frameUrl,
        debugScreenshot,
      };
    }

    return {
      status: "ok",
      frameUrl,
      bodyRef: "document.body",
      lines: payload.lines,
      rawText: payload.rawText,
      headings: payload.headings,
      semanticSnapshot,
    };
  } finally {
    await page.close().catch(() => {});
  }
}

async function main() {
  const [cliPath, shareUrl, scopeType, scopeValue, outDir] = process.argv.slice(2);
  if (!cliPath || !shareUrl || !scopeType || !outDir) {
    console.error("Usage: collect_prd_pages.js <playwright-cli-path> <share-url> <scope-type> <scope-value> <out-dir>");
    process.exit(1);
  }

  const { chromium } = requirePlaywrightCore(cliPath);
  const browser = await launchChromiumBrowser(chromium);
  const unregisterSignalCleanup = registerSignalCleanup(async () => {
    await browser.close().catch(() => {});
  });

  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  try {
    await page.goto(shareUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(700);

    const isAxhub = shareUrl.includes("axhub.im");
    if (isAxhub) {
      await dismissAxhubNotice(page);
    }

    let treeContext = page;
    let baseFrameUrl = page.url();
    let platform = isAxhub ? "axhub" : "modao";

    if (!isAxhub) {
      const contentFrame = await resolveHtmlContentFrame(page, 15000, "start.html");

      if (!contentFrame) {
        const debugScreenshot = await captureDebugScreenshot(page, outDir, "collector-blocked.png");
        emitJson(buildBlocked("content_frame_unavailable", {
          platform,
          stage: "frame_resolution",
          debugScreenshot,
        }));
        return;
      }

      treeContext = contentFrame;
      baseFrameUrl = contentFrame.url();
    } else {
      const contentFrame = await resolveHtmlContentFrame(page, 4000);
      if (contentFrame) {
        baseFrameUrl = contentFrame.url();
      }
    }

    const treeReady = await waitForTreeReady(treeContext, 30000);
    if (!treeReady) {
      const debugScreenshot = await captureDebugScreenshot(page, outDir, "collector-tree-unavailable.png");
      emitJson(buildBlocked("tree_unavailable", {
        platform,
        stage: "tree_ready",
        scopeType,
        scopeValue,
        debugScreenshot,
      }, ["tree_unavailable"]));
      return;
    }
    const { pages, matchedPages } = await collectScopedPages(treeContext, scopeType, scopeValue);

    if (!matchedPages.length) {
      if (!pages.length) {
        const debugScreenshot = await captureDebugScreenshot(page, outDir, "collector-tree-empty.png");
        emitJson(buildBlocked("tree_unavailable", {
          platform,
          stage: "tree_collect",
          scopeType,
          scopeValue,
          treeCount: 0,
          debugScreenshot,
        }, ["tree_unavailable"]));
        return;
      }
      const debugScreenshot = await captureDebugScreenshot(page, outDir, "collector-no-match.png");
      emitJson(buildBlocked("no_scope_match", {
        platform,
        stage: "scope_match",
        scopeType,
        scopeValue,
        treeCount: pages.length,
        debugScreenshot,
      }));
      return;
    }

    const collectedPages = [];
    for (const [index, pageMeta] of matchedPages.entries()) {
      const frameUrl = buildFrameUrl(baseFrameUrl, pageMeta.label);
      const extraction = await extractBodyText(browser, frameUrl, outDir, index, pageMeta.label);
      if (extraction.status !== "ok") {
        emitJson(buildBlocked(extraction.reason, {
          platform,
          stage: "body_extract",
          scopeType,
          scopeValue,
          pageLabel: pageMeta.label,
          frameUrl,
          debugScreenshot: extraction.debugScreenshot || null,
        }));
        return;
      }

      collectedPages.push({
        label: pageMeta.label,
        ancestors: pageMeta.ancestors,
        path: pageMeta.path,
        frameUrl,
        headings: extraction.headings,
        bodyRef: extraction.bodyRef,
        lines: extraction.lines,
        rawText: extraction.rawText,
      });
    }

    emitJson({
      status: "ok",
      platform,
      scopeType,
      scopeValue,
      baseFrameUrl,
      pages: collectedPages,
    });
  } finally {
    unregisterSignalCleanup();
    await page.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  emitJson(buildBlocked("collector_exception", {
    stage: "collector_runtime",
    message: error && error.message ? error.message : String(error),
  }));
  process.exit(0);
});
