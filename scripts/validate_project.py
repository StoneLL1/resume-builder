"""resume-builder v2 — 项目数据校验 CLI。

用法：
    python scripts/validate_project.py <项目目录> [--strict]

检查内容：
1. resume.json 存在、可解析、通过契约校验（resume_model.validate）。
2. （若已有渲染产物）layout-map.json 的热区 ID 与 resume.json 的字段 ID 互相对账：
   - 未知 ID（布局里有、数据里没有）→ 警告；--strict 时算错误。
   - 缺失 ID（数据里有、布局里没有）→ 提示（可能正常：模板未渲染该字段）。

本命令不做 Typst 编译（那是 render.py 的职责），只看数据层。
退出码：0 = 全部通过；1 = 存在错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resume_model  # noqa: E402
import render  # noqa: E402


def collect_known_ids(data: dict) -> set[str]:
    """resume.json 里全部合法热区 ID。

    field_texts 只收非空字段，但模板对 entry.title 是无条件埋点的（空标题
    也会渲染出 editable，热区仍在），所以 .title 一律计入。
    """
    ids = set(render.field_texts(data).keys())
    for sec in data.get("sections", []):
        for entry in sec.get("entries", []):
            ids.add(entry["id"])
            ids.add(entry["id"] + ".title")
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project_dir", help="项目目录（内含 resume.json）")
    parser.add_argument("--strict", action="store_true",
                        help="把布局对账警告也当作错误（用于 CI/发布前检查）")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    resume_path = os.path.join(project_dir, "resume.json")
    layout_path = os.path.join(project_dir, "work", "build", "layout-map.json")

    errors: list[str] = []
    warnings: list[str] = []

    # ── 1. resume.json ──
    try:
        data = resume_model.load_resume(resume_path)
    except resume_model.ResumeModelError as exc:
        print(f"[validate] {exc}")
        return 1
    print(f"[validate] resume.json 通过（{len(collect_known_ids(data))} 个字段 ID，"
          f"模板 {data['meta']['template_id']}，{data['meta']['language_mode']}，"
          f"目标 {data['meta']['page_target']} 页）")

    # ── 2. layout-map 对账 ──
    if os.path.isfile(layout_path):
        try:
            with open(layout_path, "r", encoding="utf-8") as fh:
                layout = json.load(fh)
            known = collect_known_ids(data)
            layout_ids = {f["id"] for f in layout.get("fields", [])}
            unknown = sorted(layout_ids - known)
            missing = sorted(known - layout_ids)
            if unknown:
                msg = ("layout-map 存在 resume.json 里没有的 ID：" + ", ".join(unknown)
                       + "（布局与数据不同步，请重新渲染）")
                (errors if args.strict else warnings).append(msg)
            if missing:
                warnings.append("resume.json 里有字段未出现在 layout-map（若模板有意"
                                "省略则正常，否则请重新渲染）：" + ", ".join(missing))
            print(f"[validate] layout-map 对账：{len(layout_ids)} 个热区，"
                  f"未知 {len(unknown)}，缺失 {len(missing)}")
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            errors.append(f"layout-map.json 解析失败：{exc}（请重新渲染）")
    else:
        warnings.append("未找到 work/build/layout-map.json（尚未渲染属正常，"
                        "渲染后本命令会做热区与数据的一致性对账）")

    for msg in warnings:
        print(f"[validate] 警告：{msg}", file=sys.stderr)
    if errors:
        for msg in errors:
            print(f"[validate] 错误：{msg}", file=sys.stderr)
        return 1
    print("[validate] 通过" + ("（含警告）" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
