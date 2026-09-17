"""resume-builder v2 — 渲染器：resume.json → Typst → SVG/PDF/layout-map.json。

用法：
    python scripts/render.py <项目目录> [--template <模板ID>] [--typst <typst路径>] [--json]

项目目录即 `<用途>/` 目录（内含 resume.json），产物写入
`<项目目录>/work/build/<revision>/`（成功后原子更新 current.json 指针）：
    page-{n}.svg      各页真实渲染（浏览器编辑器直接展示）
    resume.pdf        正式 PDF（导出时复制为规范文件名）
    layout-map.json   字段 ID → 页面矩形热区（点击编辑的依据）
    resume-data.typ   由 resume.json 自动生成，勿手改
    render-result.json 本次成功渲染摘要（页数、字段数、耗时）
最新尝试的摘要写入 work/render-result.json；失败不会覆盖上次成功的预览。

模板与渲染约定：
- 模板目录 assets/templates/<id>/（manifest.json + template.typ + preview.png
  + LICENSE + ATTRIBUTION.md）整体复制进 build，入口文件由 manifest.entry 指定，
  通过 main.typ 注入 resume-data.typ。
- 渲染前校验 manifest（语言模式、页数目标必须在模板能力范围内）。
- 模板用 editable(id, kind, body) 埋点，本脚本用
  `typst eval 'query(metadata).map(it => it.value)'` 读回坐标。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import hashlib
import uuid
from pathlib import Path
from local_io import file_lock, write_json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resume_model  # noqa: E402

V2_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(V2_ROOT, "assets", "templates")

MANIFEST_SCHEMA_VERSION = 1
TEMPLATE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
KNOWN_LANGUAGES = ("zh", "en", "bilingual")
KNOWN_PAGE_TARGETS = (1, 2)

# 热区最小宽度与外扩边距（pt）。
HOTZONE_PAD = 1.5


class RenderError(RuntimeError):
    pass


def runtime_home() -> str:
    """用户级运行时缓存根目录（bootstrap 安装 typst 与字体到此处）。

    RESUME_BUILDER_HOME 可整体覆盖（测试/便携部署用）；Windows 用
    %LOCALAPPDATA%\\resume-builder，与 find_typst 的约定位置一致。
    """
    env = os.environ.get("RESUME_BUILDER_HOME")
    if env:
        return env
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/AppData/Local")
        return os.path.join(base, "resume-builder")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/resume-builder")
    return os.path.expanduser("~/.local/share/resume-builder")


def font_path_args(build_dir: str | None = None) -> list[str]:
    """返回要附加给 typst 的 --font-path 参数对。

    原版字体来自模板 fonts/、固定运行时缓存或本机合法安装版本。
    缺少已声明的原字体由 check_original_fonts 拦截，不做替换。
    """
    dirs: list[str] = []
    if build_dir:
        local = os.path.join(build_dir, "fonts")
        if os.path.isdir(local):
            dirs.append(local)
    runtime_fonts = os.path.join(runtime_home(), "fonts")
    if os.path.isdir(runtime_fonts):
        dirs.append(runtime_fonts)
    args: list[str] = []
    for d in dirs:
        args += ["--font-path", d]
    packages = os.path.join(V2_ROOT, "assets", "typst-packages")
    if os.path.isdir(packages):
        args += ["--package-path", packages, "--package-cache-path", packages]
    return args


def check_original_fonts(typst: str, manifest: dict, build_dir: str) -> None:
    """Verify declared upstream families, including licensed fonts installed by the user."""
    if manifest.get("implementation") != "upstream-adapter":
        return
    args = ["fonts"]
    paths = font_path_args(build_dir)
    for index in range(0, len(paths), 2):
        if paths[index] == "--font-path":
            args.extend(paths[index:index + 2])
    available = {line.strip().casefold() for line in run_typst(typst, args, build_dir).splitlines()}
    required = {family for combo in manifest["fonts"].values()
                for family in combo["latin"] + combo["cjk"]}
    missing = sorted(family for family in required if family.casefold() not in available)
    if missing:
        raise RenderError(f"模板 {manifest['id']} 缺少原版字体：{', '.join(missing)}。"
                          f"\n请使用 bootstrap_runtime.py --template {manifest['id']} 安装此模板的开放字体。"
                          f"\n当前运行时目录：{runtime_home()}"
                          "\n系统字体需在本机合法安装，或返回画廊选择其他模板。不会替换原字体。")


# ── 模板契约（Batch 3）：manifest.json 加载与校验 ─────────────────────────────

def validate_manifest(data, template_dir: str, expect_id: str | None = None) -> list[str]:
    """校验 manifest.json 结构与所指文件的存在性，返回问题列表（空 = 通过）。

    结构问题与文件缺失分开报，
    便于一次列全（适配新模板时不用逐个试错）。
    """
    problems: list[str] = []

    def err(msg: str) -> None:
        problems.append(msg)

    def need_file(fname: str, what: str) -> None:
        if not isinstance(fname, str) or not fname:
            err(f"{what}路径必须是非空字符串。")
            return
        resolved = os.path.abspath(os.path.join(template_dir, fname))
        root = os.path.abspath(template_dir)
        if os.path.commonpath((root, resolved)) != root:
            err(f"{what}路径不能逃出模板目录：{fname}")
            return
        if not os.path.isfile(resolved):
            err(f"缺少{what}：{fname}")

    if not isinstance(data, dict):
        return ["manifest.json 顶层必须是 JSON 对象。"]
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        err(f"schema_version 必须为 {MANIFEST_SCHEMA_VERSION}，当前为 {data.get('schema_version')!r}。")

    tid = data.get("id")
    if not isinstance(tid, str) or not TEMPLATE_ID_RE.match(tid):
        err(f"id 非法：{tid!r}（需匹配 {TEMPLATE_ID_RE.pattern}）。")
    elif expect_id is not None and tid != expect_id:
        err(f"id 与目录名不一致：manifest 里是 {tid!r}，目录是 {expect_id!r}。")

    for key in ("name", "description"):
        if not isinstance(data.get(key), str) or not data.get(key, "").strip():
            err(f"{key} 必须是非空字符串。")

    if "gallery_language" in data and data["gallery_language"] not in ("zh", "en"):
        err("gallery_language 必须为 zh 或 en。")
    if data.get("gallery_language") == "en" and data.get("languages") != ["en"]:
        err("英文分类的 languages 必须为 [en]。")
    if data.get("gallery_language") == "zh" and data.get("languages") != ["zh"]:
        err("中文分类的 languages 必须为 [zh]。")

    entry = data.get("entry", "template.typ")
    if not isinstance(entry, str) or not entry:
        err("entry 必须是非空字符串（模板入口 .typ 文件）。")
    else:
        need_file(entry, "模板入口文件")

    languages = data.get("languages")
    if not isinstance(languages, list) or not languages or not set(languages) <= set(KNOWN_LANGUAGES):
        err(f"languages 必须是 {KNOWN_LANGUAGES} 的非空子集，当前为 {languages!r}。")

    pages = data.get("page_support")
    if not isinstance(pages, list) or not pages or not set(pages) <= set(KNOWN_PAGE_TARGETS):
        err(f"page_support 必须是 {KNOWN_PAGE_TARGETS} 的非空子集，当前为 {pages!r}。")

    license_ = data.get("license")
    if not isinstance(license_, dict) or not isinstance(license_.get("name"), str) or not license_.get("name"):
        err("license 必须是对象且含非空 name（如 \"MIT\"）。")
    else:
        need_file(license_.get("file", "LICENSE"), "许可证全文文件")
        need_file(license_.get("notice", "ATTRIBUTION.md"), "署名说明文件")

    # 字体配置：每种支持的语言都要显式声明拉丁/CJK 字体，禁止依赖系统回退
    fonts = data.get("fonts")
    if not isinstance(fonts, dict):
        err("fonts 必须是对象（按语言给出字体组合）。")
    elif isinstance(languages, list):
        for lang in languages:
            combo = fonts.get(lang)
            if not isinstance(combo, dict) or not isinstance(combo.get("latin"), list) or not combo.get("latin"):
                err(f"fonts.{lang} 必须含非空 latin 字体数组（显式声明，不依赖系统回退）。")
            elif not all(isinstance(name, str) and name for name in combo["latin"]):
                err(f"fonts.{lang}.latin 必须只含非空字体名。")
            elif not isinstance(combo.get("cjk"), list):
                err(f"fonts.{lang} 必须含 cjk 字体数组（纯西文模板可为空数组）。")
            elif lang in ("zh", "bilingual") and not combo["cjk"] and not data.get("native_default_cjk"):
                err(f"fonts.{lang}.cjk 不得为空（中文排版禁止依赖系统回退）。")
            elif not all(isinstance(name, str) and name for name in combo["cjk"]):
                err(f"fonts.{lang}.cjk 必须只含非空字体名。")

    tags = data.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        err("tags 必须是字符串数组（可选，缺省为空）。")

    layout = data.get("layout", {})
    if not isinstance(layout, dict):
        err("layout 必须是对象（可选，如 {\"columns\": 1, \"photo\": false}）。")

    upstream = data.get("upstream")
    if upstream is not None and (
        not isinstance(upstream, dict)
        or not isinstance(upstream.get("repo"), str)
        or not isinstance(upstream.get("commit"), str)
        or not re.match(r"^[0-9a-f]{7,40}$", upstream.get("commit", ""))
    ):
        err("upstream 为 null 或 {repo, commit}（commit 为 7-40 位十六进制）。")

    need_file(data.get("preview", "preview.png"), "画廊预览图")
    return problems


def load_manifest(template_id: str, templates_dir: str = TEMPLATES_DIR) -> dict:
    """加载并校验单个模板的 manifest.json，失败抛 RenderError（问题一次列全）。"""
    template_dir = os.path.join(templates_dir, template_id)
    manifest_path = os.path.join(template_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise RenderError(f"模板 {template_id} 缺少 manifest.json（{manifest_path}）。")
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise RenderError(f"模板 {template_id} 的 manifest.json 不是合法 JSON（第 {exc.lineno} 行：{exc.msg}）。")
    problems = validate_manifest(data, template_dir, expect_id=template_id)
    if problems:
        raise RenderError(f"模板 {template_id} 的 manifest.json 未通过契约校验：\n- " + "\n- ".join(problems))
    return data


def list_templates(templates_dir: str = TEMPLATES_DIR) -> dict:
    """枚举模板目录 → {templates: [manifest...], invalid: [{id, problems}]}。

    画廊（serve.py /api/templates）只用校验通过的模板；损坏模板单独上报，
    不让一个坏模板拖垮整个画廊。
    """
    valid: list[dict] = []
    invalid: list[dict] = []
    if not os.path.isdir(templates_dir):
        return {"templates": valid, "invalid": invalid}
    for name in sorted(os.listdir(templates_dir)):
        template_dir = os.path.join(templates_dir, name)
        if not os.path.isdir(template_dir) or name.startswith("."):
            continue
        try:
            valid.append(load_manifest(name, templates_dir))
        except RenderError as exc:
            invalid.append({"id": name, "problems": str(exc).splitlines()})
    return {"templates": valid, "invalid": invalid}


def check_template_compatibility(manifest: dict, meta: dict) -> list[str]:
    """resume.json 的 meta 与模板能力对账，返回问题列表（空 = 兼容）。"""
    problems: list[str] = []
    language = meta.get("language_mode")
    if language not in manifest.get("languages", []):
        problems.append(
            f"模板 {manifest['id']} 不支持语言模式 {language!r}"
            f"（支持：{manifest.get('languages')}）。"
        )
    target = meta.get("page_target")
    if target not in manifest.get("page_support", []):
        problems.append(
            f"模板 {manifest['id']} 不支持页数目标 {target!r}"
            f"（支持：{manifest.get('page_support')}）。"
        )
    return problems


# ── Typst 编译错误格式化 ─────────────────────────────────────────────────────

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_TYPST_ERR_RE = re.compile(r"^error\s*:\s*(.+)$", re.M)
_TYPST_LOC_RE = re.compile(r"┌─\s*(.+?):(\d+):(\d+)")


def format_typst_error(raw: str) -> str:
    """把 typst CLI 的报错输出整理成人能读的中文摘要（保留原始输出兜底）。

    typst 输出形如：
        error: unknown variable: foo
          ┌─ /path/to/main.typ:3:5
    多条错误逐条列出；定位取紧随其后的 ┌─ 行。
    """
    text = _ANSI_RE.sub("", raw)
    messages = _TYPST_ERR_RE.findall(text)
    if not messages:
        return f"Typst 命令失败（原始输出）：\n{text.strip()}"
    locations = _TYPST_LOC_RE.findall(text)
    lines = [f"Typst 编译失败，共 {len(messages)} 个错误："]
    for i, message in enumerate(messages[:10]):
        where = ""
        if i < len(locations):
            path, line_no, col = locations[i]
            where = f" — {os.path.basename(path)} 第 {line_no} 行第 {col} 列"
        lines.append(f"{i + 1}. {message}{where}")
    if len(messages) > 10:
        lines.append(f"…（其余 {len(messages) - 10} 个略，见原始输出）")
    lines.append("—— 原始输出 ——")
    lines.append(text.strip())
    return "\n".join(lines)


# ── Typst 二进制定位 ─────────────────────────────────────────────────────────

def find_typst(explicit: str | None = None) -> str:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("RESUME_BUILDER_TYPST")
    if env:
        candidates.append(env)
    candidates.append(os.path.join(runtime_home(), "bin",
                                   "typst.exe" if os.name == "nt" else "typst"))
    from shutil import which
    found = which("typst")
    if found:
        candidates.append(found)
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise RenderError(
        "未找到 Typst。请先运行 bootstrap（Batch 9），或用 --typst 指定 typst 路径。\n"
        "已尝试：" + "\n  ".join(candidates)
    )


def run_typst(typst: str, args: list[str], cwd: str) -> str:
    cmd = [typst, *args]
    try:
        timeout = float(os.environ.get("RESUME_BUILDER_TYPST_TIMEOUT", "30"))
        if not 0 < timeout <= 300:
            raise ValueError()
    except ValueError:
        raise RenderError("RESUME_BUILDER_TYPST_TIMEOUT 必须是 0–300 秒之间的正数。")
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"Typst {args[0]} 超过 {timeout:g} 秒，已终止。请检查字体、模板和本地运行时后重试。") from exc
    except OSError as exc:
        raise RenderError(f"无法启动 Typst：{exc}。请检查运行时路径及执行权限。") from exc
    if proc.returncode != 0:
        raise RenderError(f"命令失败：{' '.join(cmd)}\n" + format_typst_error(proc.stdout + proc.stderr))
    if "unknown font family" in proc.stderr or "does not contain the glyph" in proc.stderr:
        raise RenderError("原版模板字体缺失，无法保持原版字体。请安装提示中的字体后重试：\n" + format_typst_error(proc.stderr))
    return proc.stdout


# ── 坐标解析 ─────────────────────────────────────────────────────────────────
#
# Typst here().position() 锚点语义随布局结构而异（Typst 0.15 实测，见
# template.typ 文件头注释），因此模板在每个 editable() 埋点里声明 anchor：
#   inline：start/end 都是"同行基线"；但字段若是行首则 start 变为"行顶"，
#           靠 Δ=end.y−start.y 与 lh 的关系分辨（Δ≈lh → start 是行顶；Δ≈0 → 基线）。
#   bullet：start=首行基线；end=末行基线（单行 Δ≈0）或末行行顶（多行 Δ≥pitch）。
#   block ：行首字段 start=行顶（基线=start.y+lh）；end=同行基线（后续还有内容）
#           或下一行行顶（悬空，须退一整行距）。行中字段 start=基线（Δ≈0）。
# 换算出 first/last 基线后：top=first−lh，bottom=last+desc（desc≈pitch−leading−lh，
# 实测≈0），热区四边再加 HOTZONE_PAD。

_PT_RE = re.compile(r"^(-?[\d.]+)pt$")

# par leading 固定 0.62em（template.typ set par 处），度量表缺项时的兜底也用它
PAR_LEADING_EM = 0.62
_LH_FALLBACK_EM = {"latin": 0.683, "cjk": 0.756}  # 仅在模板未导出度量时兜底


def to_pt(value) -> float:
    """把 Typst 长度（"40pt" / 40）转成 float pt。"""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = _PT_RE.match(value.strip())
        if m:
            return float(m.group(1))
    raise RenderError(f"无法解析坐标值：{value!r}")


def parse_markers(eval_json: str) -> tuple[list[dict], dict[tuple[str, float], dict]]:
    """返回 (字段标记列表, 行高度量表 {(script, size_pt): {pitch, lh}})。"""
    markers = json.loads(eval_json)
    if not isinstance(markers, list):
        raise RenderError(f"typst eval 返回了意外结构：{type(markers)}")
    clean: list[dict] = []
    metrics: dict[tuple[str, float], dict] = {}
    for m in markers:
        if not isinstance(m, dict) or (m.get("kind") != "_metrics" and "phase" not in m):
            continue  # Upstream libraries also emit their own layout metadata.
        if m.get("kind") == "_metrics":
            key = (m["script"], round(to_pt(m["size"]), 2))
            metrics[key] = {"pitch": to_pt(m["pitch"]), "lh": to_pt(m["lh"])}
            continue
        clean.append({
            "kind": m["kind"], "id": m["id"], "phase": m["phase"],
            "anchor": m.get("anchor", "block"),
            "edge": m.get("edge", "left"),
            "page": int(m["page"]),
            "x": to_pt(m["x"]), "y": to_pt(m["y"]),
            "size": round(to_pt(m["size"]), 2) if "size" in m else 10.5,
        })
    return clean, metrics


def _line_metrics(metrics, size: float, text: str) -> dict:
    script = "cjk" if any(ord(ch) > 0x2E7F for ch in text) else "latin"
    m = metrics.get((script, round(size, 2)))
    if m:
        return m
    lh = _LH_FALLBACK_EM[script] * size
    return {"lh": lh, "pitch": lh + PAR_LEADING_EM * size}


def _est_width(text: str, size: float) -> float:
    """悬空字段右边界兜底：按字符类别估宽（CJK≈1em、大写≈0.72、其余≈0.55/0.35）。"""
    em = 0.0
    for ch in text:
        if ord(ch) > 0x2E7F:
            em += 1.0
        elif ch.isupper():
            em += 0.72
        elif ch.islower() or ch.isdigit():
            em += 0.55
        else:
            em += 0.35
    return em * size


def _field_baselines(start: dict, end: dict, met: dict) -> tuple[float, float]:
    """按 anchor 模式把 start/end 坐标换算成 (首行基线, 末行基线)。"""
    sx, sy, ex, ey = start["x"], start["y"], end["x"], end["y"]
    delta = ey - sy
    lh = met["lh"]
    anchor = start["anchor"]

    if anchor == "inline":
        # end 恒为同行基线；start 视行首/行中而定
        base = ey if delta >= 0.5 * lh else sy
        return base, base

    if anchor == "bullet":
        base_first = sy  # 首行基线
        if delta < 0.5 * lh:
            return base_first, ey          # 单行：end=同行基线
        return base_first, ey + lh         # 多行：end=末行行顶

    # anchor == "block"
    if delta < 0.5 * lh:
        return sy, ey                      # 行中字段：start/end 都是基线
    base_first = sy + lh                   # 行首字段：start=行顶
    if ex <= sx + 1.0:                     # 悬空：end=下一行行顶，退一整行距
        return base_first, max(ey - met["pitch"] + lh, base_first)
    return base_first, ey


def pair_markers(markers: list[dict], metrics, texts: dict[str, str],
                 page_sizes: dict[int, tuple[float, float]]) -> list[dict]:
    """把 start/end 标记对成字段矩形；跨页字段拆成两段。"""
    pending: dict[tuple[str, str], dict] = {}
    rects: list[dict] = []
    for m in markers:
        key = (m["id"], m["kind"])
        if m["phase"] == "start":
            pending[key] = m
        else:  # end
            start = pending.pop(key, None)
            if start is None:
                continue  # 容忍落单标记（不应发生）
            text = texts.get(m["id"], m["id"])
            met = _line_metrics(metrics, start["size"], text)
            base_first, base_last = _field_baselines(start, m, met)
            top = base_first - met["lh"]
            bottom = base_last + max(met["pitch"] - PAR_LEADING_EM * start["size"] - met["lh"], 0.0)
            # 右边界：光标在内容后（非悬空）→ ex；否则按文本估宽兜底
            if start["anchor"] == "bullet":
                right = None  # bullet 的 end.x 是 Typst 工件坐标；bullet 为通栏段落，取页边
            elif start.get("edge") == "right":
                right = start["x"] + 2.0
            elif m["x"] > start["x"] + 1.0:
                right = m["x"] + 2.0
            else:
                right = start["x"] + _est_width(text, start["size"])
            if start["page"] == m["page"]:
                # 右对齐 auto/grid 单元中，Typst 有时把 here().position().x
                # 报在字段右缘（尤其是短日期）。模板可声明 edge="right"，
                # 用保守估宽向左展开；同行聚类随后仍会把行尾收至页边。
                left = start["x"] - (_est_width(text, start["size"])
                                     if start.get("edge") == "right" else 0.0)
                rects.append({
                    "id": m["id"], "kind": m["kind"], "page": m["page"],
                    "x": left - 1.0, "y": top,
                    "width": (right - left + 1.0) if right is not None else 0.0,
                    "height": max(bottom - top, met["lh"]),
                })
            else:
                # 字段跨页：前段到页底，后段从页顶
                _, h1 = page_sizes.get(start["page"], (595.28, 841.89))
                rects.append({
                    "id": m["id"], "kind": m["kind"], "page": start["page"],
                    "x": start["x"] - 1.0, "y": top, "width": 0.0, "height": h1 - top,
                })
                rects.append({
                    "id": m["id"], "kind": m["kind"], "page": m["page"],
                    "x": 0.0, "y": 0.0, "width": 0.0, "height": max(bottom, met["lh"]),
                })
    return rects


def union_entry_rects(rects: list[dict], data: dict, page_sizes) -> None:
    """合成 entry 级热区：条目自身 id 的矩形 = 其全部子字段（.title/.subtitle/
    .date/.location/-bN）的并集，供点击条目空白处选中整条。"""
    all_eids = []
    for sec in data.get("sections", []):
        for entry in sec.get("entries", []):
            all_eids.append(entry["id"])
    for eid in all_eids:
        kids = [r for r in rects
                if r["id"] in (eid + ".title", eid + ".subtitle", eid + ".date", eid + ".location")
                or r["id"].startswith(eid + "-b")]
        if not kids:
            continue
        by_page: dict[int, list[dict]] = {}
        for k in kids:
            by_page.setdefault(k["page"], []).append(k)
        for page, group in by_page.items():
            x0 = min(k["x"] for k in group)
            y0 = min(k["y"] for k in group)
            x1 = max(k["x"] + k["width"] for k in group)
            y1 = max(k["y"] + k["height"] for k in group)
            rects.append({
                "id": eid, "kind": "entry", "page": page,
                "x": x0, "y": y0, "width": max(x1 - x0, 20.0), "height": y1 - y0,
            })


def same_line_split(rects: list[dict], page_sizes: dict[int, tuple[float, float]]) -> None:
    """同一行上多个字段（如 标题|日期、多个联系方式）按中点切分 x 范围。

    仅对"高度相近且纵向大幅重叠"的字段聚类切分；entry 级大矩形与其内部的
    行级字段不聚（嵌套热区由编辑器取最小命中）。
    """
    by_page: dict[int, list[dict]] = {}
    for r in rects:
        by_page.setdefault(r["page"], []).append(r)
    for page, group in by_page.items():
        pw, _ = page_sizes.get(page, (595.28, 841.89))
        line_fields = [r for r in group if r["kind"] != "entry"]
        # 贪心按 y 聚成行簇
        line_fields.sort(key=lambda r: (r["y"], r["x"]))
        cluster: list[dict] = []
        clusters: list[list[dict]] = []

        def same_line(a: dict, b: dict) -> bool:
            overlap = min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])
            min_h = min(a["height"], b["height"])
            h_ratio = max(a["height"], b["height"]) / max(min_h, 0.01)
            return overlap > 0.4 * min_h and h_ratio <= 2.2

        for r in line_fields:
            if cluster and not same_line(cluster[-1], r):
                clusters.append(cluster)
                cluster = []
            cluster.append(r)
        if cluster:
            clusters.append(cluster)
        for cl in clusters:
            if len(cl) < 2:
                continue
            cl.sort(key=lambda r: r["x"])
            for i, r in enumerate(cl):
                left = r["x"]
                if i + 1 < len(cl):
                    right = (r["x"] + r["width"] + cl[i + 1]["x"]) / 2
                else:
                    right = pw - 10  # 行尾字段的右界收到页边（点击行尾空白仍命中）
                r["x"] = left
                r["width"] = max(right - left, 20.0)


def build_layout_map(markers: list[dict], metrics, data: dict,
                     page_sizes: dict[int, tuple[float, float]]) -> dict:
    texts = field_texts(data)
    rects = pair_markers(markers, metrics, texts, page_sizes)
    union_entry_rects(rects, data, page_sizes)
    same_line_split(rects, page_sizes)
    fields = []
    for r in rects:
        pw, ph = page_sizes.get(r["page"], (595.28, 841.89))
        x = max(r["x"] - HOTZONE_PAD, 0.0)
        y = max(r["y"] - HOTZONE_PAD, 0.0)
        w = max(r["width"] if r["width"] > 0 else pw - x - 2.0, 20.0)
        h = min(r["height"] + 2 * HOTZONE_PAD, ph - y)
        fields.append({
            "id": r["id"], "kind": r["kind"], "page": r["page"],
            "x": round(x, 2), "y": round(y, 2),
            "width": round(min(w, pw - x), 2), "height": round(h, 2),
        })
    return {
        "schema_version": 1,
        "pages": len(page_sizes),
        "page_sizes": {str(p): {"width": w, "height": h} for p, (w, h) in sorted(page_sizes.items())},
        "fields": sorted(fields, key=lambda f: (f["page"], f["y"], f["x"])),
    }


def field_texts(data: dict) -> dict[str, str]:
    """字段 ID → 展示文本（估宽与中英文判定用，与编辑器热区索引一致）。"""
    texts: dict[str, str] = {}
    basics = data.get("basics", {})
    if basics.get("name"):
        texts["basics.name"] = basics["name"]
    if basics.get("name_en"):
        texts["basics.name-en"] = basics["name_en"]
    if basics.get("headline"):
        texts["basics.headline"] = basics["headline"]
    for c in basics.get("contacts", []):
        texts[c["id"]] = (c.get("label") or "") + "：" + c.get("value", "") if c.get("label") else c.get("value", "")
    for sec in data.get("sections", []):
        texts[sec["id"]] = sec.get("title", "")
        for entry in sec.get("entries", []):
            for key in ("title", "subtitle", "date", "location"):
                if entry.get(key):
                    texts[entry["id"] + "." + key] = entry[key]
            for b in entry.get("bullets", []):
                texts[b["id"]] = b.get("text", "")
    return texts


# ── SVG 页面尺寸解析 ─────────────────────────────────────────────────────────

_SVG_VIEWBOX_RE = re.compile(rb'<svg[^>]*viewBox="0 0 ([\d.]+) ([\d.]+)"')


def read_page_sizes(build_dir: str) -> dict[int, tuple[float, float]]:
    sizes: dict[int, tuple[float, float]] = {}
    for name in os.listdir(build_dir):
        m = re.match(r"page-(\d+)\.svg$", name)
        if not m:
            continue
        with open(os.path.join(build_dir, name), "rb") as fh:
            head = fh.read(400)
        vm = _SVG_VIEWBOX_RE.search(head)
        if vm:
            sizes[int(m.group(1))] = (float(vm.group(1)), float(vm.group(2)))
    if not sizes:
        raise RenderError("编译后没有找到 page-N.svg，Typst SVG 输出异常。")
    return sizes


# ── 主流程 ───────────────────────────────────────────────────────────────────

MAIN_TYP = """// 本文件由 render.py 生成。
#import "template.typ": render
#import "resume-data.typ": resume
#render(resume)
"""


def current_build_dir(project_dir: str, revision: str | None = None) -> str:
    root = Path(project_dir).resolve() / "work" / "build"
    if revision is None:
        try:
            revision = json.loads((root / "current.json").read_text(encoding="utf-8-sig"))["revision"]
        except FileNotFoundError:
            return str(root)  # older projects remain readable
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{32}", revision):
        raise RenderError("预览版本无效，请重新渲染。")
    return str(root / revision)


def render_project(project_dir: str, template_id: str | None = None,
                   typst_path: str | None = None, keep_failed: bool = True,
                   templates_dir: str | None = None) -> dict:
    """Build in isolation; publish only complete results, retaining the last preview."""
    work = Path(project_dir).resolve() / "work"
    build_root = work / "build"
    build_root.mkdir(parents=True, exist_ok=True)
    revision = uuid.uuid4().hex
    build = build_root / revision
    started = time.monotonic()
    try:
        with file_lock(work / "render.lock", timeout=5):
            result = _render_into(project_dir, template_id, typst_path, keep_failed,
                                  templates_dir, str(build))
            result.update(revision=revision, build_dir=str(build), finished_at=time.time_ns())
            layout_path = build / "layout-map.json"
            layout = json.loads(layout_path.read_text(encoding="utf-8"))
            layout["revision"] = revision
            write_json(layout_path, layout)
            _write_render_result(str(build), result)
            write_json(build_root / "current.json", {"revision": revision})
            write_json(work / "render-result.json", result)
            # Keep recent immutable previews for in-flight browser requests.
            try:
                old = sorted((p for p in build_root.iterdir() if p.is_dir()
                              and re.fullmatch(r"[0-9a-f]{32}", p.name)),
                             key=lambda p: p.stat().st_mtime, reverse=True)
            except OSError:
                old = []
            for path in old[5:]:
                if path.name != revision and path.resolve().parent == build_root.resolve():
                    try:
                        shutil.rmtree(path)
                    except OSError:
                        pass  # e.g. Windows browser/antivirus still reading a file
            return result
    except (RenderError, resume_model.ResumeModelError, OSError, ValueError) as exc:
        message = str(exc)
        result = {"ok": False, "error": message, "finished_at": time.time_ns(),
                  "elapsed_ms": round((time.monotonic() - started) * 1000)}
        write_json(work / "render-result.json", result)
        # Never delete the current successful build; failed temporary build only.
        try:
            is_current = Path(current_build_dir(project_dir)) == build
        except (OSError, ValueError, RenderError):
            is_current = True  # never remove a version when publication is uncertain
        if not is_current and build.is_dir() and build.resolve().parent == build_root.resolve():
            shutil.rmtree(build, ignore_errors=True)
        raise RenderError(message) from exc


def _render_into(project_dir: str, template_id: str | None = None,
                   typst_path: str | None = None, keep_failed: bool = True,
                   templates_dir: str | None = None, build_dir: str | None = None) -> dict:
    t0 = time.time()
    project_dir = os.path.abspath(project_dir)
    templates_dir = templates_dir or TEMPLATES_DIR
    resume_path = os.path.join(project_dir, "resume.json")
    data = resume_model.load_resume(resume_path)  # 校验失败即中止，不产出半成品

    tid = template_id or data["meta"]["template_id"]
    template_dir = os.path.join(templates_dir, tid)
    if not os.path.isdir(template_dir):
        raise RenderError(f"模板不存在：{template_dir}")
    manifest = load_manifest(tid, templates_dir)  # 契约校验（结构 + 文件齐全）
    if manifest.get("implementation") == "upstream-adapter" and data["basics"].get("name_en"):
        raise RenderError("当前为单语原版模板。请先将拟展示姓名整理到 basics.name，清空历史 name_en 字段后重试。")
    incompatible = check_template_compatibility(manifest, data["meta"])
    if incompatible:
        raise RenderError("resume.json 与模板能力不匹配：\n- " + "\n- ".join(incompatible))
    entry = manifest.get("entry", "template.typ")

    build_dir = build_dir or os.path.join(project_dir, "work", "build")
    os.makedirs(build_dir, exist_ok=True)

    # 复制模板目录 → build（多文件模板整体可用）
    for root, _dirs, files in os.walk(template_dir):
        rel = os.path.relpath(root, template_dir)
        dest_root = build_dir if rel == "." else os.path.join(build_dir, rel)
        os.makedirs(dest_root, exist_ok=True)
        for fname in files:
            if (fname == "manifest.json" and rel == ".") or fname.startswith("preview"):
                continue
            shutil.copy2(os.path.join(root, fname), os.path.join(dest_root, fname))

    if manifest.get("implementation") == "upstream-adapter":
        shutil.copy2(os.path.join(templates_dir, ".shared", "bindings.typ"),
                     os.path.join(build_dir, "bindings.typ"))
        shutil.copy2(os.path.join(templates_dir, ".shared", "english-bindings.typ"),
                     os.path.join(build_dir, "english-bindings.typ"))

    with open(os.path.join(build_dir, "resume-data.typ"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(resume_model.resume_data_literal(data))
    with open(os.path.join(build_dir, "main.typ"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(MAIN_TYP.replace("template.typ", entry))

    typst = find_typst(typst_path)
    fargs = font_path_args(build_dir)

    try:
        check_original_fonts(typst, manifest, build_dir)
        run_typst(typst, ["compile", "main.typ", "page-{n}.svg", *fargs], cwd=build_dir)
        run_typst(typst, ["compile", "main.typ", "resume.pdf", *fargs], cwd=build_dir)
        # 官方推荐的新查询方式（typst query 子命令在 0.15 已弃用）
        eval_out = run_typst(
            typst,
            ["eval", "query(metadata).map(it => it.value)", "--in", "main.typ", *fargs],
            cwd=build_dir,
        )
    except RenderError as exc:
        # 失败也留摘要：等待页/事实核对页读 render-result.json 展示错误并重试
        _write_render_result(build_dir, {
            "ok": False, "template_id": tid, "error": str(exc),
            "elapsed_ms": round((time.time() - t0) * 1000),
        })
        if not keep_failed:
            raise
        raise

    page_sizes = read_page_sizes(build_dir)
    markers, metrics = parse_markers(eval_out)
    layout_map = build_layout_map(markers, metrics, data, page_sizes)
    with open(os.path.join(build_dir, "layout-map.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(layout_map, fh, ensure_ascii=False, indent=2)

    result = {
        "ok": True,
        "template_id": tid,
        "pages": layout_map["pages"],
        "page_target": data["meta"]["page_target"],
        "fields": len(layout_map["fields"]),
        "elapsed_ms": round((time.time() - t0) * 1000),
        "content_hash": hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "export_filename": resume_model.export_filename(data),
    }
    _write_render_result(build_dir, result)
    return result


def _write_render_result(build_dir: str, result: dict) -> None:
    write_json(os.path.join(build_dir, "render-result.json"), result)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project_dir", help="项目目录（内含 resume.json）")
    parser.add_argument("--template", help="覆盖 meta.template_id")
    parser.add_argument("--typst", help="typst 可执行文件路径")
    parser.add_argument("--json", action="store_true", help="只输出结果 JSON（供 Agent/服务解析）")
    args = parser.parse_args()
    try:
        result = render_project(args.project_dir, args.template, args.typst)
    except (RenderError, resume_model.ResumeModelError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"[render] 失败：{exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print(f"[render] {result['template_id']}：{result['pages']} 页 / "
          f"{result['fields']} 个热区字段 / {result['elapsed_ms']}ms")
    if result["pages"] > result["page_target"]:
        print(f"[render] 注意：实际 {result['pages']} 页超出目标 {result['page_target']} 页，"
              "需要 Agent 精简内容（Agent 在阶段 C/E 负责最终检查）。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
