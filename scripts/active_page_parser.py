#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ACTIVE_TITLE_CONTAINER_RE = re.compile(
    r"^(?P<indent>\s*)-\s+generic\s+\[ref=[^\]]+\]\s+\[cursor=pointer\]:\s*$"
)
GENERIC_TEXT_RE = re.compile(r"^\s*-\s+generic\s+\[ref=[^\]]+\]:\s*(?P<text>.+)$")
POSITION_RE = re.compile(r"^\(\d+\s+of\s+\d+\)$")


def extract_active_page_title(snapshot_text: str) -> str | None:
    lines = snapshot_text.splitlines()
    for idx, raw in enumerate(lines):
        if '"Project Pages"' not in raw:
            continue

        project_indent = len(raw) - len(raw.lstrip(" "))
        for probe in range(idx + 1, len(lines)):
            candidate = lines[probe]
            if not candidate.strip():
                continue

            indent = len(candidate) - len(candidate.lstrip(" "))
            if indent <= project_indent:
                break

            if not ACTIVE_TITLE_CONTAINER_RE.match(candidate):
                continue

            container_indent = indent
            title: str | None = None
            position_seen = False

            for nested in lines[probe + 1 :]:
                if not nested.strip():
                    continue
                nested_indent = len(nested) - len(nested.lstrip(" "))
                if nested_indent <= container_indent:
                    break

                text_match = GENERIC_TEXT_RE.match(nested)
                if not text_match:
                    continue

                text = text_match.group("text").strip()
                if not title:
                    title = text
                    continue

                if POSITION_RE.match(text):
                    position_seen = True
                    break

            if title and position_seen:
                return title

    return None


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: active_page_parser.py <snapshot-file>", file=sys.stderr)
        return 1

    snapshot_path = Path(sys.argv[1])
    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    title = extract_active_page_title(snapshot_text)
    if title:
      print(title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
