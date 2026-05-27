#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = SCRIPT_DIR.parent / "tests" / "fixtures"

sys.path.insert(0, str(SCRIPT_DIR))

import breakdown_exporter  # noqa: E402
import page_issue_extractor  # noqa: E402
import page_risk_parser  # noqa: E402


FIXTURES = [
    (
        "axhub-15900-page.json",
        {
            "riskLevel": "high",
            "screenshotRecommendation": "recommended",
            "needsScreenshot": True,
        },
    ),
    (
        "axhub-15899-page.json",
        {
            "riskLevel": "medium",
            "screenshotRecommendation": "optional",
            "needsScreenshot": False,
        },
    ),
    (
        "modao-15686-page.json",
        {
            "riskLevel": "low",
            "screenshotRecommendation": "none",
            "needsScreenshot": False,
        },
    ),
]

SYNTHETIC_RISK_CASES = [
    (
        "example-display-risk-escalation",
        {
            "label": "同环比展示页",
            "rawText": "\n".join(
                [
                    "支持同环比结果展示",
                    "查询粒度：月；查询日期：2025-01 至 2025-12",
                    "查询指标：销售额、销售额_年同比增长率",
                    "查询指标：销售额、销售额_环比增长率、销售额_年同比增长率",
                    "查询维度：门店/门店名称",
                ]
            ),
            "lines": [
                "支持同环比结果展示",
                "查询粒度：月；查询日期：2025-01 至 2025-12",
                "查询指标：销售额、销售额_年同比增长率",
                "查询指标：销售额、销售额_环比增长率、销售额_年同比增长率",
                "查询维度：门店/门店名称",
            ],
        },
        {
            "riskLevel": "medium",
            "screenshotRecommendation": "optional",
        },
    ),
]

SYNTHETIC_ISSUE_CASES = [
    (
        "example-query-questions",
        {
            "label": "15452·支持计算同环比数据【已开发】",
            "lines": [
                "今年各月份总销售额走势如何？和去年做一下对比",
                "这个月和去年同期销售额情况如何？",
            ],
        },
        0,
    ),
    (
        "explicit-review-question",
        {
            "label": "示例",
            "lines": [
                "是否展示模型基准日期，需要和模型 SQL 的全局参数能力保持一致？",
            ],
        },
        1,
    ),
]

SYNTHETIC_BREAKDOWN_CASES = [
    (
        "flow-noise-filtering",
        {
            "label": "示例流程页",
            "lines": [
                "需求背景",
                "新增明细查询能力，支持基于数据模型直接查明细结果。",
                "开始",
                "进入明细查询",
                "选择数据模型",
                "生成查询结果",
                "结束",
                "1. 支持保存为取数模板",
                "2. 支持查看 SQL 和下载结果",
                "如果模型未上线，则不能发起明细查询",
            ],
        },
        {
            "goal": "新增明细查询能力，支持基于数据模型直接查明细结果。",
            "mainIncludes": ["支持保存为取数模板", "支持查看 SQL 和下载结果"],
            "mainExcludes": ["进入明细查询", "选择数据模型", "生成查询结果"],
        },
    ),
    (
        "supporting-config-vs-labels",
        {
            "label": "示例配置页",
            "lines": [
                "需求详情",
                "支持定义数值展示格式",
                "取数模板",
                "* 波动识别规则",
                "* 统计周期结束时间默认值",
                "模型状态：已上线",
                "如果模型未上线，则不能发起明细查询",
            ],
        },
        {
            "goal": "支持定义数值展示格式",
            "supportingIncludes": ["波动识别规则", "统计周期结束时间默认值"],
            "supportingExcludes": ["取数模板", "模型状态：已上线", "查看执行SQL", "选择字段"],
        },
    ),
    (
        "capability-vs-config-splitting",
        {
            "label": "示例能力页",
            "lines": [
                "需求详情",
                "支持明细查询能力",
                "新增【类型】字段",
                "新增【模型基准日期】",
                "选择字段默认排序 按照维度/度量/非度量进行排序",
                "如果模型未上线，则不能发起明细查询",
            ],
        },
        {
            "goal": "支持明细查询能力",
            "mainExcludes": ["新增【类型】字段", "新增【模型基准日期】", "选择字段默认排序 按照维度/度量/非度量进行排序"],
            "supportingIncludes": ["新增【类型】字段", "新增【模型基准日期】"],
            "supportingExcludes": ["选择字段默认排序 按照维度/度量/非度量进行排序"],
        },
    ),
    (
        "example-display-separation",
        {
            "label": "示例展示页",
            "lines": [
                "需求详情",
                "支持同环比结果展示",
                "查询粒度：月；查询日期：2025-01 至 2025-12",
                "查询指标：销售额、销售额_年同比增长率",
                "如果模型未上线，则不能发起明细查询",
            ],
        },
        {
            "goal": "支持同环比结果展示",
            "exampleIncludes": ["查询粒度：月；查询日期：2025-01 至 2025-12", "查询指标：销售额、销售额_年同比增长率"],
            "mainExcludes": ["查询粒度：月；查询日期：2025-01 至 2025-12", "查询指标：销售额、销售额_年同比增长率"],
            "supportingExcludes": ["查询粒度：月；查询日期：2025-01 至 2025-12", "查询指标：销售额、销售额_年同比增长率"],
            "recommendation": "optional",
        },
    ),
    (
        "multi-section-page-breakdown",
        {
            "label": "同环比功能适配页",
            "lines": [
                "需求详情",
                "同环比功能适配：",
                "1. 指标对比支持定义数值展示格式",
                "如下图红框位置展示对比指标效果示例",
                "若查询粒度为汇总，则默认展示百分数",
                "2. 查询粒度定义改造，月/季/年度汇总和月/季/年末指标数据可同时查询",
                "统计维度/指标对比均可选，至少选一个",
                "3. 指标卡2的指标单位展示",
                "* 数据量级单位",
                "* 数据展示精度",
            ],
        },
        {
            "goal": "同环比功能适配",
            "sectionTitles": [
                "指标对比支持定义数值展示格式",
                "查询粒度定义改造，月/季/年度汇总和月/季/年末指标数据可同时查询",
                "指标卡2的指标单位展示",
            ],
        },
    ),
    (
        "compound-config-title-capability",
        {
            "label": "示例表格增强页",
            "lines": [
                "需求详情",
                "表格组件能力增强，引入明细查询、导入取数模板",
                "1. 新增表格组件图标&支持明细查询",
                "表格组件图标新增",
                "数据配置组件新增配置项【查询方式】",
                "新增字段",
                "筛选条件配置",
                "2. 导入取数模板&模型日期基准",
                "明细查询导入模板时，基于模板导入筛选条件，【模型日期基准】不需要注入",
            ],
        },
        {
            "goal": "表格组件能力增强，引入明细查询、导入取数模板",
            "sectionTitles": ["新增表格组件图标&支持明细查询", "导入取数模板&模型日期基准"],
            "mainIncludes": ["表格组件能力增强，引入明细查询、导入取数模板"],
            "mainExcludes": ["新增字段", "筛选条件配置"],
        },
    ),
    (
        "anchor-block-sections",
        {
            "label": "示例锚点页",
            "lines": [
                "需求背景",
                "支持完成明细查询的核心流程",
                "1",
                "选择字段",
                "支持搜索关键词匹配模型内的字段",
                "2",
                "选择数据模型",
                "支持展示模型基本信息",
                "A01",
                "新增全局筛选",
                "1. 新增全局看板筛选，确保作用于全局子看板",
                "2. 配置条件复用【指标查询】",
                "A02",
                "导入取数模板&模型日期基准",
                "1. 基于模板导入筛选条件",
                "2. 模型日期基准取看板全局的【日期基准】",
            ],
        },
        {
            "goal": "支持完成明细查询的核心流程",
            "sectionTitles": ["选择字段", "选择数据模型", "新增全局筛选", "导入取数模板&模型日期基准"],
        },
    ),
    (
        "cross-line-rule-window",
        {
            "label": "示例跨行规则页",
            "lines": [
                "需求详情",
                "支持明细查询能力",
                "异常情况处理：",
                "直接弹窗拦截报错",
                "查询结果下载",
            ],
        },
        {
            "goal": "支持明细查询能力",
        },
    ),
]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for fixture_name, expected in FIXTURES:
        fixture_path = FIXTURE_DIR / fixture_name
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))

        risk = page_risk_parser.assess_page_risk(payload["label"], payload)
        _assert(risk["riskLevel"] == expected["riskLevel"], f"{fixture_name}: unexpected risk level")
        _assert(
            risk["screenshotRecommendation"] == expected["screenshotRecommendation"],
            f"{fixture_name}: unexpected screenshot recommendation",
        )
        _assert(
            risk["needsScreenshot"] == expected["needsScreenshot"],
            f"{fixture_name}: unexpected needsScreenshot flag",
        )

        issues = page_issue_extractor.extract_issues(payload)
        _assert("suspectedIssues" in issues, f"{fixture_name}: missing suspectedIssues")

        merged = dict(payload)
        merged["riskLevel"] = risk["riskLevel"]
        merged["needsScreenshot"] = risk["needsScreenshot"]
        merged["screenshotRecommendation"] = risk["screenshotRecommendation"]
        merged["suspectedIssues"] = issues["suspectedIssues"]

        breakdown = breakdown_exporter.build_breakdown([merged])
        _assert(breakdown["artifactType"] == "prd-understanding-input", f"{fixture_name}: artifact type regressed")
        _assert(breakdown["pageCount"] == 1, f"{fixture_name}: page count regressed")

        page = breakdown["pages"][0]
        _assert(page["label"] == payload["label"], f"{fixture_name}: page label regressed")
        _assert(isinstance(page.get("sections"), list), f"{fixture_name}: sections should be a list")
        _assert(isinstance(page.get("visualSignals"), dict), f"{fixture_name}: visualSignals should be a dict")
        _assert(isinstance(page.get("understandingOutline"), list), f"{fixture_name}: understandingOutline should be a list")
        _assert(page.get("understandingOutline"), f"{fixture_name}: understandingOutline should not be empty")
        if fixture_name == "axhub-15899-page.json":
            outline_text = " ".join(page.get("understandingOutline", []))
            _assert("23万" not in outline_text, f"{fixture_name}: low-information numeric label leaked into understandingOutline")
        if expected["screenshotRecommendation"] != "none":
            _assert(
                page.get("visualSignals", {}).get("screenshotRecommendation") == expected["screenshotRecommendation"],
                f"{fixture_name}: screenshot recommendation regressed in breakdown",
            )
            _assert(
                page.get("visualSignals", {}).get("reviewFocus")
                or page.get("visualSignals", {}).get("observations")
                or page.get("visualSignals", {}).get("note"),
                f"{fixture_name}: screenshot-oriented page should keep visual review hints",
            )
        if issues["suspectedIssues"]:
            _assert(page.get("suspectedIssues"), f"{fixture_name}: suspected issues missing from breakdown")

        if fixture_name == "modao-15686-page.json":
            _assert(
                page["goal"] == ["新增明细查询能力，支持基于数据模型直接查明细结果。"],
                f"{fixture_name}: goal extraction regressed",
            )
            _assert(
                any(item.startswith("支持") for item in page["mainRequirements"]),
                f"{fixture_name}: Modao main requirements should prefer capability summaries",
            )
            section_map = {section.get("title"): section for section in page.get("sections", [])}
            template_section = section_map.get("保存为取数模板", {})
            _assert(
                "字段范围是已选模型内的所有字段" not in template_section.get("supportingRequirements", []),
                f"{fixture_name}: explanatory supporting line should be lifted into rules",
            )
            _assert(
                "支持保存为取数模板" in page.get("mainRequirements", []),
                f"{fixture_name}: capability wording for 保存为取数模板 regressed",
            )
            outline_text = " ".join(page.get("understandingOutline", []))
            _assert("数据模型选择" in outline_text, f"{fixture_name}: outline should summarize 选择数据模型 as 数据模型选择")
            _assert("保存为取数模板" in outline_text, f"{fixture_name}: outline should keep natural 保存为取数模板 wording")
            _assert("支持将支持保存设置为取数模板" not in outline_text, f"{fixture_name}: outline should not keep duplicated title-rewrite artifacts")
            evidence_refs = page.get("evidenceReferences", {}).get("mainRequirements", [])
            template_ref = next((item for item in evidence_refs if item.get("item") == "支持保存为取数模板"), {})
            _assert(
                "新增【类型】字段" not in template_ref.get("evidenceLines", []),
                f"{fixture_name}: unrelated template field noise should not leak into 保存为取数模板 evidence",
            )
        if fixture_name == "axhub-15900-page.json":
            _assert(
                "一优先级" not in page["goal"],
                f"{fixture_name}: noisy goal line should not be selected",
            )
        if fixture_name == "axhub-15899-page.json":
            _assert("查询粒度" not in page["mainRequirements"], f"{fixture_name}: field label leaked into main requirements")
            _assert("波动识别规则" in page["supportingRequirements"], f"{fixture_name}: supporting requirement extraction regressed")

    for case_name, payload, expected in SYNTHETIC_RISK_CASES:
        risk = page_risk_parser.assess_page_risk(payload["label"], payload)
        _assert(risk["riskLevel"] == expected["riskLevel"], f"{case_name}: unexpected risk level")
        _assert(
            risk["screenshotRecommendation"] == expected["screenshotRecommendation"],
            f"{case_name}: unexpected screenshot recommendation",
        )

    for case_name, payload, expected_count in SYNTHETIC_ISSUE_CASES:
        issues = page_issue_extractor.extract_issues(payload)
        _assert(
            len(issues["suspectedIssues"]) == expected_count,
            f"{case_name}: unexpected suspected issue count",
        )

    for case_name, payload, expected in SYNTHETIC_BREAKDOWN_CASES:
        breakdown = breakdown_exporter.build_breakdown([payload])
        page = breakdown["pages"][0]
        section_supporting = {
            item
            for section in page.get("sections", [])
            for item in section.get("supportingRequirements", [])
        }
        _assert(expected["goal"] in page["goal"], f"{case_name}: goal extraction regressed")
        for item in expected.get("mainIncludes", []):
            _assert(item in page["mainRequirements"], f"{case_name}: missing main requirement {item}")
        for item in expected.get("mainExcludes", []):
            _assert(item not in page["mainRequirements"], f"{case_name}: flow noise leaked into main requirements")
        for item in expected.get("supportingIncludes", []):
            _assert(
                item in page["supportingRequirements"] or item in section_supporting,
                f"{case_name}: missing supporting requirement {item}",
            )
        for item in expected.get("supportingExcludes", []):
            _assert(item not in page["supportingRequirements"], f"{case_name}: label noise leaked into supporting requirements")
        for item in expected.get("exampleIncludes", []):
            _assert(item in page["exampleDisplay"], f"{case_name}: missing example/display item {item}")
        for item in expected.get("sectionTitles", []):
            _assert(
                any(
                    section.get("title") == item or section.get("rawTitle") == item
                    for section in page.get("sections", [])
                )
                or item in page.get("pageSummary", []),
                f"{case_name}: missing section or summary title {item}",
            )
        if case_name == "compound-config-title-capability":
            _assert(
                page.get("mainRequirements") == ["表格组件能力增强，引入明细查询、导入取数模板"],
                f"{case_name}: page-level requirements should prefer the higher-level capability summary without duplicate shorter variants",
            )
            icon_section = next(
                (
                    section
                    for section in page.get("sections", [])
                    if section.get("title") == "支持新增表格组件图标，并支持明细查询"
                    or section.get("rawTitle") == "新增表格组件图标&支持明细查询"
                ),
                {},
            )
            _assert(
                icon_section.get("mainRequirements") == ["支持新增表格组件图标，并支持明细查询"],
                f"{case_name}: compound title should be rewritten as natural capability summary",
            )
            _assert(
                "新增字段" not in icon_section.get("supportingRequirements", [])
                and "筛选条件配置" not in icon_section.get("supportingRequirements", []),
                f"{case_name}: low-information config labels should not stay in supporting requirements",
            )
            _assert(
                "数据配置组件新增配置项【查询方式】" in icon_section.get("rulesAndConstraints", []),
                f"{case_name}: explanatory config line should be classified as a rule",
            )
            _assert(
                "表格组件图标新增" not in page.get("supportingRequirements", []),
                f"{case_name}: low-value page-level supporting residue should be removed when section capabilities already cover it",
            )
        if expected.get("recommendation"):
            _assert(
                page["visualSignals"]["screenshotRecommendation"] == expected["recommendation"],
                f"{case_name}: example-display page should inherit refreshed screenshot recommendation",
            )
            _assert(
                page.get("visualSignals", {}).get("exampleDisplayNote"),
                f"{case_name}: example-display page should include visual note",
            )
        if case_name == "cross-line-rule-window":
            _assert(
                "直接弹窗拦截报错" in page["globalRules"],
                f"{case_name}: cross-line rule line should be classified as a rule",
            )

    _assert(
        breakdown_exporter._should_merge_adjacent_sections("导出数据详情", "数据导出详情"),
        "sequence-matcher merge should handle reordered but highly similar section titles",
    )

    print("Regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
