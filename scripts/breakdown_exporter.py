#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path

import page_risk_parser


FEATURE_LINE_RE = re.compile(r"^(?:\d+[.、]|[A-Z]\d+)")
NUMERIC_LINE_RE = re.compile(r"[0-9]+(?:/[0-9]+)?")
NUMERIC_UNIT_RE = re.compile(r"\d+(?:\.\d+)?(?:万|亿|千|百|%)")
SHORT_ALNUM_RE = re.compile(r"[A-Za-z0-9_-]{1,3}")
CASE_LINE_RE = re.compile(r"case\d+", re.IGNORECASE)
ANCHOR_BLOCK_RE = re.compile(r"A\d{2,}")
SNAKE_IDENT_RE = re.compile(r"[A-Za-z]+_[A-Za-z0-9_]+")
CHECKMARK_LINE_RE = re.compile(r"[✅❌]+")
PLUS_MINUS_LINE_RE = re.compile(r"[+＋-]+")
FIELD_LABEL_COLON_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9_]+\s*[:：]")
PRIORITY_LINE_RE = re.compile(r"[一二三四五六七八九十0-9]+优先级")
DATE_YYYY_MM_RE = re.compile(r"(?<!\d)\d{4}-\d{2}(?!\d)")
DATE_YYYY_MM_DD_RE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
DATE_GENERIC_RE = re.compile(r"(?<!\d)\d{4}[-/]\d{1,2}[-/]\d{1,2}(?!\d)")
QUARTER_RE = re.compile(r"\d{4}[qQ]\d")
REPEATED_SUFFIX_RE = re.compile(r"(.{1,3})\1$")
ORDER_MARKER_RE = re.compile(r"\d{1,2}")
FIELD_OR_INDEX_RE = re.compile(r"(?:字段|指标)\d+")
SUMMARY_MIN_LENGTH = 18

FEATURE_PREFIXES = (
    "新增",
    "支持",
    "增加",
    "配置",
    "选择",
    "导入",
    "导出",
    "保存",
    "查看",
    "查询",
)

ACTION_KEYWORDS = (
    "新增",
    "支持",
    "增加",
    "引入",
    "适配",
    "改造",
    "增强",
    "实现",
)

ACTION_PREFIXES = (
    "新增",
    "支持",
    "增加",
    "引入",
    "适配",
    "改造",
    "增强",
    "实现",
    "配置",
    "选择",
    "导入",
    "导出",
    "保存",
    "查看",
    "查询",
    "展示",
    "切换",
    "复用",
)

STRONG_ACTION_PREFIXES = (
    "新增",
    "支持",
    "增加",
    "引入",
    "适配",
    "改造",
    "增强",
    "实现",
)

SUPPORTING_ACTION_PREFIXES = (
    "配置",
    "选择",
    "导入",
    "导出",
    "保存",
    "查看",
    "查询",
    "切换",
    "带入",
)

IGNORED_REQUIREMENT_LABELS = {
    "需求背景",
    "需求详情",
    "需求说明",
}

UI_NOISE_EXACT = {
    "开始",
    "结束",
    "更新",
    "标题",
    "文本",
    "表格",
    "设置",
    "取消",
    "确认",
    "确 定",
    "取 消",
    "删除",
    "筛选",
    "新增",
    "字段",
    "功能",
    "类型",
    "数据配置",
    "样式配置",
    "指标查询",
    "明细查询",
    "指标选择",
    "维度选择",
    "查看数据",
    "查看SQL",
    "查询粒度",
    "查询方式",
}

UI_NOISE_PREFIXES = (
    "请输入",
    "点击",
    "日期基准：",
)

SUPPORTING_PREFIXES = (
    "保存",
    "下载",
    "查看",
    "导入",
    "导出",
    "排序",
    "筛选",
    "授权",
)

GENERIC_UI_OPERATION_PREFIXES = (
    "选择",
    "查看",
    "切换",
)

CONFIG_ITEM_HINTS = (
    "字段",
    "配置项",
    "默认值",
    "默认角色",
    "默认权限",
    "图标",
    "查询方式",
    "展示格式",
    "展示精度",
    "量级单位",
    "基准日期",
    "时间范围",
    "结束时间",
    "排序规则",
    "筛选条件",
    "类型",
)

RULE_KEYWORDS = (
    "默认",
    "默认值",
    "要求",
    "必须",
    "至少",
    "上限",
    "不能",
    "不可",
    "仅",
    "作用于",
    "用于",
    "根据",
    "需要",
    "单选",
    "多选",
    "跳转",
    "显示",
    "隐藏",
    "如果",
    "若",
    "当",
    "则",
    "状态要求",
    "状态",
    "权限",
    "优先",
    "枚举",
    "限制",
)

RULE_CONTEXT_KEYWORDS = (
    "逻辑",
    "处理",
    "规则",
    "异常",
    "权限",
    "默认值",
    "默认规则",
    "展示口径",
    "配置说明",
    "注意",
    "约束",
)

BOUNDARY_KEYWORDS = (
    "第一版",
    "后续",
    "未来",
    "暂不",
    "暂未",
    "当前不",
    "目前前端不用显示",
    "不在本期",
)

EXAMPLE_DISPLAY_PREFIXES = (
    "查询粒度",
    "查询日期",
    "查询指标",
    "查询维度",
    "业务日期",
)

EXAMPLE_DISPLAY_HINTS = (
    "当前日期",
    "日期选择",
    "取数配置项",
    "累计数据",
    "月末数据",
    "年末数据",
    "季末数据",
    "效果示例",
    "如下图",
)

SECTION_TITLE_PREFIXES = (
    "看板",
    "指标卡",
    "表格",
    "折线图",
    "柱状图",
    "饼图",
    "交叉表",
    "弹窗",
)

SECTION_IDENTITY_TOKENS = (
    "指标卡1",
    "指标卡2",
    "指标卡",
    "表格",
    "折线图",
    "柱状图",
    "饼图",
    "交叉表",
    "弹窗",
)

TITLE_CONTEXT_PREFIXES = (
    "指标看板",
    "看板",
    "表格组件",
    "组件",
    "页面",
    "模块",
)

MODULE_TITLE_KEYWORD_GROUPS = {
    "indicator_card_1": ("指标卡1",),
    "indicator_card_2": ("指标卡2",),
    "indicator_card": ("指标卡",),
    "chart": ("折线图", "柱状图", "饼图"),
    "table": ("表格",),
}

MODULE_DETAIL_KEYWORD_GROUPS = {
    "indicator_card_1": (
        "指标卡1",
        "指标看板-指标卡1",
        "对比弹窗",
        "数据展示格式",
        "数据展示精度",
        "数据量级单位",
        "位置移动至查询粒度下方",
    ),
    "indicator_card_2": (
        "指标卡2",
        "指标单位展示",
    ),
    "chart": (
        "横轴",
        "横轴分组",
        "统计维度",
        "指标对比",
        "饼图上限",
        "对比指标定义",
        "图效果",
    ),
    "table": (
        "表格",
        "看板-表格",
        "表头",
        "展示规则",
        "指标设置弹窗",
    ),
}


def _clean_lines(page: dict[str, object]) -> list[str]:
    return [str(item).strip() for item in page.get("lines", []) if str(item).strip()]


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) <= 1:
        return True
    if NUMERIC_LINE_RE.fullmatch(stripped):
        return True
    if SHORT_ALNUM_RE.fullmatch(stripped):
        return True
    return False


def _normalize_numbered(line: str) -> str:
    return re.sub(r"^\d+[.、]\s*", "", line.lstrip("*").strip()).strip()


def _contains_action_keyword(line: str) -> bool:
    return any(keyword in line for keyword in ACTION_KEYWORDS)


def _starts_with_action_prefix(line: str) -> bool:
    return line.startswith(ACTION_PREFIXES)


def _starts_with_strong_action_prefix(line: str) -> bool:
    return line.startswith(STRONG_ACTION_PREFIXES)


def _starts_with_supporting_action_prefix(line: str) -> bool:
    return line.startswith(SUPPORTING_ACTION_PREFIXES)


def _looks_like_field_label(line: str) -> bool:
    stripped = line.strip().rstrip("：:")
    if len(stripped) > 12:
        return False
    if _contains_action_keyword(stripped) or _starts_with_action_prefix(stripped):
        return False
    if " " in stripped:
        return False
    if any(mark in stripped for mark in ("，", "。", "；", ";")):
        return False
    if stripped.startswith("【") and "】" in stripped:
        return False
    return True


def _is_ignorable_requirement_line(line: str) -> bool:
    stripped = line.strip().rstrip("：:")
    if stripped in IGNORED_REQUIREMENT_LABELS:
        return True
    if stripped in UI_NOISE_EXACT:
        return True
    if stripped.startswith(UI_NOISE_PREFIXES):
        return True
    if CASE_LINE_RE.fullmatch(stripped):
        return True
    if ANCHOR_BLOCK_RE.fullmatch(stripped):
        return True
    if SNAKE_IDENT_RE.fullmatch(stripped):
        return True
    if CHECKMARK_LINE_RE.fullmatch(stripped):
        return True
    if PLUS_MINUS_LINE_RE.fullmatch(stripped):
        return True
    if FIELD_LABEL_COLON_RE.fullmatch(line.strip()):
        return True
    return False


def _looks_like_goal_candidate(line: str) -> bool:
    stripped = _normalize_numbered(line)
    if _is_noise_line(stripped):
        return False
    if stripped in {"需求背景", "需求详情", "需求说明"}:
        return False
    if stripped.endswith(("：", ":")) and len(stripped) <= 12:
        return False
    if PRIORITY_LINE_RE.fullmatch(stripped):
        return False
    if stripped.startswith("【") and "】" in stripped and "、" in stripped:
        return False
    if _looks_like_field_label(stripped):
        return False
    return len(stripped) >= 8


def _detect_flow_ranges(lines: list[str]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start_index: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "开始":
            start_index = index
            continue
        if stripped == "结束" and start_index is not None:
            ranges.append((start_index, index))
            start_index = None
    return ranges


def _is_in_flow_range(index: int, flow_ranges: list[tuple[int, int]]) -> bool:
    return any(start <= index <= end for start, end in flow_ranges)


def _looks_like_short_action_item(line: str) -> bool:
    stripped = line.strip().rstrip("：:")
    if len(stripped) < 4 or len(stripped) > 16:
        return False
    if _is_ignorable_requirement_line(stripped):
        return False
    return _starts_with_action_prefix(stripped) or stripped.endswith(("查询", "导出", "导入", "授权"))


def _looks_like_generic_ui_operation(line: str) -> bool:
    stripped = line.strip().rstrip("：:")
    if not stripped.startswith(GENERIC_UI_OPERATION_PREFIXES):
        return False
    return len(stripped) <= 10


def _looks_like_config_item_requirement(line: str) -> bool:
    stripped = line.strip().rstrip("：:")
    if not any(hint in stripped for hint in CONFIG_ITEM_HINTS):
        return False
    if any(mark in stripped for mark in ("，", "。", "；", ";")) and len(stripped) > 24:
        return False
    return True


def _looks_like_short_config_item(line: str) -> bool:
    stripped = line.strip().rstrip("：:")
    if not _looks_like_config_item_requirement(stripped):
        return False
    if len(stripped) > 18 or len(stripped) < 5:
        return False
    if any(mark in stripped for mark in ("，", "。", "；", ";")):
        return False
    return True


def _looks_like_structural_heading_only(line: str) -> bool:
    stripped = line.strip().rstrip("：:")
    if not stripped:
        return False
    if _looks_like_generic_intro_heading(stripped):
        return True
    if _looks_like_ordered_block_title(stripped):
        return True
    if _looks_like_short_config_item(stripped):
        return True
    if _looks_like_field_label(stripped):
        return True
    if len(stripped) <= 20 and ("/" in stripped or " / " in stripped) and not _looks_like_rule_heavy_line(stripped):
        return True
    if len(stripped) <= 18 and _starts_with_action_prefix(stripped) and not _looks_like_rule_heavy_line(stripped):
        return True
    return False


def _looks_like_rule_heavy_line(line: str) -> bool:
    stripped = line.strip()
    hit_count = sum(1 for keyword in RULE_KEYWORDS if keyword in stripped)
    if hit_count >= 2 or stripped.startswith(("如果", "若", "当")):
        return True
    if any(keyword in stripped for keyword in ("默认", "权限", "状态", "上限", "影响范围", "要求满足")):
        return True
    if "则" in stripped and any(keyword in stripped for keyword in ("展示", "采用", "带出", "触发", "统一")):
        return True
    return False


def _previous_line_implies_rule_context(previous_line: str | None) -> bool:
    if not previous_line:
        return False
    stripped = previous_line.strip()
    if not stripped.endswith(("：", ":")):
        return False
    stripped = stripped.rstrip("：:")
    return any(keyword in stripped for keyword in RULE_CONTEXT_KEYWORDS)


def _looks_like_explanatory_rule_candidate(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 10:
        return False
    if _looks_like_rule_heavy_line(stripped):
        return True
    return any(
        keyword in stripped
        for keyword in (
            "字段范围",
            "逻辑",
            "用于",
            "作用",
            "需要根据",
            "系统需",
            "系统将",
            "数据模型来源于",
            "模型状态",
            "数据权限",
            "默认排序",
            "可参考",
            "跳转到",
            "区分",
            "分流",
            "自动带入",
            "回显",
            "前端展示为",
            "新增配置项",
            "组件新增配置项",
        )
    )


def _looks_like_example_display_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 6:
        return False
    if stripped.startswith(EXAMPLE_DISPLAY_PREFIXES):
        return True
    if re.match(r"^[^=＝]{1,12}\s*[=＝]\s*.+$", stripped):
        return True
    if "示例" in stripped and any(mark in stripped for mark in ("：", ":", "如下")):
        return True
    if "至" in stripped and DATE_YYYY_MM_RE.search(stripped):
        return True
    return False


def _looks_like_example_heavy_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 12:
        return False
    if any(keyword in stripped for keyword in EXAMPLE_DISPLAY_HINTS):
        return True
    if len(DATE_YYYY_MM_DD_RE.findall(stripped)) >= 2:
        return True
    if len(DATE_YYYY_MM_RE.findall(stripped)) >= 2 and "至" in stripped:
        return True
    if "查近" in stripped and any(keyword in stripped for keyword in ("年", "月", "季")):
        return True
    return False


def _looks_like_repeated_suffix_noise(line: str) -> bool:
    stripped = line.strip().rstrip("：:")
    return bool(REPEATED_SUFFIX_RE.search(stripped))


def _collapse_repeated_suffix(text: str) -> str:
    normalized = text.strip().rstrip("：:")
    collapsed = REPEATED_SUFFIX_RE.sub(r"\1", normalized)
    return collapsed or normalized


def _strip_number_prefix(line: str) -> str:
    return re.sub(r"^(?:\d+[.、]\s*|第[一二三四五六七八九十]+(?:部分|章节|点|项|条)\s*)", "", line).strip()


def _parse_standalone_order_marker(line: str) -> int | None:
    stripped = line.strip()
    if ORDER_MARKER_RE.fullmatch(stripped):
        value = int(stripped)
        if 1 <= value <= 20:
            return value
    return None


def _parse_anchor_block_marker(line: str) -> str | None:
    stripped = line.strip()
    if ANCHOR_BLOCK_RE.fullmatch(stripped):
        return stripped
    return None


def _meaningful_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if not _is_noise_line(line)]


def _dedupe_keep_order(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _prune_empty_values(value: object) -> object:
    if isinstance(value, dict):
        pruned: dict[str, object] = {}
        for key, item in value.items():
            cleaned = _prune_empty_values(item)
            if cleaned in (None, "", [], {}):
                continue
            pruned[key] = cleaned
        return pruned
    if isinstance(value, list):
        cleaned_list = [_prune_empty_values(item) for item in value]
        return [item for item in cleaned_list if item not in (None, "", [], {})]
    return value


def _strip_action_prefix_for_title(title: str) -> str:
    normalized = title.strip().rstrip("：:")
    for prefix in (
        "新增",
        "支持",
        "增加",
        "添加",
        "保存为",
        "另存为",
        "从",
        "选择",
        "下载",
        "查看",
        "跳转",
    ):
        if normalized.startswith(prefix):
            return normalized[len(prefix) :].strip("【】 ")
    return normalized.strip("【】 ")


def _normalize_title_subject(title: str) -> str:
    normalized = _strip_action_prefix_for_title(title)
    changed = True
    while changed:
        changed = False
        for prefix in TITLE_CONTEXT_PREFIXES:
            if normalized.startswith(prefix) and len(normalized) > len(prefix) + 2:
                normalized = normalized[len(prefix) :].strip("【】 -—")
                changed = True
    normalized = _strip_action_prefix_for_title(normalized)
    normalized = _collapse_repeated_suffix(normalized)
    if "全局看板" in normalized and any(token in normalized for token in ("筛选", "过滤")):
        normalized = normalized.replace("全局看板", "全局")
    return normalized


def _title_bigram_tokens(title: str) -> set[str]:
    normalized = _strip_action_prefix_for_title(title)
    if len(normalized) < 2:
        return set()
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def _looks_like_action_or_config_title(title: str) -> bool:
    normalized = title.strip().rstrip("：:")
    if any(normalized.startswith(prefix) for prefix in ("新增", "支持", "增加", "添加", "保存为", "另存为", "从", "选择", "下载", "查看")):
        return True
    if "新增" in normalized or "跳转" in normalized:
        return True
    return False


def _looks_like_generic_intro_heading(title: str) -> bool:
    normalized = title.strip().rstrip("：:")
    if len(normalized) < 4:
        return False
    return any(
        phrase in normalized
        for phrase in (
            "涉及的主要功能点",
            "主要功能点如下",
            "功能点如下",
            "如下所示",
            "页面如下",
        )
    )


def _should_merge_adjacent_sections(previous_title: str, current_title: str) -> bool:
    previous_body = _strip_action_prefix_for_title(previous_title)
    current_body = _strip_action_prefix_for_title(current_title)

    if not previous_body or not current_body:
        return False

    current_action = _looks_like_action_or_config_title(current_title)
    previous_action = _looks_like_action_or_config_title(previous_title)
    overlap = _title_bigram_tokens(previous_title) & _title_bigram_tokens(current_title)
    similarity = SequenceMatcher(None, previous_body, current_body).ratio()

    if previous_body in current_body or current_body in previous_body:
        return True
    if overlap and (current_action or previous_action):
        return True
    if len(previous_body) >= 6 and len(current_body) >= 6 and overlap and similarity >= 0.65:
        return True
    return False


def _is_low_information_supporting_item(
    line: str,
    title: str,
    main_requirements: list[str],
) -> bool:
    normalized = line.strip().rstrip("：:")
    if not normalized:
        return True

    if normalized in {"新增字段", "筛选条件配置", "数据查询", "保存取数模版"}:
        return True

    if (
        len(normalized) <= 8
        and any(keyword in normalized for keyword in ("字段", "配置", "查询", "模板", "图标"))
        and not _starts_with_supporting_action_prefix(normalized)
        and not _starts_with_strong_action_prefix(normalized)
    ):
        return True

    title_overlap = _title_bigram_tokens(title) & _title_bigram_tokens(normalized)
    if title_overlap and len(normalized) <= 14 and not _looks_like_explanatory_rule_candidate(normalized):
        return True

    for requirement in main_requirements:
        if normalized in requirement:
            return True

    return False


def _looks_like_section_heading(line: str) -> bool:
    stripped = line.strip()
    normalized = _normalize_numbered(stripped).rstrip("：:")
    if len(normalized) < 6 or len(normalized) > 96:
        return False
    if _looks_like_generic_intro_heading(normalized):
        return False
    if _is_noise_line(normalized):
        return False
    # 多需求页里最稳的小节锚点通常就是“1. xxx / 2. xxx”这种编号标题。
    # 这里优先识别，避免像“查询粒度定义改造...”这种标题被后续规则误当成展示口径。
    if FEATURE_LINE_RE.match(stripped):
        return True
    if _looks_like_field_label(normalized):
        return False
    if _looks_like_short_config_item(normalized):
        return False
    if _looks_like_rule_heavy_line(normalized):
        return False
    if _looks_like_example_display_line(normalized):
        return False
    if normalized in IGNORED_REQUIREMENT_LABELS:
        return False
    if line.startswith("*"):
        return False
    if "——" in normalized and any(keyword in normalized for keyword in SECTION_TITLE_PREFIXES):
        return True
    if normalized.endswith(("模块", "页面", "弹窗")) and any(keyword in normalized for keyword in SECTION_TITLE_PREFIXES):
        return True
    return False


def _looks_like_block_heading(line: str, next_lines: list[str], prev_line: str | None = None) -> bool:
    stripped = line.strip()
    normalized = stripped.rstrip("：:")
    if not normalized or FEATURE_LINE_RE.match(stripped):
        return False
    if _looks_like_generic_intro_heading(normalized):
        return False
    if stripped.startswith("*"):
        return False
    if len(normalized) < 3 or len(normalized) > 28:
        return False
    if _is_noise_line(normalized) or _is_ignorable_requirement_line(normalized):
        return False
    if _looks_like_rule_heavy_line(normalized) or _looks_like_example_display_line(normalized):
        return False
    if ANCHOR_BLOCK_RE.fullmatch(normalized):
        return False
    if FIELD_OR_INDEX_RE.fullmatch(normalized):
        return False
    if DATE_YYYY_MM_DD_RE.fullmatch(normalized):
        return False
    if normalized.startswith(("（", "(")) and normalized.endswith(("）", ")")):
        return False
    if normalized.startswith(("可参考", "用于", "多数情况下", "系统需根据", "注意")):
        return False
    if any(mark in normalized for mark in ("。", "；", ";")):
        return False
    if "，" in normalized:
        return False
    if normalized in {"UI"}:
        return False

    numbered_hits = sum(1 for item in next_lines[:6] if FEATURE_LINE_RE.match(item.strip()))
    if prev_line and prev_line.strip() in IGNORED_REQUIREMENT_LABELS and numbered_hits >= 2:
        return False
    if normalized in {"取数模板", "明细查询", "指标查询"} and numbered_hits == 0:
        return False
    if numbered_hits >= 2:
        return True
    if "/" in normalized or " / " in normalized:
        return True
    if normalized.endswith(("流程", "规则")):
        return True
    if any(keyword in normalized for keyword in ("字段", "模型", "筛选", "排序", "查询", "模板", "授权")) and numbered_hits >= 1:
        return True
    return False


def _looks_like_ordered_block_title(line: str) -> bool:
    normalized = line.strip().rstrip("：:")
    if not normalized:
        return False
    if len(normalized) < 3 or len(normalized) > 40:
        return False
    if _is_noise_line(normalized) or _is_ignorable_requirement_line(normalized):
        return False
    if _looks_like_low_quality_numbered_title(normalized):
        return False
    if _looks_like_low_quality_block_title(normalized) and not (
        _starts_with_action_prefix(normalized)
        or normalized.endswith("区分")
        or any(keyword in normalized for keyword in ("流程", "规则", "模板", "授权", "模型", "字段", "筛选", "排序", "查询"))
    ):
        return False
    if _looks_like_example_display_line(normalized):
        return False
    if _looks_like_explanatory_rule_candidate(normalized) and not _contains_action_keyword(normalized):
        return False
    if any(mark in normalized for mark in ("。", "；", ";")):
        return False
    return True


def _extract_ordered_block_sections(lines: list[str]) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    index = 0

    while index < len(lines):
      line = lines[index]
      order_marker = _parse_standalone_order_marker(line)
      next_line = lines[index + 1] if index + 1 < len(lines) else None
      if order_marker is not None and next_line and _looks_like_ordered_block_title(next_line):
          if current_title and current_lines:
              sections.append({"title": current_title, "lines": current_lines[:]})
          current_title = next_line.strip().rstrip("：:")
          current_lines = [current_title]
          index += 2
          continue
      if current_title:
          current_lines.append(line)
      index += 1

    if current_title and current_lines:
        sections.append({"title": current_title, "lines": current_lines[:]})

    return sections if len(sections) >= 2 else []


def _extract_anchor_block_sections(lines: list[str]) -> tuple[list[dict[str, object]], int | None]:
    sections: list[dict[str, object]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    first_anchor_index: int | None = None
    index = 0

    while index < len(lines):
        line = lines[index]
        anchor_marker = _parse_anchor_block_marker(line)
        next_line = lines[index + 1] if index + 1 < len(lines) else None
        if anchor_marker and next_line and _looks_like_ordered_block_title(next_line):
            if first_anchor_index is None:
                first_anchor_index = index
            if current_title and current_lines:
                sections.append({"title": current_title, "lines": current_lines[:]})
            current_title = next_line.strip().rstrip("：:")
            current_lines = [current_title]
            index += 2
            continue
        if current_title:
            current_lines.append(line)
        index += 1

    if current_title and current_lines:
        sections.append({"title": current_title, "lines": current_lines[:]})

    return (sections if len(sections) >= 2 else [], first_anchor_index)


def _section_title_quality_score(title: str) -> int:
    normalized = title.strip().rstrip("：:")
    if not normalized:
        return -10

    score = 0
    if 4 <= len(normalized) <= 28:
        score += 3
    elif len(normalized) <= 2 or len(normalized) > 40:
        score -= 4

    if _looks_like_low_quality_block_title(normalized) or _looks_like_low_quality_numbered_title(normalized):
        score -= 6

    if len(normalized) >= 24 and any(mark in normalized for mark in ("，", "。", "；", ";")):
        score -= 4

    if _looks_like_explanatory_rule_candidate(normalized) and not _starts_with_strong_action_prefix(normalized):
        score -= 5

    if normalized.startswith(("配置", "带入", "可复用")):
        score -= 4

    if _starts_with_action_prefix(normalized) or _contains_action_keyword(normalized):
        score += 3

    if normalized.endswith(("流程", "规则", "授权")):
        score += 3

    if any(keyword in normalized for keyword in ("字段", "模型", "筛选", "排序", "查询", "模板", "表格", "看板")):
        score += 2

    if FIELD_OR_INDEX_RE.fullmatch(normalized):
        score -= 6
    if ANCHOR_BLOCK_RE.fullmatch(normalized):
        score -= 6
    if _looks_like_field_label(normalized):
        score -= 4

    return score


def _score_section_set(sections: list[dict[str, object]]) -> int:
    if len(sections) < 2:
        return -999

    titles = [str(section.get("title", "")).strip() for section in sections if str(section.get("title", "")).strip()]
    if len(titles) < 2:
        return -999

    score = sum(_section_title_quality_score(title) for title in titles)
    duplicate_count = len(titles) - len(set(titles))
    score -= duplicate_count * 5
    if len(titles) > 10:
        score -= (len(titles) - 10) * 2
    return score


def _pick_best_section_set(candidates: list[list[dict[str, object]]]) -> list[dict[str, object]]:
    best_sections: list[dict[str, object]] = []
    best_score = -999
    for sections in candidates:
        score = _score_section_set(sections)
        if score > best_score:
            best_score = score
            best_sections = sections
    return best_sections


def _should_merge_subordinate_section(previous_title: str, current_title: str) -> bool:
    previous_normalized = previous_title.strip().rstrip("：:")
    current_normalized = current_title.strip().rstrip("：:")
    if not previous_normalized or not current_normalized:
        return False

    previous_score = _section_title_quality_score(previous_normalized)
    current_score = _section_title_quality_score(current_normalized)
    overlap = _title_bigram_tokens(previous_normalized) & _title_bigram_tokens(current_normalized)

    if current_normalized == previous_normalized:
        return True

    if (
        current_score <= 1
        and previous_score >= 2
        and (
            _looks_like_short_config_item(current_normalized)
            or current_normalized.startswith(("配置", "带入", "可复用"))
            or _looks_like_explanatory_rule_candidate(current_normalized)
        )
    ):
        return True

    if (previous_normalized in current_normalized or current_normalized in previous_normalized) and len(overlap) >= 2:
        return True

    if len(overlap) >= 4 and len(current_normalized) >= len(previous_normalized):
        return True

    return False


def _coalesce_subordinate_sections(sections: list[dict[str, object]]) -> list[dict[str, object]]:
    if len(sections) < 2:
        return sections

    coalesced: list[dict[str, object]] = []
    for section in sections:
        title = str(section.get("title", "")).strip()
        lines = [str(item) for item in section.get("lines", [])]
        if coalesced and _should_merge_subordinate_section(str(coalesced[-1].get("title", "")), title):
            merged_lines = list(coalesced[-1].get("lines", []))
            if title:
                merged_lines.append(title)
            if lines:
                merged_lines.extend(lines[1:] if lines and lines[0] == title else lines)
            coalesced[-1]["lines"] = merged_lines
            continue
        coalesced.append({"title": title, "lines": lines})

    return coalesced


def _extract_block_sections(lines: list[str]) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for index, line in enumerate(lines):
        look_ahead = lines[index + 1 : index + 7]
        prev_line = lines[index - 1] if index > 0 else None
        if _looks_like_block_heading(line, look_ahead, prev_line):
            if current_title and current_lines:
                sections.append({"title": current_title, "lines": current_lines[:]})
            current_title = line.strip().rstrip("：:")
            current_lines = [current_title]
            continue
        if current_title:
            current_lines.append(line)

    if current_title and current_lines:
        sections.append({"title": current_title, "lines": current_lines[:]})

    if len(sections) < 2:
        return []

    merged_sections: list[dict[str, object]] = []
    for section in sections:
        if merged_sections and merged_sections[-1]["title"] == section["title"]:
            merged_sections[-1]["lines"].extend(section["lines"][1:])
        else:
            merged_sections.append(section)

    if len(merged_sections) < 2:
        return merged_sections

    coalesced_sections: list[dict[str, object]] = []
    for section in merged_sections:
        if (
            coalesced_sections
            and _should_merge_adjacent_sections(str(coalesced_sections[-1]["title"]), str(section["title"]))
        ):
            coalesced_sections[-1]["lines"].append(str(section["title"]))
            coalesced_sections[-1]["lines"].extend(section["lines"][1:])
            continue
        coalesced_sections.append(section)

    return coalesced_sections


def _looks_like_low_quality_block_title(title: str) -> bool:
    normalized = title.strip().rstrip("：:")
    if not normalized:
        return True
    if NUMERIC_UNIT_RE.fullmatch(normalized):
        return True
    if _looks_like_short_config_item(normalized):
        return True
    if normalized in {"新增字段", "筛选条件配置", "数据查询"}:
        return True
    if "新增配置项" in normalized or "配置项【" in normalized:
        return True
    if len(normalized) <= 8 and any(keyword in normalized for keyword in ("字段", "配置", "查询")):
        return True
    return False


def _looks_like_low_quality_numbered_title(title: str) -> bool:
    normalized = title.strip().rstrip("：:")
    if not normalized:
        return True
    if ANCHOR_BLOCK_RE.fullmatch(normalized):
        return True
    if normalized in {"新增字段", "筛选条件配置", "数据查询"}:
        return True
    if "新增配置项" in normalized or "配置项【" in normalized:
        return True
    if len(normalized) >= 24 and not _starts_with_strong_action_prefix(normalized) and not _contains_action_keyword(normalized) and (
        _looks_like_explanatory_rule_candidate(normalized)
        or any(mark in normalized for mark in ("，", "。", "；", ";"))
    ):
        return True
    return False


def _looks_like_low_quality_capability_phrase(text: str) -> bool:
    normalized = text.strip().rstrip("：:")
    if not normalized:
        return True
    if _looks_like_low_quality_block_title(normalized) or _looks_like_low_quality_numbered_title(normalized):
        return True
    if normalized.startswith("新增【") and any(keyword in normalized for keyword in ("配置功能", "配置项", "能力")):
        return True
    if len(normalized) >= 18 and normalized.endswith("配置功能"):
        return True
    return False


def _extract_numbered_sections(lines: list[str]) -> list[dict[str, object]]:
    numbered_sections: list[dict[str, object]] = []
    current_numbered_title: str | None = None
    current_numbered_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if FEATURE_LINE_RE.match(stripped):
            candidate_title = _normalize_numbered(line).rstrip("：:")
            if not _looks_like_low_quality_numbered_title(candidate_title):
                if current_numbered_title and current_numbered_lines:
                    numbered_sections.append({"title": current_numbered_title, "lines": current_numbered_lines[:]})
                current_numbered_title = candidate_title
                current_numbered_lines = [current_numbered_title]
                continue
        if current_numbered_title:
            current_numbered_lines.append(line)

    if current_numbered_title and current_numbered_lines:
        numbered_sections.append({"title": current_numbered_title, "lines": current_numbered_lines[:]})

    return numbered_sections


def _extract_visual_sections(lines: list[str]) -> list[dict[str, object]]:
    visual_sections: list[dict[str, object]] = []
    current_visual_title: str | None = None
    current_visual_lines: list[str] = []
    current_visual_order: int | None = None
    current_visual_start_index: int | None = None

    for index, line in enumerate(lines):
        stripped = line.strip()
        normalized = _normalize_numbered(stripped).rstrip("：:")
        is_visual_heading = "——" in normalized and any(keyword in normalized for keyword in SECTION_TITLE_PREFIXES)
        if is_visual_heading:
            if current_visual_title and current_visual_lines:
                visual_sections.append(
                    {
                        "title": current_visual_title,
                        "lines": current_visual_lines[:],
                        "orderHint": current_visual_order,
                        "sourceIndex": current_visual_start_index if current_visual_start_index is not None else index,
                    }
                )
            current_visual_title = normalized
            current_visual_lines = [normalized]
            current_visual_start_index = index
            order_hint = None
            for look_ahead in range(index + 1, min(index + 3, len(lines))):
                order_hint = _parse_standalone_order_marker(lines[look_ahead])
                if order_hint is not None:
                    break
            if order_hint is None and index > 0:
                order_hint = _parse_standalone_order_marker(lines[index - 1])
            current_visual_order = order_hint
            continue
        if current_visual_title:
            current_visual_lines.append(line)

    if current_visual_title and current_visual_lines:
        visual_sections.append(
            {
                "title": current_visual_title,
                "lines": current_visual_lines[:],
                "orderHint": current_visual_order,
                "sourceIndex": current_visual_start_index if current_visual_start_index is not None else len(lines),
            }
        )

    if len(visual_sections) >= 2:
        hinted = [section for section in visual_sections if section.get("orderHint") is not None]
        if len(hinted) >= 2:
            visual_sections = sorted(
                visual_sections,
                key=lambda item: (
                    item.get("orderHint") is None,
                    item.get("orderHint") or 999,
                ),
            )
        return visual_sections
    return []


def _module_kind_for_title(title: str) -> str | None:
    for kind, keywords in MODULE_TITLE_KEYWORD_GROUPS.items():
        if any(keyword in title for keyword in keywords):
            return kind
    return None


def _collect_module_detail_lines(title: str, lines: list[str]) -> list[str]:
    kind = _module_kind_for_title(title)
    if not kind:
        return []

    keywords = MODULE_DETAIL_KEYWORD_GROUPS.get(kind, ())
    if not keywords:
        return []

    collected: list[str] = []
    seen: set[str] = set()
    anchor_indexes: list[int] = []

    for index, line in enumerate(lines):
        normalized = _normalize_numbered(line)
        if any(keyword in normalized for keyword in keywords):
            anchor_indexes.append(index)
            if normalized not in seen and not _is_ignorable_requirement_line(normalized):
                collected.append(normalized)
                seen.add(normalized)

    # 对于强视觉页面，很多有效信息会跟在锚点后面几行，以短配置项或规则句出现。
    # 这里只做短窗口前向收集，避免又把整页公共规则吃回某个模块。
    for anchor_index in anchor_indexes:
        for candidate in lines[anchor_index + 1 : anchor_index + 9]:
            normalized = _normalize_numbered(candidate)
            if not normalized or _is_noise_line(normalized):
                continue
            if _looks_like_section_heading(candidate):
                break
            if normalized in seen:
                continue
            if _looks_like_short_config_item(normalized) or _looks_like_rule_heavy_line(normalized) or normalized.startswith("*"):
                collected.append(normalized)
                seen.add(normalized)

    return _dedupe_keep_order(collected, 10)


def _visual_sections_reordered(sections: list[dict[str, object]]) -> bool:
    source_indexes = [int(section.get("sourceIndex", 0)) for section in sections]
    return source_indexes != sorted(source_indexes)


def _extract_sections(lines: list[str]) -> list[dict[str, object]]:
    visual_sections = _extract_visual_sections(lines)
    if visual_sections:
        return _coalesce_subordinate_sections(visual_sections)

    anchor_sections, first_anchor_index = _extract_anchor_block_sections(lines)
    ordered_block_sections = _extract_ordered_block_sections(lines)
    block_sections = _extract_block_sections(lines)
    numbered_sections = _extract_numbered_sections(lines)

    anchor_combo_sections: list[dict[str, object]] = []
    if anchor_sections:
        prefix_sections: list[dict[str, object]] = []
        if first_anchor_index and first_anchor_index > 0:
            prefix_sections = _extract_ordered_block_sections(lines[:first_anchor_index])
        anchor_combo_sections = prefix_sections + anchor_sections if prefix_sections else anchor_sections

    best_structured_sections = _pick_best_section_set(
        [sections for sections in (anchor_combo_sections, ordered_block_sections, block_sections, numbered_sections) if sections]
    )

    # 优先使用编号小节。对多数 PRD 来说，这类标题和真实需求项的对应关系最稳定，
    # 比“某某模块调整”“某某弹窗”这类视觉分块标题更适合作为对外展示的小节。
    # 但在 Modao 这类“块标题 + 编号细节”的页面里，如果块标题已经足够稳定，
    # 再把所有编号句都抬成一级小节会严重破坏导读结构。
    if not best_structured_sections and len(numbered_sections) >= 2:
        low_quality_block_count = sum(
            1 for section in block_sections if _looks_like_low_quality_block_title(str(section.get("title", "")))
        )
        if not block_sections or low_quality_block_count >= max(1, len(block_sections) // 2):
            return numbered_sections
    if best_structured_sections:
        return _coalesce_subordinate_sections(best_structured_sections)

    sections: list[dict[str, object]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if _looks_like_section_heading(line):
            if current_title and current_lines:
                sections.append({"title": current_title, "lines": current_lines[:]})
            current_title = _normalize_numbered(line).rstrip("：:")
            current_lines = [current_title]
            continue
        if current_title:
            current_lines.append(line)

    if current_title and current_lines:
        sections.append({"title": current_title, "lines": current_lines[:]})

    # 小节拆解只在真正识别出多个需求段时启用，避免把普通页面强行切碎。
    if len(sections) < 2:
        return []
    return _coalesce_subordinate_sections(sections)


def _extract_summary(lines: list[str]) -> list[str]:
    candidates = [
        line
        for line in lines
        if len(line) >= SUMMARY_MIN_LENGTH
        and _looks_like_goal_candidate(line)
        and not FEATURE_LINE_RE.match(line)
        and not any(keyword in line for keyword in RULE_KEYWORDS)
    ]
    return _dedupe_keep_order(candidates, 3)


def _extract_goal(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines[:-1]):
        if line in {"需求背景", "需求详情", "需求说明"}:
            for candidate in lines[index + 1 : index + 5]:
                next_line = _normalize_numbered(candidate)
                if (
                    next_line.endswith(("：", ":"))
                    and len(next_line.rstrip("：:")) >= 6
                    and not FEATURE_LINE_RE.match(candidate)
                    and not _looks_like_rule_heavy_line(next_line)
                ):
                    return [next_line.rstrip("：:")]
                if _looks_like_goal_candidate(next_line):
                    return [next_line.rstrip("：:")]

    summary = _extract_summary(lines)
    if summary:
        return summary[:2]
    candidates = [line for line in _meaningful_lines(lines) if _looks_like_goal_candidate(line)]
    return _dedupe_keep_order(candidates, 2)


def _extract_page_summary(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines[:-1]):
        if line in {"需求背景", "需求详情", "需求说明"}:
            summary_items: list[str] = []
            start_index = index + 1
            if start_index < len(lines):
                title_line = _normalize_numbered(lines[start_index]).rstrip("：:")
                if title_line and not FEATURE_LINE_RE.match(lines[start_index]) and len(title_line) >= 4:
                    start_index += 1
            for candidate in lines[start_index : start_index + 8]:
                if FEATURE_LINE_RE.match(candidate.strip()):
                    normalized = _normalize_numbered(candidate).rstrip("：:")
                    if (
                        not normalized
                        or _is_noise_line(normalized)
                        or _is_ignorable_requirement_line(normalized)
                        or _looks_like_field_label(normalized)
                    ):
                        continue
                    summary_items.append(normalized)
                elif summary_items:
                    break
            if len(summary_items) >= 2:
                return _dedupe_keep_order(summary_items, 6)
    return []


def _extract_section_identity_tokens(text: str) -> set[str]:
    return {token for token in SECTION_IDENTITY_TOKENS if token in text}


def _map_summary_items_to_section_titles(page_summary: list[str], sections: list[dict[str, object]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {str(section.get("title", "")): [] for section in sections}
    section_tokens = {
        str(section.get("title", "")): _extract_section_identity_tokens(str(section.get("title", "")))
        for section in sections
    }

    for item in page_summary:
        item_tokens = _extract_section_identity_tokens(item)
        if not item_tokens:
            continue
        best_title = None
        best_score = 0
        for title, tokens in section_tokens.items():
            score = len(item_tokens & tokens)
            if score > best_score:
                best_score = score
                best_title = title
        if best_title and best_score > 0:
            mapping[best_title].append(item)
    return mapping


def _fallback_summary_for_section(
    title: str,
    page_summary: list[str],
    section: dict[str, object],
    existing: list[str],
    allow_order_fallback: bool = True,
) -> list[str]:
    if existing:
        return existing
    if not allow_order_fallback:
        return []
    order_hint = section.get("orderHint")
    if isinstance(order_hint, int) and 1 <= order_hint <= len(page_summary):
        return [page_summary[order_hint - 1]]
    return []


def _extract_feature_points(lines: list[str], goal_items: set[str]) -> list[str]:
    flow_ranges = _detect_flow_ranges(lines)
    candidates: list[str] = []
    for index, line in enumerate(lines):
        normalized = _normalize_numbered(line)
        if len(normalized) < 4:
            continue
        if normalized in goal_items:
            continue
        if _is_ignorable_requirement_line(normalized):
            continue
        if _looks_like_example_display_line(normalized):
            continue
        if _looks_like_repeated_suffix_noise(normalized):
            continue
        # 主需求只保留“能力主线”，配置项/示例口径/短 UI 噪音都尽量下沉。
        if _looks_like_config_item_requirement(normalized):
            continue
        if _is_in_flow_range(index, flow_ranges):
            continue
        if line.startswith("*"):
            continue
        if normalized.startswith(SUPPORTING_PREFIXES):
            continue
        if _starts_with_supporting_action_prefix(normalized) and _looks_like_rule_heavy_line(normalized):
            continue
        if normalized.endswith(("：", ":")):
            continue
        has_action = _contains_action_keyword(normalized)
        starts_action = _starts_with_action_prefix(normalized)
        strong_action = _starts_with_strong_action_prefix(normalized)
        is_numbered = bool(FEATURE_LINE_RE.match(line))
        if _looks_like_field_label(normalized):
            continue
        if _looks_like_explanatory_rule_candidate(normalized) and not strong_action:
            continue
        if _looks_like_rule_heavy_line(normalized) and not strong_action:
            continue
        if is_numbered and (strong_action or (has_action and len(normalized) >= 8)):
            candidates.append(normalized)
            continue
        if strong_action:
            candidates.append(normalized)
            continue
        if starts_action and len(normalized) >= 8 and not _looks_like_short_action_item(normalized):
            candidates.append(normalized)
            continue
        if has_action and len(normalized) >= 14 and any(mark in normalized for mark in ("，", "。", "；", "：", ":")):
            candidates.append(normalized)
    return _dedupe_keep_order(candidates, 8)


def _extract_supporting_requirements(lines: list[str], main_items: list[str], goal_items: set[str]) -> list[str]:
    flow_ranges = _detect_flow_ranges(lines)
    candidates: list[str] = []
    main_set = set(main_items)
    for index, line in enumerate(lines):
        normalized = _normalize_numbered(line)
        if len(normalized) < 4 or normalized in main_set or normalized in goal_items:
            continue
        if _is_ignorable_requirement_line(normalized):
            continue
        if _looks_like_example_display_line(normalized):
            continue
        if _looks_like_repeated_suffix_noise(normalized):
            continue
        if _looks_like_generic_ui_operation(normalized):
            continue
        # 配套需求保留“和主能力配套的配置/操作能力”，不再直接收纯 UI 操作项。
        if normalized.endswith(("：", ":")):
            continue
        if _is_in_flow_range(index, flow_ranges):
            continue
        if line.startswith("*") and len(normalized) <= 4 and not _contains_action_keyword(normalized):
            continue
        if _looks_like_short_config_item(normalized):
            candidates.append(normalized)
            continue
        if _looks_like_rule_heavy_line(normalized):
            continue
        if _looks_like_config_item_requirement(normalized):
            if len(normalized) >= 5 or _contains_action_keyword(normalized):
                candidates.append(normalized)
            continue
        if (
            line.startswith("*")
            or _starts_with_supporting_action_prefix(normalized)
            or _looks_like_short_action_item(normalized)
        ):
            candidates.append(normalized)
    return _dedupe_keep_order(candidates, 6)


def _extract_rules(lines: list[str], excluded_items: set[str]) -> list[str]:
    candidates: list[str] = []
    previous_line: str | None = None
    for line in lines:
        normalized = _normalize_numbered(line)
        previous_line_implies_rule = _previous_line_implies_rule_context(previous_line)
        if len(line) < 8:
            previous_line = line
            continue
        if any(keyword in line for keyword in BOUNDARY_KEYWORDS):
            previous_line = line
            continue
        if normalized in excluded_items:
            previous_line = line
            continue
        if _looks_like_structural_heading_only(normalized) and not previous_line_implies_rule:
            previous_line = line
            continue
        if _looks_like_example_display_line(normalized) or _looks_like_example_heavy_line(normalized):
            previous_line = line
            continue
        if any(keyword in line for keyword in RULE_KEYWORDS) or previous_line_implies_rule:
            candidates.append(normalized)
        previous_line = line
    return _dedupe_keep_order(candidates, 10)


def _extract_example_display(lines: list[str], excluded_items: set[str]) -> list[str]:
    candidates = [
        _normalize_numbered(line)
        for line in lines
        if len(_normalize_numbered(line)) >= 6
        and _normalize_numbered(line) not in excluded_items
        and (
            _looks_like_example_display_line(_normalize_numbered(line))
            or _looks_like_example_heavy_line(_normalize_numbered(line))
        )
    ]
    return _dedupe_keep_order(candidates, 8)


def _extract_boundaries(lines: list[str], suspected_issues: list[dict[str, object]]) -> list[str]:
    candidates = [
        str(issue.get("evidence", "")).strip()
        for issue in suspected_issues
        if issue.get("type") == "scope_boundary" and str(issue.get("evidence", "")).strip()
    ]
    candidates.extend(
        line
        for line in lines
        if len(line) >= 8 and any(keyword in line for keyword in BOUNDARY_KEYWORDS)
    )
    return _dedupe_keep_order(candidates, 6)


def _build_section_summary(
    title: str,
    mapped_summary: list[str],
    main_requirements: list[str],
    supporting_requirements: list[str],
    rules: list[str],
    example_display: list[str],
) -> list[str]:
    normalized_title = title.strip().rstrip("：:")
    summary: list[str] = []
    prefer_capability_summary = (
        _looks_like_action_or_config_title(normalized_title)
        or "为" in normalized_title
        or "&" in normalized_title
        or " / " in normalized_title
    )
    if prefer_capability_summary and main_requirements:
        summary.extend(main_requirements[:1])
    if not summary and mapped_summary:
        summary.extend(mapped_summary[:1])
    if not summary and normalized_title.startswith("【") and normalized_title.endswith("】"):
        summary.append(normalized_title)
    if not summary and main_requirements:
        if _looks_like_config_item_requirement(normalized_title):
            summary.append(f"围绕{normalized_title}，{main_requirements[0]}")
        else:
            summary.extend(main_requirements[:1])
    elif supporting_requirements:
        if _looks_like_config_item_requirement(normalized_title):
            summary.append(f"围绕{normalized_title}，补充{supporting_requirements[0]}")
        else:
            summary.extend(supporting_requirements[:1])
    elif rules:
        if _looks_like_config_item_requirement(normalized_title):
            summary.append(f"围绕{normalized_title}，约束为：{rules[0]}")
        else:
            summary.extend(rules[:1])
    elif example_display:
        if _looks_like_config_item_requirement(normalized_title):
            summary.append(f"围绕{normalized_title}，示例口径为：{example_display[0]}")
        else:
            summary.extend(example_display[:1])

    if not summary:
        summary.append(normalized_title)

    return _dedupe_keep_order(summary, 2)


def _rewrite_title_as_capability(title: str) -> str | None:
    normalized = title.strip().rstrip("：:")
    if not normalized:
        return None
    if normalized.startswith("支持保存为"):
        return normalized
    if normalized.startswith("保存为"):
        return f"支持{normalized}"
    if normalized.startswith("另存为"):
        return f"支持{normalized}"
    if normalized.startswith("支持将") and "设置为" in normalized:
        left, right = normalized[len("支持将") :].split("设置为", 1)
        left = left.strip("【】 ")
        right = right.strip("【】 ")
        if left.startswith("支持"):
            left = left[len("支持") :].strip()
        if left == "保存" and right:
            return f"支持保存为{right}"
    if "为" in normalized and len(normalized) <= 24:
        left, right = normalized.split("为", 1)
        left = left.strip("【】 ")
        right = right.strip("【】 ")
        if left and right:
            return f"支持将{left}设置为{right}"
    if "&" in normalized:
        parts = [item.strip("【】 ") for item in normalized.split("&") if item.strip("【】 ")]
        if len(parts) >= 2:
            second = parts[1]
            if second.startswith("支持"):
                return f"支持{parts[0]}，并{second}"
            return f"支持{parts[0]}，并处理{second}"
    if " / " in normalized and any(keyword in normalized for keyword in ("查询方式", "模板", "筛选", "排序")):
        parts = [item.strip("【】 ") for item in normalized.split(" / ") if item.strip("【】 ")]
        if len(parts) >= 2:
            left = parts[0]
            if left.startswith("添加"):
                left = left[len("添加") :].strip()
            return f"支持配置{left}与{parts[1]}"
    if normalized.startswith("支持配置"):
        inner = normalized[len("支持配置") :].strip()
        if inner and any(keyword in inner for keyword in ("日期", "时间", "方式", "权限")):
            return f"支持设置{inner}"
    return None


def _choose_section_display_title(
    raw_title: str,
    main_requirements: list[str],
    summary: list[str],
) -> str:
    normalized = raw_title.strip().rstrip("：:")
    rewritten = _rewrite_title_as_capability(normalized)
    if rewritten:
        return rewritten
    if _looks_like_explanatory_section_title(normalized) and main_requirements:
        compressed = _compress_capability_clause(main_requirements[0])
        if compressed:
            return compressed
    if _looks_like_repeated_suffix_noise(normalized) and main_requirements:
        compressed = _compress_capability_clause(main_requirements[0])
        if compressed:
            return compressed
        return main_requirements[0]
    if (_looks_like_low_quality_block_title(normalized) or _looks_like_low_quality_numbered_title(normalized)) and main_requirements:
        compressed = _compress_capability_clause(main_requirements[0])
        if compressed:
            return compressed
        return main_requirements[0]
    if (_looks_like_low_quality_block_title(normalized) or _looks_like_low_quality_numbered_title(normalized)) and summary:
        return summary[0]
    return normalized


def _compress_capability_clause(text: str) -> str:
    normalized = text.strip().rstrip("：:")
    normalized = _collapse_repeated_suffix(normalized)
    if len(normalized) < 20:
        return normalized
    if not (_starts_with_action_prefix(normalized) or _contains_action_keyword(normalized)):
        return normalized
    parts = re.split(r"[，；。;]", normalized, maxsplit=1)
    first = parts[0].strip()
    return first if len(first) >= 6 else normalized


def _dedupe_capability_phrases(items: list[str], limit: int) -> list[str]:
    result: list[str] = []
    seen_subjects: set[str] = set()
    for item in items:
        normalized = str(item).strip()
        if not normalized:
            continue
        compressed = _compress_capability_clause(normalized)
        subject = _normalize_title_subject(compressed or normalized)
        key = subject or compressed or normalized
        if key in seen_subjects:
            continue
        seen_subjects.add(key)
        result.append(compressed or normalized)
        if len(result) >= limit:
            break
    return result


def _normalize_capability_list(items: list[str], limit: int) -> list[str]:
    normalized_items: list[str] = []
    for item in items:
        normalized = _compress_capability_clause(str(item).strip())
        if normalized:
            normalized_items.append(normalized)
    return _dedupe_capability_phrases(normalized_items, limit)


def _capability_subject_key(text: str) -> str:
    normalized = str(text).strip()
    compressed = _compress_capability_clause(normalized) or normalized
    subject = _normalize_title_subject(compressed) or compressed
    return subject


def _merge_page_summary_and_section_capabilities(
    page_summary: list[str],
    section_main_requirements: list[str],
    limit: int,
) -> list[str]:
    result: list[str] = []
    seen_subjects: set[str] = set()

    for item in page_summary:
        normalized = str(item).strip()
        if not normalized:
            continue
        subject = _capability_subject_key(normalized)
        if subject in seen_subjects:
            continue
        seen_subjects.add(subject)
        result.append(normalized)
        if len(result) >= limit:
            return result

    for item in section_main_requirements:
        normalized = str(item).strip()
        if not normalized:
            continue
        compressed = _compress_capability_clause(normalized) or normalized
        subject = _capability_subject_key(compressed)
        if subject in seen_subjects:
            continue
        seen_subjects.add(subject)
        result.append(compressed)
        if len(result) >= limit:
            break

    return result


def _looks_like_page_level_capability_summary(text: str) -> bool:
    normalized = text.strip().rstrip("：:")
    if not normalized:
        return False
    compressed = _compress_capability_clause(normalized)
    if compressed and len(compressed) >= 6 and (
        _starts_with_strong_action_prefix(compressed) or _contains_action_keyword(compressed)
    ):
        return True
    if _looks_like_explanatory_rule_candidate(normalized) and not _starts_with_strong_action_prefix(normalized):
        return False
    if normalized.startswith(("客户", "用户", "目前", "当前", "为了", "需要")) and not any(
        keyword in normalized for keyword in ("支持", "新增", "增强", "改造", "引入", "适配", "优化", "提供")
    ):
        return False
    if len(normalized) >= 48 and any(mark in normalized for mark in ("，", "。", "；", ";")) and not any(
        keyword in normalized for keyword in ("支持", "新增", "增强", "改造", "引入", "适配", "优化", "提供")
    ):
        return False
    return any(keyword in normalized for keyword in ("支持", "新增", "增强", "改造", "引入", "适配", "优化", "提供"))


def _is_low_value_page_supporting_requirement(
    item: str,
    page_main_requirements: list[str],
    section_titles: set[str],
    section_main_requirements: set[str],
) -> bool:
    normalized = str(item).strip().rstrip("：:")
    if not normalized:
        return True

    subject = _capability_subject_key(normalized)
    page_main_subjects = {_capability_subject_key(entry) for entry in page_main_requirements if str(entry).strip()}
    section_main_subjects = {_capability_subject_key(entry) for entry in section_main_requirements if str(entry).strip()}
    section_title_subjects = {_capability_subject_key(entry) for entry in section_titles if str(entry).strip()}

    if subject in page_main_subjects or subject in section_main_subjects or subject in section_title_subjects:
        return True

    if normalized in {"新增字段", "字段新增"}:
        return True

    if (
        len(normalized) <= 10
        and any(keyword in normalized for keyword in ("图标", "字段", "配置", "查询", "模板"))
        and not _starts_with_supporting_action_prefix(normalized)
        and not _starts_with_strong_action_prefix(normalized)
    ):
        return True

    return False


def _looks_like_explanatory_section_title(title: str) -> bool:
    normalized = title.strip().rstrip("：:")
    if not normalized:
        return False
    if len(normalized) >= 24 and any(mark in normalized for mark in ("，", "。", "；", ";")):
        return True
    return _looks_like_explanatory_rule_candidate(normalized) and not _starts_with_strong_action_prefix(normalized)


def _looks_like_configuration_extension_detail(line: str) -> bool:
    normalized = line.strip().rstrip("：:")
    if not normalized:
        return False
    if not normalized.startswith("新增"):
        return False
    if not any(keyword in normalized for keyword in ("字段", "筛选", "标识", "类型", "默认值", "图标")):
        return False
    if any(mark in normalized for mark in ("，", "。", "；", "：", ":")):
        return True
    return len(normalized) <= 12


def _should_merge_built_sections(previous: dict[str, object], current: dict[str, object]) -> bool:
    previous_title = str(previous.get("title", "")).strip()
    current_title = str(current.get("title", "")).strip()
    if not previous_title or not current_title:
        return False
    if str(previous.get("kind", "")) != str(current.get("kind", "")):
        return False

    previous_body = _normalize_title_subject(previous_title)
    current_body = _normalize_title_subject(current_title)
    overlap = _title_bigram_tokens(previous_title) & _title_bigram_tokens(current_title)

    if previous_body == current_body:
        return True

    if (
        (previous_body and previous_body in current_body) or (current_body and current_body in previous_body)
    ) and len(overlap) >= 3:
        return True

    if len(overlap) >= 5 and (
        _looks_like_explanatory_section_title(current_title)
        or _looks_like_explanatory_section_title(previous_title)
        or _looks_like_low_quality_numbered_title(str(current.get("rawTitle", current_title)))
    ):
        return True

    current_raw_title = str(current.get("rawTitle", current_title))
    if len(overlap) >= 3 and (
        _looks_like_low_quality_numbered_title(current_raw_title)
        or _looks_like_repeated_suffix_noise(current_raw_title)
    ):
        return True

    return False


def _merge_section_payloads(sections: list[dict[str, object]]) -> list[dict[str, object]]:
    if len(sections) < 2:
        return sections

    merged: list[dict[str, object]] = []
    for section in sections:
        if merged and _should_merge_built_sections(merged[-1], section):
            target = merged[-1]
            for field in (
                "mainRequirements",
                "supportingRequirements",
                "rulesAndConstraints",
                "exampleDisplay",
                "summary",
                "evidenceLines",
            ):
                target[field] = _dedupe_keep_order(
                    [*target.get(field, []), *section.get(field, [])], 12 if field == "evidenceLines" else 6
                )
            if section.get("confidenceNote") and not target.get("confidenceNote"):
                target["confidenceNote"] = section["confidenceNote"]
            if section.get("readingHint") and not target.get("readingHint"):
                target["readingHint"] = section["readingHint"]
            if section.get("rawTitle"):
                raw_titles = [str(target.get("rawTitle", "")).strip(), str(section.get("rawTitle", "")).strip()]
                raw_titles = [item for item in raw_titles if item]
                if raw_titles:
                    target["rawTitle"] = " / ".join(_dedupe_keep_order(raw_titles, 2))
            continue
        merged.append(section)

    return merged


def _infer_section_capability_from_title(
    title: str,
    supporting_requirements: list[str],
    rules: list[str],
) -> str | None:
    normalized = title.strip().rstrip("：:")
    if _looks_like_generic_intro_heading(normalized):
        return None
    rewritten = _rewrite_title_as_capability(normalized)
    if rewritten:
        return rewritten

    if normalized.endswith("主任务流程"):
        return f"支持完成{normalized.replace('主任务流程', '').strip() or normalized}的核心流程"
    if normalized.startswith("选择") and any(keyword in " ".join(supporting_requirements + rules) for keyword in ("搜索", "模糊匹配", "展示", "排序", "信息")):
        return f"支持{normalized}，并提供相关信息展示或配置能力"
    if normalized.startswith("选择"):
        return f"支持{normalized}"
    if normalized.startswith("添加") and "/" in normalized:
        return f"支持配置{normalized.replace('添加', '', 1).strip()}"
    if normalized.startswith("下载") and "sql" in normalized.lower():
        return "支持下载查询结果并查看查询 SQL"
    if normalized.startswith("保存为"):
        return f"支持{normalized}"
    if normalized.startswith("另存为"):
        return f"支持{normalized}"
    if normalized.startswith("从") and "跳转" in normalized:
        return f"支持{normalized}"
    if normalized.startswith("新增【") and normalized.endswith("】"):
        inner = normalized.strip("【】").replace("新增", "", 1).strip("【】 ")
        if any(keyword in inner for keyword in ("日期", "时间", "方式", "权限")):
            return f"支持设置{inner}"
        return f"支持配置{inner}"
    if normalized.endswith("访问授权"):
        return f"支持{normalized}"
    if normalized.endswith("使用样式区分"):
        return "支持按不同字段类型区分展示样式"
    if _contains_action_keyword(normalized) and len(normalized) >= 8 and not _looks_like_explanatory_rule_candidate(normalized):
        return normalized
    if _starts_with_strong_action_prefix(normalized) and len(normalized) >= 8 and not _looks_like_rule_heavy_line(normalized):
        return normalized
    return None


def _build_section_breakdowns(
    lines: list[str],
    goal_items: set[str],
    page_summary: list[str] | None = None,
    screenshot_recommendation: str | None = None,
    has_screenshot: bool = False,
) -> list[dict[str, object]]:
    visual_sections = _extract_visual_sections(lines)
    if visual_sections:
        sections = visual_sections
        section_kind = "visual"
        visual_reordered = _visual_sections_reordered(visual_sections)
    else:
        sections = _extract_sections(lines)
        section_kind = "numbered"
        visual_reordered = False
    if not sections:
        return []

    summary_mapping = _map_summary_items_to_section_titles(page_summary or [], sections)

    results: list[dict[str, object]] = []
    for section in sections:
        title = str(section.get("title", "")).strip()
        raw_section_lines = [str(item).strip() for item in section.get("lines", []) if str(item).strip()]
        related_modules = [str(item).strip() for item in section.get("relatedModules", []) if str(item).strip()]
        if not title or not raw_section_lines:
            continue

        module_detail_lines = _collect_module_detail_lines(title, lines) if section_kind == "visual" else []

        if section_kind == "visual" and visual_reordered:
            # 当视觉模块的页面顺序和抽取到的正文顺序明显不一致时，
            # 不再把整段正文硬塞给某个模块，避免把公共规则误归到第一个模块。
            # 这种情况下模块内只保留能稳定确认的内容，其余信息交给跨模块部分承接。
            section_lines = [title] + module_detail_lines
        else:
            section_lines = raw_section_lines

        main_requirements = _extract_feature_points(section_lines, goal_items)
        supporting_requirements = _extract_supporting_requirements(section_lines, main_requirements, goal_items)
        excluded_items = set(goal_items) | {title} | set(main_requirements) | set(supporting_requirements)
        example_display = _extract_example_display(section_lines, excluded_items)
        excluded_items |= set(example_display)
        rules = _extract_rules(section_lines, excluded_items)
        # 一些句子虽然会被 supporting 规则命中，但本质更像“配置约束/系统行为说明”，
        # 对 AI 理解来说，把它们放到规则里比放在配套能力里更稳。
        supporting_rule_like = [
            item
            for item in supporting_requirements
            if _looks_like_explanatory_rule_candidate(item) or _looks_like_configuration_extension_detail(item)
        ]
        if supporting_rule_like:
            rules = _dedupe_keep_order(rules + supporting_rule_like, 10)
            supporting_requirements = [item for item in supporting_requirements if item not in supporting_rule_like]
        supporting_requirements = [
            item
            for item in supporting_requirements
            if not _is_low_information_supporting_item(item, title, main_requirements)
        ]
        supporting_requirements = [item for item in supporting_requirements if item != title]
        main_requirements = [item for item in main_requirements if item != title]
        inferred_capability = _infer_section_capability_from_title(title, supporting_requirements, rules)
        if inferred_capability and inferred_capability not in main_requirements:
            if not main_requirements:
                main_requirements = [inferred_capability]
            elif (
                len(main_requirements[0]) < 8
                or _looks_like_low_quality_capability_phrase(main_requirements[0])
                or _looks_like_explanatory_section_title(main_requirements[0])
            ) and len(inferred_capability) >= 6:
                main_requirements = [
                    inferred_capability,
                    *[
                        item
                        for item in main_requirements
                        if item != inferred_capability and not _looks_like_low_quality_capability_phrase(item)
                    ],
                ]
        if section_kind == "visual" and visual_reordered:
            # 强视觉页面里，页头摘要和模块正文往往不是顺序一一对应的；
            # 即便某一条摘要“看起来像”属于某个模块，也很容易误导读者。
            # 这里统一把摘要留在页头，不再强挂到模块下，保证导读结构稳定。
            mapped_summary = []
        else:
            mapped_summary = _fallback_summary_for_section(
                title,
                page_summary or [],
                section,
                summary_mapping.get(title, []),
                allow_order_fallback=not (section_kind == "visual" and visual_reordered),
            )
        if not main_requirements and mapped_summary:
            mapped_capability = mapped_summary[0]
            if not _looks_like_explanatory_rule_candidate(mapped_capability):
                main_requirements = [mapped_capability]
        section_demands = _build_section_summary(
            title,
            mapped_summary,
            main_requirements,
            supporting_requirements,
            rules,
            example_display,
        )
        section_note = None
        if not main_requirements and not supporting_requirements and not rules and not example_display:
            if has_screenshot or screenshot_recommendation in {"optional", "recommended"}:
                section_note = "该小节在页面中有明确模块展示，但当前可抽取文本较少，建议结合截图核对具体配置和展示效果。"
        elif section_kind == "visual" and visual_reordered and (has_screenshot or screenshot_recommendation in {"optional", "recommended"}):
            section_note = "该模块的详细规则可能与其他模块共用；当前结果仅保留可稳定归属的内容，其余信息已下沉到跨模块补充中。"

        section_scope_note = None
        if section_kind == "visual":
            # 强视觉页面更适合先把“这个模块在页面里是什么”讲清楚，再决定能否稳定归属正文细节。
            # 这里不补业务脑补，只给出保守的阅读提示，帮助读者按页面顺序理解各模块。
            if "指标卡" in title:
                section_scope_note = "该模块对应页面中的指标卡展示区域及相关配置入口，阅读时可重点关注卡片展示效果、对比指标入口和与查询条件的相对位置。"
            elif any(keyword in title for keyword in ("折线图", "柱状图", "饼图")):
                section_scope_note = "该模块对应图表类组件的展示区域及配置效果，阅读时可重点关注图表展示、横轴/分组效果和对比指标配置结果。"
            elif "表格" in title:
                section_scope_note = "该模块对应表格类组件的展示区域及配置效果，阅读时可重点关注表格展示规则、查询值与展示样式的对应关系。"

        evidence_lines = _dedupe_keep_order(
            mapped_summary + related_modules + module_detail_lines + main_requirements + supporting_requirements,
            12,
        )
        display_title = _choose_section_display_title(title, main_requirements, section_demands)
        section_payload = {
            "title": display_title,
            "mainRequirements": _normalize_capability_list(main_requirements, 3),
            "supportingRequirements": _dedupe_keep_order(supporting_requirements, 4),
            "rulesAndConstraints": rules,
            "exampleDisplay": example_display,
        }
        if display_title != title:
            section_payload["rawTitle"] = title
        if section_demands:
            section_payload["summary"] = section_demands
        if evidence_lines:
            section_payload["evidenceLines"] = evidence_lines
        if section_scope_note:
            section_payload["readingHint"] = section_scope_note
        if section_note:
            section_payload["confidenceNote"] = section_note
        cleaned_section_payload = _prune_empty_values(section_payload)
        for stable_key in ("mainRequirements", "supportingRequirements", "rulesAndConstraints", "exampleDisplay"):
            if stable_key not in cleaned_section_payload:
                cleaned_section_payload[stable_key] = []
        results.append(cleaned_section_payload)
    return _merge_section_payloads(results)


def _screenshot_note_for(page: dict[str, object]) -> str | None:
    recommendation = page.get("screenshotRecommendation")
    if page.get("screenshotPath") and recommendation == "none" and not page.get("needsScreenshot"):
        return "本页已保留截图，可按需核对界面细节或补充正文未完全表达的视觉信息。"
    if recommendation == "recommended" or page.get("needsScreenshot"):
        return "建议结合截图核对视觉关系、布局指向或图片标注。"
    if recommendation == "optional":
        return "可按需结合截图核对交互布局或图示细节。"
    return None


def _visual_review_focus_for(page: dict[str, object], lines: list[str], issues: list[dict[str, object]]) -> list[str]:
    recommendation = page.get("screenshotRecommendation")
    has_screenshot = bool(page.get("screenshotPath"))
    if recommendation == "none" and not page.get("needsScreenshot") and not has_screenshot:
        return []

    label = str(page.get("label", ""))
    focuses: list[str] = []
    raw_text = "\n".join(lines)

    if any(keyword in raw_text for keyword in ("如下图", "见下图", "红框", "箭头", "圈选", "示意")):
        focuses.append("核对图中标注、红框、箭头或示意区域与正文描述是否一一对应。")

    if any(keyword in label for keyword in ("弹窗", "配置", "指标卡", "表格", "交叉表", "图", "布局")):
        focuses.append("核对页面布局、组件分区和配置项位置关系，避免只靠文本误判界面结构。")

    if any(issue.get("type") == "conditional_behavior" for issue in issues):
        focuses.append("核对条件分支触发后的界面展示差异，例如显示、隐藏、默认值或跳转结果。")

    if any(line.startswith("*") for line in lines):
        focuses.append("核对配置项分组、顺序和从属关系，尤其是短文本表单项是否依赖界面语境。")

    if not focuses:
        focuses.append("核对截图中的视觉关系和正文是否一致，重点关注文本无法表达的布局与指向信息。")

    return _dedupe_keep_order(focuses, 3)


def _visual_observations_for(page: dict[str, object], lines: list[str], issues: list[dict[str, object]]) -> list[str]:
    recommendation = page.get("screenshotRecommendation")
    has_screenshot = bool(page.get("screenshotPath"))
    if recommendation not in {"optional", "recommended"} and not page.get("needsScreenshot") and not has_screenshot:
        return []

    label = str(page.get("label", ""))
    observations: list[str] = []

    if any(line.startswith("*") for line in lines):
        observations.append("页面包含较多短文本配置项，界面分组与字段从属关系可能无法仅靠正文完整表达。")

    if any(issue.get("type") == "conditional_behavior" for issue in issues):
        observations.append("页面存在条件分支规则，最终展示效果可能需要结合界面状态变化一起理解。")

    if any(keyword in label for keyword in ("弹窗", "配置", "指标卡", "布局", "图", "表格")):
        observations.append("本页需求不仅是字段清单，还包含组件布局、配置入口或展示区域之间的视觉关系。")

    if not observations and recommendation == "recommended":
        observations.append("本页视觉信息占比高，截图更适合补充正文未表达完整的界面指向与交互关系。")
    elif not observations and has_screenshot:
        observations.append("本页已保留截图，可在需要时补充核对界面布局、字段位置或示例展示。")

    return _dedupe_keep_order(observations, 2)


def _example_display_visual_note_for(page: dict[str, object]) -> str | None:
    example_display = page.get("exampleDisplay") or []
    recommendation = page.get("screenshotRecommendation")
    if not example_display:
        return None
    if recommendation in {"optional", "recommended"} or page.get("screenshotPath") or len(example_display) >= 3:
        return "本页包含较多示例配置或展示口径，建议结合截图核对这些示例项在界面中的展示方式和归属位置。"
    return None


def _build_visual_signals(
    page: dict[str, object],
    lines: list[str],
    suspected_issues: list[dict[str, object]],
    *,
    risk_level: str,
    needs_screenshot: bool,
    screenshot_recommendation: str,
    example_display: list[str],
) -> dict[str, object]:
    enriched_page = dict(page)
    enriched_page["riskLevel"] = risk_level
    enriched_page["needsScreenshot"] = needs_screenshot
    enriched_page["screenshotRecommendation"] = screenshot_recommendation

    result = {
        "riskLevel": risk_level,
        "needsScreenshot": needs_screenshot,
        "screenshotRecommendation": screenshot_recommendation,
    }
    if page.get("screenshotPath"):
        result["screenshotPath"] = page.get("screenshotPath")

    screenshot_note = _screenshot_note_for(enriched_page)
    if screenshot_note:
        result["note"] = screenshot_note

    visual_review_focus = _visual_review_focus_for(enriched_page, lines, suspected_issues)
    if visual_review_focus:
        result["reviewFocus"] = visual_review_focus

    visual_observations = _visual_observations_for(enriched_page, lines, suspected_issues)
    if visual_observations:
        result["observations"] = visual_observations

    example_display_visual_note = _example_display_visual_note_for({**enriched_page, "exampleDisplay": example_display})
    if example_display_visual_note:
        result["exampleDisplayNote"] = example_display_visual_note

    return result


def _build_semantic_signals(
    page: dict[str, object],
    *,
    lines: list[str],
    sections: list[dict[str, object]],
) -> dict[str, object] | None:
    def _looks_like_low_information_control_name(name: str) -> bool:
        normalized = str(name).strip()
        if not normalized:
            return True
        lowered = normalized.lower()
        if lowered in {"radio", "checkbox", "button", "link", "textbox", "combobox"}:
            return True
        if DATE_GENERIC_RE.fullmatch(normalized):
            return True
        if QUARTER_RE.fullmatch(normalized):
            return True
        if normalized in {"指标名称", "日期", "时间", "名称"}:
            return True
        return False

    semantic_snapshot = page.get("semanticSnapshot")
    if not isinstance(semantic_snapshot, dict):
        semantic_snapshot = {"available": False, "headings": [], "controls": [], "tableLike": []}

    headings = [
        str(item.get("name", "")).strip()
        for item in semantic_snapshot.get("headings", [])
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    controls = []
    for item in semantic_snapshot.get("controls", []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        lowered = name.lower()
        if lowered in {"radio", "checkbox", "button", "link", "textbox", "combobox"}:
            continue
        if role and lowered == role.lower():
            continue
        controls.append(item)
    table_like = [
        str(item.get("name", "") or item.get("role", "")).strip()
        for item in semantic_snapshot.get("tableLike", [])
        if isinstance(item, dict) and str(item.get("name", "") or item.get("role", "")).strip()
    ]

    control_roles = _dedupe_keep_order(
        [str(item.get("role", "")).strip() for item in controls if str(item.get("role", "")).strip()],
        6,
    )
    control_summary: list[str] = []
    for item in controls[:6]:
        role = str(item.get("role", "")).strip()
        name = str(item.get("name", "")).strip()
        if not role or not name:
            continue
        if role in {"button", "link"}:
            control_summary.append(f"可见{role}：{name}")
        elif role in {"combobox", "textbox", "searchbox"}:
            control_summary.append(f"可配置输入项：{name}")
        elif role in {"checkbox", "radio", "switch"}:
            control_summary.append(f"可切换控件：{name}")
        elif role in {"tab", "tablist"}:
            control_summary.append(f"可切换页签：{name}")
        else:
            control_summary.append(f"{role}：{name}")

    result: dict[str, object] = {}
    if semantic_snapshot.get("available"):
        result["source"] = str(semantic_snapshot.get("source") or "semantic")
    if headings:
        result["headings"] = _dedupe_keep_order(headings, 8)
    if control_roles:
        result["controlRoles"] = control_roles
    if control_summary:
        result["controlSummary"] = _dedupe_keep_order(control_summary, 6)
    if table_like:
        result["tableLike"] = _dedupe_keep_order(table_like, 6)

    observations: list[str] = []
    if any(role in {"combobox", "textbox", "searchbox", "checkbox", "radio", "switch"} for role in control_roles):
        observations.append("页面包含可配置控件，需求不只是静态文案，还涉及选项、输入或切换状态。")
    if table_like:
        observations.append("页面存在表格或类表格结构，理解规则时要注意列、表头或分组关系。")
    if headings and not controls:
        observations.append("页面语义标题较明确，但交互控件较少，当前内容更偏说明和展示。")
    if observations:
        result["observations"] = _dedupe_keep_order(observations, 3)

    # Modao 这类页面经常是静态导出页，原生 DOM 控件语义很弱。
    # 当 a11y / DOM 语义层抽不到明显控件时，退回到页面结构语义，
    # 至少给后续模型一个“这是流程页、配置页、还是模板/结果页”的稳定提示。
    low_information_flags = [
        _looks_like_low_information_control_name(str(item.split("：", 1)[-1]).strip())
        for item in control_summary
    ]
    low_information_controls = not control_summary or all(low_information_flags)
    mostly_low_information_controls = bool(control_summary) and sum(1 for item in low_information_flags if item) >= max(1, len(low_information_flags) - 1)
    if (low_information_controls and not table_like) or (len(control_summary) <= 2 and len(sections) >= 3):
        if not low_information_controls and not mostly_low_information_controls and table_like:
            return result or None
        section_titles = [str(section.get("title", "")).strip() for section in sections if str(section.get("title", "")).strip()]
        action_patterns: list[str] = []
        for section in sections:
            main_requirements = [str(item).strip() for item in section.get("mainRequirements", []) if str(item).strip()]
            if main_requirements:
                action_patterns.append(main_requirements[0])
        if action_patterns:
            interaction_patterns = _merge_outline_labels(
                [
                    _compress_outline_label(_compress_capability_clause(item) or item)
                    for item in action_patterns
                    if str(item).strip()
                ],
                6,
            )
            if interaction_patterns:
                result["interactionPatterns"] = interaction_patterns

        data_concepts: list[str] = []
        source_texts = list(lines)
        for section in sections:
            source_texts.extend(
                str(item).strip()
                for item in section.get("summary", [])
                if str(item).strip()
            )
            source_texts.extend(
                str(item).strip()
                for field in ("mainRequirements", "supportingRequirements", "rulesAndConstraints")
                for item in section.get(field, [])
                if str(item).strip()
            )
        joined_text = "\n".join(source_texts)

        def add_concept(summary: str, *keyword_groups: tuple[str, ...] | str) -> None:
            groups: list[tuple[str, ...]] = []
            for group in keyword_groups:
                if isinstance(group, str):
                    groups.append((group,))
                else:
                    groups.append(tuple(group))
            for group in groups:
                if all(token in joined_text for token in group):
                    data_concepts.append(summary)
                    return

        add_concept("涉及看板级公共维度筛选", ("全局筛选",), ("公共维度",))
        add_concept("涉及字段选择与展示", ("选择字段",), ("字段范围",), ("字段描述",))
        add_concept("涉及数据模型选择与模型约束", ("数据模型",), ("模型状态",))
        add_concept("涉及筛选与排序配置", ("筛选条件", "排序规则"))
        add_concept("涉及筛选条件配置", "筛选条件")
        add_concept("涉及排序规则配置", "排序规则")
        add_concept("涉及明细查询方式切换", ("查询方式", "明细查询"), ("切换到明细查询方式",))
        add_concept("涉及 SQL 查看或查询语句确认", "SQL")
        add_concept("涉及取数模板保存、导入与复用", ("取数模板", "导入"), ("取数模板", "保存"), ("取数模板", "复用"))
        add_concept("涉及模型基准日期处理", "模型基准日期")
        add_concept("涉及表格组件配置与展示", ("表格组件",), ("表格", "组件"))
        add_concept("涉及结果导出或下载", ("下载",), ("导出",))
        if "涉及筛选与排序配置" in data_concepts:
            data_concepts = [
                item
                for item in data_concepts
                if item not in {"涉及筛选条件配置", "涉及排序规则配置"}
            ]
        if data_concepts:
            result["dataConcepts"] = _dedupe_keep_order(data_concepts, 6)

        if section_titles or data_concepts:
            if semantic_snapshot.get("available") and (control_summary or table_like):
                result["source"] = "hybrid"
            else:
                result["source"] = "derived"
            derived_observations = list(result.get("observations", []))
            if result["source"] == "hybrid":
                derived_observations.append("页面已结合弱控件语义与结构语义共同表达需求，后续理解时应优先看 interactionPatterns 与 dataConcepts。")
            else:
                derived_observations.append("页面原生控件语义较弱，当前更多依赖流程块、配置块和规则块来表达需求。")
            if any("流程" in title for title in section_titles):
                derived_observations.append("页面包含明显流程步骤，理解时应按任务流程和配置节点一起阅读。")
            result["observations"] = _dedupe_keep_order(derived_observations, 4)

    return result or None


def _looks_like_outline_noise_label(text: str) -> bool:
    normalized = str(text).strip().rstrip("：:")
    if not normalized:
        return True
    if _is_noise_line(normalized):
        return True
    if _looks_like_field_label(normalized):
        return True
    if NUMERIC_LINE_RE.fullmatch(normalized):
        return True
    if NUMERIC_UNIT_RE.fullmatch(normalized):
        return True
    if DATE_YYYY_MM_RE.fullmatch(normalized) or DATE_YYYY_MM_DD_RE.fullmatch(normalized) or DATE_GENERIC_RE.fullmatch(normalized):
        return True
    if QUARTER_RE.fullmatch(normalized):
        return True
    if len(normalized) <= 4 and any(ch.isdigit() for ch in normalized):
        return True
    if _looks_like_low_quality_block_title(normalized) or _looks_like_low_quality_numbered_title(normalized):
        return True
    return False


def _choose_outline_section_label(section: dict[str, object]) -> str | None:
    title = str(section.get("title", "")).strip().rstrip("：:")
    raw_title = str(section.get("rawTitle", "")).strip().rstrip("：:")
    summary_items = [str(item).strip() for item in section.get("summary", []) if str(item).strip()]
    main_requirements = [str(item).strip() for item in section.get("mainRequirements", []) if str(item).strip()]

    candidates: list[str] = []
    for item in (title, raw_title):
        if item and not _looks_like_outline_noise_label(item):
            candidates.append(item)
    if summary_items:
        candidates.append(_compress_capability_clause(summary_items[0]) or summary_items[0])
    if main_requirements:
        candidates.append(_compress_capability_clause(main_requirements[0]) or main_requirements[0])

    for item in candidates:
        normalized = str(item).strip().rstrip("：:")
        if not normalized:
            continue
        if _looks_like_outline_noise_label(normalized) and not (
            len(normalized) >= 6 and (_starts_with_action_prefix(normalized) or _contains_action_keyword(normalized))
        ):
            continue
        return normalized
    return None


def _compress_outline_label(label: str) -> str:
    normalized = str(label).strip().rstrip("：:")
    if not normalized:
        return normalized
    if normalized.startswith("支持完成") and normalized.endswith("的核心流程"):
        inner = normalized[len("支持完成") : -len("的核心流程")].strip()
        if inner:
            return f"{inner}主流程"
    if normalized.startswith("支持选择"):
        inner = normalized[len("支持选择") :].strip()
        if "并" in inner:
            inner = inner.split("并", 1)[0].strip()
        if inner:
            return f"{inner}选择"
    if normalized.startswith("选择"):
        inner = normalized[len("选择") :].strip()
        if "并" in inner:
            inner = inner.split("并", 1)[0].strip()
        if inner:
            return f"{inner}选择"
    if normalized.startswith("支持配置添加"):
        inner = normalized[len("支持配置添加") :].strip()
        if inner:
            return f"{inner}配置"
    if normalized.startswith("支持配置"):
        inner = normalized[len("支持配置") :].strip()
        if inner:
            return f"{inner}配置"
    if normalized.startswith("支持设置"):
        inner = normalized[len("支持设置") :].strip()
        if inner:
            return f"{inner}设置"
    if normalized.startswith("支持下载") and "SQL" in normalized.upper():
        return "结果下载与 SQL 查看"
    if normalized.startswith("支持保存为"):
        inner = normalized[len("支持") :].strip()
        return inner or normalized
    if normalized.startswith("支持查看") and "SQL" in normalized.upper():
        return "SQL 查看与结果下载"
    if normalized.startswith("支持明细查询访问授权"):
        return "明细查询访问授权"
    if normalized.startswith("支持") and len(normalized) <= 14:
        stripped = normalized[len("支持") :].strip()
        if stripped:
            return stripped
    return normalized


def _merge_outline_labels(labels: list[str], limit: int) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(labels):
        current = str(labels[index]).strip()
        if index + 1 < len(labels):
            nxt = str(labels[index + 1]).strip()
            for suffix in ("选择", "配置"):
                if current.endswith(suffix) and nxt.endswith(suffix):
                    left = current[: -len(suffix)].strip()
                    right = nxt[: -len(suffix)].strip()
                    if left and right and len(left) <= 8 and len(right) <= 8:
                        merged.append(f"{left}与{right}{suffix}")
                        index += 2
                        break
            else:
                merged.append(current)
                index += 1
                continue
            continue
        merged.append(current)
        index += 1
    return _dedupe_keep_order(merged, limit)


def _merge_adjacent_page_capabilities(items: list[str], limit: int) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(items):
        current = str(items[index]).strip()
        if index + 1 < len(items):
            nxt = str(items[index + 1]).strip()
            if current.startswith("支持选择") and nxt.startswith("支持选择"):
                left = current[len("支持选择") :].strip()
                right = nxt[len("支持选择") :].strip()
                if left and right and len(left) <= 8 and len(right) <= 8:
                    merged.append(f"支持选择{left}与{right}")
                    index += 2
                    continue
        merged.append(current)
        index += 1
    return _dedupe_keep_order(merged, limit)


def _build_understanding_outline(
    *,
    goal: list[str],
    page_summary: list[str],
    sections: list[dict[str, object]],
    global_rules: list[str],
    suspected_issues: list[dict[str, object]],
    visual_signals: dict[str, object],
) -> list[str]:
    outline: list[str] = []

    if goal:
        outline.append(f"这页的核心目标是：{goal[0]}")
    elif page_summary:
        outline.append(f"这页主要在讲：{page_summary[0]}")

    if sections:
        section_labels = _dedupe_keep_order(
            [
                _compress_outline_label(label)
                for label in (_choose_outline_section_label(section) for section in sections)
                if label
            ],
            4,
        )
        if section_labels:
            section_labels = _merge_outline_labels(section_labels, 4)
            joined = "、".join(section_labels[:4])
            outline.append(f"页面主要分为这些部分：{joined}")

    if global_rules:
        outline.append(f"全局规则重点：{global_rules[0]}")

    if suspected_issues:
        outline.append("这页存在需要额外确认的内容，后续理解时应保留疑点。")

    recommendation = visual_signals.get("screenshotRecommendation")
    if recommendation in {"optional", "recommended"}:
        outline.append(f"视觉信息建议：{recommendation}，必要时结合截图理解页面结构和示例口径。")

    return _dedupe_keep_order(outline, 4)


def _score_evidence_line_relevance(item: str, line: str) -> int:
    item_normalized = str(item).strip().rstrip("：:")
    line_normalized = str(line).strip().rstrip("：:")
    if not item_normalized or not line_normalized:
        return 0

    if item_normalized == line_normalized:
        return 100

    item_subject = _normalize_title_subject(item_normalized) or item_normalized
    line_subject = _normalize_title_subject(line_normalized) or line_normalized

    if item_subject and line_subject and item_subject == line_subject:
        return 90

    if item_subject and item_subject in line_normalized:
        return 80
    if line_subject and line_subject in item_normalized:
        return 70

    item_tokens = _title_bigram_tokens(item_subject)
    line_tokens = _title_bigram_tokens(line_subject)
    overlap = len(item_tokens & line_tokens)
    if overlap >= 2:
        return overlap * 10

    return 0


def _select_local_evidence_lines(item: str, field: str, evidence_lines: list[str]) -> list[str]:
    normalized_item = str(item).strip()
    if not normalized_item:
        return []

    ranked: list[tuple[int, str]] = []
    for line in evidence_lines:
        normalized_line = str(line).strip()
        if not normalized_line:
            continue
        score = _score_evidence_line_relevance(normalized_item, normalized_line)
        if score > 0:
            ranked.append((score, normalized_line))

    ranked.sort(key=lambda entry: (-entry[0], len(entry[1])))
    local = _dedupe_keep_order([line for _, line in ranked], 3)

    if field in {"rulesAndConstraints", "exampleDisplay"}:
        return _dedupe_keep_order([normalized_item] + local, 3)

    if local:
        return local

    return [normalized_item]


def _build_requirement_evidence_index(sections: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    index: dict[str, dict[str, object]] = {}
    for section in sections:
        title = str(section.get("title", "")).strip()
        raw_title = str(section.get("rawTitle", "")).strip()
        evidence_lines = [str(item).strip() for item in section.get("evidenceLines", []) if str(item).strip()]
        source_titles = [item for item in (title, raw_title) if item]
        field_values: list[tuple[str, str]] = []
        for field in ("mainRequirements", "supportingRequirements", "rulesAndConstraints", "exampleDisplay", "summary"):
            field_values.extend(
                (field, str(item).strip()) for item in section.get(field, []) if str(item).strip()
            )
        for field, item in field_values:
            payload = index.setdefault(item, {"fromSections": [], "evidenceLines": []})
            payload["fromSections"] = _dedupe_keep_order(payload["fromSections"] + source_titles, 4)
            local_evidence = _select_local_evidence_lines(item, field, evidence_lines)
            payload["evidenceLines"] = _dedupe_keep_order(payload["evidenceLines"] + local_evidence, 6)
    return index


def _collect_evidence_references(items: list[str], evidence_index: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    references: list[dict[str, object]] = []
    for item in items:
        normalized = str(item).strip()
        if not normalized:
            continue
        evidence = evidence_index.get(normalized)
        if not evidence:
            matched_payloads: list[dict[str, object]] = []
            for candidate, payload in evidence_index.items():
                if normalized in candidate or candidate in normalized:
                    matched_payloads.append(payload)
            if matched_payloads:
                merged_sections: list[str] = []
                merged_lines: list[str] = []
                for payload in matched_payloads:
                    merged_sections.extend(payload.get("fromSections", []))
                    merged_lines.extend(payload.get("evidenceLines", []))
                evidence = {
                    "fromSections": _dedupe_keep_order(merged_sections, 6),
                    "evidenceLines": _dedupe_keep_order(merged_lines, 6),
                }
        if normalized.startswith("支持选择") and "与" in normalized:
            body = normalized[len("支持选择") :].strip()
            parts = [part.strip() for part in body.split("与") if part.strip()]
            if len(parts) >= 2:
                matched_payloads = []
                for part in parts:
                    for candidate, payload in evidence_index.items():
                        if candidate == f"支持选择{part}" or candidate == part:
                            matched_payloads.append(payload)
                if matched_payloads:
                    merged_sections: list[str] = []
                    merged_lines: list[str] = []
                    if evidence:
                        merged_sections.extend(evidence.get("fromSections", []))
                        merged_lines.extend(evidence.get("evidenceLines", []))
                    for payload in matched_payloads:
                        merged_sections.extend(payload.get("fromSections", []))
                        merged_lines.extend(payload.get("evidenceLines", []))
                    evidence = {
                        "fromSections": _dedupe_keep_order(merged_sections, 6),
                        "evidenceLines": _dedupe_keep_order(merged_lines, 6),
                    }
        reference = {"item": normalized}
        if evidence:
            if evidence.get("fromSections"):
                reference["fromSections"] = evidence["fromSections"]
            if evidence.get("evidenceLines"):
                reference["evidenceLines"] = evidence["evidenceLines"][:3]
        references.append(reference)
    return references


def build_breakdown(pages: list[dict[str, object]]) -> dict[str, object]:
    if not pages:
        return {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "pageCount": 0,
            "pages": [],
        }

    pages_out: list[dict[str, object]] = []

    for page in pages:
        lines = _clean_lines(page)
        suspected_issues = page.get("suspectedIssues", []) or []
        # 旧 pages.json 可能缺少新版本的风险字段；这里统一按当前规则重算一遍，
        # 这样重渲染历史产物时也能吃到最新的截图建议和图文核对逻辑。
        risk_payload = page_risk_parser.assess_page_risk(str(page.get("label") or ""), page)
        risk_level = page.get("riskLevel") or risk_payload["riskLevel"]
        needs_screenshot = page.get("needsScreenshot")
        if needs_screenshot is None:
            needs_screenshot = risk_payload["needsScreenshot"]
        screenshot_recommendation = page.get("screenshotRecommendation") or risk_payload["screenshotRecommendation"]
        goal = _extract_goal(lines)
        goal_set = set(goal)
        page_summary = _extract_page_summary(lines)
        section_breakdowns = _build_section_breakdowns(
            lines,
            goal_set,
            page_summary=page_summary,
            screenshot_recommendation=screenshot_recommendation,
            has_screenshot=bool(page.get("screenshotPath")),
        )
        main_requirements = _extract_feature_points(lines, goal_set)
        supporting_requirements = _extract_supporting_requirements(lines, main_requirements, goal_set)
        if section_breakdowns:
            section_titles = [str(section.get("title", "")).strip() for section in section_breakdowns if str(section.get("title", "")).strip()]
            section_main_requirements = [
                str(item).strip()
                for section in section_breakdowns
                for item in section.get("mainRequirements", [])
                if str(item).strip()
            ]
            section_identity_titles = {
                str(section.get("title", "")).strip()
                for section in section_breakdowns
                if str(section.get("title", "")).strip()
            }
            section_identity_titles |= {
                str(section.get("rawTitle", "")).strip()
                for section in section_breakdowns
                if str(section.get("rawTitle", "")).strip()
            }
            if section_main_requirements:
                # 页级主需求优先汇总 section 的能力摘要，避免把页头背景句或说明句直接抬成主需求。
                # pageSummary 仍可作为高层概括补充，但只有在不和 section 能力重复时才保留。
                if page_summary and all(_looks_like_page_level_capability_summary(item) for item in page_summary):
                    main_requirements = _dedupe_keep_order(page_summary, 8)
                elif page_summary:
                    main_requirements = _merge_page_summary_and_section_capabilities(
                        page_summary,
                        section_main_requirements,
                        8,
                    )
                else:
                    main_requirements = _dedupe_capability_phrases(section_main_requirements, 8)
            elif page_summary:
                main_requirements = _dedupe_capability_phrases(page_summary, 8)
            else:
                main_requirements = _dedupe_capability_phrases(section_titles + main_requirements, 8)
            main_requirements = _merge_adjacent_page_capabilities(main_requirements, 8)
            supporting_requirements = [
                item
                for item in supporting_requirements
                if item not in section_identity_titles and item not in set(main_requirements)
            ]
        excluded_items = set(goal) | set(main_requirements) | set(supporting_requirements)
        # 示例配置/展示口径单独分组，避免混进主需求/配套需求，导致拆解看起来像页面抄录。
        example_display = _extract_example_display(lines, excluded_items)
        excluded_items |= set(example_display)
        section_rules = {
            item
            for section in section_breakdowns
            for item in section.get("rulesAndConstraints", [])
            if str(item).strip()
        }
        section_examples = {
            item
            for section in section_breakdowns
            for item in section.get("exampleDisplay", [])
            if str(item).strip()
        }
        section_supporting = {
            item
            for section in section_breakdowns
            for item in section.get("supportingRequirements", [])
            if str(item).strip()
        }

        visual_signals = _build_visual_signals(
            page,
            lines,
            suspected_issues,
            risk_level=risk_level,
            needs_screenshot=needs_screenshot,
            screenshot_recommendation=screenshot_recommendation,
            example_display=example_display,
        )

        global_rules = [item for item in _extract_rules(lines, excluded_items) if item not in section_rules]
        if section_breakdowns:
            lifted_rule_like_supporting = [
                item
                for item in supporting_requirements
                if _looks_like_explanatory_rule_candidate(item)
            ]
            if lifted_rule_like_supporting:
                global_rules = _dedupe_keep_order(global_rules + lifted_rule_like_supporting, 10)
                supporting_requirements = [
                    item for item in supporting_requirements if item not in set(lifted_rule_like_supporting)
                ]

        page_out = {
            "label": page.get("label"),
            "path": page.get("path"),
            "pageSummary": page_summary,
            "goal": goal,
            "sections": section_breakdowns,
            "mainRequirements": main_requirements,
            "supportingRequirements": [
                item
                for item in supporting_requirements
                if item not in section_supporting
                and not _is_low_value_page_supporting_requirement(
                    item,
                    main_requirements,
                    section_identity_titles if section_breakdowns else set(),
                    section_main_requirements if section_breakdowns else set(),
                )
            ],
            "globalRules": global_rules,
            "exampleDisplay": [item for item in example_display if item not in section_examples],
            "boundaries": _extract_boundaries(lines, suspected_issues),
            "suspectedIssues": suspected_issues,
            "visualSignals": visual_signals,
            "understandingOutline": _build_understanding_outline(
                goal=goal,
                page_summary=page_summary,
                sections=section_breakdowns,
                global_rules=global_rules,
                suspected_issues=suspected_issues,
                visual_signals=visual_signals,
            ),
        }
        semantic_signals = _build_semantic_signals(
            page,
            lines=lines,
            sections=section_breakdowns,
        )
        if semantic_signals:
            page_out["semanticSignals"] = semantic_signals
        if section_breakdowns and not page_summary:
            section_capabilities = []
            for section in section_breakdowns:
                title = str(section.get("title", "")).strip()
                if not title or _is_ignorable_requirement_line(title) or _looks_like_generic_intro_heading(title):
                    continue
                section_main = [str(item).strip() for item in section.get("mainRequirements", []) if str(item).strip()]
                if section_main:
                    section_capabilities.append(section_main[0])
                    continue
                section_summary = [str(item).strip() for item in section.get("summary", []) if str(item).strip()]
                if section_summary and not _looks_like_explanatory_rule_candidate(section_summary[0]):
                    section_capabilities.append(section_summary[0])
            if section_capabilities:
                if goal and _looks_like_page_level_capability_summary(goal[0]):
                    page_out["mainRequirements"] = [goal[0]]
                else:
                    page_out["mainRequirements"] = _merge_adjacent_page_capabilities(
                        _dedupe_capability_phrases(section_capabilities, 8),
                        8,
                    )

        evidence_index = _build_requirement_evidence_index(section_breakdowns)
        page_out["evidenceReferences"] = {
            "mainRequirements": _collect_evidence_references(page_out["mainRequirements"], evidence_index),
            "supportingRequirements": _collect_evidence_references(page_out["supportingRequirements"], evidence_index),
            "globalRules": _collect_evidence_references(page_out["globalRules"], evidence_index),
        }
        cleaned_page_out = _prune_empty_values(page_out)
        for stable_key in (
            "sections",
            "mainRequirements",
            "supportingRequirements",
            "globalRules",
            "exampleDisplay",
            "suspectedIssues",
        ):
            if stable_key not in cleaned_page_out:
                cleaned_page_out[stable_key] = []
        pages_out.append(cleaned_page_out)

    first_page = pages[0]
    inferred_scope_type = first_page.get("scopeType") or ("page" if len(pages) == 1 else "pages")
    inferred_scope_value = first_page.get("scopeValue") or (
        first_page.get("label") if len(pages) == 1 else f"{len(pages)} pages"
    )
    result = _prune_empty_values({
        "artifactType": "prd-understanding-input",
        "formatVersion": 1,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "sourceUrl": first_page.get("sourceUrl") or first_page.get("url"),
        "scopeType": inferred_scope_type,
        "scopeValue": inferred_scope_value,
        "pageCount": len(pages_out),
        "pages": pages_out,
    })
    for page in result.get("pages", []):
        for stable_key in (
            "sections",
            "mainRequirements",
            "supportingRequirements",
            "globalRules",
            "exampleDisplay",
            "suspectedIssues",
        ):
            if stable_key not in page:
                page[stable_key] = []
        for section in page.get("sections", []):
            for stable_key in ("mainRequirements", "supportingRequirements", "rulesAndConstraints", "exampleDisplay"):
                if stable_key not in section:
                    section[stable_key] = []
    return result


def _build_blocked_breakdown(*, pages_path: Path, message: str) -> dict[str, object]:
    return {
        "artifactType": "prd-understanding-input",
        "formatVersion": 1,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": "blocked",
        "reason": "python_parser_crash",
        "message": message,
        "sourcePath": str(pages_path),
        "pageCount": 0,
        "pages": [],
    }


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        print("Usage: breakdown_exporter.py <pages-json-file> <output-dir> [output-mode]", file=sys.stderr)
        return 1

    pages_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_mode = sys.argv[3] if len(sys.argv) == 4 else "standard"
    understanding_json_path = output_dir / "understanding-input.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        pages = json.loads(pages_path.read_text(encoding="utf-8"))
        breakdown = build_breakdown(pages)
    except Exception as error:
        print(f"breakdown_exporter blocked: {error}", file=sys.stderr)
        blocked = _build_blocked_breakdown(
            pages_path=pages_path,
            message=error.message if hasattr(error, "message") and error.message else str(error),
        )
        understanding_json_path.write_text(
            json.dumps(blocked, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return 0

    # 默认主产物改成 AI 优先消费的结构化 JSON。
    # 这里不再默认落盘面向人阅读的导读文档，避免 skill 重心再次偏向“生成说明文档”。
    understanding_json_path.write_text(
        json.dumps(breakdown, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
