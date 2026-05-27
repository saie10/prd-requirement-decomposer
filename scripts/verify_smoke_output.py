#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from urllib.parse import unquote


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read_png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        header = fh.read(24)
    _assert(header.startswith(b"\x89PNG\r\n\x1a\n"), f"{path} is not a PNG file")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def main() -> int:
    if len(sys.argv) not in {5, 7}:
        print(
            "Usage: verify_smoke_output.py <output-dir> <scope-type:page|dir> <with-screenshot:true|false> <output-mode:concise|standard|rich> [<require-primary:true|false> <expected-collector>]",
            file=sys.stderr,
        )
        return 1

    output_dir = Path(sys.argv[1])
    scope_type = sys.argv[2]
    with_screenshot = sys.argv[3].lower() == "true"
    output_mode = sys.argv[4]
    require_primary = sys.argv[5].lower() == "true" if len(sys.argv) == 7 else False
    expected_collector = sys.argv[6] if len(sys.argv) == 7 else ""

    extraction_summary_path = output_dir / "extraction-summary.json"
    _assert(extraction_summary_path.exists(), "missing extraction-summary.json")
    extraction_summary = json.loads(extraction_summary_path.read_text(encoding="utf-8"))
    _assert(extraction_summary.get("mode") in {"primary", "legacy-fallback"}, "unexpected extraction mode")
    _assert(isinstance(extraction_summary.get("fallbackUsed"), bool), "extraction summary missing fallbackUsed")
    _assert(extraction_summary.get("collectorKind"), "extraction summary missing collectorKind")
    if require_primary:
        _assert(extraction_summary.get("mode") == "primary", "smoke expected primary path but got fallback")
        _assert(extraction_summary.get("fallbackUsed") is False, "smoke expected fallback=false")
    if expected_collector:
        _assert(
            extraction_summary.get("collectorKind") == expected_collector,
            f"smoke expected collector={expected_collector} but got {extraction_summary.get('collectorKind')}",
        )

    understanding_json = output_dir / "understanding-input.json"
    _assert(understanding_json.exists(), "missing understanding-input.json")
    understanding = json.loads(understanding_json.read_text(encoding="utf-8"))
    _assert(understanding.get("artifactType") == "prd-understanding-input", "unexpected artifact type")
    _assert(isinstance(understanding.get("pages"), list), "understanding-input.json missing pages list")
    _assert(understanding.get("pageCount") == len(understanding.get("pages", [])), "pageCount does not match pages length")
    understanding_pages = understanding["pages"]
    _assert(understanding_pages, "understanding-input.json should contain at least one page")
    if scope_type == "page":
        _assert(len(understanding_pages) == 1, "page scope should export exactly one understanding page")

    pages_json = output_dir / "pages.json"
    if pages_json.exists():
        pages = json.loads(pages_json.read_text(encoding="utf-8"))
        _assert(isinstance(pages, list), "pages.json is not a list")
        if scope_type == "page":
            _assert(len(pages) == 1, "page scope should export exactly one page")
        else:
            _assert(len(pages) >= 1, "directory scope should export at least one page")
    else:
        pages = None
        _assert(output_mode == "concise", "pages.json should only be absent in concise mode")

    page_dirs = sorted(path for path in output_dir.glob("page-*") if path.is_dir())
    if scope_type == "page":
        if with_screenshot:
            _assert(len(page_dirs) == 1, "page scope with screenshot should keep one page dir")
        else:
            if pages_json.exists():
                _assert(len(page_dirs) == 1, "page scope standard/rich should keep one page dir")
            else:
                _assert(len(page_dirs) == 0, "page scope concise without screenshot should not keep page dir")
    else:
        if output_mode == "concise" and not with_screenshot:
            _assert(len(page_dirs) == 0, "directory scope concise without screenshot should not keep page dirs")
        else:
            _assert(len(page_dirs) >= 1, "directory scope should keep page dirs")
            if pages is not None:
                _assert(len(page_dirs) == len(pages), "directory scope page dir count should match pages.json count")
            else:
                _assert(len(page_dirs) == len(understanding_pages), "directory scope concise screenshot output should keep one page dir per understanding page")

    _assert(not (output_dir / "page-guide.md").exists(), "default flow should not export page-guide.md")
    _assert(not (output_dir / "page-guide.json").exists(), "default flow should not export page-guide.json")

    if with_screenshot:
        _assert(page_dirs, "screenshot run should retain page dirs")
        _assert(all(page_dir.joinpath("page.png").exists() for page_dir in page_dirs), "screenshot run should retain page.png for every page dir")
        for page_dir in page_dirs:
            # 这里只做“弱但实用”的质量校验：挡掉空图、极小图、明显残图。
            width, height = _read_png_size(page_dir / "page.png")
            _assert(width >= 600 and height >= 600, f"{page_dir}/page.png is unexpectedly small: {width}x{height}")
    else:
        _assert(not any(page_dir.joinpath("page.png").exists() for page_dir in page_dirs), "non-screenshot run unexpectedly exported page.png")

    if pages:
        if with_screenshot:
            _assert(all(page.get("screenshotPath") for page in pages), "screenshot run should retain screenshotPath for every page in pages.json")
            for page in pages:
                screenshot = page.get("screenshot") or {}
                frame_url = screenshot.get("frameUrl")
                page_size = screenshot.get("pageSize") or {}
                # 这里不做 OCR/多模态比对，只做来源 URL 和页面尺寸的轻量一致性校验。
                _assert(frame_url, f"{page.get('label')}: screenshot metadata missing frameUrl")
                _assert(page_size.get("scrollWidth", 0) >= 600, f"{page.get('label')}: screenshot scrollWidth looks too small")
                _assert(page_size.get("scrollHeight", 0) >= 600, f"{page.get('label')}: screenshot scrollHeight looks too small")
                label = page.get("label")
                if label:
                    _assert(label in unquote(frame_url), f"{label}: screenshot frameUrl does not appear to match target page")
        else:
            _assert(all(not page.get("screenshotPath") for page in pages), "non-screenshot run should not retain screenshotPath in pages.json")

    for page in understanding_pages:
        _assert(page.get("label"), "understanding page missing label")
        if "goal" in page:
            _assert(isinstance(page.get("goal"), list), f"{page.get('label')}: goal should be a list")
        _assert("sections" in page, f"{page.get('label')}: understanding page missing sections")
        _assert("visualSignals" in page, f"{page.get('label')}: understanding page missing visualSignals")
        if with_screenshot:
            visual_signals = page.get("visualSignals") or {}
            _assert(visual_signals.get("screenshotRecommendation") is not None, f"{page.get('label')}: missing screenshot recommendation")
            _assert(
                visual_signals.get("screenshotPath") or visual_signals.get("reviewFocus") or visual_signals.get("observations") or visual_signals.get("note"),
                f"{page.get('label')}: screenshot run should retain visual-review related fields",
            )

    print(
        f"Smoke output verified. extraction_mode={extraction_summary['mode']} collector={extraction_summary['collectorKind']} fallback={str(extraction_summary['fallbackUsed']).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
