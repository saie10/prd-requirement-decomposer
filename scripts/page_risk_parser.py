#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


NUMERIC_RE = re.compile(r"^[0-9]+(?:/[0-9]+)?$")
SHORT_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,3}$")

STRONG_VISUAL_KEYWORDS = [
    "如下图",
    "见下图",
    "红框",
    "箭头",
    "圈选",
    "效果示例",
    "示意",
    "图效果",
    "位置移动",
]

WEAK_VISUAL_KEYWORDS = [
    "hover",
    "弹窗",
    "交互",
    "布局",
    "点击",
    "按钮",
    "下拉",
    "勾选",
    "选择",
    "预览",
    "筛选",
]

LAYOUT_TITLE_KEYWORDS = [
    "弹窗",
    "交互",
    "配置结构",
    "样式",
    "布局",
    "图",
    "表格",
    "结构",
    "原型",
    "示意",
]

EXAMPLE_DISPLAY_PREFIXES = (
    "查询粒度",
    "查询日期",
    "查询指标",
    "查询维度",
    "业务日期",
)


def _is_noise_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if NUMERIC_RE.match(stripped):
        return True
    if SHORT_TOKEN_RE.match(stripped):
        return True
    if len(stripped) <= 2 and not any("\u4e00" <= ch <= "\u9fff" for ch in stripped):
        return True
    return False


def _looks_like_example_display_line(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 6:
        return False
    if stripped.startswith(EXAMPLE_DISPLAY_PREFIXES):
        return True
    if "示例" in stripped and any(mark in stripped for mark in ("：", ":", "如下")):
        return True
    if "至" in stripped and re.search(r"\d{4}-\d{2}", stripped):
        return True
    return False


def assess_page_risk(page_label: str, payload: dict[str, object]) -> dict[str, object]:
    lines = [str(item).strip() for item in payload.get("lines", []) if str(item).strip()]
    raw_text = str(payload.get("rawText", ""))
    total_lines = len(lines)
    total_chars = sum(len(line) for line in lines)
    avg_line_length = round(total_chars / total_lines, 2) if total_lines else 0
    noise_lines = sum(1 for line in lines if _is_noise_line(line))
    noise_ratio = round(noise_lines / total_lines, 3) if total_lines else 1.0

    strong_visual_hits = [kw for kw in STRONG_VISUAL_KEYWORDS if kw in raw_text or kw in page_label]
    weak_visual_hits = [kw for kw in WEAK_VISUAL_KEYWORDS if kw in raw_text or kw in page_label]
    layout_title_hits = [kw for kw in LAYOUT_TITLE_KEYWORDS if kw in page_label]
    starred_lines = sum(1 for line in lines if line.startswith("*"))
    ui_action_hits = sum(1 for kw in ["点击", "选择", "筛选", "预览", "hover", "弹窗"] if kw in raw_text)
    example_display_lines = [line for line in lines if _looks_like_example_display_line(line)]

    score = 0
    signals: list[str] = []

    if total_lines < 6:
        score += 2
        signals.append("文本行数偏少")
    elif total_lines < 16:
        score += 1
        signals.append("文本行数较少")

    if noise_ratio >= 0.35:
        score += 2
        signals.append("噪音行占比高")
    elif noise_ratio >= 0.2:
        score += 1
        signals.append("噪音行占比较高")

    if avg_line_length and avg_line_length < 6:
        score += 1
        signals.append("平均文本长度偏短")

    if starred_lines >= 6 and (noise_ratio >= 0.2 or avg_line_length < 9):
        score += 1
        signals.append("配置项/表单项较多")

    if starred_lines >= 3 and total_lines <= 40 and avg_line_length < 8:
        score += 1
        signals.append("短文本配置项较多")

    if len(strong_visual_hits) >= 2:
        score += 2
        signals.append("命中多个视觉提示词")
    elif len(strong_visual_hits) == 1:
        score += 1
        signals.append("命中视觉提示词")

    if (
        len(weak_visual_hits) >= 3
        and total_lines <= 120
        and (noise_ratio >= 0.15 or avg_line_length < 12)
    ):
        score += 1
        signals.append("弱视觉提示较多")

    if len(weak_visual_hits) >= 2 and starred_lines >= 3 and avg_line_length < 8 and total_lines <= 120:
        score += 1
        signals.append("短页配置项依赖界面语境")

    if ui_action_hits >= 4 and noise_ratio >= 0.15:
        score += 1
        signals.append("交互动作描述较多")

    if len(example_display_lines) >= 4:
        score += 2
        signals.append("示例配置/展示口径较多")
    elif len(example_display_lines) >= 2:
        score += 1
        signals.append("存在多条示例配置/展示口径")

    if layout_title_hits and (len(strong_visual_hits) >= 1 or noise_ratio >= 0.15):
        score += 1
        signals.append("页面标题偏强交互/强布局")

    only_example_driven = (
        len(example_display_lines) >= 2
        and not strong_visual_hits
        and len(weak_visual_hits) < 2
        and not layout_title_hits
        and ui_action_hits == 0
    )

    if score >= 4 and not only_example_driven:
        risk_level = "high"
        screenshot_recommendation = "recommended"
    elif score >= 2:
        risk_level = "medium"
        screenshot_recommendation = "optional"
    else:
        risk_level = "low"
        screenshot_recommendation = "none"

    return {
        "riskLevel": risk_level,
        "needsScreenshot": risk_level == "high",
        "screenshotRecommendation": screenshot_recommendation,
        "score": score,
        "signals": signals,
        "metrics": {
            "totalLines": total_lines,
            "noiseLines": noise_lines,
            "noiseRatio": noise_ratio,
            "avgLineLength": avg_line_length,
            "starredLines": starred_lines,
            "uiActionHitCount": ui_action_hits,
            "exampleDisplayLineCount": len(example_display_lines),
            "strongVisualKeywordHits": strong_visual_hits,
            "weakVisualKeywordHits": weak_visual_hits,
            "layoutTitleHits": layout_title_hits,
        },
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: page_risk_parser.py <raw-json-file> <page-label>", file=sys.stderr)
        return 1

    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    page_label = sys.argv[2]
    print(json.dumps(assess_page_risk(page_label, payload), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
