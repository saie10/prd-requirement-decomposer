#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


EXPLICIT_QUESTION_KEYWORDS = [
    "待确认",
    "需确认",
    "是否",
    "有没有",
    "是否支持",
    "是否需要",
    "是否允许",
    "是否展示",
    "是否显示",
    "是否可",
    "是否能",
]

QUESTION_PUNCTUATION = ("？", "?")

SCOPE_BOUNDARY_KEYWORDS = [
    "第一版",
    "后续",
    "未来",
    "暂不",
    "暂未",
    "目前前端不用显示",
    "当前不",
    "不在本期",
]

REVIEW_NOTE_KEYWORDS = [
    "注意",
    "补充",
]

CONDITIONAL_PREFIXES = ("若", "如果", "当", "视", "根据")
CONDITIONAL_OUTCOME_KEYWORDS = ("显示", "隐藏", "跳转", "带出", "不用", "不显示", "才", "则", "就", "取决于")


def _clean_lines(payload: dict[str, object]) -> list[str]:
    return [str(item).strip() for item in payload.get("lines", []) if str(item).strip()]


def _looks_like_conditional(line: str) -> bool:
    if len(line) < 12:
        return False
    if (
        not any(line.startswith(prefix) for prefix in CONDITIONAL_PREFIXES)
        and "多数情况下" not in line
        and "是否展示" not in line
        and "是否显示" not in line
    ):
        return False
    return any(keyword in line for keyword in CONDITIONAL_OUTCOME_KEYWORDS)


def _question_for(issue_type: str, line: str) -> str:
    if issue_type == "open_question":
        return "确认该问题或疑问在 PRD 中是否已有明确结论。"
    if issue_type == "scope_boundary":
        return "确认这条范围边界是否属于本次交付，以及后续版本是否需要单独跟踪。"
    if issue_type == "conditional_behavior":
        return "确认条件分支对应的展示、隐藏、跳转或默认值规则是否完整。"
    return "确认这条补充说明是否会影响需求边界或验收口径。"


def _looks_like_example_query(line: str) -> bool:
    stripped = line.strip()
    if not any(mark in stripped for mark in QUESTION_PUNCTUATION):
        return False
    if any(keyword in stripped for keyword in EXPLICIT_QUESTION_KEYWORDS):
        return False
    if len(stripped) < 8:
        return False
    return True


def _detect_issue_type(line: str) -> tuple[str, str, str] | None:
    if any(keyword in line for keyword in EXPLICIT_QUESTION_KEYWORDS):
        return ("open_question", "页面里存在明确待确认或疑问表述", "high")
    if _looks_like_example_query(line):
        return None
    if any(mark in line for mark in QUESTION_PUNCTUATION):
        return ("open_question", "页面里存在明确待确认或疑问表述", "high")
    if any(keyword in line for keyword in SCOPE_BOUNDARY_KEYWORDS):
        return ("scope_boundary", "页面里存在版本边界或后续范围说明", "medium")
    if _looks_like_conditional(line):
        return ("conditional_behavior", "页面里存在条件分支或动态显示规则", "medium")
    if (
        any(keyword in line for keyword in REVIEW_NOTE_KEYWORDS)
        and len(line) >= 10
        and ("：" in line or ":" in line or line.startswith("注意"))
    ):
        return ("review_note", "页面里存在补充说明或注意事项", "low")
    return None


def extract_issues(payload: dict[str, object]) -> dict[str, object]:
    lines = _clean_lines(payload)
    issues: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for line in lines:
        detected = _detect_issue_type(line)
        if not detected:
            continue
        issue_type, reason, severity = detected
        key = (issue_type, line)
        if key in seen:
            continue
        seen.add(key)
        issues.append(
            {
                "type": issue_type,
                "severity": severity,
                "reason": reason,
                "evidence": line,
                "question": _question_for(issue_type, line),
            }
        )

    return {
        "needsManualReview": bool(issues),
        "suspectedIssues": issues[:12],
        "issueCounts": {
            "openQuestion": sum(1 for item in issues if item["type"] == "open_question"),
            "scopeBoundary": sum(1 for item in issues if item["type"] == "scope_boundary"),
            "conditionalBehavior": sum(1 for item in issues if item["type"] == "conditional_behavior"),
            "reviewNote": sum(1 for item in issues if item["type"] == "review_note"),
        },
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: page_issue_extractor.py <page-json-file>", file=sys.stderr)
        return 1

    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(extract_issues(payload), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
