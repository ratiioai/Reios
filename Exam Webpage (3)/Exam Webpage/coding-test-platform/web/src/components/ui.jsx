import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { markdownToHtml } from "../lib/format.js";

/* ── Brand ─────────────────────────────────────────────────────────── */
export function Mark({ size = 30, light = false }) {
  const id = useMemo(() => "rg" + Math.random().toString(36).slice(2, 8), []);
  return (
    <svg className={"mark" + (light ? " mark-light" : "")} width={size} height={size}
         viewBox="0 0 32 32" aria-hidden="true">
      {!light && <rect width="32" height="32" rx="9" fill={`url(#${id})`} />}
      <circle cx="16" cy="16" r="8" fill="none" stroke="#fff" strokeWidth="2.6" opacity=".5" />
      <circle cx="16" cy="16" r="3.6" fill="#fff" />
      {!light && (
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="32" y2="32">
            <stop stopColor="#6366f1" /><stop offset="1" stopColor="#4338ca" />
          </linearGradient>
        </defs>
      )}
    </svg>
  );
}

export function Brand({ sub, light = false, style }) {
  return (
    <div className="brand" style={style}>
      <Mark light={light} />
      <span className="wordmark">Reios{sub && <span className="sub">{sub}</span>}</span>
    </div>
  );
}

/** Credit line shown on every screen. */
export const Credit = ({ style }) => <div className="credit" style={style}>Developed by Ratiio</div>;

/** The organization's own logo and name when its branding add-on is on, else the Reios mark. */
export function OrgBrand({ branding, sub, style }) {
  if (!branding) return <Brand sub={sub} style={style} />;
  return (
    <div className="brand" style={style}>
      {branding.logo
        ? <img src={branding.logo} alt="" style={{ height: 34, maxWidth: 120, objectFit: "contain", borderRadius: 6 }} />
        : <Mark />}
      <span className="wordmark" style={branding.color ? { color: branding.color } : undefined}>
        {branding.name}{sub && <span className="sub">{sub}</span>}
      </span>
    </div>
  );
}

/* ── Small primitives ──────────────────────────────────────────────── */
export const Spinner = ({ lg }) => <span className={"spinner" + (lg ? " lg" : "")} />;

export const Loading = ({ label = "Loading…" }) => (
  <div className="loading"><Spinner lg /> {label}</div>
);

export const Badge = ({ color = "", dot = false, children, ...rest }) => (
  <span className={`badge ${color}${dot ? " dot" : ""}`} {...rest}>{children}</span>
);

export const Empty = ({ title, hint }) => (
  <div className="card empty">
    <span className="big">{title}</span>
    {hint && <span className="small">{hint}</span>}
  </div>
);

export const Progress = ({ value, max, color = "" }) => (
  <div className={`progress ${color}`}>
    <span style={{ width: `${max ? Math.max(0, Math.min(100, (value / max) * 100)) : 0}%` }} />
  </div>
);

export const Markdown = ({ children, className = "md", style }) => (
  <div className={className} style={style}
       dangerouslySetInnerHTML={{ __html: markdownToHtml(children) }} />
);

export function Field({ label, hint, children, style }) {
  return (
    <div className="field" style={style}>
      {label && <label>{label}</label>}
      {children}
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

/* ── Toasts ────────────────────────────────────────────────────────── */
const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastHost({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((message, type = "info", ms = 3500) => {
    const id = Math.random().toString(36).slice(2);
    setItems((xs) => [...xs, { id, message, type }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), ms);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      {createPortal(
        <div id="toasts">
          {items.map((t) => <div key={t.id} className={"toast " + t.type}>{t.message}</div>)}
        </div>,
        document.body
      )}
    </ToastCtx.Provider>
  );
}

/* ── Modal ─────────────────────────────────────────────────────────── */
export function Modal({ title, children, actions, onClose, wide, narrow, closable = true }) {
  const backdrop = useRef(null);
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape" && closable) onClose?.(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, closable]);

  return createPortal(
    <div
      className="modal-backdrop"
      ref={backdrop}
      onMouseDown={(e) => { if (closable && e.target === backdrop.current) onClose?.(); }}
    >
      <div className={`modal${wide ? " wide" : ""}${narrow ? " narrow" : ""}`} role="dialog" aria-modal="true">
        <div className="modal-head">
          <h2>{title}</h2>
          {closable && (
            <button className="btn ghost sm" onClick={onClose} aria-label="Close">✕</button>
          )}
        </div>
        <div className="modal-body">{children}</div>
        {actions && <div className="modal-foot">{actions}</div>}
      </div>
    </div>,
    document.body
  );
}

/** Async-aware footer button: disables itself while its handler runs. */
export function ModalButton({ onClick, cls = "", children }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      className={"btn " + cls}
      disabled={busy}
      onClick={async () => {
        if (!onClick) return;
        setBusy(true);
        try { await onClick(); } finally { setBusy(false); }
      }}
    >
      {busy && <Spinner />} {children}
    </button>
  );
}

/** Promise-based confirm, mounted by ConfirmHost. */
const ConfirmCtx = createContext(() => Promise.resolve(false));
export const useConfirm = () => useContext(ConfirmCtx);

export function ConfirmHost({ children }) {
  const [req, setReq] = useState(null);
  const ask = useCallback(
    (title, message, okLabel = "Confirm", danger = false) =>
      new Promise((resolve) => setReq({ title, message, okLabel, danger, resolve })),
    []
  );
  const settle = (value) => { req?.resolve(value); setReq(null); };

  return (
    <ConfirmCtx.Provider value={ask}>
      {children}
      {req && (
        <Modal
          title={req.title}
          narrow
          onClose={() => settle(false)}
          actions={
            <>
              <button className="btn" onClick={() => settle(false)}>Cancel</button>
              <button className={"btn " + (req.danger ? "danger solid" : "primary")}
                      onClick={() => settle(true)}>{req.okLabel}</button>
            </>
          }
        >
          <p>{req.message}</p>
        </Modal>
      )}
    </ConfirmCtx.Provider>
  );
}

/* ── Theme ─────────────────────────────────────────────────────────── */
export function ThemeToggle({ className = "btn ghost sm" }) {
  const toggle = () => {
    const current =
      document.documentElement.getAttribute("data-theme") ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("reios_theme", next); } catch { /* ignore */ }
  };
  return (
    <button className={className} onClick={toggle} title="Toggle dark mode" aria-label="Toggle dark mode">
      ◐
    </button>
  );
}
