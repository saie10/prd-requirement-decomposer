#!/usr/bin/env node

const fs = require("fs");
const {
  dismissAxhubNotice,
  launchChromiumBrowser,
  requirePlaywrightCore,
  resolveHtmlContentFrame,
} = require("./playwright_helpers");

async function main() {
  const [cliPath, shareUrl, outPath, targetPageLabel] = process.argv.slice(2);
  if (!cliPath || !shareUrl || !outPath || !targetPageLabel) {
    console.error("Usage: capture_axhub_single_page_screenshot.js <playwright-cli-path> <share-url> <output-path> <target-page-label>");
    process.exit(1);
  }

  const { chromium } = requirePlaywrightCore(cliPath);
  const browser = await launchChromiumBrowser(chromium);

  let frameUrl = null;
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  try {
    await page.goto(shareUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1200);
    await dismissAxhubNotice(page);

    const targetFrame = await resolveHtmlContentFrame(page, 6000);

    if (!targetFrame) {
      throw new Error("Unable to locate Axhub content frame.");
    }

    const baseFrameUrl = targetFrame.url();
    if (!baseFrameUrl) {
      throw new Error("Axhub content frame URL is empty.");
    }

    const baseFrame = new URL(baseFrameUrl);
    const targetPath = `${baseFrame.pathname.replace(/\/[^/]*$/, "")}/${encodeURIComponent(targetPageLabel)}.html`;
    frameUrl = `${baseFrame.origin}${targetPath}`;

    const shotPage = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    try {
      await shotPage.goto(frameUrl, { waitUntil: "networkidle", timeout: 60000 });
      await shotPage.waitForTimeout(1000);

      const pageSize = await shotPage.evaluate(() => ({
        scrollWidth: Math.max(
          document.documentElement.scrollWidth || 0,
          document.body ? document.body.scrollWidth || 0 : 0
        ),
        scrollHeight: Math.max(
          document.documentElement.scrollHeight || 0,
          document.body ? document.body.scrollHeight || 0 : 0
        ),
        clientWidth: document.documentElement.clientWidth || 0,
        clientHeight: document.documentElement.clientHeight || 0,
      }));

      await shotPage.screenshot({
        path: outPath,
        fullPage: true,
      });

      const size = fs.statSync(outPath).size;
      const meta = {
        mode: "axhub-page-fullpage",
        targetPageLabel,
        baseFrameUrl,
        frameUrl,
        out: outPath,
        size,
        pageSize,
      };

      process.stdout.write(`${JSON.stringify(meta)}\n`);
    } finally {
      await shotPage.close().catch(() => {});
    }
  } finally {
    await page.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
