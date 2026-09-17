#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime_home="${RESUME_BUILDER_HOME:-$HOME/Library/Application Support/resume-builder}"
if [[ "${1:-}" == '--runtime-home' ]]; then runtime_home="$2"; shift 2; fi
script="${1:-}"; shift || true
case "$script" in serve|render|session|wait_for_event|validate_project|bootstrap_runtime) ;;
  *) printf 'Usage: run.sh [--runtime-home PATH] serve|render|session|wait_for_event|validate_project|bootstrap_runtime [args]\n' >&2; exit 2 ;;
esac
python_exe=""
if [[ -f "$runtime_home/runtime-state.json" ]]; then
  python_exe="$(/usr/bin/plutil -extract python.executable raw -o - "$runtime_home/runtime-state.json" 2>/dev/null || true)"
fi
if [[ ! -x "$python_exe" ]]; then
  version="$(/usr/bin/plutil -extract python.version raw -o - "$script_dir/../assets/runtime-manifest.json")"
  case "$(uname -m)" in arm64|aarch64) arch=arm64 ;; *) arch=x64 ;; esac
  python_exe="$runtime_home/python-$version-$arch/bin/python3"
fi
if [[ ! -x "$python_exe" ]]; then python_exe="$(command -v python3 || command -v python || true)"; fi
[[ -n "$python_exe" ]] || { printf 'Python unavailable. Run bootstrap.sh first.\n' >&2; exit 1; }
export RESUME_BUILDER_HOME="$runtime_home"
export PYTHONUTF8=1
exec "$python_exe" "$script_dir/$script.py" "$@"
