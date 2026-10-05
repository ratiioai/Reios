/* Reios shared helpers: API calls, auth storage, UI utilities */
(function () {
  const TOKEN_KEY = "reios_token";
  const USER_KEY = "reios_user";

  function apiBase() {
    // Served by the backend itself (http://host:8000/app/reios/...) -> same origin
    if (location.protocol.startsWith("http") && location.pathname.startsWith("/app/")) return location.origin;
    if (window.APP_CONFIG && window.APP_CONFIG.getApiBase) return window.APP_CONFIG.getApiBase();
    return "http://localhost:8000";
  }

  const store = {
    get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* storage blocked */ } },
    del(key) { try { localStorage.removeItem(key); } catch (e) { /* storage blocked */ } },
  };

  const auth = {
    token: () => store.get(TOKEN_KEY),
    user: () => { try { return JSON.parse(store.get(USER_KEY) || "null"); } catch (e) { return null; } },
    save(token, user) { store.set(TOKEN_KEY, token); store.set(USER_KEY, JSON.stringify(user)); },
    clear() { store.del(TOKEN_KEY); store.del(USER_KEY); },
  };

  class ApiError extends Error {
    constructor(status, message, data) { super(message); this.status = status; this.data = data; }
  }

  function errorMessage(data, status) {
    if (!data) return `Request failed (${status})`;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map(d => `${(d.loc || []).filter(x => x !== "body").join(".")}: ${d.msg}`).join("; ");
    }
    return data.error || `Request failed (${status})`;
  }

  async function api(method, path, body, opts = {}) {
    const headers = Object.assign({}, opts.headers || {});
    const token = auth.token();
    if (token) headers["Authorization"] = "Bearer " + token;
    let payload;
    if (body instanceof FormData) payload = body;
    else if (body !== undefined && body !== null) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
    let res;
    try {
      res = await fetch(apiBase() + path, { method, headers, body: payload, keepalive: !!opts.keepalive });
    } catch (e) {
      throw new ApiError(0, "Cannot reach the server. Check your connection.");
    }
    if (opts.raw) {
      if (!res.ok) throw new ApiError(res.status, `Request failed (${res.status})`);
      return res;
    }
    let data = null;
    const text = await res.text();
    if (text) { try { data = JSON.parse(text); } catch (e) { data = { detail: text }; } }
    if (!res.ok) {
      if (res.status === 401 && !opts.noRedirect && !path.includes("/auth/login")) {
        auth.clear();
        location.href = "index.html?expired=1";
      }
      throw new ApiError(res.status, errorMessage(data, res.status), data);
    }
    return data;
  }

  function qs(params) {
    const parts = [];
    for (const [k, v] of Object.entries(params || {})) {
      if (v === undefined || v === null || v === "") continue;
      parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(v));
    }
    return parts.length ? "?" + parts.join("&") : "";
  }

  function esc(value) {
    return String(value === undefined || value === null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fmtDate(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (isNaN(d)) return "—";
    return d.toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function toLocalInput(value) {
    const d = value ? new Date(value) : new Date();
    const pad = n => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function fromLocalInput(value) { return value ? new Date(value).toISOString() : null; }

  function fmtDuration(seconds) {
    seconds = Math.max(0, Math.floor(seconds || 0));
    const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
    const pad = n => String(n).padStart(2, "0");
    return h ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
  }

  function toast(message, type = "info", ms = 3500) {
    let box = document.getElementById("toasts");
    if (!box) { box = document.createElement("div"); box.id = "toasts"; document.body.appendChild(box); }
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.textContent = message;
    box.appendChild(el);
    setTimeout(() => el.remove(), ms);
  }

  /** Open a modal. Returns {el, close}. `actions` = [{label, cls, onClick(close)}] */
  function modal({ title, body, actions = [], wide = false, onClose }) {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal ${wide ? "wide" : ""}" role="dialog" aria-modal="true">
        <div class="modal-head"><h2>${esc(title)}</h2><button class="btn ghost sm" data-close aria-label="Close">✕</button></div>
        <div class="modal-body"></div>
        <div class="modal-foot"></div>
      </div>`;
    const bodyEl = backdrop.querySelector(".modal-body");
    if (typeof body === "string") bodyEl.innerHTML = body; else if (body) bodyEl.appendChild(body);
    const close = () => { backdrop.remove(); if (onClose) onClose(); };
    const foot = backdrop.querySelector(".modal-foot");
    if (!actions.length) foot.remove();
    actions.forEach(a => {
      const b = document.createElement("button");
      b.className = "btn " + (a.cls || "");
      b.textContent = a.label;
      b.addEventListener("click", async () => {
        if (!a.onClick) return close();
        b.disabled = true;
        try { await a.onClick(close, backdrop); } finally { b.disabled = false; }
      });
      foot.appendChild(b);
    });
    backdrop.querySelector("[data-close]").addEventListener("click", close);
    backdrop.addEventListener("mousedown", e => { if (e.target === backdrop) close(); });
    document.body.appendChild(backdrop);
    return { el: backdrop, close };
  }

  function confirmBox(title, message, okLabel = "Confirm", danger = false) {
    return new Promise(resolve => {
      let answered = false;
      modal({
        title, body: `<p>${esc(message)}</p>`,
        actions: [
          { label: "Cancel", onClick: c => { answered = true; resolve(false); c(); } },
          { label: okLabel, cls: danger ? "danger solid" : "primary", onClick: c => { answered = true; resolve(true); c(); } },
        ],
        onClose: () => { if (!answered) resolve(false); },
      });
    });
  }

  async function download(path, filename) {
    const res = await api("GET", path, null, { raw: true });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function downloadCSV(filename, header, rows) {
    const cell = v => {
      const s = String(v === undefined || v === null ? "" : v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const text = [header, ...rows].map(r => r.map(cell).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function requireRole(roles) {
    const user = auth.user();
    if (!auth.token() || !user || !roles.includes(user.role)) {
      location.href = "index.html";
      throw new Error("redirecting");
    }
    return user;
  }

  function homeFor(role) { return role === "student" ? "student.html" : "console.html"; }

  async function logout() {
    auth.clear();
    location.href = "index.html";
  }

  function markdown(text) {
    if (window.marked) {
      const html = window.marked.parse(text || "");
      // Strip scripts and inline handlers from authored content
      const tpl = document.createElement("template");
      tpl.innerHTML = html;
      tpl.content.querySelectorAll("script,iframe,object,embed,style").forEach(n => n.remove());
      tpl.content.querySelectorAll("*").forEach(n => {
        [...n.attributes].forEach(a => { if (/^on/i.test(a.name) || /javascript:/i.test(a.value)) n.removeAttribute(a.name); });
      });
      return tpl.innerHTML;
    }
    return esc(text || "").replace(/\n/g, "<br>");
  }

  function initTheme() {
    const saved = store.get("reios_theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);
  }
  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    store.set("reios_theme", next);
  }
  initTheme();

  window.Reios = {
    api, qs, auth, esc, fmtDate, fmtDuration, toLocalInput, fromLocalInput, toast, modal, confirmBox,
    download, downloadCSV, requireRole, homeFor, logout, markdown, toggleTheme, apiBase, ApiError, store,
  };
})();
