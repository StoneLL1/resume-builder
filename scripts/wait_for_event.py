"""resume-builder v2 — Agent 等待浏览器事件（Batch 4）。

用法：
    python scripts/wait_for_event.py <项目目录> [--types 事件类型列表]
                                     [--timeout 秒] [--history]

行为：
- 默认先读取持久游标之后的最新未消费事件，再等新事件，不漏掉先点击的选择。
- ``--history`` 显式重放最近匹配事件，用于 Agent 接收后中断的恢复。
- stdout 输出一行 JSON（事件对象），供 Agent 解析；人读信息走 stderr。

退出码：0 = 等到事件；124 = 超时；1 = 错误。
"""

from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import session as session_mod  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project_dir", help="项目目录（内含 work/events.jsonl）")
    parser.add_argument("--types", default=",".join(session_mod.AGENT_EVENTS),
                        help=f"等待的事件类型，逗号分隔（默认 {','.join(session_mod.AGENT_EVENTS)}）")
    parser.add_argument("--timeout", type=float, default=3600.0,
                        help="最长等待秒数，0 表示无限等（默认 3600）")
    parser.add_argument("--history", action="store_true",
                        help="显式重放最近匹配事件（会话恢复用）")
    parser.add_argument("--new-only", action="store_true", help="仅等命令启动后的事件（诊断用）")
    parser.add_argument("--poll", type=float, default=0.25, help="轮询间隔秒（默认 0.25）")
    args = parser.parse_args()

    types = tuple(t.strip() for t in args.types.split(",") if t.strip())
    timeout = None if args.timeout <= 0 else args.timeout
    print(f"[wait] 等待事件 {list(types)}（timeout={'∞' if timeout is None else timeout}s）…",
          file=sys.stderr)
    event = session_mod.wait_for_event(args.project_dir, types,
                                       timeout=timeout, poll=args.poll,
                                       include_history=not args.new_only, replay=args.history)
    if event is None:
        print("[wait] 超时，没有等到匹配事件。", file=sys.stderr)
        return 124
    print(json.dumps(event, ensure_ascii=False))
    print(f"[wait] 收到事件 #{event['seq']} {event['type']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
