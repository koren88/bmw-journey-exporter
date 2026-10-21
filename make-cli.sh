#!/bin/sh
# Thin, argument-safe adapter from Make variables to the existing Python CLI.
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$project_dir"
action=${1:-help}
python_was_overridden=${PYTHON+x}
PYTHON=${PYTHON:-python3}
YEAR=${YEAR:-}
MONTH=${MONTH:-}
FROM=${FROM:-}
TO=${TO:-}
OUTPUT=${OUTPUT:-}
SERIAL=${SERIAL:-}
TIMEZONE=${TIMEZONE:-}
PAUSE=${PAUSE:-}
MAX_PAGES=${MAX_PAGES:-}
KEEP_AWAKE=${KEEP_AWAKE:-}
INPUT=${INPUT:-}
INPUTS=${INPUTS:-}
CONFLICT=${CONFLICT:-}
FORMATS=${FORMATS:-}
KEEP_CAPTURE=${KEEP_CAPTURE:-}
KEEP_DEBUG=${KEEP_DEBUG:-}

show_args() {
  if [ "${BMW_MAKE_DRY_RUN:-0}" = 1 ]; then
    for arg do printf 'ARG:%s\n' "$arg"; done
    exit 0
  fi
}

platform_launcher() {
  case "$(uname -s)" in
    Darwin) printf '%s\n' "$project_dir/docker-macos.sh" ;;
    Linux) printf '%s\n' "$project_dir/docker-linux.sh" ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
      echo 'Make capture/report/merge launchers are supported on macOS and Linux. On Windows, use the documented native Python/PowerShell or WSL instructions.' >&2
      exit 2 ;;
    *)
      echo "Unsupported platform $(uname -s). Use the documented local Python CLI." >&2
      exit 2 ;;
  esac
}

case "$action" in
  setup)
    case "$(uname -s)" in Darwin|Linux) ;; *) echo 'make setup supports macOS/Linux shells; use the documented Windows Python setup.' >&2; exit 2 ;; esac
    command -v "$PYTHON" >/dev/null 2>&1 || { echo "Python command '$PYTHON' was not found. Install Python 3.9+ or use Docker for capture." >&2; exit 2; }
    "$PYTHON" -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    ;;
  doctor)
    set -- --doctor
    if [ -n "${SERIAL:-}" ]; then set -- "$@" --serial "$SERIAL"; fi
    show_args "$@"
    launcher=$(platform_launcher)
    exec "$launcher" "$@"
    ;;
  capture|resume)
    set --
    if [ "$action" = resume ]; then
      [ -n "${OUTPUT:-}" ] || { echo 'make resume requires OUTPUT=./existing-capture.' >&2; exit 2; }
      [ -d "$OUTPUT" ] || { echo "Resume directory does not exist: $OUTPUT" >&2; exit 2; }
      set -- --resume --output "$OUTPUT"
    else
      if [ -n "${OUTPUT:-}" ]; then
        [ ! -e "$OUTPUT" ] || { echo "Output already exists: $OUTPUT (use make resume OUTPUT='$OUTPUT' to continue)." >&2; exit 2; }
        set -- --output "$OUTPUT"
      else
        stamp=$(date '+%Y%m%d-%H%M%S')
        candidate="./bmw-export-${stamp}-$$"
        suffix=1
        while [ -e "$candidate" ]; do candidate="./bmw-export-${stamp}-$$-${suffix}"; suffix=$((suffix + 1)); done
        OUTPUT=$candidate
        set -- --output "$OUTPUT"
      fi
    fi
    if [ -n "${YEAR:-}" ]; then set -- "$@" --year "$YEAR"; fi
    if [ -n "${MONTH:-}" ]; then set -- "$@" --month "$MONTH"; fi
    if [ -n "${FROM:-}" ]; then set -- "$@" --from-month "$FROM"; fi
    if [ -n "${TO:-}" ]; then set -- "$@" --to-month "$TO"; fi
    if [ -n "${SERIAL:-}" ]; then set -- "$@" --serial "$SERIAL"; fi
    if [ -n "${TIMEZONE:-}" ]; then set -- "$@" --timezone "$TIMEZONE"; fi
    if [ -n "${PAUSE:-}" ]; then set -- "$@" --pause "$PAUSE"; fi
    if [ -n "${MAX_PAGES:-}" ]; then set -- "$@" --max-pages "$MAX_PAGES"; fi
    if [ -n "${FORMATS:-}" ]; then set -- "$@" --formats "$FORMATS"; fi
    case "${KEEP_AWAKE:-}" in
      1|true|TRUE|yes|YES|on|ON) set -- "$@" --keep-awake ;;
      0|false|FALSE|no|NO|off|OFF) if [ "$action" = resume ]; then set -- "$@" --no-keep-awake; fi ;;
      '') ;;
      *) echo 'KEEP_AWAKE must be one of 1/0, true/false, yes/no, or on/off.' >&2; exit 2 ;;
    esac
    case "${KEEP_CAPTURE:-}" in
      1|true|TRUE|yes|YES|on|ON) set -- "$@" --keep-capture ;;
      0|false|FALSE|no|NO|off|OFF) if [ "$action" = resume ]; then set -- "$@" --no-keep-capture; fi ;;
      '') ;;
      *) echo 'KEEP_CAPTURE must be one of 1/0, true/false, yes/no, or on/off.' >&2; exit 2 ;;
    esac
    case "${KEEP_DEBUG:-}" in
      1|true|TRUE|yes|YES|on|ON) set -- "$@" --keep-debug ;;
      0|false|FALSE|no|NO|off|OFF) if [ "$action" = resume ]; then set -- "$@" --no-keep-debug; fi ;;
      '') ;;
      *) echo 'KEEP_DEBUG must be one of 1/0, true/false, yes/no, or on/off.' >&2; exit 2 ;;
    esac
    show_args "$@"
    launcher=$(platform_launcher)
    exec "$launcher" "$@"
    ;;
  report)
    [ -n "${INPUT:-}" ] || { echo 'make report requires INPUT=./existing-capture.' >&2; exit 2; }
    set -- --report-only "$INPUT"
    if [ -n "${FORMATS:-}" ]; then set -- "$@" --formats "$FORMATS"; fi
    show_args "$@"
    launcher=$(platform_launcher)
    exec "$launcher" "$@"
    ;;
  merge)
    [ -n "${INPUTS:-}" ] || { echo 'make merge requires INPUTS=path1:path2.' >&2; exit 2; }
    [ -n "${OUTPUT:-}" ] || { echo 'make merge requires OUTPUT=./new-directory.' >&2; exit 2; }
    temp_inputs=$(mktemp "${TMPDIR:-/tmp}/bmw-merge-inputs.XXXXXX")
    trap 'rm -f "$temp_inputs"' EXIT HUP INT TERM
    # Colon-separated paths preserve whitespace without eval or shell re-parsing.
    printf '%s' "$INPUTS" | awk -F: '{ for (i = 1; i <= NF; i++) if (length($i)) print $i; else exit 2 }' > "$temp_inputs" || { echo 'INPUTS must be colon-separated non-empty paths.' >&2; exit 2; }
    set --
    while IFS= read -r input_path; do set -- "$@" --merge "$input_path"; done < "$temp_inputs"
    [ "$#" -gt 0 ] || { echo 'INPUTS must name at least one capture directory.' >&2; exit 2; }
    set -- "$@" --output "$OUTPUT"
    if [ -n "${CONFLICT:-}" ]; then set -- "$@" --conflict "$CONFLICT"; fi
    if [ -n "${FORMATS:-}" ]; then set -- "$@" --formats "$FORMATS"; fi
    case "${KEEP_CAPTURE:-}" in
      1|true|TRUE|yes|YES|on|ON) set -- "$@" --keep-capture ;;
      0|false|FALSE|no|NO|off|OFF) set -- "$@" --no-keep-capture ;;
      '') ;;
      *) echo 'KEEP_CAPTURE must be one of 1/0, true/false, yes/no, or on/off.' >&2; exit 2 ;;
    esac
    case "${KEEP_DEBUG:-}" in
      1|true|TRUE|yes|YES|on|ON) set -- "$@" --keep-debug ;;
      0|false|FALSE|no|NO|off|OFF) set -- "$@" --no-keep-debug ;;
      '') ;;
      *) echo 'KEEP_DEBUG must be one of 1/0, true/false, yes/no, or on/off.' >&2; exit 2 ;;
    esac
    rm -f "$temp_inputs"
    trap - EXIT HUP INT TERM
    show_args "$@"
    launcher=$(platform_launcher)
    exec "$launcher" "$@"
    ;;
  test)
    if [ -n "$python_was_overridden" ]; then
      test_python=$PYTHON
    elif [ -x "$project_dir/.venv/bin/python" ]; then
      test_python=$project_dir/.venv/bin/python
    else
      test_python=python3
    fi
    if command -v "$test_python" >/dev/null 2>&1 && "$test_python" -c 'import openpyxl, zoneinfo' >/dev/null 2>&1; then
      exec "$test_python" -m unittest discover -s tests -v
    fi
    if command -v docker >/dev/null 2>&1; then
      exec "$project_dir/docker-launch.sh" test
    fi
    if [ -n "$python_was_overridden" ]; then
      echo "PYTHON='$PYTHON' is not usable or is missing project dependencies. Install requirements in that environment, or unset PYTHON to use .venv/bin/python/python3 or Docker." >&2
    else
      echo 'Tests need Python with project dependencies. Run make setup, install requirements for python3, or install Docker for the documented fallback.' >&2
    fi
    exit 2
    ;;
  *)
    echo "Unknown make action: $action" >&2
    exit 2
    ;;
esac
