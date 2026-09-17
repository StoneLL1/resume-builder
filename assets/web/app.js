/* ═══ Resume Builder V2 · 共享运行时（Batch 5-7） ═════════════════
   令牌引导 / API 客户端 / 事件轮询 / toast / 小工具。
   页面约定：先加载本文件，再跑页面自己的 <script>。
   ═══════════════════════════════════════════════════════════════ */
'use strict';

/* ── 令牌：URL ?token= 优先，其次 sessionStorage（同会话刷新免带） ── */
const RB = {
  token: (function () {
    const qs = new URLSearchParams(location.search);
    let t = qs.get('token') || '';
    try {
      t = t || sessionStorage.getItem('rb-token') || '';
      if (t) sessionStorage.setItem('rb-token', t);
    } catch (_) { /* URL token works when storage is unavailable. */ }
    return t;
  })(),
  /* <img> 等标签发不了自定义头，带令牌的资源 URL 用查询参数补（服务端两种方式都认） */
  authedUrl(url) {
    return url + (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(this.token);
  },
};

/* ── API 客户端（失败抛 Error，message 面向用户） ── */
async function api(path, opts = {}) {
  const { timeoutMs = 10000, ...options } = opts;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const init = { ...options, signal: controller.signal,
    headers: { 'X-Resume-Token': RB.token, ...(options.headers || {}) } };
  if (init.body && typeof init.body === 'object') {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(init.body);
  }
  try {
    const r = await fetch(path + (path.includes('?') ? '&' : '?') + 't=' + Date.now(), init);
    const data = await r.json();
    if (!r.ok) {
      const error = new Error(data.error || (path + ' → HTTP ' + r.status));
      error.status = r.status;
      throw error;
    }
    return data;
  } catch (e) {
    if (e.status) throw e;
    if (e.name === 'AbortError') throw new Error('本地服务响应超时。内容可能已保存，请重连后核对；不要反复点击。');
    throw new Error('无法连接本地服务（' + e.message + '）');
  } finally {
    clearTimeout(timer);
  }
}

function showConnectionError(error) {
  let banner = document.getElementById('connectionError');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'connectionError';
    banner.className = 'connection-error banner banner-error';
    banner.setAttribute('role', 'alert');
    document.body.appendChild(banner);
  }
  banner.hidden = !error;
  banner.textContent = error ? (error.status === 401
    ? '服务会话已改变。请从 Agent 提供的最新完整链接重新打开页面。'
    : '与本地服务的连接中断，正在重连。' + error.message) : '';
}

/* ── 阶段工具 ── */
const STAGE_LIST = [
  ['gallery', '选模板'],
  ['generating', '生成中'],
  ['editor', '编辑'],
  ['done', '完成'],
];
const STAGE_URL = {
  writing: '/gallery',
  gallery: '/gallery',
  generating: '/waiting',
  editor: '/editor',
  done: '/editor',
};

/* ── 事件轮询：周期拉 /api/events，把新事件分发给订阅者 ── */
function startEventPolling(handlers, intervalMs = 1200) {
  let cursor = null;  // 首轮先建基线：只处理加载之后的新事件（历史回放会把
                      // 旧的 stage 事件再触发一遍，编辑器会被旧 generating
                      // 事件踢回等待页死循环）；与 Agent 侧 wait_for_event
                      // 的 future-only 语义一致
  let stopped = false;
  (async function loop() {
    if (stopped) return;
    try {
      const res = await api('/api/events?cursor=' + (cursor === null ? 0 : cursor));
      showConnectionError(null);
      if (cursor === null) {
        cursor = res.cursor;  // 基线：本次响应里的事件视为历史，不派发
      } else {
        cursor = res.cursor;
        for (const ev of res.events || []) {
          for (const h of handlers) {
            try { await h(ev, res.state); } catch (e) { console.error('event handler failed', e); }
          }
        }
      }
      // 没有新事件也把最新 state 交给只关心状态的订阅者（null 事件）
      for (const h of handlers) {
        try { await h(null, res.state); } catch (e) { console.error('state handler failed', e); }
      }
    } catch (e) {
      showConnectionError(e);
    }
    if (!stopped) setTimeout(loop, intervalMs);
  })();
  return { stop() { stopped = true; } };
}

/* ── 小工具 ── */
function $(sel, root) { return (root || document).querySelector(sel); }
function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }
function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function timeAgo(ts) {
  if (!ts) return '';
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 5) return '刚刚';
  if (s < 60) return s + ' 秒前';
  return Math.round(s / 60) + ' 分钟前';
}

let toastTimer = null;
function toast(msg, ms = 2400) {
  let el = $('.toast');
  if (!el) {
    el = document.createElement('div');
    el.className = 'toast';
    el.setAttribute('role', 'status');
    document.body.appendChild(el);
  }
  el.textContent = msg;
  requestAnimationFrame(() => el.classList.add('show'));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), ms);
}

/* ── 通用 SVG 图标（内联，省一次请求） ── */
const ICONS = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>',
  caret: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>',
  grip: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M8 6h.01M8 12h.01M8 18h.01M16 6h.01M16 12h.01M16 18h.01"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13"/></svg>',
  plus: '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  chevronR: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>',
};

/* 无令牌时给页面一个可见提示（页面自己决定是否还要继续初始化） */
function warnNoToken(prefix) {
  if (RB.token) return false;
  const el = $('#noToken');
  if (el) el.classList.remove('hidden');
  else toast(prefix + '：缺少令牌，请从 Agent 给出的带 ?token= 的链接打开本页', 6000);
  return true;
}
