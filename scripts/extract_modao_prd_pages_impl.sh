#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  extract_prd_pages.sh [--with-screenshot] [--output-mode <concise|standard|rich>] [--scope-dir <dir-label> | --scope-page <page-label>] <prd-url> [output-dir]
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd npx
require_cmd node
require_cmd jq
require_cmd grep
require_cmd sed
require_cmd cp
require_cmd cmp
require_cmd python3

TMP_ROOT="${TMPDIR:-/tmp}"

SCOPE_DIR=""
SCOPE_PAGE=""
WITH_SCREENSHOT=0
OUTPUT_MODE="standard"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --scope-dir)
      [[ $# -ge 2 ]] || { echo "--scope-dir requires a value" >&2; exit 1; }
      SCOPE_DIR="$2"
      shift 2
      ;;
    --scope-page)
      [[ $# -ge 2 ]] || { echo "--scope-page requires a value" >&2; exit 1; }
      SCOPE_PAGE="$2"
      shift 2
      ;;
    --with-screenshot)
      WITH_SCREENSHOT=1
      shift
      ;;
    --output-mode)
      [[ $# -ge 2 ]] || { echo "--output-mode requires a value" >&2; exit 1; }
      OUTPUT_MODE="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

case "$OUTPUT_MODE" in
  concise|standard|rich)
    ;;
  *)
    echo "Unsupported output mode: $OUTPUT_MODE" >&2
    exit 1
    ;;
esac

if [[ -n "$SCOPE_DIR" && -n "$SCOPE_PAGE" ]]; then
  echo "Use either --scope-dir or --scope-page, not both." >&2
  exit 1
fi

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage >&2
  exit 1
fi

URL="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SHORT_TS="$(date +%H%M%S)"
RUNTIME_ROOT="${PRD_CAPTURE_RUNTIME_DIR:-$TMP_ROOT/prd-requirement-decomposer}"
CLI_RUNTIME_DIR="${PRD_PLAYWRIGHT_CLI_DIR:-$TMP_ROOT/prd-playwright-cli}"
OUTPUT_DIR="${2:-$RUNTIME_ROOT/$TIMESTAMP}"
SESSION="prd-$SHORT_TS-$$"
PAGES_PARSER="$SCRIPT_DIR/snapshot_tree_parser.py"
TEXT_PARSER="$SCRIPT_DIR/page_text_parser.py"
RISK_PARSER="$SCRIPT_DIR/page_risk_parser.py"
ISSUE_PARSER="$SCRIPT_DIR/page_issue_extractor.py"
BREAKDOWN_EXPORTER="$SCRIPT_DIR/breakdown_exporter.py"
ACTIVE_PAGE_PARSER="$SCRIPT_DIR/active_page_parser.py"
AXHUB_SCREENSHOT_HELPER="$SCRIPT_DIR/capture_axhub_single_page_screenshot.js"
MODAO_SCREENSHOT_HELPER="$SCRIPT_DIR/capture_modao_single_page_screenshot.js"
DIRECT_SINGLE_PAGE_COLLECTOR="$SCRIPT_DIR/collect_prd_single_page.js"
DIRECT_PAGES_COLLECTOR="$SCRIPT_DIR/collect_prd_pages.js"
SCOPE_TYPE="all"
SCOPE_VALUE=""
IS_AXHUB=0
DIRECT_PAGE_FALLBACK=0
AXHUB_SINGLE_PAGE_TREE_WAIT_SECONDS=6

if [[ "$URL" == *"axhub.im"* ]]; then
  IS_AXHUB=1
fi

if [[ -n "$SCOPE_DIR" ]]; then
  SCOPE_TYPE="directory"
  SCOPE_VALUE="$SCOPE_DIR"
elif [[ -n "$SCOPE_PAGE" ]]; then
  SCOPE_TYPE="page"
  SCOPE_VALUE="$SCOPE_PAGE"
fi

mkdir -p "$OUTPUT_DIR"
mkdir -p "$CLI_RUNTIME_DIR"
cd "$CLI_RUNTIME_DIR"

export PLAYWRIGHT_DAEMON_SESSION_DIR="${PLAYWRIGHT_DAEMON_SESSION_DIR:-$TMP_ROOT/prd-playwright-daemon}"
mkdir -p "$PLAYWRIGHT_DAEMON_SESSION_DIR"

LOCAL_PLAYWRIGHT_CLI="$TOOL_ROOT/node_modules/@playwright/cli/playwright-cli.js"
if [[ -f "$LOCAL_PLAYWRIGHT_CLI" ]]; then
  PWCLI_BASE=(node "$LOCAL_PLAYWRIGHT_CLI" --json)
else
  LOCAL_PLAYWRIGHT_CLI="$(
    find "$HOME/.npm/_npx" -path '*/node_modules/@playwright/cli/playwright-cli.js' 2>/dev/null | sort | tail -n 1
  )"
  if [[ -n "$LOCAL_PLAYWRIGHT_CLI" && -f "$LOCAL_PLAYWRIGHT_CLI" ]]; then
    PWCLI_BASE=(node "$LOCAL_PLAYWRIGHT_CLI" --json)
  else
    PWCLI_BASE=(npx --yes @playwright/cli --json)
  fi
fi
PWCLI=("${PWCLI_BASE[@]}" -s="$SESSION")
ROOT_SNAPSHOT="$OUTPUT_DIR/root-snapshot.txt"
TMP_SNAPSHOT="$OUTPUT_DIR/tmp-snapshot.txt"
PAGES_JSON="$OUTPUT_DIR/pages.json"
TMP_PAGES_JSON="$OUTPUT_DIR/tmp-pages.json"
TMP_CANDIDATES_JSON="$OUTPUT_DIR/tmp-candidates.json"
EXTRACTION_SUMMARY_JSON="$OUTPUT_DIR/extraction-summary.json"

cleanup() {
  "${PWCLI[@]}" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup_output_artifacts() {
  # rich 模式保留中间产物用于排障；其他模式默认只留最终结果。
  if [[ "$OUTPUT_MODE" == "rich" ]]; then
    return 0
  fi
  rm -f "$ROOT_SNAPSHOT" "$TMP_SNAPSHOT" "$TMP_PAGES_JSON" "$TMP_CANDIDATES_JSON"
}

cleanup_page_artifacts() {
  local page_dir="$1"
  if [[ "$OUTPUT_MODE" == "rich" ]]; then
    return 0
  fi
  rm -f \
    "$page_dir/page-label.txt" \
    "$page_dir/snapshot.txt" \
    "$page_dir/raw.json" \
    "$page_dir/raw.txt" \
    "$page_dir/risk.json" \
    "$page_dir/issues.json" \
    "$page_dir/page.tmp.json" \
    "$page_dir/screenshot.json" \
    "$page_dir/manifest.json"
}

apply_output_mode_cleanup() {
  local page_dir page_json_file

  case "$OUTPUT_MODE" in
    concise)
      # concise 面向“AI 只吃最终理解输入”的场景：去掉 pages.json 和每页 page.json，
      # 只保留 understanding-input.json，以及用户显式要求保留的截图文件。
      rm -f "$PAGES_JSON"
      for page_dir in "$OUTPUT_DIR"/page-*; do
        [[ -d "$page_dir" ]] || continue
        page_json_file="$page_dir/page.json"
        rm -f "$page_json_file"
        if [[ ! -e "$page_dir/page.png" ]] && ! compgen -G "$page_dir/shot-*.png" >/dev/null; then
          rmdir "$page_dir" 2>/dev/null || true
        fi
      done
      ;;
    standard)
      ;;
    rich)
      ;;
  esac
}

normalize_page_json() {
  local page_json_file="$1"
  local tmp_file="$page_json_file.normalized"

  jq '{
    sourceUrl,
    scopeType,
    scopeValue,
    label,
    path,
    rawText,
    lines,
    semanticSnapshot,
    riskLevel,
    needsScreenshot,
    screenshotRecommendation,
    suspectedIssues,
    screenshotPath,
    screenshot
  } + (
    if .needsScreenshot then
      { screenshotNote: "建议结合截图核对视觉关系、布局指向或图片标注。" }
    elif .screenshotRecommendation == "optional" then
      { screenshotNote: "可按需结合截图核对交互布局或图示细节。" }
    else
      {}
    end
  )' "$page_json_file" > "$tmp_file"
  mv "$tmp_file" "$page_json_file"
}

run_pw() {
  "${PWCLI[@]}" "$@"
}

write_extraction_summary() {
  local mode="$1"
  local fallback_used="$2"
  local collector_kind="$3"
  local reason="${4:-}"

  jq -nc \
    --arg mode "$mode" \
    --arg collectorKind "$collector_kind" \
    --arg platform "$([[ $IS_AXHUB -eq 1 ]] && echo axhub || echo modao)" \
    --arg scopeType "$SCOPE_TYPE" \
    --arg scopeValue "$SCOPE_VALUE" \
    --arg sourceUrl "$URL" \
    --arg reason "$reason" \
    --argjson fallbackUsed "$fallback_used" \
    '{
      mode: $mode,
      fallbackUsed: $fallbackUsed,
      collectorKind: $collectorKind,
      platform: $platform,
      scopeType: $scopeType,
      scopeValue: $scopeValue,
      sourceUrl: $sourceUrl
    } + (if $reason != "" then { fallbackReason: $reason } else {} end)' > "$EXTRACTION_SUMMARY_JSON"
}

legacy_fallback_allowed() {
  local reason="$1"
  case "$reason" in
    content_frame_unavailable|empty_page_text|launch_failed|tree_unavailable)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

dismiss_axhub_notice_if_present() {
  local attempt snapshot_json snapshot_text notice_ref

  if (( IS_AXHUB == 0 )); then
    return 0
  fi

  for attempt in $(seq 1 10); do
    snapshot_json="$(run_pw snapshot)"
    snapshot_text="$(printf '%s' "$snapshot_json" | jq -r '.snapshot // empty')"
    notice_ref="$(
      printf '%s\n' "$snapshot_text" |
        sed -n 's/.*button "知道了" \[ref=\([^]]*\)\].*/\1/p' |
        head -n 1
    )"

    if [[ -n "$notice_ref" ]]; then
      run_pw click "$notice_ref" >/dev/null
      sleep 2
      return 0
    fi

    sleep 1
  done

  return 0
}

wait_for_snapshot() {
  local target_file="$1"
  local attempt snapshot_json snapshot_text
  for attempt in $(seq 1 30); do
    snapshot_json="$(run_pw snapshot)"
    snapshot_text="$(printf '%s' "$snapshot_json" | jq -r '.snapshot // empty')"
    if [[ -n "$snapshot_text" ]] \
      && [[ "$(grep -E -c 'iframe( \[active\])? \[ref=' <<<"$snapshot_text")" -ge 1 ]]; then
      printf '%s' "$snapshot_text" > "$target_file"
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for PRD page snapshot." >&2
  return 1
}

has_rendered_body() {
  local snapshot_file="$1"
  grep -Eq 'paragraph \[ref=|textbox \[ref=' "$snapshot_file"
}

axhub_direct_page_matches_scope() {
  python3 - "$URL" "$SCOPE_PAGE" <<'PY'
from urllib.parse import urlparse, parse_qs
import sys

url = sys.argv[1]
scope_page = sys.argv[2]
fragment = urlparse(url).fragment
params = parse_qs(fragment)
target = params.get("p", [""])[0]
print("1" if target == scope_page else "0")
PY
}

capture_screenshot_if_requested() {
  local page_dir="$1"
  local page_json_file="$2"
  local page_label="$3"
  local screenshot_path screenshot_meta_file tmp_page_json

  if (( WITH_SCREENSHOT == 0 )); then
    return 0
  fi

  if [[ -z "$LOCAL_PLAYWRIGHT_CLI" || ! -f "$LOCAL_PLAYWRIGHT_CLI" ]]; then
    echo "Skipping screenshot: local Playwright CLI path unavailable." >&2
    return 0
  fi

  screenshot_path="$page_dir/page.png"
  screenshot_meta_file="$page_dir/screenshot.json"
  tmp_page_json="$page_dir/page.tmp.json"

  if (( IS_AXHUB == 1 )); then
    echo "Capturing page screenshot for Axhub: $page_label"
    node "$AXHUB_SCREENSHOT_HELPER" "$LOCAL_PLAYWRIGHT_CLI" "$URL" "$screenshot_path" "$page_label" > "$screenshot_meta_file"
  else
    echo "Capturing page screenshot for Modao: $page_label"
    node "$MODAO_SCREENSHOT_HELPER" "$LOCAL_PLAYWRIGHT_CLI" "$URL" "$page_dir" "$page_label" > "$screenshot_meta_file"
  fi

  jq \
    --arg screenshotPath "$screenshot_path" \
    --slurpfile screenshot "$screenshot_meta_file" \
    '. + {
      screenshotPath: $screenshotPath,
      screenshot: $screenshot[0]
    }' "$page_json_file" > "$tmp_page_json"
  mv "$tmp_page_json" "$page_json_file"
}

extract_single_page_direct() {
  local page_dir page_label raw_json_file raw_text_file risk_json_file issue_json_file page_json_file page_tmp_json status reason retryable

  if [[ -z "$SCOPE_PAGE" ]]; then
    return 1
  fi
  if [[ -z "$LOCAL_PLAYWRIGHT_CLI" || ! -f "$LOCAL_PLAYWRIGHT_CLI" ]]; then
    return 1
  fi

  page_label="$SCOPE_PAGE"
  page_dir="$OUTPUT_DIR/page-000"
  raw_json_file="$page_dir/raw.json"
  raw_text_file="$page_dir/raw.txt"
  risk_json_file="$page_dir/risk.json"
  issue_json_file="$page_dir/issues.json"
  page_json_file="$page_dir/page.json"
  page_tmp_json="$page_dir/page.tmp.json"

  mkdir -p "$page_dir"
  printf '%s\n' "$page_label" > "$page_dir/page-label.txt"

  node "$DIRECT_SINGLE_PAGE_COLLECTOR" "$LOCAL_PLAYWRIGHT_CLI" "$URL" "$page_label" "$page_dir" > "$raw_json_file"
  status="$(jq -r '.status // "error"' "$raw_json_file")"
  if [[ "$status" != "ok" ]]; then
    reason="$(jq -r '.reason // "unknown"' "$raw_json_file")"
    retryable="$(jq -r '.retryable // false' "$raw_json_file")"
    if [[ "$retryable" != "true" ]] || ! legacy_fallback_allowed "$reason"; then
      echo "Direct single-page collector blocked ($reason), skipping legacy fallback." >&2
      write_extraction_summary "blocked" false "single-page-node" "$reason"
      return 2
    fi
    echo "Direct single-page collector unavailable ($reason), falling back to legacy extractor." >&2
    write_extraction_summary "fallback-pending" true "single-page-node" "$reason"
    return 1
  fi

  jq -r '.rawText' "$raw_json_file" > "$raw_text_file"
  python3 "$RISK_PARSER" "$raw_json_file" "$page_label" > "$risk_json_file"

  jq -nc \
    --arg label "$page_label" \
    --arg sourceUrl "$URL" \
    --arg scopeType "$SCOPE_TYPE" \
    --arg scopeValue "$SCOPE_VALUE" \
    --argjson ancestors '[]' \
    --argjson path "[\"$page_label\"]" \
    --slurpfile raw "$raw_json_file" \
    --slurpfile risk "$risk_json_file" \
    '{
      label: $label,
      sourceUrl: $sourceUrl,
      scopeType: $scopeType,
      scopeValue: $scopeValue,
      ancestors: $ancestors,
      path: $path,
      bodyRef: $raw[0].bodyRef,
      lines: $raw[0].lines,
      rawText: $raw[0].rawText,
      semanticSnapshot: $raw[0].semanticSnapshot,
      riskLevel: $risk[0].riskLevel,
      needsScreenshot: $risk[0].needsScreenshot,
      screenshotRecommendation: $risk[0].screenshotRecommendation,
      riskAssessment: $risk[0]
    }' > "$page_json_file"

  capture_screenshot_if_requested "$page_dir" "$page_json_file" "$page_label"
  python3 "$ISSUE_PARSER" "$page_json_file" > "$issue_json_file"
  jq \
    --slurpfile issues "$issue_json_file" \
    '. + {
      needsManualReview: $issues[0].needsManualReview,
      suspectedIssues: $issues[0].suspectedIssues,
      issueExtraction: $issues[0]
    }' "$page_json_file" > "$page_tmp_json"
  mv "$page_tmp_json" "$page_json_file"
  normalize_page_json "$page_json_file"
  cleanup_page_artifacts "$page_dir"

  jq -s '.' "$page_json_file" > "$PAGES_JSON"
  python3 "$BREAKDOWN_EXPORTER" "$PAGES_JSON" "$OUTPUT_DIR" "$OUTPUT_MODE"
  write_extraction_summary "primary" false "single-page-node"
  cleanup_output_artifacts
  apply_output_mode_cleanup
  return 0
}

extract_pages_direct() {
  local collector_json_file page_count page_index page_dir raw_json_file raw_text_file risk_json_file issue_json_file page_json_file page_tmp_json
  local page_label page_ancestors page_path page_raw_json_file status reason retryable

  if [[ -n "$SCOPE_PAGE" ]]; then
    return 1
  fi
  if [[ -z "$LOCAL_PLAYWRIGHT_CLI" || ! -f "$LOCAL_PLAYWRIGHT_CLI" ]]; then
    return 1
  fi

  collector_json_file="$OUTPUT_DIR/direct-pages.json"
  node "$DIRECT_PAGES_COLLECTOR" "$LOCAL_PLAYWRIGHT_CLI" "$URL" "$SCOPE_TYPE" "$SCOPE_VALUE" "$OUTPUT_DIR" > "$collector_json_file"
  status="$(jq -r '.status // "error"' "$collector_json_file")"
  if [[ "$status" != "ok" ]]; then
    reason="$(jq -r '.reason // "unknown"' "$collector_json_file")"
    retryable="$(jq -r '.retryable // false' "$collector_json_file")"
    if [[ "$retryable" != "true" ]] || ! legacy_fallback_allowed "$reason"; then
      echo "Direct page collector blocked ($reason), skipping legacy fallback." >&2
      write_extraction_summary "blocked" false "multi-page-node" "$reason"
      return 2
    fi
    echo "Direct page collector unavailable ($reason), falling back to legacy extractor." >&2
    write_extraction_summary "fallback-pending" true "multi-page-node" "$reason"
    return 1
  fi

  jq '.pages' "$collector_json_file" > "$PAGES_JSON"
  page_count="$(jq 'length' "$PAGES_JSON")"

  for page_index in $(seq 0 $(( page_count - 1 ))); do
    page_dir="$OUTPUT_DIR/page-$(printf '%03d' "$page_index")"
    raw_json_file="$page_dir/raw.json"
    raw_text_file="$page_dir/raw.txt"
    risk_json_file="$page_dir/risk.json"
    issue_json_file="$page_dir/issues.json"
    page_json_file="$page_dir/page.json"
    page_tmp_json="$page_dir/page.tmp.json"
    page_raw_json_file="$page_dir/page.raw.json"

    mkdir -p "$page_dir"
    jq ".[$page_index]" "$PAGES_JSON" > "$page_raw_json_file"

    page_label="$(jq -r '.label' "$page_raw_json_file")"
    page_ancestors="$(jq '.ancestors' "$page_raw_json_file")"
    page_path="$(jq '.path' "$page_raw_json_file")"
    printf '%s\n' "$page_label" > "$page_dir/page-label.txt"

    jq '{ bodyRef, lines, rawText, semanticSnapshot }' "$page_raw_json_file" > "$raw_json_file"
    jq -r '.rawText' "$raw_json_file" > "$raw_text_file"
    python3 "$RISK_PARSER" "$raw_json_file" "$page_label" > "$risk_json_file"

    jq -nc \
      --arg label "$page_label" \
      --arg sourceUrl "$URL" \
      --arg scopeType "$SCOPE_TYPE" \
      --arg scopeValue "$SCOPE_VALUE" \
      --argjson ancestors "$page_ancestors" \
      --argjson path "$page_path" \
      --slurpfile raw "$page_raw_json_file" \
      --slurpfile risk "$risk_json_file" \
      '{
        label: $label,
        sourceUrl: $sourceUrl,
        scopeType: $scopeType,
        scopeValue: $scopeValue,
        ancestors: $ancestors,
        path: $path,
        bodyRef: $raw[0].bodyRef,
        lines: $raw[0].lines,
        rawText: $raw[0].rawText,
        semanticSnapshot: $raw[0].semanticSnapshot,
        riskLevel: $risk[0].riskLevel,
        needsScreenshot: $risk[0].needsScreenshot,
        screenshotRecommendation: $risk[0].screenshotRecommendation,
        riskAssessment: $risk[0]
      }' > "$page_json_file"

    capture_screenshot_if_requested "$page_dir" "$page_json_file" "$page_label"
    python3 "$ISSUE_PARSER" "$page_json_file" > "$issue_json_file"
    jq \
      --slurpfile issues "$issue_json_file" \
      '. + {
        needsManualReview: $issues[0].needsManualReview,
        suspectedIssues: $issues[0].suspectedIssues,
        issueExtraction: $issues[0]
      }' "$page_json_file" > "$page_tmp_json"
    mv "$page_tmp_json" "$page_json_file"
    normalize_page_json "$page_json_file"
    cleanup_page_artifacts "$page_dir"

    if [[ "$OUTPUT_MODE" != "rich" ]]; then
      rm -f "$page_raw_json_file"
    fi
  done

  jq -s '.' "$OUTPUT_DIR"/page-*/page.json > "$PAGES_JSON"
  python3 "$BREAKDOWN_EXPORTER" "$PAGES_JSON" "$OUTPUT_DIR" "$OUTPUT_MODE"
  write_extraction_summary "primary" false "multi-page-node"
  cleanup_output_artifacts
  if [[ "$OUTPUT_MODE" != "rich" ]]; then
    rm -f "$collector_json_file"
  fi
  apply_output_mode_cleanup
  return 0
}

wait_for_target_page() {
  local target_label="$1"
  local target_file="$2"
  local attempt snapshot_json snapshot_text active_title

  if (( IS_AXHUB == 0 )); then
    wait_for_snapshot "$target_file"
    return 0
  fi

  for attempt in $(seq 1 45); do
    snapshot_json="$(run_pw snapshot)"
    snapshot_text="$(printf '%s' "$snapshot_json" | jq -r '.snapshot // empty')"
    if [[ -n "$snapshot_text" ]] \
      && [[ "$(grep -E -c 'iframe( \[active\])? \[ref=' <<<"$snapshot_text")" -ge 1 ]]; then
      printf '%s' "$snapshot_text" > "$target_file"
      active_title="$(python3 "$ACTIVE_PAGE_PARSER" "$target_file" 2>/dev/null || true)"
      if [[ "$active_title" == "$target_label" ]]; then
        return 0
      fi
    fi
    sleep 1
  done

  echo "Timed out waiting for Axhub page switch: $target_label" >&2
  return 1
}

wait_for_page_tree() {
  local target_file="$1"
  local max_attempts="${2:-45}"
  local attempt snapshot_json snapshot_text parsed_count
  for attempt in $(seq 1 "$max_attempts"); do
    snapshot_json="$(run_pw snapshot)"
    snapshot_text="$(printf '%s' "$snapshot_json" | jq -r '.snapshot // empty')"
    if [[ -n "$snapshot_text" ]] \
      && [[ "$(grep -E -c 'iframe( \[active\])? \[ref=' <<<"$snapshot_text")" -ge 1 ]]; then
      printf '%s' "$snapshot_text" > "$target_file"
      parsed_count="$(
        python3 - "$PAGES_PARSER" "$target_file" <<'PY'
import json
import subprocess
import sys

parser = sys.argv[1]
snapshot_path = sys.argv[2]
result = subprocess.run(
    [sys.executable, parser, snapshot_path],
    capture_output=True,
    check=True,
    text=True,
)
pages = json.loads(result.stdout)
print(len(pages))
PY
      )"

      if (( IS_AXHUB == 0 )); then
        # Modao 首次会出现“页面（0）”的假页树，必须等真实叶子页出来再继续。
        if [[ "$parsed_count" =~ ^[0-9]+$ ]] && (( parsed_count > 1 )) && ! grep -q '页面（0）' "$target_file"; then
          return 0
        fi
      else
        # Axhub 只要能解析出任意叶子页，就足够进入后续范围过滤。
        if [[ "$parsed_count" =~ ^[0-9]+$ ]] && (( parsed_count > 0 )); then
          return 0
        fi
      fi
    fi
    sleep 1
  done
  echo "Timed out waiting for PRD page tree to load." >&2
  return 1
}

resolve_current_page_ref() {
  local target_label="$1"
  local target_path_json="$2"

  if (( DIRECT_PAGE_FALLBACK == 1 )); then
    # Axhub 单页兜底时没有稳定页树 ref，后面直接复用当前正文页。
    printf '%s\n' "__current__"
    return 0
  fi

  wait_for_page_tree "$TMP_SNAPSHOT" >/dev/null

  python3 - "$PAGES_PARSER" "$TMP_SNAPSHOT" "$target_label" "$target_path_json" <<'PY'
import json
import subprocess
import sys

parser = sys.argv[1]
snapshot_path = sys.argv[2]
target_label = sys.argv[3]
target_path = json.loads(sys.argv[4])

result = subprocess.run(
    [sys.executable, parser, snapshot_path],
    capture_output=True,
    check=True,
    text=True,
)
pages = json.loads(result.stdout)

for page in pages:
    if page.get("path") == target_path:
        print(page["ref"])
        raise SystemExit(0)

for page in pages:
    if page.get("label") == target_label:
        print(page["ref"])
        raise SystemExit(0)

raise SystemExit(1)
PY
}

open_and_prepare() {
  local initial_tree_wait=45

  echo "Opening PRD page..."
  run_pw open "$URL" >/dev/null
  dismiss_axhub_notice_if_present

  if (( IS_AXHUB == 1 )) && [[ -n "$SCOPE_PAGE" ]]; then
    # Axhub 单页直达链接常常正文先渲染、页树后渲染，先短等避免白白卡满整轮超时。
    initial_tree_wait="$AXHUB_SINGLE_PAGE_TREE_WAIT_SECONDS"
  fi

  if wait_for_page_tree "$ROOT_SNAPSHOT" "$initial_tree_wait"; then
    return 0
  fi

  if (( IS_AXHUB == 1 )) && [[ -n "$SCOPE_PAGE" ]]; then
    echo "Axhub page tree unavailable, falling back to direct single-page extraction."
    wait_for_snapshot "$ROOT_SNAPSHOT"
    if has_rendered_body "$ROOT_SNAPSHOT"; then
      # 只要正文已渲染，就允许把当前页当目标页继续抽取，避免单页直达无页树时整体失败。
      DIRECT_PAGE_FALLBACK=1
      return 0
    fi
  fi

  return 1
}

build_page_list() {
  if (( DIRECT_PAGE_FALLBACK == 1 )); then
    jq -nc --arg label "$SCOPE_PAGE" \
      '[{
        ref: "__current__",
        label: $label,
        ancestors: [],
        path: [$label]
      }]' > "$PAGES_JSON"
    return 0
  fi

  python3 "$PAGES_PARSER" "$ROOT_SNAPSHOT" > "$PAGES_JSON"
}

write_expansion_candidates() {
  local input_file="$1"
  local output_file="$2"

  if [[ -n "$SCOPE_DIR" ]]; then
    # Modao 目录模式只扩目标目录相关的分支，避免为无关子树付出整棵树探测成本。
    jq --arg scopeDir "$SCOPE_DIR" \
      'map(select(.label == $scopeDir or ((.ancestors | index($scopeDir)) != null)))' \
      "$input_file" > "$output_file"
  else
    cp "$input_file" "$output_file"
  fi
}

apply_scope_filter() {
  local filtered_count direct_match

  if [[ -n "$SCOPE_DIR" ]]; then
    jq --arg scopeDir "$SCOPE_DIR" \
      'map(select((.ancestors | index($scopeDir)) != null))' \
      "$PAGES_JSON" > "$TMP_PAGES_JSON"
    mv "$TMP_PAGES_JSON" "$PAGES_JSON"
  elif [[ -n "$SCOPE_PAGE" ]]; then
    jq --arg scopePage "$SCOPE_PAGE" \
      'map(select(.label == $scopePage))' \
      "$PAGES_JSON" > "$TMP_PAGES_JSON"
    mv "$TMP_PAGES_JSON" "$PAGES_JSON"
  fi

  filtered_count="$(jq 'length' "$PAGES_JSON")"
  if (( filtered_count == 0 )); then
    if (( IS_AXHUB == 1 )) && [[ -n "$SCOPE_PAGE" ]]; then
      direct_match="$(axhub_direct_page_matches_scope)"
      if [[ "$direct_match" == "1" ]] && has_rendered_body "$ROOT_SNAPSHOT"; then
        echo "Axhub page tree did not expose target leaf, falling back to direct current-page extraction."
        DIRECT_PAGE_FALLBACK=1
        # g=1 等链接可能正文已切到目标页，但页树里没有暴露对应叶子节点。
        jq -nc --arg label "$SCOPE_PAGE" \
          '[{
            ref: "__current__",
            label: $label,
            ancestors: [],
            path: [$label]
          }]' > "$PAGES_JSON"
        return 0
      fi
    fi
    echo "No pages matched the requested scope ($SCOPE_TYPE: $SCOPE_VALUE)." >&2
    exit 1
  fi
}

expand_tree_generic() {
  local mode="$1"
  local progress pass candidate_count candidate_index candidate_ref candidate_label current_count next_count
  local compare_diff=0

  if [[ "$mode" == "scoped" ]]; then
    compare_diff=1
  fi

  progress=1
  pass=0
  while (( progress )); do
    progress=0
    pass=$(( pass + 1 ))
    build_page_list
    if (( compare_diff == 1 )); then
      write_expansion_candidates "$PAGES_JSON" "$TMP_CANDIDATES_JSON"
      candidate_count="$(jq 'length' "$TMP_CANDIDATES_JSON")"
      echo "Expand scoped pass $pass: checking $candidate_count relevant candidates."
    else
      cp "$PAGES_JSON" "$TMP_CANDIDATES_JSON"
      candidate_count="$(jq 'length' "$TMP_CANDIDATES_JSON")"
      current_count="$candidate_count"
      echo "Expand pass $pass: checking $candidate_count leaf candidates."
    fi

    if (( candidate_count == 0 )); then
      break
    fi

    for candidate_index in $(seq 0 $(( candidate_count - 1 ))); do
      candidate_ref="$(jq -r ".[$candidate_index].ref" "$TMP_CANDIDATES_JSON")"
      candidate_label="$(jq -r ".[$candidate_index].label" "$TMP_CANDIDATES_JSON")"
      echo "  probing $candidate_label ($candidate_ref)"
      run_pw click "$candidate_ref" >/dev/null
      wait_for_snapshot "$TMP_SNAPSHOT"
      python3 "$PAGES_PARSER" "$TMP_SNAPSHOT" > "$TMP_PAGES_JSON"

      if (( compare_diff == 1 )); then
        if ! cmp -s "$TMP_PAGES_JSON" "$PAGES_JSON"; then
          echo "    expanded relevant tree"
          cp "$TMP_SNAPSHOT" "$ROOT_SNAPSHOT"
          cp "$TMP_PAGES_JSON" "$PAGES_JSON"
          progress=1
          break
        fi
      else
        next_count="$(jq 'length' "$TMP_PAGES_JSON")"
        if (( next_count > current_count )); then
          echo "    expanded: $current_count -> $next_count leaf candidates"
          cp "$TMP_SNAPSHOT" "$ROOT_SNAPSHOT"
          cp "$TMP_PAGES_JSON" "$PAGES_JSON"
          progress=1
          break
        fi
      fi
    done
  done
}

expand_page_tree() {
  expand_tree_generic "full"
}

expand_relevant_tree() {
  expand_tree_generic "scoped"
}

extract_pages_legacy() {
  local page_count page_index page_ref current_page_ref page_label page_dir snapshot_file raw_json_file raw_text_file risk_json_file issue_json_file page_json_file page_tmp_json page_ancestors page_path

  open_and_prepare
  if (( IS_AXHUB == 0 )); then
    if [[ -n "$SCOPE_DIR" ]]; then
      expand_relevant_tree
    else
      expand_page_tree
    fi
  else
    echo "Skipping tree expansion for Axhub: root page tree is already fully navigable."
  fi
  build_page_list
  apply_scope_filter
  page_count="$(jq 'length' "$PAGES_JSON")"
  echo "Detected $page_count matching leaf pages."

  for page_index in $(seq 0 $(( page_count - 1 ))); do
    page_ref="$(jq -r ".[$page_index].ref" "$PAGES_JSON")"
    page_label="$(jq -r ".[$page_index].label" "$PAGES_JSON")"
    page_ancestors="$(jq ".[$page_index].ancestors" "$PAGES_JSON")"
    page_path="$(jq ".[$page_index].path" "$PAGES_JSON")"
    page_dir="$OUTPUT_DIR/page-$(printf '%03d' "$page_index")"
    snapshot_file="$page_dir/snapshot.txt"
    raw_json_file="$page_dir/raw.json"
    raw_text_file="$page_dir/raw.txt"
    risk_json_file="$page_dir/risk.json"
    issue_json_file="$page_dir/issues.json"
    page_json_file="$page_dir/page.json"
    page_tmp_json="$page_dir/page.tmp.json"

    mkdir -p "$page_dir"
    printf '%s\n' "$page_label" > "$page_dir/page-label.txt"

    current_page_ref="$page_ref"
    if ! current_page_ref="$(resolve_current_page_ref "$page_label" "$page_path")"; then
      echo "Failed to resolve current page ref for: $page_label" >&2
      exit 1
    fi

    echo "Extracting page $page_index: $page_label ($current_page_ref)"
    if [[ "$current_page_ref" == "__current__" ]]; then
      cp "$ROOT_SNAPSHOT" "$snapshot_file"
    else
      run_pw click "$current_page_ref" >/dev/null
      wait_for_target_page "$page_label" "$snapshot_file"
    fi
    python3 "$TEXT_PARSER" "$snapshot_file" > "$raw_json_file"
    jq -r '.rawText' "$raw_json_file" > "$raw_text_file"
    python3 "$RISK_PARSER" "$raw_json_file" "$page_label" > "$risk_json_file"

    jq -nc \
      --arg index "$page_index" \
      --arg ref "$page_ref" \
      --arg label "$page_label" \
      --arg sourceUrl "$URL" \
      --arg scopeType "$SCOPE_TYPE" \
      --arg scopeValue "$SCOPE_VALUE" \
      --arg snapshotPath "$snapshot_file" \
      --arg rawTextPath "$raw_text_file" \
      --argjson ancestors "$page_ancestors" \
      --argjson path "$page_path" \
      --slurpfile raw "$raw_json_file" \
      --slurpfile risk "$risk_json_file" \
      '{
        index: ($index | tonumber),
        ref: $ref,
        label: $label,
        sourceUrl: $sourceUrl,
        scopeType: $scopeType,
        scopeValue: $scopeValue,
        ancestors: $ancestors,
        path: $path,
        snapshotPath: $snapshotPath,
        rawTextPath: $rawTextPath,
        bodyRef: $raw[0].bodyRef,
        lines: $raw[0].lines,
        rawText: $raw[0].rawText,
        semanticSnapshot: $raw[0].semanticSnapshot,
        riskLevel: $risk[0].riskLevel,
        needsScreenshot: $risk[0].needsScreenshot,
        screenshotRecommendation: $risk[0].screenshotRecommendation,
        riskAssessment: $risk[0]
      }' > "$page_json_file"

    capture_screenshot_if_requested "$page_dir" "$page_json_file" "$page_label"
    python3 "$ISSUE_PARSER" "$page_json_file" > "$issue_json_file"
    jq \
      --slurpfile issues "$issue_json_file" \
      '. + {
        needsManualReview: $issues[0].needsManualReview,
        suspectedIssues: $issues[0].suspectedIssues,
        issueExtraction: $issues[0]
      }' "$page_json_file" > "$page_tmp_json"
    mv "$page_tmp_json" "$page_json_file"
    normalize_page_json "$page_json_file"
    cleanup_page_artifacts "$page_dir"
  done

  jq -s '.' "$OUTPUT_DIR"/page-*/page.json > "$PAGES_JSON"
  python3 "$BREAKDOWN_EXPORTER" "$PAGES_JSON" "$OUTPUT_DIR" "$OUTPUT_MODE"
  write_extraction_summary "legacy-fallback" true "legacy-bash"
  cleanup_output_artifacts
  apply_output_mode_cleanup
}

main() {
  # 新的 Node Playwright collector 是主路径；只有“可恢复且被 allowlist 接受”的失败，
  # 才回退到历史 Bash/snapshot 链路，避免把真正的主链路问题偷偷吃掉。
  local rc
  if extract_single_page_direct; then
    return 0
  else
    rc=$?
  fi
  if [[ $rc -eq 2 ]]; then
    return 1
  fi

  if extract_pages_direct; then
    return 0
  else
    rc=$?
  fi
  if [[ $rc -eq 2 ]]; then
    return 1
  fi

  extract_pages_legacy
}

main "$@"
