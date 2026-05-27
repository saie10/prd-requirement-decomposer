#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


IFRAME_RE = re.compile(r"^(?P<indent>\s*)-\s+iframe(?:\s+\[active\])?\s+\[ref=(?P<ref>[^\]]+)\]")
GENERIC_RE = re.compile(r"^(?P<indent>\s*)-\s+generic(?:\s+\[active\])?\s+\[ref=(?P<ref>[^\]]+)\]")
TEXT_RE = re.compile(
    r"^\s*-\s+(?:paragraph|textbox|generic|text|option|button|radio|combobox)[^:]*:\s*(?P<text>.+)$"
)


def _line_indent(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" "))


def _find_content_root(lines: list[str]) -> tuple[int, str] | None:
    active_candidates: list[tuple[int, str, int]] = []
    fallback_candidates: list[tuple[int, str, int]] = []

    for idx, raw in enumerate(lines):
        match = GENERIC_RE.match(raw)
        if not match:
            continue

        indent = _line_indent(raw)
        text_count = 0
        for probe in lines[idx + 1 :]:
            if not probe.strip():
                continue
            next_indent = _line_indent(probe)
            if next_indent <= indent:
                break
            if TEXT_RE.match(probe):
                text_count += 1

        if text_count == 0:
            continue

        candidate = (idx, match.group("ref"), indent)
        if "[active]" in raw:
            active_candidates.append(candidate)
        else:
            fallback_candidates.append(candidate)

    if active_candidates:
        active_candidates.sort(key=lambda item: (item[2], item[0]))
        idx, ref, _ = active_candidates[-1]
        return idx, ref

    if fallback_candidates:
        fallback_candidates.sort(key=lambda item: (item[2], item[0]))
        idx, ref, _ = fallback_candidates[-1]
        return idx, ref

    iframe_indexes: list[tuple[int, int]] = []
    for idx, raw in enumerate(lines):
        match = IFRAME_RE.match(raw)
        if match:
            iframe_indexes.append((idx, _line_indent(raw)))

    if len(iframe_indexes) < 2:
        return None

    second_iframe_index, second_iframe_indent = iframe_indexes[1]
    fallback: tuple[int, str] | None = None

    for idx in range(second_iframe_index + 1, len(lines)):
        raw = lines[idx]
        if not raw.strip():
            continue
        indent = _line_indent(raw)
        if indent <= second_iframe_indent:
            break
        match = GENERIC_RE.match(raw)
        if not match:
            continue
        ref = match.group("ref")
        if "[active]" in raw:
            return idx, ref
        if fallback is None:
            fallback = (idx, ref)

    return fallback


def _clean_text(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    return text.strip()


def extract_page_text(snapshot_text: str) -> dict[str, object]:
    lines = snapshot_text.splitlines()
    root = _find_content_root(lines)
    if root is None:
        return {"bodyRef": None, "lines": [], "rawText": ""}

    start_index, body_ref = root
    body_indent = _line_indent(lines[start_index])
    collected: list[str] = []

    for raw in lines[start_index + 1 :]:
        if not raw.strip():
            continue
        indent = _line_indent(raw)
        if indent <= body_indent:
            break
        match = TEXT_RE.match(raw)
        if not match:
            continue
        text = _clean_text(match.group("text"))
        if not text:
            continue
        if collected and collected[-1] == text:
            continue
        collected.append(text)

    return {
        "bodyRef": body_ref,
        "lines": collected,
        "rawText": "\n".join(collected),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: page_text_parser.py <snapshot-file>", file=sys.stderr)
        return 1

    snapshot_path = Path(sys.argv[1])
    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    print(json.dumps(extract_page_text(snapshot_text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
