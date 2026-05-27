#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const {
  launchChromiumBrowser,
  requirePlaywrightCore,
  resolveHtmlContentFrame,
} = require("./playwright_helpers");

async function waitForImageSlice(page, imageBase64, offsetY, width, height) {
  await page.setViewportSize({ width, height });
  await page.setContent(`
    <!doctype html>
    <html>
      <body style="margin:0;background:#fff;">
        <canvas id="c" width="${width}" height="${height}"></canvas>
      </body>
    </html>
  `);

  await page.evaluate(
    ({ imageBase64, offsetY, width, height }) =>
      new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
          const canvas = document.getElementById("c");
          const ctx = canvas.getContext("2d");
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, width, height);
          ctx.drawImage(img, 0, offsetY, width, height, 0, 0, width, height);
          resolve();
        };
        img.onerror = () => reject(new Error("Failed to load stitched image into canvas."));
        img.src = `data:image/png;base64,${imageBase64}`;
      }),
    { imageBase64, offsetY, width, height }
  );
}

async function main() {
  const [cliPath, shareUrl, outDir, targetPageLabel] = process.argv.slice(2);
  if (!cliPath || !shareUrl || !outDir || !targetPageLabel) {
    console.error("Usage: capture_modao_single_page_screenshot.js <playwright-cli-path> <share-url> <output-dir> <target-page-label>");
    process.exit(1);
  }

  fs.mkdirSync(outDir, { recursive: true });
  const { chromium } = requirePlaywrightCore(cliPath);
  const browser = await launchChromiumBrowser(chromium);

  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  try {
    await page.goto(shareUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1200);

    const targetFrame = await resolveHtmlContentFrame(page, 15000, "start.html");

    if (!targetFrame) {
      throw new Error("Unable to locate Modao content frame.");
    }

    const baseFrameUrl = targetFrame.url();
    if (!baseFrameUrl) {
      throw new Error("Modao content frame URL is empty.");
    }

    const baseFrame = new URL(baseFrameUrl);
    const targetPath = `${baseFrame.pathname.replace(/\/[^/]*$/, "")}/${encodeURIComponent(targetPageLabel)}.html`;
    const frameUrl = `${baseFrame.origin}${targetPath}`;

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

      const fullPagePath = path.join(outDir, "page.png");
      await shotPage.screenshot({
        path: fullPagePath,
        fullPage: true,
      });

      const imageBase64 = fs.readFileSync(fullPagePath).toString("base64");
      const segmentHeight = 1200;
      const shots = [];
      const slicePage = await browser.newPage({
        viewport: {
          width: Math.min(pageSize.scrollWidth, 2200),
          height: Math.min(segmentHeight, pageSize.scrollHeight),
        },
      });

      try {
        for (let offsetY = 0, index = 0; offsetY < pageSize.scrollHeight; offsetY += segmentHeight, index += 1) {
          const currentHeight = Math.min(segmentHeight, pageSize.scrollHeight - offsetY);
          const shotName = `shot-${String(index).padStart(3, "0")}.png`;
          const shotPath = path.join(outDir, shotName);

          await waitForImageSlice(slicePage, imageBase64, offsetY, pageSize.scrollWidth, currentHeight);
          const canvas = await slicePage.$("#c");
          await canvas.screenshot({ path: shotPath });

          shots.push({
            index,
            path: shotPath,
            offsetY,
            width: pageSize.scrollWidth,
            height: currentHeight,
          });
        }
      } finally {
        await slicePage.close().catch(() => {});
      }

      const manifest = {
        mode: "modao-single-page-fullpage-and-segments",
        targetPageLabel,
        baseFrameUrl,
        frameUrl,
        outDir,
        fullPagePath,
        pageSize,
        segmentHeight,
        shotCount: shots.length,
        shots,
      };

      fs.writeFileSync(path.join(outDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
      process.stdout.write(`${JSON.stringify(manifest)}\n`);
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
