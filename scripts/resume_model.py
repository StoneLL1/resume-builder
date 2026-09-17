"""resume-builder v2 — resume.json 数据契约核心模块。

职责：
- JSON 结构校验、必填字段检查、重复 ID 检测。
- Typst 特殊字符安全转义。
- 受限 Markdown（加粗 / 链接）到 Typst 标记的安全转换。
- 生成注入模板的 resume-data.typ 字面量。
- 原子保存：先写临时文件再 os.replace，损坏数据不会覆盖最后一份有效内容。

本模块只依赖 Python 标准库，供 render.py / serve.py / validate_project.py 共用。
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from local_io import replace
from typing import Any

SCHEMA_VERSION = 1

# ── ID 规则 ──────────────────────────────────────────────────────────────────
# 稳定字段 ID：字母或数字开头，允许字母/数字/下划线/连字符，长度 1..64。
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

PURPOSES = {"job", "competition", "academic"}
LANGUAGE_MODES = {"zh", "en", "bilingual"}
PAGE_TARGETS = {1, 2}
SECTION_TYPES = {"education", "experience", "project", "skill", "award", "custom"}
CONTACT_TYPES = {"phone", "email", "link", "location", "custom"}

# 板块类型 → 双语模式下自动补充的英文标题（模板可覆盖）。
BILINGUAL_SECTION_TITLES = {
    "education": "EDUCATION",
    "experience": "EXPERIENCE",
    "project": "PROJECTS",
    "skill": "SKILLS",
    "award": "HONORS & AWARDS",
    "custom": "",
}


class ResumeModelError(ValueError):
    """resume.json 校验/解析失败。message 面向用户，可直接展示。"""


# ── 校验 ─────────────────────────────────────────────────────────────────────

def validate(data: Any) -> list[str]:
    """校验已解析的 resume.json 数据，返回错误列表（空列表 = 通过）。

    只做契约检查，不做内容质量判断（那是 Agent 写作阶段的事）。
    """
    errors: list[str] = []

    def err(msg: str) -> None:
        errors.append(msg)

    if not isinstance(data, dict):
        return ["resume.json 顶层必须是 JSON 对象。"]

    if data.get("schema_version") != SCHEMA_VERSION:
        err(f"schema_version 必须为 {SCHEMA_VERSION}，当前为 {data.get('schema_version')!r}。")

    seen_ids: dict[str, str] = {}

    def check_id(value: Any, where: str) -> bool:
        if not isinstance(value, str) or not ID_PATTERN.match(value):
            err(f"{where} 的 id 非法：{value!r}（需匹配 {ID_PATTERN.pattern}）。")
            return False
        if value in seen_ids:
            err(f"重复 id：{value!r} 同时出现在 {seen_ids[value]} 和 {where}。")
            return False
        seen_ids[value] = where
        return True

    # ── meta ──
    meta = data.get("meta")
    if not isinstance(meta, dict):
        err("缺少 meta 对象。")
        meta = {}
    else:
        if meta.get("purpose") not in PURPOSES:
            err(f"meta.purpose 必须是 {sorted(PURPOSES)} 之一，当前为 {meta.get('purpose')!r}。")
        if meta.get("language_mode") not in LANGUAGE_MODES:
            err(f"meta.language_mode 必须是 {sorted(LANGUAGE_MODES)} 之一，当前为 {meta.get('language_mode')!r}。")
        if meta.get("page_target") not in PAGE_TARGETS:
            err(f"meta.page_target 必须是 1 或 2，当前为 {meta.get('page_target')!r}。")
        if not isinstance(meta.get("template_id"), str) or not meta.get("template_id"):
            err("meta.template_id 必须是非空字符串。")
        target = meta.get("target_position")
        if not isinstance(target, str) or not target.strip():
            err("meta.target_position 必须是非空字符串（用于简历定位与导出文件名）。")

    # ── basics ──
    basics = data.get("basics")
    if not isinstance(basics, dict):
        err("缺少 basics 对象。")
        basics = {}
    else:
        if not isinstance(basics.get("name"), str) or not basics.get("name", "").strip():
            err("basics.name 必须是非空字符串。")
        if "name_en" in basics and not isinstance(basics["name_en"], str):
            err("basics.name_en 必须是字符串（可选）。")
        if "headline" in basics and not isinstance(basics["headline"], str):
            err("basics.headline 必须是字符串（可选）。")
        contacts = basics.get("contacts", [])
        if not isinstance(contacts, list):
            err("basics.contacts 必须是数组。")
        else:
            phone_count = 0
            for i, contact in enumerate(contacts):
                where = f"basics.contacts[{i}]"
                if not isinstance(contact, dict):
                    err(f"{where} 必须是对象。")
                    continue
                ok = check_id(contact.get("id"), where)
                ctype = contact.get("type")
                if ctype not in CONTACT_TYPES:
                    err(f"{where}.type 必须是 {sorted(CONTACT_TYPES)} 之一，当前为 {ctype!r}。")
                if not isinstance(contact.get("value"), str) or not contact.get("value", "").strip():
                    err(f"{where}.value 必须是非空字符串。")
                if "label" in contact and not isinstance(contact["label"], str):
                    err(f"{where}.label 必须是字符串（可选）。")
                if ok and ctype == "phone":
                    phone_count += 1
            if phone_count > 1:
                err("basics.contacts 中 type=phone 的条目最多一个（用于导出文件名）。")

    # ── sections ──
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        err("sections 必须是非空数组。")
        sections = sections if isinstance(sections, list) else []
    for si, section in enumerate(sections):
        where = f"sections[{si}]"
        if not isinstance(section, dict):
            err(f"{where} 必须是对象。")
            continue
        check_id(section.get("id"), where)
        stype = section.get("type")
        if stype not in SECTION_TYPES:
            err(f"{where}.type 必须是 {sorted(SECTION_TYPES)} 之一，当前为 {stype!r}。")
        if not isinstance(section.get("title"), str) or not section.get("title", "").strip():
            err(f"{where}.title 必须是非空字符串。")
        entries = section.get("entries")
        if not isinstance(entries, list):
            err(f"{where}.entries 必须是数组。")
            continue
        for ei, entry in enumerate(entries):
            ewhere = f"{where}.entries[{ei}] ({section.get('id', '?')})"
            if not isinstance(entry, dict):
                err(f"{ewhere} 必须是对象。")
                continue
            check_id(entry.get("id"), ewhere)
            for field in ("title", "subtitle", "date", "location"):
                if field in entry and not isinstance(entry[field], str):
                    err(f"{ewhere}.{field} 必须是字符串（可选）。")
            bullets = entry.get("bullets", [])
            if not isinstance(bullets, list):
                err(f"{ewhere}.bullets 必须是数组。")
                continue
            for bi, bullet in enumerate(bullets):
                bwhere = f"{ewhere}.bullets[{bi}]"
                if not isinstance(bullet, dict):
                    err(f"{bwhere} 必须是对象。")
                    continue
                check_id(bullet.get("id"), bwhere)
                if not isinstance(bullet.get("text"), str) or not bullet.get("text", "").strip():
                    err(f"{bwhere}.text 必须是非空字符串。")
            has_content = any(
                isinstance(entry.get(f), str) and entry.get(f, "").strip()
                for f in ("title", "subtitle", "date", "location")
            ) or bool(bullets)
            if not has_content:
                err(f"{ewhere} 内容为空：至少要有 title/subtitle/date/location 之一或 bullets。")

    return errors


def load_resume(path: str | os.PathLike[str]) -> dict:
    """读取并校验 resume.json。任何失败抛 ResumeModelError（含可展示信息）。"""
    path = os.fspath(path)
    try:
        with open(path, "rb") as fh:  # json accepts UTF-8/UTF-16 BOM from Windows shells
            data = json.load(fh)
    except FileNotFoundError:
        raise ResumeModelError(f"找不到文件：{path}")
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ResumeModelError(
            f"resume.json 不是合法 JSON：{exc}。请使用 UTF-8，或带 BOM 的 UTF-16。"
            "文件未被修改，请修正后再保存。"
        )
    errors = validate(data)
    if errors:
        raise ResumeModelError("resume.json 校验失败：\n- " + "\n- ".join(errors))
    return data


def save_resume(path: str | os.PathLike[str], data: dict) -> None:
    """校验后原子保存。数据非法时抛 ResumeModelError，绝不触碰原文件。"""
    errors = validate(data)
    if errors:
        raise ResumeModelError("保存被拒绝，resume.json 校验失败：\n- " + "\n- ".join(errors))
    path = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_path = tempfile.mkstemp(prefix=".resume-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        replace(tmp_path, path)  # 容忍 Windows 文件监视器/杀毒软件的短暂占用
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ── Typst 转换 ───────────────────────────────────────────────────────────────

# Typst 标记模式中的特殊标点，全部用反斜杠转义（转义任何标点在 Typst 中均合法）。
# * 必须在内：两个孤立 * 会被 Typst 配对成 strong（单位测试抓出过）。
_TYPST_SPECIALS = set('\\`"\'#$_[]()@<>~+-/*=')

_ESCAPE_TABLE = {c: "\\" + c for c in _TYPST_SPECIALS}


def typst_escape(text: str) -> str:
    """把纯文本转成 Typst 标记字面量（不含引号包裹）。"""
    return text.translate(str.maketrans(_ESCAPE_TABLE))


def typst_string(text: str) -> str:
    """把字符串转成 Typst 字符串字面量（用于代码位置，如 link 的 url）。"""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


# 受限行内格式：**加粗** 与 [文字](链接)。
_MD_TOKEN = re.compile(r"\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)\s]+)\)", re.S)


def md_to_typst(text: str) -> str:
    """受限 Markdown → Typst 标记。未配对的 *、[、] 等按字面转义。"""
    parts: list[str] = []
    pos = 0
    for match in _MD_TOKEN.finditer(text):
        parts.append(typst_escape(text[pos:match.start()]))
        if match.group(1) is not None:  # **加粗**
            parts.append("#strong[" + typst_escape(match.group(1)) + "]")
        else:  # [文字](链接)
            parts.append(
                "#link(" + typst_string(match.group(3)) + ")[" + typst_escape(match.group(2)) + "]"
            )
        pos = match.end()
    parts.append(typst_escape(text[pos:]))
    return "".join(parts)


def _typst_dict_line(key: str, value: str) -> str:
    return f"  {key}: {value},"


def _markup(text: str | None) -> str:
    """可空文本字段 → Typst 内容字面量；None → none。"""
    if text is None or text == "":
        return "none"
    return "[" + md_to_typst(text) + "]"


def _plain(text: str | None) -> str:
    """结构性字符串（id、type、日期等）→ 转义后的 Typst 字符串。"""
    if text is None:
        return '""'
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + escaped + '"'


def resume_data_literal(data: dict) -> str:
    """生成 resume-data.typ 的 `#let resume = (...)` 声明。

    文本字段（含行内格式）→ 内容字面量 [..]，结构字段 → 字符串。
    """

    def entry_literal(entry: dict) -> str:
        lines = [
            "(",
            _typst_dict_line("id", _plain(entry.get("id"))),
            _typst_dict_line("title", _markup(entry.get("title"))),
            _typst_dict_line("subtitle", _markup(entry.get("subtitle"))),
            _typst_dict_line("date", _plain(entry.get("date"))),
            _typst_dict_line("location", _plain(entry.get("location"))),
        ]
        bullets = entry.get("bullets") or []
        if bullets:
            bullet_lines = [f"    (id: {_plain(b.get('id'))}, text: {_markup(b.get('text'))})," for b in bullets]
            lines.append("  bullets: (\n" + "\n".join(bullet_lines) + "\n  ),")
        else:
            lines.append("  bullets: (),")
        lines.append("),")
        return "\n".join(lines)

    meta = data.get("meta", {})
    basics = data.get("basics", {})

    meta_lines = [
        "(",
        _typst_dict_line("purpose", _plain(meta.get("purpose"))),
        _typst_dict_line("target-position", _plain(meta.get("target_position"))),
        _typst_dict_line("language-mode", _plain(meta.get("language_mode"))),
        _typst_dict_line("page-target", str(int(meta.get("page_target", 1)))),
        _typst_dict_line("template-id", _plain(meta.get("template_id"))),
        "),",
    ]

    contact_lines = []
    for contact in basics.get("contacts", []):
        contact_lines.append(
            "    (id: " + _plain(contact.get("id"))
            + ", type: " + _plain(contact.get("type"))
            + ", label: " + _markup(contact.get("label"))
            + ", value: " + _markup(contact.get("value")) + "),"
        )
    basics_lines = [
        "(",
        _typst_dict_line("name", _markup(basics.get("name"))),
        _typst_dict_line("name-plain", json.dumps(basics.get("name", ""), ensure_ascii=False)),
        _typst_dict_line("name-en", _markup(basics.get("name_en"))),
        _typst_dict_line("headline", _markup(basics.get("headline"))),
        "  contacts: (\n" + "\n".join(contact_lines) + "\n  )," if contact_lines else "  contacts: (),",
        "),",
    ]

    section_blocks: list[str] = []
    for section in data.get("sections", []):
        entry_lines = [entry_literal(entry) for entry in section.get("entries", [])]
        section_blocks.append(
            "(\n"
            + _typst_dict_line("id", _plain(section.get("id")))
            + _typst_dict_line("type", _plain(section.get("type")))
            + _typst_dict_line("title", _markup(section.get("title")))
            + "  entries: (\n" + "\n".join(entry_lines) + "\n  ),\n),"
        )

    body = (
        "// 本文件由 render.py 从 resume.json 自动生成，请勿手改。\n"
        "#let resume = (\n"
        "  meta: \n" + "\n".join(meta_lines) + "\n"
        "  basics: \n" + "\n".join(basics_lines) + "\n"
        "  sections: (\n" + "\n".join(section_blocks) + "\n  ),\n"
        ")\n"
    )
    return body


# ── 查询辅助 ─────────────────────────────────────────────────────────────────

def find_contact(data: dict, ctype: str) -> dict | None:
    """返回第一个指定 type 的联系方式（找不到返回 None）。"""
    for contact in data.get("basics", {}).get("contacts", []):
        if contact.get("type") == ctype:
            return contact
    return None


def export_filename(data: dict) -> str:
    """正式导出文件名：姓名-目标岗位-电话.pdf。"""
    name = data.get("basics", {}).get("name", "").strip()
    position = data.get("meta", {}).get("target_position", "").strip()
    phone = (find_contact(data, "phone") or {}).get("value", "")
    for ch in r'<>:"/\|?*':  # Windows 非法文件名字符
        phone = phone.replace(ch, "-")
    phone = phone.strip()
    parts = [p for p in (name, position, phone) if p]
    return "-".join(parts) + ".pdf" if parts else "resume.pdf"
