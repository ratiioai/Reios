const TOKEN_KEY = "reios_token";
const USER_KEY = "reios_user";

export const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage blocked */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* storage blocked */ } },
};

export const auth = {
  token: () => store.get(TOKEN_KEY),
  user() { try { return JSON.parse(store.get(USER_KEY) || "null"); } catch { return null; } },
  save(token, user) { store.set(TOKEN_KEY, token); store.set(USER_KEY, JSON.stringify(user)); },
  clear() { store.del(TOKEN_KEY); store.del(USER_KEY); },
};

export class ApiError extends Error {
  constructor(status, message, data) { super(message); this.status = status; this.data = data; }
}

function apiBase() {
  // Vite dev server proxies /api to the backend; in production the backend serves this app.
  const configured = import.meta.env.VITE_API_BASE;
  if (configured) return configured.replace(/\/$/, "");
  return "";
}

function errorMessage(data, status) {
  if (!data) return `Request failed (${status})`;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((d) => `${(d.loc || []).filter((x) => x !== "body").join(".")}: ${d.msg}`)
      .join("; ");
  }
  return data.error || `Request failed (${status})`;
}

/** Fired on 401 so the router can bounce to the login screen. */
export const onUnauthorized = { handler: null };

export async function api(method, path, body, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = auth.token();
  if (token) headers.Authorization = "Bearer " + token;

  let payload;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined && body !== null) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  // Reads (and calls marked safe to repeat) retry through a dropped connection or a busy server,
  // which is what a whole lab signing in at once looks like.
  const attempts = method === "GET" || opts.retry ? 4 : 1;
  let res;
  for (let attempt = 1; ; attempt++) {
    try {
      res = await fetch(apiBase() + path, { method, headers, body: payload, keepalive: !!opts.keepalive });
      if (![502, 503, 504].includes(res.status) || attempt >= attempts) break;
    } catch {
      if (attempt >= attempts) throw new ApiError(0, "Cannot reach the server. Check your connection.");
    }
    await new Promise((r) => setTimeout(r, 400 * 2 ** (attempt - 1) + Math.random() * 300));
  }

  if (opts.raw) {
    if (!res.ok) throw new ApiError(res.status, `Request failed (${res.status})`);
    return res;
  }

  let data = null;
  const text = await res.text();
  if (text) { try { data = JSON.parse(text); } catch { data = { detail: text }; } }

  if (!res.ok) {
    if (res.status === 401 && !opts.noRedirect && !path.includes("/auth/login")) {
      auth.clear();
      if (onUnauthorized.handler) onUnauthorized.handler();
    }
    throw new ApiError(res.status, errorMessage(data, res.status), data);
  }
  return data;
}

export function qs(params) {
  const parts = [];
  for (const [k, v] of Object.entries(params || {})) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(v));
  }
  return parts.length ? "?" + parts.join("&") : "";
}

export async function download(path, filename) {
  const res = await api("GET", path, null, { raw: true });
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function downloadCSV(filename, header, rows) {
  const cell = (v) => {
    const s = String(v ?? "");
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const text = [header, ...rows].map((r) => r.map(cell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const homeFor = (role) => (role === "student" ? "/student" : "/console");
