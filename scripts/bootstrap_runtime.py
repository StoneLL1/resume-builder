"""Install/check pinned Typst and fonts in the resume-builder user cache.

This helper is invoked by bootstrap.ps1/bootstrap.sh after they have found or
installed Python.  It uses only the standard library and consumes the single
source of truth in assets/runtime-manifest.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform as platform_mod
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
import uuid
import zipfile


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "assets" / "runtime-manifest.json"
PLATFORMS = {"windows-x64", "windows-arm64", "mac-x64", "mac-arm64"}


class BootstrapError(RuntimeError):
    pass


def runtime_home() -> Path:
    override = os.environ.get("RESUME_BUILDER_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "resume-builder"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "resume-builder"
    return Path.home() / ".local" / "share" / "resume-builder"


def platform_key() -> str:
    machine = platform_mod.machine().lower()
    arch = "arm64" if machine in {"arm64", "aarch64"} else "x64" if machine in {"amd64", "x86_64"} else ""
    system = platform_mod.system().lower()
    prefix = "windows" if system == "windows" else "mac" if system == "darwin" else ""
    key = f"{prefix}-{arch}"
    if key not in PLATFORMS:
        raise BootstrapError(f"不支持的平台：system={system!r}, machine={machine!r}")
    return key


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_artifact(artifact: object, label: str) -> None:
    if not isinstance(artifact, dict):
        raise BootstrapError(f"运行时清单缺少 {label} 对象。")
    for key in ("filename", "url", "sha256"):
        value = artifact.get(key)
        if not isinstance(value, str) or not value:
            raise BootstrapError(f"运行时清单 {label}.{key} 必须是非空字符串。")
    if len(artifact["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in artifact["sha256"]):
        raise BootstrapError(f"运行时清单 {label}.sha256 非法。")
    if not artifact["url"].startswith(("https://", "file://")):
        raise BootstrapError(f"运行时清单 {label}.url 必须使用 HTTPS（测试可用 file://）。")


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"无法读取运行时清单 {path}：{exc}") from exc
    if data.get("schema_version") != 1:
        raise BootstrapError("runtime-manifest.json 的 schema_version 必须为 1。")
    for resource in ("python", "typst"):
        platforms = data.get(resource, {}).get("platforms", {})
        missing = PLATFORMS - set(platforms)
        if missing:
            raise BootstrapError(f"运行时清单 {resource}.platforms 缺少：{sorted(missing)}")
        for key in PLATFORMS:
            _require_artifact(platforms[key], f"{resource}.platforms.{key}")
    fonts = data.get("fonts", {}).get("files")
    if not isinstance(fonts, list) or not fonts:
        raise BootstrapError("运行时清单 fonts.files 必须是非空数组。")
    names: set[str] = set()
    for index, font in enumerate(fonts):
        _require_artifact(font, f"fonts.files[{index}]")
        if "archive" in font:
            _require_artifact(font["archive"], f"fonts.files[{index}].archive")
            if not isinstance(font["archive"].get("member"), str) or not font["archive"]["member"]:
                raise BootstrapError(f"字体压缩包缺少成员路径：{index}")
        name = font["filename"]
        if PurePosixPath(name).name != name or name in names:
            raise BootstrapError(f"字体目标文件名非法或重复：{name!r}")
        names.add(name)
    return data


def _resolved_urls(url: str, mirror: str | None) -> list[str]:
    if not mirror or url.startswith("file://"):
        return [url]
    mirror = mirror.strip()
    mirrored = mirror.replace("{url}", url) if "{url}" in mirror else f"{mirror.rstrip('/')}/{url}"
    return [mirrored, url]


def download(artifact: dict, cache_dir: Path, mirror: str | None, force: bool = False) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / artifact["filename"]
    expected = artifact["sha256"]
    if not force and target.is_file() and sha256(target) == expected:
        print(f"[bootstrap] 使用已校验缓存：{target.name}")
        return target

    errors: list[str] = []
    for url in _resolved_urls(artifact["url"], mirror):
        part = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
        try:
            print(f"[bootstrap] 下载：{url}")
            request = Request(url, headers={"User-Agent": "resume-builder-v2-bootstrap/1"})
            with urlopen(request, timeout=60) as response, part.open("wb") as out:
                shutil.copyfileobj(response, out, length=1024 * 1024)
            actual = sha256(part)
            if actual != expected:
                raise BootstrapError(
                    f"SHA-256 不匹配：{artifact['filename']}\n期望 {expected}\n实际 {actual}"
                )
            os.replace(part, target)
            return target
        except (OSError, URLError, BootstrapError) as exc:
            errors.append(f"{url}: {exc}")
            try:
                part.unlink()
            except FileNotFoundError:
                pass
    raise BootstrapError("下载失败（镜像与官方源均不可用）：\n- " + "\n- ".join(errors))


def _copy_typst_binary(archive: Path, archive_format: str, executable_name: str, target: Path) -> None:
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if archive_format == "zip":
            with zipfile.ZipFile(archive) as bundle:
                matches = [name for name in bundle.namelist() if PurePosixPath(name).name == executable_name]
                if len(matches) != 1:
                    raise BootstrapError(f"{archive.name} 中 typst 可执行文件数量异常：{matches}")
                with bundle.open(matches[0]) as source, temp.open("wb") as out:
                    shutil.copyfileobj(source, out)
        elif archive_format == "tar.xz":
            with tarfile.open(archive, "r:xz") as bundle:
                matches = [m for m in bundle.getmembers() if m.isfile() and PurePosixPath(m.name).name == executable_name]
                if len(matches) != 1:
                    raise BootstrapError(f"{archive.name} 中 typst 可执行文件数量异常。")
                source = bundle.extractfile(matches[0])
                if source is None:
                    raise BootstrapError(f"无法从 {archive.name} 读取 {executable_name}。")
                with source, temp.open("wb") as out:
                    shutil.copyfileobj(source, out)
        else:
            raise BootstrapError(f"不支持的 Typst 归档格式：{archive_format!r}")
        temp.chmod(temp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(temp, target)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _typst_version(path: Path) -> str | None:
    try:
        proc = subprocess.run([str(path), "--version"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (proc.stdout + proc.stderr).strip() if proc.returncode == 0 else None


def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def check_runtime(manifest: dict, home: Path, key: str) -> list[str]:
    problems: list[str] = []
    minimum = tuple(int(part) for part in manifest["minimum_python"].split("."))
    if sys.version_info[:2] < minimum:
        problems.append(f"Python {sys.version_info.major}.{sys.version_info.minor} < {manifest['minimum_python']}")
    typst_name = manifest["typst"]["platforms"][key]["executable_name"]
    typst_path = home / "bin" / typst_name
    version = _typst_version(typst_path)
    if not version or manifest["typst"]["version"] not in version:
        problems.append(f"Typst 缺失或版本不符：{typst_path}")
    for font in manifest["fonts"]["files"]:
        path = home / "fonts" / font["filename"]
        if not path.is_file() or sha256(path) != font["sha256"]:
            problems.append(f"字体缺失或校验失败：{font['filename']}")
    return problems


def install_font(font: dict, target: Path, cache: Path,
                 mirror: str | None = None, force: bool = False) -> None:
    """Install one original font, verifying both the archive and extracted member."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
    try:
        if font.get("archive"):
            archived = download(font["archive"], cache, mirror, force=force)
            with zipfile.ZipFile(archived) as archive:
                temp.write_bytes(archive.read(font["archive"]["member"]))
        else:
            cached = download(font, cache, mirror, force=force)
            shutil.copy2(cached, temp)
        if sha256(temp) != font["sha256"]:
            raise BootstrapError(f"字体文件校验失败：{font['filename']}")
        os.replace(temp, target)
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise BootstrapError(f"无法安装原字体 {font['filename']}：{exc}") from exc
    finally:
        temp.unlink(missing_ok=True)


def install_runtime(manifest: dict, home: Path, key: str,
                    mirror: str | None = None, force: bool = False) -> dict:
    home.mkdir(parents=True, exist_ok=True)
    cache = home / "downloads"
    state_path = home / "runtime-state.json"
    old_state = _load_state(state_path)

    typst = manifest["typst"]
    artifact = typst["platforms"][key]
    typst_path = home / "bin" / artifact["executable_name"]
    version = _typst_version(typst_path)
    typst_valid = (
        not force
        and version is not None
        and typst["version"] in version
        and old_state.get("typst", {}).get("archive_sha256") == artifact["sha256"]
    )
    if typst_valid:
        print(f"[bootstrap] Typst 已就绪：{version}")
    else:
        archive = download(artifact, cache, mirror, force=force)
        _copy_typst_binary(archive, artifact["archive_format"], artifact["executable_name"], typst_path)
        if sys.platform == "darwin" and shutil.which("xattr"):
            subprocess.run(["xattr", "-d", "com.apple.quarantine", str(typst_path)],
                           capture_output=True, check=False)
        version = _typst_version(typst_path)
        if not version or typst["version"] not in version:
            raise BootstrapError(f"Typst 安装后版本检查失败：{version!r}")
        print(f"[bootstrap] Typst 安装完成：{version}")

    font_dir = home / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    installed_fonts: list[dict] = []
    for font in manifest["fonts"]["files"]:
        target = font_dir / font["filename"]
        if not force and target.is_file() and sha256(target) == font["sha256"]:
            print(f"[bootstrap] 字体已就绪：{font['filename']}")
        else:
            install_font(font, target, cache, mirror=mirror, force=force)
            print(f"[bootstrap] 字体安装完成：{font['filename']}")
        installed_fonts.append({"filename": font["filename"], "sha256": font["sha256"]})

    state = {
        "schema_version": 1,
        "runtime_version": manifest["runtime_version"],
        "platform": key,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": {"version": platform_mod.python_version(), "executable": sys.executable},
        "typst": {"version": typst["version"], "archive_sha256": artifact["sha256"],
                  "executable": str(typst_path)},
        "fonts": installed_fonts,
    }
    _write_state(state_path, state)
    problems = check_runtime(manifest, home, key)
    if problems:
        raise BootstrapError("安装后自检失败：\n- " + "\n- ".join(problems))
    return state


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--runtime-home")
    parser.add_argument("--platform", choices=sorted(PLATFORMS))
    parser.add_argument("--mirror", default=os.environ.get("RESUME_BUILDER_DOWNLOAD_MIRROR"),
                        help="下载镜像前缀；可含 {url} 占位符，失败后回退官方 URL")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true", help="只校验现有运行时，不下载或修改")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        manifest = load_manifest(Path(args.manifest).resolve())
        home = Path(args.runtime_home).expanduser().resolve() if args.runtime_home else runtime_home()
        key = args.platform or platform_key()
        if args.check:
            problems = check_runtime(manifest, home, key)
            result = {"ok": not problems, "runtime_home": str(home), "platform": key, "problems": problems}
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            elif problems:
                print("[bootstrap] 自检失败：\n- " + "\n- ".join(problems), file=sys.stderr)
            else:
                print(f"[bootstrap] 自检通过：{home}")
            return 1 if problems else 0
        state = install_runtime(manifest, home, key, mirror=args.mirror, force=args.force)
        if args.json:
            print(json.dumps({"ok": True, "runtime_home": str(home), "state": state}, ensure_ascii=False))
        else:
            print(f"[bootstrap] 完成：{home}")
        return 0
    except BootstrapError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"[bootstrap] 失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
