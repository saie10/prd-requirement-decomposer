#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


CLICKABLE_RE = re.compile(
    r"^(?P<indent>\s*)-\s+generic\s+\[ref=(?P<ref>[^\]]+)\]\s+\[cursor=pointer\]:(?P<label>.*)$"
)
LIST_RE = re.compile(r"^(?P<indent>\s*)-\s+list(?:\s+\[ref=[^\]]+\])?:?\s*$")


@dataclass
class PageNode:
    ref: str
    label: str
    indent: int


def _line_indent(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" "))


def _has_child_list(lines: list[str], index: int, indent: int) -> bool:
    for raw in lines[index + 1 :]:
        if not raw.strip():
            continue
        next_indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.lstrip()
        if stripped.startswith("- list [") and next_indent >= indent:
            return True
        if next_indent <= indent:
            return False
    return False


def _count_clickables_in_subtree(lines: list[str], start_index: int) -> int:
    root_indent = _line_indent(lines[start_index])
    count = 0
    for raw in lines[start_index + 1 :]:
        if not raw.strip():
            continue
        indent = _line_indent(raw)
        if indent <= root_indent:
            break
        if CLICKABLE_RE.match(raw):
            count += 1
    return count


def _select_navigation_lines(lines: list[str]) -> list[str]:
    best_start: int | None = None
    best_end = len(lines)
    best_count = -1

    for idx, raw in enumerate(lines):
        if not LIST_RE.match(raw):
            continue
        count = _count_clickables_in_subtree(lines, idx)
        if count <= best_count:
            continue

        root_indent = _line_indent(raw)
        end = len(lines)
        for probe in range(idx + 1, len(lines)):
            candidate = lines[probe]
            if not candidate.strip():
                continue
            if _line_indent(candidate) <= root_indent:
                end = probe
                break

        best_start = idx
        best_end = end
        best_count = count

    if best_start is None:
        return lines

    return lines[best_start:best_end]


def extract_leaf_pages(snapshot_text: str) -> list[dict[str, object]]:
    lines = _select_navigation_lines(snapshot_text.splitlines())
    leaves: list[dict[str, object]] = []
    stack: list[PageNode] = []

    for idx, raw in enumerate(lines):
        match = CLICKABLE_RE.match(raw)
        if not match:
            continue

        label = match.group("label").strip()
        if not label:
            continue

        indent = len(match.group("indent"))
        while stack and stack[-1].indent >= indent:
            stack.pop()

        ancestors = [node.label for node in stack]
        if _has_child_list(lines, idx, indent):
            stack.append(PageNode(ref=match.group("ref"), label=label, indent=indent))
            continue

        leaves.append(
            {
                "ref": match.group("ref"),
                "label": label,
                "ancestors": ancestors,
                "path": ancestors + [label],
            }
        )

    return leaves


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: snapshot_tree_parser.py <snapshot-file>", file=sys.stderr)
        return 1

    snapshot_path = Path(sys.argv[1])
    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    print(json.dumps(extract_leaf_pages(snapshot_text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
