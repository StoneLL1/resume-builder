"""resume-builder v2 — 本地服务与 Agent 事件协作（Batch 4）。

用法：
    python scripts/serve.py <项目目录> [--port 8765] [--no-open] [--token <开发用固定令牌>]

职责：
- 只监听 127.0.0.1 的本地 HTTP 服务，承载画廊 / 等待页 / 编辑器 / 事实核对页
  （Batch 5-7 页面 + /status 阶段观察页供调试）。
  首页 ``/`` 按当前阶段 302 到对应页面，并透传 ``?token=``。
- REST API：状态、模板、选择、简历读写、渲染、预览、布局图、claim-map、导出、事件。
- 事件协作：浏览器动作写 work/events.jsonl，Agent 用 wait_for_event.py 等待；
  Agent 改 session.json / resume.json 后，服务通过 mtime 检测并广播/重渲染。
- 会话恢复：skill 再次调用时读取现有 work/session.json 继续（serve 启动即接管）。

安全：
- 仅绑定 127.0.0.1；Host 必须是 127.0.0.1[:port] / localhost[:port]（防 DNS rebinding）。
- 随机会话令牌：所有 /api/* 必须携带（header ``X-Resume-Token`` 或 query ``token``），
  常数时间比较。页面通过 URL ?token= 获得并存 sessionStorage。
- 状态变更类请求校验 Origin（防跨站写）；请求体必须是 JSON 且 ≤4MB。
- 静态文件只出白名单（assets/web 页面与样式脚本、build 产物、模板预览图），不接受任意路径。

只依赖 Python 标准库（http.server / threading / json）。
"""

from __future__ import annotations

import argparse
import hmac
import http.client
import json
import os
import queue
import re
import secrets
import shutil
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render  # noqa: E402
import resume_model  # noqa: E402
import session as session_mod  # noqa: E402

MAX_BODY_BYTES = 4 * 1024 * 1024
WATCH_INTERVAL = 0.4          # 文件变化轮询间隔（秒）
_TEMPLATE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# 静态页面白名单：URL 路径 → assets/web 下的文件（Batch 5-7）
STATIC_PAGES = {
    "status": "status.html",  # 阶段观察页（调试用）
    "gallery": "gallery.html",      # Batch 5
    "waiting": "waiting.html",      # Batch 5
    "editor": "editor.html",        # Batch 6
    "facts": "facts.html",          # Batch 7
}

# 静态资源白名单：/assets/<名> → assets/web 下同名文件 + Content-Type
STATIC_ASSETS = {
    "app.css": "text/css; charset=utf-8",
    "app.js": "application/javascript; charset=utf-8",
}

# 首页按阶段重定向（与前端 app.js 的 STAGE_URL 一致，服务端再挡一层直接访问）
STAGE_ENTRY = {
    "writing": "/gallery",
    "gallery": "/gallery",
    "generating": "/waiting",
    "editor": "/editor",
    "done": "/editor",
}


class ServeError(RuntimeError):
    """请求处理失败（将映射为 4xx/5xx JSON 响应）。"""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# ── 服务核心（与 HTTP 层解耦，便于测试直接驱动）──────────────────────────────

class ServerCore:
    def __init__(self, project_dir: str, templates_dir: str | None = None,
                 typst_path: str | None = None, token: str | None = None):
        self.project_dir = os.path.abspath(project_dir)
        self.templates_dir = templates_dir or render.TEMPLATES_DIR
        self.typst_path = typst_path
        self.token = token or secrets.token_urlsafe(24)
        self.port: int | None = None       # bind 后由 serve 填
        self.rendering = False
        self.last_render: dict | None = None
        self._render_q: "queue.Queue[str]" = queue.Queue(maxsize=1)
        self._render_lock = threading.Lock()
        self._resume_io_lock = threading.Lock()  # 消除 PUT 保存与监听线程的竞窗
        self._resume_stat = self._stat(resume_model_path(self.project_dir))
        self._session_stat = self._stat(session_mod.session_path(self.project_dir))
        self._pending_own_write = False
        self.session = session_mod.ensure_session(self.project_dir)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    # ── 基础 ──

    @staticmethod
    def _stat(path: str) -> tuple[int, int] | None:
        try:
            st = os.stat(path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def build_dir(self) -> str:
        return os.path.join(self.project_dir, "work", "build")

    def start_background(self) -> None:
        """启动后台线程：渲染队列 + 文件监听。幂等。"""
        if self._threads:
            return
        t1 = threading.Thread(target=self._render_worker, name="render-worker", daemon=True)
        t2 = threading.Thread(target=self._file_watcher, name="file-watcher", daemon=True)
        t1.start()
        t2.start()
        self._threads = [t1, t2]

    def stop_background(self) -> None:
        self._stop.set()
        try:
            self._render_q.put_nowait("__exit__")
        except queue.Full:
            pass
        # 等在途渲染收尾：typst 子进程以 build 目录为 cwd，不 join 的话
        # 调用方紧接着删项目目录会在 Windows 上撞文件句柄（WinError 32）
        for t in self._threads:
            t.join(timeout=30)
        self._threads = []

    # ── 状态 ──

    def state_summary(self) -> dict:
        session = self.session
        render_info = None
        result_path = os.path.join(self.build_dir(), "render-result.json")
        if self.last_render is not None:
            render_info = self.last_render
        elif os.path.isfile(result_path):
            try:
                with open(result_path, "r", encoding="utf-8") as fh:
                    render_info = json.load(fh)
            except (json.JSONDecodeError, OSError):
                render_info = None
        return {
            "stage": session.get("stage"),
            "note": session.get("note"),
            "error": session.get("error"),
            "template_id": session.get("template_id"),
            "selected_template": session.get("selected_template"),
            "rendering": self.rendering,
            "render": render_info,
            "updated_at": session.get("updated_at"),
        }

    # ── 渲染 ──

    def queue_render(self, reason: str) -> bool:
        """请求一次后台渲染（进行中/待渲染时合并，立即返回）。"""
        try:
            self._render_q.put_nowait(reason)
            return True
        except queue.Full:
            return False

    def _render_worker(self) -> None:
        while True:
            reason = self._render_q.get()
            if reason == "__exit__":
                return
            try:
                self._render_one(reason)
            except Exception as exc:  # noqa: BLE001 — 兜底，见下
                # 渲染线程绝不允许死掉：死了以后队列静默堆积、页面永远
                # 「渲染中」。可预期错误在 _render_one 里已按 render_failed
                # 落事件，这里只拦漏网异常，同样落事件后继续服务。
                try:
                    session_mod.append_event(self.project_dir, "render_failed", {
                        "reason": reason, "ok": False,
                        "error": f"渲染线程内部错误：{exc!r}"[:2000],
                    })
                except OSError:
                    pass  # 事件文件也写不进去时只能放弃记录

    def _render_one(self, reason: str) -> None:
        with self._render_lock:
            self.rendering = True
            try:
                result = render.render_project(
                    self.project_dir, typst_path=self.typst_path,
                    templates_dir=self.templates_dir)
                self.last_render = result
                session_mod.append_event(self.project_dir, "rendered", {
                    "reason": reason, "ok": True,
                    "pages": result["pages"], "fields": result["fields"],
                })
                # 成功的渲染让上一次失败的 sticky 错误失效；等待页
                # 「重试渲染」按钮（reason=api-request）成功且仍卡在
                # generating 时自动放行到编辑器——此时 Agent 可能已停，
                # 无人推进阶段页面会永远等待（Agent 自驱的渲染仍由
                # Agent 决定何时切阶段，不在此处代劳）。
                cleanup = {}
                if self.session.get("error") is not None:
                    cleanup["error"] = None
                if reason == "api-request" and self.session.get("stage") == "generating":
                    cleanup["stage"] = "editor"
                    cleanup["note"] = "重试渲染成功，已进入编辑器"
                if cleanup:
                    self._session_update(**cleanup)
            except (render.RenderError, resume_model.ResumeModelError) as exc:
                self.last_render = None
                message = str(exc)
                session_mod.append_event(self.project_dir, "render_failed", {
                    "reason": reason, "ok": False, "error": message[:2000],
                })
                self._session_update(error={"message": message[:2000],
                                            "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
            finally:
                self.rendering = False

    def render_now(self) -> dict:
        """同步渲染（导出等需要确定性结果的场景）。"""
        with self._render_lock:
            self.rendering = True
            try:
                result = render.render_project(
                    self.project_dir, typst_path=self.typst_path,
                    templates_dir=self.templates_dir)
                self.last_render = result
                return result
            finally:
                self.rendering = False

    # ── 文件监听（Agent 侧修改 → 自动反应）─────────────────────────────────

    def _file_watcher(self) -> None:
        while not self._stop.wait(WATCH_INTERVAL):
            # resume.json 外部变化（Agent 写盘）→ 自动重渲染。
            # 与 PUT 保存互斥：避免监视线程抢在 note_own_resume_write 之前
            # 读到新 mtime、把自己写的当成外部修改。
            if self._resume_io_lock.acquire(blocking=False):
                try:
                    stat = self._stat(resume_model_path(self.project_dir))
                    if stat != self._resume_stat:
                        self._resume_stat = stat
                        if not self._consume_own_write():
                            session_mod.append_event(self.project_dir, "resume_changed",
                                                     {"source": "external"})
                            self.queue_render("external-resume-change")
                finally:
                    self._resume_io_lock.release()
            # session.json 外部变化（Agent set-stage）→ 重载内存副本
            stat = self._stat(session_mod.session_path(self.project_dir))
            if stat != self._session_stat:
                self._session_stat = stat
                try:
                    data = session_mod.load_session(self.project_dir)
                except session_mod.SessionError:
                    data = None
                if data is not None:
                    self.session = data

    def note_own_resume_write(self) -> None:
        """PUT /api/resume 保存成功后调用：标记下一次 mtime 变化是自己造成的。"""
        self._resume_stat = self._stat(resume_model_path(self.project_dir))
        self._pending_own_write = True

    def _consume_own_write(self) -> bool:
        if self._pending_own_write:
            self._pending_own_write = False
            return True
        return False

    def _session_update(self, **changes) -> None:
        """服务侧修改会话（与 Agent 的 CLI 写盘同一原子语义，后保存者生效）。

        会话尚不存在时从合法骨架起步（stage=writing），避免渲染失败
        抢在首次 select 之前落错误信息时炸掉调用线程。
        涉及阶段切换时补一条 stage 事件，保证 events.jsonl 是完整历史
        （浏览器轮询 /api/events 即可感知，无需另设推送通道）。
        """
        data = dict(self.session) if isinstance(self.session, dict) else {
            "schema_version": 1, "stage": "writing",
        }
        stage_changed = "stage" in changes and changes["stage"] != data.get("stage")
        data.update(changes)
        session_mod.save_session(self.project_dir, data)
        self.session = session_mod.load_session(self.project_dir) or data
        self._session_stat = self._stat(session_mod.session_path(self.project_dir))
        if stage_changed:
            session_mod.append_event(self.project_dir, "stage", {
                "stage": data["stage"], "note": data.get("note"), "error": data.get("error")})

    # ── 业务动作 ──

    def list_templates(self, include_internal: bool = False) -> dict:
        listing = render.list_templates(self.templates_dir)
        templates = [t for t in listing["templates"]
                     if include_internal or not t.get("internal")]
        return {
            "templates": [self._template_card(t) for t in sorted(templates, key=lambda t: (t.get("gallery_language", "zh"), t.get("gallery_order", 99), t["id"]))],
            "invalid": listing["invalid"],
            "language_mode": self._gallery_language_mode(),
            "selected_template": self.session.get("selected_template"),
        }

    def _gallery_language_mode(self) -> str:
        if self.session.get("selected_language"):
            return self.session["selected_language"]
        try:
            return resume_model.load_resume(os.path.join(self.project_dir, "resume.json"))["meta"]["language_mode"]
        except resume_model.ResumeModelError:
            return "zh"

    def _template_card(self, manifest: dict) -> dict:
        return {
            "id": manifest["id"],
            "name": manifest["name"],
            "description": manifest.get("description", ""),
            "tags": manifest.get("tags", []),
            "internal": bool(manifest.get("internal")),
            "languages": manifest.get("languages", []),
            "gallery_language": manifest.get("gallery_language", "zh"),
            "color_mode": manifest.get("color_mode", "color"),
            "preview_source": manifest.get("preview_source", {"kind": "rendered"}),
            "page_support": manifest.get("page_support", []),
            "layout": manifest.get("layout", {}),
            "license": manifest.get("license", {}).get("name"),
            "upstream": manifest.get("upstream"),
            "preview_url": f"/api/template-preview/{manifest['id']}",
        }

    def select_template(self, template_id: str, language_mode: str | None = None) -> dict:
        """用户确认模板：校验能力 → 落事件 → 进入 generating。

        画廊阶段是首次选择（template_selected）；编辑阶段是换模板
        （template_change_requested）。两种事件都会唤醒
        等待中的 Agent（wait_for_event.py 默认同时等这两类）。
        """
        if not _TEMPLATE_ID_RE.match(template_id or ""):
            raise ServeError(400, f"模板 ID 非法：{template_id!r}。")
        manifest = render.load_manifest(template_id, self.templates_dir)  # 校验失败 → 500 带原因
        if manifest.get("retired"):
            raise ServeError(409, "该模板已退出画廊，请选择当前中英文模板。")
        if language_mode is not None and language_mode not in manifest["languages"]:
            raise ServeError(409, "该模板不支持所选语言模式。")
        resume_path = resume_model_path(self.project_dir)
        if os.path.isfile(resume_path):
            try:
                data = resume_model.load_resume(resume_path)
            except resume_model.ResumeModelError as exc:
                raise ServeError(409, f"resume.json 当前无效，无法核对模板能力：{exc}")
            meta = dict(data["meta"])
            if language_mode is not None:
                meta["language_mode"] = language_mode
            incompatible = render.check_template_compatibility(manifest, meta)
            if incompatible:
                raise ServeError(409, "该模板与当前简历不匹配：\n- " + "\n- ".join(incompatible))

        stage = self.session.get("stage")
        event_type = "template_change_requested" if stage == "editor" else "template_selected"
        chosen_mode = language_mode or self._gallery_language_mode()
        event = session_mod.append_event(self.project_dir, event_type,
                                         {"template_id": template_id, "from_stage": stage,
                                          "language_mode": chosen_mode})
        self._session_update(
            stage="generating",
            selected_template=template_id,
            template_id=template_id,
            selected_language=chosen_mode,
            note="Agent 正在做第二轮精修与排版检查，完成后自动进入编辑器…",
            error=None,
        )
        return {"ok": True, "event_type": event_type, "event_seq": event["seq"],
                "stage": "generating"}

    def save_resume(self, data) -> dict:
        """网页侧保存简历：校验 + 原子写盘 + 排队重渲染（后保存者生效）。"""
        try:
            with self._resume_io_lock:
                resume_model.save_resume(resume_model_path(self.project_dir), data)
                self.note_own_resume_write()
        except resume_model.ResumeModelError as exc:
            raise ServeError(400, str(exc))
        self.queue_render("web-save")
        return {"ok": True, "rendering": True}

    def export_pdf(self) -> dict:
        """导出正式 PDF：强制重渲染 → 复制为规范文件名 → 阶段 done。"""
        try:
            result = self.render_now()
            data = resume_model.load_resume(resume_model_path(self.project_dir))
        except (render.RenderError, resume_model.ResumeModelError) as exc:
            raise ServeError(500, str(exc))
        filename = resume_model.export_filename(data)
        src = os.path.join(self.build_dir(), "resume.pdf")
        if not os.path.isfile(src):
            raise ServeError(500, "渲染完成但没有找到 resume.pdf，导出中止。")
        shutil.copy2(src, os.path.join(self.project_dir, filename))
        warning = None
        if result["pages"] > 2:
            warning = f"实际 {result['pages']} 页超过两页上限，正式简历需 Agent 精简。"
        session_mod.append_event(self.project_dir, "exported", {
            "filename": filename, "pages": result["pages"]})
        self._session_update(stage="done",
                             note=f"已导出：{filename}" + (f"（⚠ {warning}）" if warning else ""),
                             error=None)
        out = {"ok": True, "filename": filename, "pages": result["pages"]}
        if warning:
            out["warning"] = warning
        return out

    def editing_done(self) -> dict:
        """编辑器「完成编辑」按钮：落事件唤醒 Agent 做终检与导出。"""
        event = session_mod.append_event(self.project_dir, "editing_done", {})
        self._session_update(note="已通知 Agent 进行最终检查与导出…")
        return {"ok": True, "event_seq": event["seq"]}

    def preview_listing(self) -> dict:
        layout_path = os.path.join(self.build_dir(), "layout-map.json")
        if not os.path.isfile(layout_path):
            return {"pages": 0, "items": [], "page_sizes": {}}
        try:
            with open(layout_path, "r", encoding="utf-8") as fh:
                layout = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {"pages": 0, "items": [], "page_sizes": {}}
        sizes = layout.get("page_sizes", {})
        items = []
        for page in range(1, layout.get("pages", 0) + 1):
            size = sizes.get(str(page), {})
            items.append({"page": page, "url": f"/api/preview/{page}",
                          "width": size.get("width"), "height": size.get("height")})
        return {"pages": layout.get("pages", 0), "items": items, "page_sizes": sizes}

    def read_layout_map(self) -> dict:
        layout_path = os.path.join(self.build_dir(), "layout-map.json")
        if not os.path.isfile(layout_path):
            raise ServeError(404, "还没有渲染产物：layout-map.json 不存在（先 POST /api/render）。")
        with open(layout_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def read_page_svg(self, page: int) -> bytes:
        path = os.path.join(self.build_dir(), f"page-{page}.svg")
        if page < 1 or page > 99 or not os.path.isfile(path):
            raise ServeError(404, f"预览页不存在：page-{page}.svg（先渲染，或页数已变化）。")
        with open(path, "rb") as fh:
            return fh.read()

    def read_template_preview(self, template_id: str) -> tuple[bytes, str]:
        if not _TEMPLATE_ID_RE.match(template_id):
            raise ServeError(400, f"模板 ID 非法：{template_id!r}。")
        folder = os.path.join(self.templates_dir, template_id)
        if not os.path.isdir(folder):
            raise ServeError(404, f"模板 {template_id} 没有预览图。")
        manifest = render.load_manifest(template_id, self.templates_dir)
        path = os.path.join(folder, manifest.get("preview", "preview.png"))
        content_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml"}
        with open(path, "rb") as fh:
            return fh.read(), content_types.get(os.path.splitext(path)[1].lower(), "application/octet-stream")

    def read_static_page(self, page_key: str) -> bytes:
        fname = STATIC_PAGES.get(page_key)
        if fname is None:
            raise ServeError(404, f"页面不存在：/{page_key}（可用：{sorted(set(STATIC_PAGES))}）。")
        path = os.path.join(render.V2_ROOT, "assets", "web", fname)
        if not os.path.isfile(path):
            raise ServeError(404, f"页面 {fname} 尚未实现（对应 Batch 5-7）。")
        with open(path, "rb") as fh:
            return fh.read()


def resume_model_path(project_dir: str) -> str:
    return os.path.join(project_dir, "resume.json")


# ── HTTP 层 ──────────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "resume-builder/2"

    @property
    def core(self) -> ServerCore:
        return self.server.core  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:  # 静默访问日志（保留错误输出）
        pass

    # ── 分发 ──

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def _dispatch(self, method: str) -> None:
        try:
            self._check_host()
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = urllib.parse.parse_qs(parsed.query)
            self._route(method, path, query)
        except ServeError as exc:
            self._send_json(exc.status, {"error": str(exc)})
        except (render.RenderError, resume_model.ResumeModelError) as exc:
            self._send_json(500, {"error": str(exc)})
        except BrokenPipeError:
            pass
        except Exception as exc:  # noqa: BLE001 — 兜底成 JSON，不让线程崩
            self._send_json(500, {"error": f"服务内部错误：{exc!r}"})

    def _route(self, method: str, path: str, query: dict) -> None:
        if path == "/":
            if method != "GET":
                raise ServeError(405, "静态页面只支持 GET。")
            target = STAGE_ENTRY.get(self.core.session.get("stage"), "/gallery")
            # 透传令牌等查询参数，用户打开带 ?token= 的首页时不需重新输入
            qs = urllib.parse.urlencode(
                {k: v[-1] for k, v in query.items() if k == "token"}) if query.get("token") else ""
            self.send_response(302)
            self.send_header("Location", target + (f"?{qs}" if qs else ""))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path in ("/status", "/gallery", "/waiting", "/editor", "/facts"):
            if method != "GET":
                raise ServeError(405, "静态页面只支持 GET。")
            body = self.core.read_static_page(path.lstrip("/"))
            self._send_bytes(body, "text/html; charset=utf-8")
            return
        if path.startswith("/assets/") and method == "GET":
            name = path[len("/assets/"):]
            ctype = STATIC_ASSETS.get(name)
            if ctype is None:
                raise ServeError(404, f"静态资源不在白名单：{path}（可用：app.css、app.js）。")
            asset_path = os.path.join(render.V2_ROOT, "assets", "web", name)
            if not os.path.isfile(asset_path):
                raise ServeError(404, f"静态资源缺失：{name}。")
            with open(asset_path, "rb") as fh:
                self._send_bytes(fh.read(), ctype)
            return
        if not path.startswith("/api/"):
            raise ServeError(404, f"未知路径：{path}")

        # /api/* 一律要求令牌（含 GET：简历是个人数据，本机其他页面不得读走）
        self._check_token(query)
        if method in ("POST", "PUT"):
            self._check_origin()
            # Consume optional JSON on action endpoints before a keep-alive
            # connection is reused for polling; otherwise '{}' becomes '{}GET'.
            if (path in ("/api/render", "/api/export", "/api/editing-done")
                    and self.headers.get("Content-Length") not in (None, "0")):
                self._read_json_body()

        if path == "/api/state" and method == "GET":
            self._send_json(200, self.core.state_summary())

        elif path == "/api/templates" and method == "GET":
            self._send_json(200, self.core.list_templates(
                include_internal=query.get("all", ["0"])[0] == "1"))

        elif path == "/api/template/select" and method == "POST":
            body = self._read_json_body()
            template_id = body.get("template_id")
            if not isinstance(template_id, str) or not template_id:
                raise ServeError(400, "template_id 必须是非空字符串。")
            language_mode = body.get("language_mode")
            if language_mode is not None and language_mode not in render.KNOWN_LANGUAGES:
                raise ServeError(400, "language_mode 必须为 zh、en 或 bilingual。")
            self._send_json(200, self.core.select_template(template_id, language_mode))

        elif path == "/api/resume" and method == "GET":
            resume_path = resume_model_path(self.core.project_dir)
            if not os.path.isfile(resume_path):
                raise ServeError(404, "resume.json 尚不存在（Agent 在阶段 C 写入）。")
            try:
                data = resume_model.load_resume(resume_path)
            except resume_model.ResumeModelError as exc:
                raise ServeError(409, str(exc))
            self._send_json(200, data)

        elif path == "/api/resume" and method == "PUT":
            self._send_json(200, self.core.save_resume(self._read_json_body()))

        elif path == "/api/render" and method == "POST":
            queued = self.core.queue_render("api-request")
            self._send_json(200, {"ok": True, "queued": queued,
                                  "rendering": self.core.rendering})

        elif path == "/api/preview" and method == "GET":
            self._send_json(200, self.core.preview_listing())

        elif path.startswith("/api/preview/") and method == "GET":
            m = re.match(r"^/api/preview/(\d+)$", path)
            if not m:
                raise ServeError(400, "预览路径应为 /api/preview/<页码>。")
            self._send_bytes(self.core.read_page_svg(int(m.group(1))),
                             "image/svg+xml", no_store=True)

        elif path == "/api/layout-map" and method == "GET":
            self._send_json(200, self.core.read_layout_map())

        elif path == "/api/claim-map" and method == "GET":
            self._send_json(200, session_mod.read_claim_map(self.core.project_dir))

        elif path == "/api/export" and method == "POST":
            self._send_json(200, self.core.export_pdf())

        elif path == "/api/editing-done" and method == "POST":
            self._send_json(200, self.core.editing_done())

        elif path == "/api/events" and method == "GET":
            try:
                cursor = int(query.get("cursor", ["0"])[0])
            except ValueError:
                raise ServeError(400, "cursor 必须是整数。")
            events = session_mod.read_events(self.core.project_dir, cursor)
            new_cursor = events[-1]["seq"] if events else cursor
            self._send_json(200, {"cursor": new_cursor, "events": events,
                                  "state": self.core.state_summary()})

        elif path.startswith("/api/template-preview/") and method == "GET":
            template_id = path[len("/api/template-preview/"):]
            body, ctype = self.core.read_template_preview(template_id)
            self._send_bytes(body, ctype, no_store=True)

        else:
            raise ServeError(404, f"未知接口：{method} {path}")

    # ── 安全检查 ──

    def _check_host(self) -> None:
        """Host 只认本机回环（防 DNS rebinding：外部域名解析到 127.0.0.1）。"""
        host = (self.headers.get("Host") or "").lower()
        port = self.core.port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}",
                   "127.0.0.1", "localhost", f"[::1]:{port}", "[::1]"}
        if host not in allowed:
            raise ServeError(403, f"Host 不被允许：{host!r}（服务只对本机回环开放）。")

    def _check_token(self, query: dict) -> None:
        token = self.headers.get("X-Resume-Token") or (query.get("token", [""])[0])
        if not token or not hmac.compare_digest(token, self.core.token):
            raise ServeError(401, "缺少或错误的会话令牌（通过带 ?token= 的页面链接获取）。")

    def _check_origin(self) -> None:
        """状态变更请求的 Origin 校验（同源或无 Origin 的本机工具调用）。"""
        origin = self.headers.get("Origin")
        if not origin:
            return  # curl / Python http.client 不带 Origin；令牌仍是硬门槛
        port = self.core.port
        if origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
            return
        raise ServeError(403, f"Origin 不被允许：{origin!r}。")

    def _read_json_body(self) -> dict:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or 0)
        except (TypeError, ValueError):
            # The body cannot be framed reliably, so do not leave unread bytes
            # on a keep-alive connection where they could corrupt the next request.
            self.close_connection = True
            raise ServeError(400, "Content-Length 必须是非负整数。")
        if length < 0:
            self.close_connection = True
            raise ServeError(400, "Content-Length 必须是非负整数。")
        if length <= 0:
            raise ServeError(400, "请求体不能为空（需要 JSON）。")
        if length > MAX_BODY_BYTES:
            raise ServeError(413, f"请求体过大（>{MAX_BODY_BYTES // (1024 * 1024)}MB）。")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ServeError(400, f"请求体不是合法 JSON：{exc}。")
        if not isinstance(data, dict):
            raise ServeError(400, "请求体必须是 JSON 对象。")
        return data

    # ── 响应 ──

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8", no_store=True, status=status)

    def _send_bytes(self, body: bytes, ctype: str, no_store: bool = False,
                    status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if no_store:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class _HTTPD(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, handler, core: ServerCore):
        self.core = core
        super().__init__(addr, handler)


def create_server(project_dir: str, port: int = 8765, templates_dir: str | None = None,
                  typst_path: str | None = None, token: str | None = None):
    """创建（并绑定）本地服务。端口被占时依次尝试 port..port+10，再退回随机。

    返回 (httpd, core)。调用方自行 serve_forever()（测试用线程驱动）。
    """
    core = ServerCore(project_dir, templates_dir=templates_dir,
                      typst_path=typst_path, token=token)
    httpd = None
    last_error: OSError | None = None
    for candidate in [port + i for i in range(11)] + [0]:
        try:
            httpd = _HTTPD(("127.0.0.1", candidate), _Handler, core)
            break
        except OSError as exc:
            last_error = exc
    if httpd is None:
        raise RuntimeError(f"无法绑定本地端口（尝试 {port}..{port + 10} 与随机端口）：{last_error}")
    core.port = httpd.server_address[1]
    core.start_background()
    return httpd, core


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project_dir", help="项目目录（内含 resume.json 与 work/）")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("PORT", "8765")),
                        help="首选端口（默认 8765 或环境变量 PORT，占用则递增）")
    parser.add_argument("--templates", help="模板目录（默认 assets/templates）")
    parser.add_argument("--typst", help="typst 可执行文件路径")
    parser.add_argument("--token", help="固定会话令牌（仅本地开发/测试用；默认随机生成）")
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    httpd, core = create_server(args.project_dir, port=args.port,
                                templates_dir=args.templates,
                                typst_path=args.typst, token=args.token)
    base = f"http://127.0.0.1:{core.port}"
    print(f"[serve] Resume Builder 本地服务已启动（仅 127.0.0.1）")
    print(f"[serve] 项目：{core.project_dir}")
    print(f"[serve] 状态页：{base}/status?token={core.token}")
    print(f"[serve] 画廊：  {base}/gallery?token={core.token}")
    print(f"[serve] Agent 等待事件：python scripts/wait_for_event.py \"{args.project_dir}\"")
    if not args.no_open:
        try:
            webbrowser.open(f"{base}/gallery?token={core.token}")
        except OSError:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[serve] 已停止。")
    finally:
        core.stop_background()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
