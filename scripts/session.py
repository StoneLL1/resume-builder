"""resume-builder v2 — 会话状态与事件协作层（Batch 4）。

Agent（对话侧）与本地服务（serve.py）/ 浏览器通过两个磁盘文件协作：

- ``work/session.json``：当前阶段（状态机）+ 错误信息。双方都可写，
  原子保存、后保存者生效（与 resume.json 同一语义）。
- ``work/events.jsonl``：追加式事件日志（一行一个 JSON）。浏览器动作
  （选模板、换模板、完成编辑）与服务端状态变化都落事件；Agent 用
  wait_for_event.py 等待新事件被唤醒。

状态机：

    writing → gallery → generating → editor → done
                                ↑        │
                                └─ 换模板 ─┘

本模块只依赖 Python 标准库。CLI 用法：

    python scripts/session.py <项目目录> show
    python scripts/session.py <项目目录> set-stage <阶段> [--note "说明"]
    python scripts/session.py <项目目录> log <消息>          # 追加一条自定义事件
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from local_io import file_lock, write_json

SESSION_SCHEMA_VERSION = 1

# 状态机阶段。writing 由 Agent 在阶段 A 使用（服务未启动）；
# gallery/generating/editor/done 由服务与 Agent 协作流转。
STAGES = ("writing", "gallery", "generating", "editor", "done")

# 事件类型约定（wait_for_event.py 默认等待前三类）。
AGENT_EVENTS = ("template_selected", "template_change_requested", "editing_done")

# claim-map 四态：emoji → (机器码, 中文标签)。
CLAIM_STATUSES = {
    "✅": ("ok", "已确认"),
    "❓": ("wait", "待确认"),
    "⛔": ("block", "缺失阻塞"),
    "➖": ("skip", "已省略"),
}


class SessionError(ValueError):
    """session.json / events.jsonl 读写失败。message 面向用户。"""


def _replace_with_retry(source: str, target: str) -> None:
    """原子替换，容忍 Windows 上读取窗口导致的短暂共享冲突。

    文件监听线程、杀毒软件或另一个 Agent 进程可能恰好正在打开
    session.json。Windows 会让 os.replace 以 PermissionError 失败，而
    POSIX 不会。重试总等待不足 1 秒；持久的权限问题仍原样抛出。
    """
    delays = (0.0, 0.02, 0.05, 0.1, 0.2, 0.4)
    last_error: PermissionError | None = None
    for delay in delays:
        if delay:
            time.sleep(delay)
        try:
            os.replace(source, target)
            return
        except PermissionError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


# ── 路径 ─────────────────────────────────────────────────────────────────────

def work_dir(project_dir: str) -> str:
    return os.path.join(os.path.abspath(project_dir), "work")


def session_path(project_dir: str) -> str:
    return os.path.join(work_dir(project_dir), "session.json")


def events_path(project_dir: str) -> str:
    return os.path.join(work_dir(project_dir), "events.jsonl")


# ── session.json ─────────────────────────────────────────────────────────────

def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def default_session(project_dir: str, stage: str = "gallery") -> dict:
    if stage not in STAGES:
        raise SessionError(f"未知阶段：{stage!r}（合法值 {STAGES}）。")
    return {
        "schema_version": SESSION_SCHEMA_VERSION,
        "project": os.path.basename(os.path.abspath(project_dir)),
        "stage": stage,
        "note": None,
        "error": None,
        "template_id": None,        # 当前使用中的模板
        "selected_template": None,  # 最近一次被选择、等待 Agent 处理的模板
        "created_at": _now(),
        "updated_at": _now(),
    }


def load_session(project_dir: str) -> dict | None:
    """读取 session.json；不存在返回 None；损坏抛 SessionError。"""
    path = session_path(project_dir)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise SessionError(
            f"session.json 不是合法 JSON：{exc}。"
            "文件未被修改；请修复或删除后重建会话。"
        )
    if not isinstance(data, dict) or data.get("schema_version") != SESSION_SCHEMA_VERSION:
        raise SessionError("session.json 结构不认识（schema_version 不为 1），请删除后重建会话。")
    if data.get("stage") not in STAGES:
        raise SessionError(f"session.json 的 stage 非法：{data.get('stage')!r}。")
    return data


def ensure_session(project_dir: str, stage: str = "gallery") -> dict:
    """读取现有会话；没有则创建默认会话（skill 再次调用时借此恢复）。"""
    data = load_session(project_dir)
    if data is not None:
        return data
    data = default_session(project_dir, stage)
    save_session(project_dir, data)
    return data


def save_session(project_dir: str, data: dict) -> None:
    """原子保存 session.json（与 resume_model.save_resume 同一套写法）。"""
    if not isinstance(data, dict) or data.get("schema_version") != SESSION_SCHEMA_VERSION:
        raise SessionError("session.json 结构不认识（schema_version 不为 1），拒绝写盘。")
    if data.get("stage") not in STAGES:
        raise SessionError(f"stage 非法：{data.get('stage')!r}，拒绝写盘。")
    data = dict(data)
    data["updated_at"] = _now()
    directory = work_dir(project_dir)
    os.makedirs(directory, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_path = tempfile.mkstemp(prefix=".session-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        _replace_with_retry(tmp_path, session_path(project_dir))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def set_stage(project_dir: str, stage: str, note: str | None = None,
              error: dict | None = None, **extra) -> dict:
    """切换阶段并落一条 stage 事件（浏览器轮询 events 即可感知切换）。

    支持 extra 键值对合并进 session（如 template_id="rendercv-classic"）。
    """
    data = ensure_session(project_dir)
    if stage not in STAGES:
        raise SessionError(f"未知阶段：{stage!r}（合法值 {STAGES}）。")
    data["stage"] = stage
    if note is not None:
        data["note"] = note
    if error is not None:
        data["error"] = error
    data.update(extra)
    save_session(project_dir, data)
    append_event(project_dir, "stage", {"stage": stage, "note": note, "error": error})
    return data


# ── events.jsonl ─────────────────────────────────────────────────────────────

def append_event(project_dir: str, type_: str, data: dict | None = None) -> dict:
    """追加一条事件（seq 单调递增），返回完整事件对象。"""
    with file_lock(os.path.join(work_dir(project_dir), "events.lock")):
        events = _read_events_raw(project_dir)
        seq = events[-1]["seq"] + 1 if events else 1
        event = {"seq": seq, "at": _now(), "type": type_, "data": data or {}}
        with open(events_path(project_dir), "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event


def _read_events_raw(project_dir: str) -> list[dict]:
    """读全部事件，容忍并跳过损坏行（崩溃残留的半行不致命）。"""
    path = events_path(project_dir)
    if not os.path.isfile(path):
        return []
    events: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and isinstance(event.get("seq"), int):
                events.append(event)
    events.sort(key=lambda e: e["seq"])
    return events


def read_events(project_dir: str, after_seq: int = 0) -> list[dict]:
    """读取 seq 大于 after_seq 的事件（轮询游标语义）。"""
    return [e for e in _read_events_raw(project_dir) if e["seq"] > after_seq]


def wait_for_event(project_dir: str, types: tuple[str, ...] | list[str],
                   timeout: float | None = None, poll: float = 0.25,
                   include_history: bool = True, replay: bool = False) -> dict | None:
    """Return latest unconsumed matching action, including clicks before startup.

    A durable Agent cursor prevents replaying old choices. replay=True explicitly
    recovers the latest matching action after an interrupted Agent turn.
    """
    cursor_path = os.path.join(work_dir(project_dir), "agent-cursor.json")
    try:
        with open(cursor_path, encoding="utf-8-sig") as fh:
            baseline = int(json.load(fh)["seq"])
    except (FileNotFoundError, ValueError, KeyError):
        baseline = 0
    if replay:
        baseline = 0
    elif not include_history:
        baseline = (_read_events_raw(project_dir) or [{"seq": 0}])[-1]["seq"]
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        matches = [event for event in read_events(project_dir, baseline)
                   if not types or event.get("type") in types]
        if matches:
            event = matches[-1]
            write_json(cursor_path, {"seq": event["seq"]})
            return event
        if deadline is not None and time.monotonic() >= deadline:
            return None
        time.sleep(poll)


# ── claim-map 解析（三列表格）─────────────────────────────────────────────

_SEP_ROW_RE = re.compile(r"^[-: ]+$")


def parse_claim_map(text: str) -> dict:
    """解析 V1 claim-map 三列表格 → {rows, counts}。

    - 容忍 ``\\|`` 转义竖线（V1 已知写法，先占位再切分再还原）。
    - 状态列含 ✅/❓/⛔/➖ 之一即识别；识别不到的行保留原文、status=None。
    - 本函数只读不改：状态永不自动变更。
    """
    rows: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        inner = stripped[1:-1].replace("\\|", "\x00")
        cells = [c.strip().replace("\x00", "|") for c in inner.split("|")]
        if len(cells) < 3:
            continue
        if all(_SEP_ROW_RE.match(c) for c in cells if c):
            continue  # |---|---|---| 分隔行
        if cells[0] in ("简历内容", "Claim") and cells[1] in ("来源", "Source"):
            continue  # 表头
        claim, source, status_cell = cells[0], cells[1], cells[2]
        code = label = None
        for emoji, (c, zh) in CLAIM_STATUSES.items():
            if emoji in status_cell:
                code, label = c, zh
                break
        rows.append({"claim": claim, "source": source, "status": code,
                     "status_label": label, "raw_status": status_cell})
    counts = {code: 0 for code in ("ok", "wait", "block", "skip")}
    for row in rows:
        if row["status"] in counts:
            counts[row["status"]] += 1
    return {"rows": rows, "counts": counts}


def read_claim_map(project_dir: str) -> dict:
    """读 work/claim-map.md；缺失返回 exists=False（事实核对页显示空态）。"""
    path = os.path.join(work_dir(project_dir), "claim-map.md")
    if not os.path.isfile(path):
        return {"exists": False, "rows": [], "counts": {}}
    with open(path, "r", encoding="utf-8") as fh:
        parsed = parse_claim_map(fh.read())
    parsed["exists"] = True
    return parsed


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project_dir", help="项目目录（内含 work/）")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="打印当前会话 JSON")
    p_set = sub.add_parser("set-stage", help="切换阶段（Agent 完成工作后调用）")
    p_set.add_argument("stage", help=f"目标阶段：{' / '.join(STAGES)}")
    p_set.add_argument("--note", help="给用户的阶段说明")
    p_set.add_argument("--template", help="同时更新当前模板 ID")
    p_log = sub.add_parser("log", help="追加一条自定义事件")
    p_log.add_argument("message")
    args = parser.parse_args(argv)

    try:
        if args.cmd == "show":
            data = load_session(args.project_dir)
            print(json.dumps(data, ensure_ascii=False, indent=2) if data
                  else "（无会话：work/session.json 不存在）")
        elif args.cmd == "set-stage":
            extra = {"template_id": args.template} if args.template else {}
            data = set_stage(args.project_dir, args.stage, note=args.note, **extra)
            print(f"[session] stage={data['stage']} note={data['note']!r}")
        elif args.cmd == "log":
            event = append_event(args.project_dir, "agent_log", {"message": args.message})
            print(f"[session] event #{event['seq']} {event['type']}")
    except SessionError as exc:
        print(f"[session] 失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
