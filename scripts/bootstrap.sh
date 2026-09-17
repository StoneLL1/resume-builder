#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
v2_root="$(cd "$script_dir/.." && pwd)"
manifest_path="$v2_root/assets/runtime-manifest.json"
runtime_home="${RESUME_BUILDER_HOME:-$HOME/Library/Application Support/resume-builder}"
mirror="${RESUME_BUILDER_DOWNLOAD_MIRROR:-}"
force=0
check=0
template=""
all_fonts=0
offline_dir="${RESUME_BUILDER_OFFLINE_DIR:-}"

usage() {
  printf '%s\n' "Usage: bootstrap.sh [--runtime-home PATH] [--mirror PREFIX] [--force] [--check]"
}

while (($#)); do
  case "$1" in
    --runtime-home) runtime_home="$2"; shift 2 ;;
    --mirror) mirror="$2"; shift 2 ;;
    --force) force=1; shift ;;
    --check) check=1; shift ;;
    --template) template="$2"; shift 2 ;;
    --all-fonts) all_fonts=1; shift ;;
    --offline-dir) offline_dir="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf '[bootstrap] Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$(uname -m)" in
  arm64|aarch64) platform_key="mac-arm64"; arch_key="arm64" ;;
  x86_64|amd64) platform_key="mac-x64"; arch_key="x64" ;;
  *) printf '[bootstrap] Unsupported macOS CPU architecture: %s\n' "$(uname -m)" >&2; exit 1 ;;
esac

python_ok() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

python_exe=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && python_ok "$(command -v "$candidate")"; then
    python_exe="$(command -v "$candidate")"
    break
  fi
done

json_get() {
  /usr/bin/plutil -extract "$1" raw -o - "$manifest_path"
}

resolve_urls() {
  local url="$1"
  if [[ -n "$mirror" ]]; then
    if [[ "$mirror" == *'{url}'* ]]; then
      printf '%s\n' "${mirror//\{url\}/$url}"
    else
      printf '%s\n' "${mirror%/}/$url"
    fi
  fi
  printf '%s\n' "$url"
}

download_python() {
  local filename url expected target part actual fetched=0
  filename="$(json_get "python.platforms.$platform_key.filename")"
  url="$(json_get "python.platforms.$platform_key.url")"
  expected="$(json_get "python.platforms.$platform_key.sha256")"
  mkdir -p "$runtime_home/downloads"
  target="$runtime_home/downloads/$filename"
  if [[ $force -eq 0 && -f "$target" ]] && [[ "$(shasum -a 256 "$target" | awk '{print $1}')" == "$expected" ]]; then
    printf '[bootstrap] Using verified cache: %s\n' "$filename"
    printf '%s\n' "$target"
    return
  fi
  if [[ -n "$offline_dir" ]]; then
    local source="$offline_dir/$filename"
    if [[ ! -f "$source" ]] || [[ "$(shasum -a 256 "$source" | awk '{print $1}')" != "$expected" ]]; then
      printf '[bootstrap] Missing or invalid offline artifact: %s (network disabled)\n' "$filename" >&2
      exit 1
    fi
    [[ "$source" == "$target" ]] || cp "$source" "$target"
    printf '%s\n' "$target"
    return
  fi
  while IFS= read -r candidate_url; do
    part="$runtime_home/downloads/.$filename.$$.part"
    printf '[bootstrap] Downloading Python: %s\n' "$candidate_url" >&2
    if /usr/bin/curl --fail --location --retry 2 --connect-timeout 15 --max-time 180 --output "$part" "$candidate_url"; then
      actual="$(shasum -a 256 "$part" | awk '{print $1}')"
      if [[ "$actual" == "$expected" ]]; then
        mv -f "$part" "$target"
        fetched=1
        break
      fi
      printf '[bootstrap] SHA-256 mismatch for %s (expected %s, got %s)\n' "$filename" "$expected" "$actual" >&2
    fi
    rm -f -- "$part"
  done < <(resolve_urls "$url")
  if [[ $fetched -ne 1 ]]; then
    printf '[bootstrap] Python download failed via mirror and official URL.\n' >&2
    exit 1
  fi
  printf '%s\n' "$target"
}

if [[ -z "$python_exe" ]]; then
  python_version="$(json_get 'python.version')"
  python_root="$runtime_home/python-$python_version-$arch_key"
  python_exe="$python_root/bin/python3"
  if [[ $force -eq 0 && -x "$python_exe" ]] && python_ok "$python_exe"; then
    printf '[bootstrap] Managed Python is ready: %s\n' "$python_exe"
  else
    if [[ $check -eq 1 ]]; then
      printf '[bootstrap] Python 3.10+ not found; --check does not install anything.\n' >&2
      exit 1
    fi
    archive="$(download_python | tail -n 1)"
    mkdir -p "$runtime_home"
    staging="$runtime_home/.python-staging-$$"
    case "$staging" in "$runtime_home"/.python-staging-*) ;; *) exit 1 ;; esac
    trap '[[ -n "${staging:-}" && -d "${staging:-}" ]] && rm -rf -- "$staging"' EXIT INT TERM
    mkdir -p "$staging"
    /usr/bin/tar -xzf "$archive" -C "$staging"
    if [[ ! -x "$staging/python/bin/python3" ]]; then
      printf '[bootstrap] Invalid Python archive layout.\n' >&2
      exit 1
    fi
    if [[ -e "$python_root" ]]; then
      mv "$python_root" "$python_root.invalid.$(date +%s)"
    fi
    mv "$staging/python" "$python_root"
    chmod +x "$python_exe"
    if command -v xattr >/dev/null 2>&1; then
      xattr -dr com.apple.quarantine "$python_root" 2>/dev/null || true
    fi
    rm -rf -- "$staging"
    staging=""
    trap - EXIT INT TERM
    python_ok "$python_exe" || { printf '[bootstrap] Managed Python failed to start.\n' >&2; exit 1; }
    printf '[bootstrap] Python installed: %s\n' "$python_exe"
  fi
fi

args=(
  "$script_dir/bootstrap_runtime.py"
  --manifest "$manifest_path"
  --runtime-home "$runtime_home"
  --platform "$platform_key"
)
[[ -n "$mirror" ]] && args+=(--mirror "$mirror")
[[ $force -eq 1 ]] && args+=(--force)
[[ $check -eq 1 ]] && args+=(--check)
[[ -n "$template" ]] && args+=(--template "$template")
[[ $all_fonts -eq 1 ]] && args+=(--all-fonts)
[[ -n "$offline_dir" ]] && args+=(--offline-dir "$offline_dir")
"$python_exe" "${args[@]}"

export RESUME_BUILDER_HOME="$runtime_home"
export RESUME_BUILDER_TYPST="$runtime_home/bin/typst"
chmod +x "$runtime_home/bin/typst"
if command -v xattr >/dev/null 2>&1; then
  xattr -d com.apple.quarantine "$runtime_home/bin/typst" 2>/dev/null || true
fi
printf '[bootstrap] RESUME_BUILDER_HOME=%s\n' "$runtime_home"
printf '[bootstrap] Browser opening uses macOS /usr/bin/open via Python webbrowser.\n'
printf '[bootstrap] Start with: "%s" "%s/serve.py" "<project-directory>"\n' "$python_exe" "$script_dir"
