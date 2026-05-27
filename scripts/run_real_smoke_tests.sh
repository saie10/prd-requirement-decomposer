#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTRACT_SCRIPT="$SCRIPT_DIR/extract_prd_pages.sh"
VERIFY_SCRIPT="$SCRIPT_DIR/verify_smoke_output.py"
OUT_ROOT="${PRD_SMOKE_ROOT:-/private/tmp/prd-real-smoke}"
MODE="${PRD_SMOKE_OUTPUT_MODE:-standard}"
WITH_SCREENSHOT=0
REQUIRE_PRIMARY="${PRD_SMOKE_REQUIRE_PRIMARY:-true}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-screenshot)
      WITH_SCREENSHOT=1
      shift
      ;;
    --output-mode)
      [[ $# -ge 2 ]] || { echo "--output-mode requires a value" >&2; exit 1; }
      MODE="$2"
      shift 2
      ;;
    *)
      break
      ;;
  esac
done

CASE_NAME="${1:-all}"

mkdir -p "$OUT_ROOT"

run_case() {
  local name="$1"
  local scope_type="$2"
  local expected_collector="$3"
  shift 3
  local out_dir="$OUT_ROOT/$name"
  rm -rf "$out_dir"
  echo "==> Running smoke case: $name"
  if (( WITH_SCREENSHOT == 1 )); then
    "$EXTRACT_SCRIPT" --output-mode "$MODE" --with-screenshot "$@" "$out_dir"
  else
    "$EXTRACT_SCRIPT" --output-mode "$MODE" "$@" "$out_dir"
  fi
  python3 "$VERIFY_SCRIPT" "$out_dir" "$scope_type" "$([[ $WITH_SCREENSHOT -eq 1 ]] && echo true || echo false)" "$MODE" "$REQUIRE_PRIMARY" "$expected_collector"
  if [[ -f "$out_dir/extraction-summary.json" ]]; then
    echo "    path: $(jq -r '.mode' "$out_dir/extraction-summary.json") / $(jq -r '.collectorKind' "$out_dir/extraction-summary.json")"
  fi
  echo "    saved: $out_dir"
}

case "$CASE_NAME" in
  axhub-page)
    run_case "axhub-page" "page" "single-page-node" \
      --scope-page "15899·指标卡支持选择时间范围、适配查询粒度、自定义数值格式" \
      "https://axhub.im/ax9/88a869475d1591b8/#id=u3oj9e&p=15899%C2%B7%E6%8C%87%E6%A0%87%E5%8D%A1%E6%94%AF%E6%8C%81%E9%80%89%E6%8B%A9%E6%97%B6%E9%97%B4%E8%8C%83%E5%9B%B4%E3%80%81%E9%80%82%E9%85%8D%E6%9F%A5%E8%AF%A2%E7%B2%92%E5%BA%A6%E3%80%81%E8%87%AA%E5%AE%9A%E4%B9%89%E6%95%B0%E5%80%BC%E6%A0%BC%E5%BC%8F&g=1"
    ;;
  axhub-dir)
    run_case "axhub-dir" "dir" "multi-page-node" \
      --scope-dir "紧急需求427新增——520上线" \
      "https://axhub.im/ax9/88a869475d1591b8/#g=1&id=4o2e14&p=15900%C2%B7%E6%8C%87%E6%A0%87%E7%9C%8B%E6%9D%BF%E5%90%8C%E7%8E%AF%E6%AF%94%E5%8A%9F%E8%83%BD%E9%80%82%E9%85%8D"
    ;;
  modao-page)
    run_case "modao-page" "page" "single-page-node" \
      --scope-page "15686·自助取数-新增明细查询" \
      "https://modao.cc/axbox/share/A8gSs7CCtdfpdeZHeNf4iI?screen=wstu2q&s=0"
    ;;
  modao-dir)
    run_case "modao-dir" "dir" "multi-page-node" \
      --scope-dir "第一批交付（4.24 上线V6.2）" \
      "https://modao.cc/axbox/share/A8gSs7CCtdfpdeZHeNf4iI?screen=wstu2q&s=0"
    ;;
  all)
    all_args=()
    if (( WITH_SCREENSHOT == 1 )); then
      all_args+=(--with-screenshot)
    fi
    all_args+=(--output-mode "$MODE")
    "$0" "${all_args[@]}" axhub-page
    "$0" "${all_args[@]}" axhub-dir
    "$0" "${all_args[@]}" modao-page
    "$0" "${all_args[@]}" modao-dir
    ;;
  *)
    echo "Unknown smoke case: $CASE_NAME" >&2
    echo "Use one of: axhub-page | axhub-dir | modao-page | modao-dir | all" >&2
    exit 1
    ;;
esac
