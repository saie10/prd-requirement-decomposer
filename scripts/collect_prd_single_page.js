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

function splitLines(text) {
  return String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

async function extractInnerText(page) {
  return page.evaluate(() => {
    const body = document.body;
    if (!body) {
      return { lines: [], rawText: "" };
    }

    const text = body.innerText || "";
    const lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    return {
      lines,
      rawText: lines.join("\n"),
    };
  });
}


async function resolveFrameUrl(browserPage, targetPageLabel) {
  const isAxhub = browserPage.url().includes("axhub.im");
  const contentFrame = await resolveHtmlContentFrame(
    browserPage,
    isAxhub ? 6000 : 15000,
    isAxhub ? "" : "start.html"
  );

  if (!contentFrame) {
    return null;
  }

  const baseFrameUrl = contentFrame.url();
  if (!baseFrameUrl) {
    return null;
  }

  const baseFrame = new URL(baseFrameUrl);
  const targetPath = `${baseFrame.pathname.replace(/\/[^/]*$/, "")}/${encodeURIComponent(targetPageLabel)}.html`;
  return {
    baseFrameUrl,
    frameUrl: `${baseFrame.origin}${targetPath}`,
  };
}

async function captureFailureScreenshot(page, outDir, name) {
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
    return ((body.innerText || "").trim().length > 0);
  }, { timeout: timeoutMs });
}

async function main() {
  const [cliPath, shareUrl, targetPageLabel, outDir] = process.argv.slice(2);
  if (!cliPath || !shareUrl || !targetPageLabel || !outDir) {
    console.error("Usage: collect_prd_single_page.js <playwright-cli-path> <share-url> <target-page-label> <out-dir>");
    process.exit(1);
  }

  const { chromium } = requirePlaywrightCore(cliPath);

  const platform = shareUrl.includes("axhub.im") ? "axhub" : "modao";
  const browser = await launchChromiumBrowser(chromium);
  const unregisterSignalCleanup = registerSignalCleanup(async () => {
    await browser.close().catch(() => {});
  });

  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  try {
    await page.goto(shareUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(800);

    if (platform === "axhub") {
      await dismissAxhubNotice(page);
    }

    const frameMeta = await resolveFrameUrl(page, targetPageLabel);
    if (!frameMeta) {
      const debugScreenshot = await captureFailureScreenshot(page, outDir, "collector-blocked.png");
      emitJson(buildBlocked("content_frame_unavailable", {
        platform,
        stage: "frame_resolution",
        targetPageLabel,
        debugScreenshot,
      }));
      return;
    }

    const shotPage = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    try {
      await shotPage.goto(frameMeta.frameUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
      await waitForReadableBody(shotPage, 10000);
      await shotPage.waitForTimeout(180);

      const textPayload = await extractInnerText(shotPage);
      const semanticSnapshot = await extractSemanticSnapshot(shotPage);
      if (!textPayload.lines.length) {
        const debugScreenshot = await captureFailureScreenshot(shotPage, outDir, "collector-empty-page.png");
        emitJson(buildBlocked("empty_page_text", {
          platform,
          stage: "body_extract",
          targetPageLabel,
          baseFrameUrl: frameMeta.baseFrameUrl,
          frameUrl: frameMeta.frameUrl,
          debugScreenshot,
        }));
        return;
      }

      const title = await shotPage.title().catch(() => "");
      const headings = await shotPage
        .evaluate(() => {
          const values = [];
          for (const el of Array.from(document.querySelectorAll("h1, h2, h3, h4, [role='heading']"))) {
            const text = (el.textContent || "").trim();
            if (text) values.push(text);
          }
          return values;
        })
        .catch(() => []);

      emitJson({
        status: "ok",
        platform,
        targetPageLabel,
        pageTitle: title,
        baseFrameUrl: frameMeta.baseFrameUrl,
        frameUrl: frameMeta.frameUrl,
        headings: splitLines(headings.join("\n")),
        semanticSnapshot,
        bodyRef: "document.body",
        lines: textPayload.lines,
        rawText: textPayload.rawText,
      });
    } finally {
      await shotPage.close().catch(() => {});
    }
  } finally {
    unregisterSignalCleanup();
    await page.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch(async (error) => {
  emitJson(buildBlocked("collector_exception", {
    stage: "collector_runtime",
    message: error && error.message ? error.message : String(error),
  }));
  process.exit(0);
});
