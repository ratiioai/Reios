import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api.js";
import { useAuth } from "../../lib/auth.jsx";
import { fmtDate, fmtDuration } from "../../lib/format.js";
import { Badge, Loading, Markdown, Modal, OrgBrand, Spinner, useToast } from "../../components/ui.jsx";
import CodingPanel from "./CodingPanel.jsx";
import LeaderboardModal from "./LeaderboardModal.jsx";
import {
  DEFAULT_CODE, VIOLATION_TEXT, buildAnswerState, enterFullscreen, exitFullscreen,
  isAnswered, isFullscreen,
} from "./examState.js";

export default function Exam() {
  const { examId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const [phase, setPhase] = useState("loading"); // loading | prestart | running | done | locked
  const [info, setInfo] = useState(null);
  const [paper, setPaper] = useState(null);
  const [error, setError] = useState("");
  const [doneMsg, setDoneMsg] = useState("");
  const [boardOn, setBoardOn] = useState(false);
  const [showBoard, setShowBoard] = useState(false);
  const closeBoard = useCallback(() => setShowBoard(false), []);
  const [lock, setLock] = useState(null);

  const [index, setIndex] = useState(0);
  const [visited, setVisited] = useState(() => new Set());
  const [mcq, setMcq] = useState({});
  const [code, setCode] = useState({});
  const [violations, setViolations] = useState(0);
  const [left, setLeft] = useState(0);
  const [showFsOverlay, setShowFsOverlay] = useState(false);
  const [warning, setWarning] = useState(null);
  const [showInstr, setShowInstr] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [saveLabel, setSaveLabel] = useState("");

  // Refs mirror state for use inside long-lived event listeners.
  const R = useRef({});
  R.current = { paper, mcq, code, index, violations, phase };
  const deadlineRef = useRef(0);
  const sessionRef = useRef(null);
  const attemptRef = useRef(null);
  const finishedRef = useRef(false);
  const savingRef = useRef(Promise.resolve());
  const retryRef = useRef(null);

  /* ── API helpers ─────────────────────────────────────────────────── */
  const hdr = useCallback(() => ({ headers: { "X-Exam-Session": sessionRef.current } }), []);

  const finish = useCallback((message) => {
    if (finishedRef.current) return;
    finishedRef.current = true;
    document.body.classList.remove("exam-mode", "no-select");
    exitFullscreen();
    setDoneMsg(message);
    setPhase("done");
  }, []);

  const lockOut = useCallback((title, text) => {
    finishedRef.current = true;
    document.body.classList.remove("exam-mode", "no-select");
    exitFullscreen();
    setLock({ title, text });
    setPhase("locked");
  }, []);

  const handleConflict = useCallback((message) => {
    if (finishedRef.current) return;
    if (/another window|another device|one session/i.test(message)) {
      lockOut(
        "Exam opened somewhere else",
        "This exam was opened in another tab or device, so this window has been locked. Only one session is allowed at a time."
      );
    } else {
      finish(message);
    }
  }, [finish, lockOut]);

  const examApi = useCallback((method, path, body) =>
    api(method, `/api/reios/student/attempts/${attemptRef.current}${path}`, body, hdr())
      .catch((err) => { if (err.status === 409) handleConflict(err.message); throw err; }),
    [hdr, handleConflict]
  );

  const retryLater = useCallback((fn) => {
    clearTimeout(retryRef.current);
    retryRef.current = setTimeout(() => { if (!finishedRef.current) fn(); }, 5000);
  }, []);

  /* ── Violations ──────────────────────────────────────────────────── */
  const violation = useCallback(async (type, details) => {
    if (finishedRef.current || R.current.phase !== "running") return;
    try {
      const r = await api("POST", `/api/reios/student/attempts/${attemptRef.current}/violation`,
                          { type, details }, hdr());
      setViolations(r.violations);
      if (r.auto_submitted) {
        finish("Your exam was submitted automatically because of repeated violations.");
        return;
      }
      // The fullscreen overlay already explains that case.
      if (r.counted && !(type === "fullscreen_exit" && R.current.paper?.exam.require_fullscreen)) {
        setWarning({ type, left: r.max_violations - r.violations });
      }
    } catch (err) {
      if (err.status === 409) handleConflict(err.message);
    }
  }, [hdr, finish, handleConflict]);

  /* ── Load pre-start info ─────────────────────────────────────────── */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const i = await api("GET", `/api/reios/student/exams/${examId}`);
        if (cancelled) return;
        if (i.must_change_password) { navigate("/student", { replace: true }); return; }
        setBoardOn(!!i.leaderboard_enabled);
        if (i.attempt && i.attempt.status !== "in_progress") {
          attemptRef.current = i.attempt.id;
          setDoneMsg("You have already submitted this exam.");
          setPhase("done");
          return;
        }
        setInfo(i);
        setPhase("prestart");
      } catch (err) {
        if (!cancelled) { setError(err.message); setPhase("prestart"); }
      }
    })();
    return () => { cancelled = true; };
  }, [examId, navigate]);

  /* ── Start ───────────────────────────────────────────────────────── */
  const [startErr, setStartErr] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [starting, setStarting] = useState(false);

  const start = useCallback(async () => {
    setStartErr("");
    if (window.screen && window.screen.isExtended) {
      setStartErr("Multiple displays detected. Disconnect extra monitors and reload this page to start.");
      return;
    }
    setStarting(true);
    try {
      if (info.require_fullscreen) await enterFullscreen();
    } catch (err) {
      setStartErr(err.message || "Allow fullscreen to start the exam.");
      setStarting(false);
      return;
    }
    try {
      const p = await api("POST", `/api/reios/student/exams/${examId}/start`, null, { retry: true });
      sessionRef.current = p.session;
      attemptRef.current = p.attempt_id;
      deadlineRef.current = Date.now() + p.seconds_left * 1000;

      const { mcq: m, code: c } = buildAnswerState(p);
      const firstOpen = p.items.findIndex((it) => !isAnswered(it, m, c));
      const startAt = firstOpen >= 0 ? firstOpen : 0;
      const seen = new Set();
      p.items.forEach((it, idx) => { if (isAnswered(it, m, c) || idx < startAt) seen.add(it.item_id); });
      if (p.items[startAt]) seen.add(p.items[startAt].item_id);

      setMcq(m); setCode(c); setVisited(seen); setIndex(startAt);
      setViolations(p.violations);
      setPaper(p);
      document.body.classList.add("exam-mode");
      if (p.exam.block_copy_paste) document.body.classList.add("no-select");
      setPhase("running");
    } catch (err) {
      setStartErr(err.message);
      setStarting(false);
      exitFullscreen();
    }
  }, [examId, info]);

  /* ── Saving answers ──────────────────────────────────────────────── */
  const saveMcq = useCallback((itemId, next) => {
    savingRef.current = savingRef.current
      .then(() => examApi("PUT", `/mcq/${itemId}`,
        { selected: next.selected, marked_for_review: next.review }))
      .catch((err) => {
        if (err.status !== 409) {
          toast("Couldn't save your answer: " + err.message + ". It will retry.", "error");
          retryLater(() => saveMcq(itemId, next));
        }
      });
  }, [examApi, toast, retryLater]);

  const saveCode = useCallback((force) => {
    const { paper: p, index: i, code: c } = R.current;
    const item = p?.items[i];
    if (!item || item.type !== "coding" || finishedRef.current) return savingRef.current;
    const st = c[item.item_id];
    if (!st || (!st.dirty && !force)) return savingRef.current;

    setCode((prev) => ({ ...prev, [item.item_id]: { ...prev[item.item_id], dirty: false } }));
    const body = { language: st.language, code: st.drafts[st.language] || "" };
    setSaveLabel("Saving…");
    savingRef.current = savingRef.current
      .then(() => examApi("PUT", `/code/${item.item_id}`, body))
      .then(() => setSaveLabel("Saved " + new Date().toLocaleTimeString()))
      .catch((err) => {
        setCode((prev) => ({ ...prev, [item.item_id]: { ...prev[item.item_id], dirty: true } }));
        setSaveLabel("Not saved");
        if (err.status !== 409) retryLater(() => saveCode(false));
      });
    return savingRef.current;
  }, [examApi, retryLater]);

  /* ── Heartbeat ───────────────────────────────────────────────────── */
  const heartbeat = useCallback(async () => {
    if (finishedRef.current) return;
    try {
      const r = await api("POST", `/api/reios/student/attempts/${attemptRef.current}/heartbeat`,
                          null, hdr());
      if (r.status !== "in_progress") {
        finish(r.status === "auto_submitted" ? "Your exam was submitted." : "Exam submitted.");
        return;
      }
      if (!r.session_valid) { handleConflict("opened in another window"); return; }
      deadlineRef.current = Date.now() + r.seconds_left * 1000;
      setViolations((v) => (r.violations !== v ? r.violations : v));
    } catch {
      /* offline — the next heartbeat will resync */
    }
  }, [hdr, finish, handleConflict]);

  /* ── Timers ──────────────────────────────────────────────────────── */
  const autoSubmitting = useRef(false);
  useEffect(() => {
    if (phase !== "running") return undefined;
    const tick = setInterval(() => {
      const secs = Math.max(0, (deadlineRef.current - Date.now()) / 1000);
      setLeft(secs);
      if (secs <= 0 && !autoSubmitting.current) {
        autoSubmitting.current = true;
        saveCode(true).finally(() =>
          examApi("POST", "/submit")
            .then(() => finish("Time is up. Your exam was submitted automatically."))
            .catch(() => heartbeat())
        );
      }
    }, 500);
    const hb = setInterval(heartbeat, 20000);
    const autosave = setInterval(() => saveCode(false), 15000);
    return () => { clearInterval(tick); clearInterval(hb); clearInterval(autosave); };
  }, [phase, saveCode, examApi, finish, heartbeat]);

  /* ── Anti-cheat listeners ────────────────────────────────────────── */
  useEffect(() => {
    if (phase !== "running" || !paper) return undefined;
    const ex = paper.exam;
    const off = [];
    const on = (target, type, fn, opts) => {
      target.addEventListener(type, fn, opts);
      off.push(() => target.removeEventListener(type, fn, opts));
    };

    if (ex.require_fullscreen) {
      const onFs = () => {
        if (finishedRef.current) return;
        if (isFullscreen()) setShowFsOverlay(false);
        else { setShowFsOverlay(true); violation("fullscreen_exit"); }
      };
      ["fullscreenchange", "webkitfullscreenchange", "MSFullscreenChange"]
        .forEach((t) => on(document, t, onFs));
      if (!isFullscreen()) setShowFsOverlay(true);
    }

    on(document, "visibilitychange", () => {
      if (document.hidden) violation("tab_switch", "Page hidden");
    });
    on(window, "blur", () => {
      // Alt-tabbing to another app blurs the window; clicking inside the page does not.
      setTimeout(() => {
        if (!document.hasFocus() && !document.hidden) {
          violation("window_blur", "Focus moved to another window");
        }
      }, 300);
    });

    if (ex.block_copy_paste) {
      on(document, "copy", (e) => { e.preventDefault(); violation("copy_attempt"); }, true);
      on(document, "cut", (e) => { e.preventDefault(); violation("copy_attempt", "cut"); }, true);
      on(document, "paste", (e) => {
        // The editor cancels its own pastes; this catches everything else.
        if (!e.target.closest || !e.target.closest(".cm-editor")) {
          e.preventDefault(); violation("paste_attempt");
        }
      }, true);
      on(document, "contextmenu", (e) => { e.preventDefault(); violation("right_click"); }, true);
      on(document, "dragstart", (e) => e.preventDefault(), true);
      on(document, "drop", (e) => {
        if (!e.target.closest || !e.target.closest(".cm-editor")) e.preventDefault();
      }, true);
      on(document, "keydown", (e) => {
        const k = (e.key || "").toLowerCase();
        const ctrl = e.ctrlKey || e.metaKey;
        if (k === "f12" || (ctrl && e.shiftKey && ["i", "j", "c", "k"].includes(k)) ||
            (ctrl && ["u", "s", "p"].includes(k))) {
          e.preventDefault();
          violation(
            k === "f12" || e.shiftKey ? "devtools_open" : "keyboard_shortcut",
            `${ctrl ? "Ctrl+" : ""}${e.shiftKey ? "Shift+" : ""}${e.key}`
          );
        }
        if (k === "printscreen") violation("print_screen");
      }, true);
      on(document, "keyup", (e) => {
        if ((e.key || "").toLowerCase() === "printscreen") {
          navigator.clipboard?.writeText("").catch(() => {});
        }
      }, true);
    }

    on(window, "beforeunload", (e) => {
      if (!finishedRef.current) { saveCode(true); e.preventDefault(); e.returnValue = ""; }
    });
    on(window, "offline", () =>
      toast("You're offline. Keep working; answers will sync when you reconnect.", "error", 6000));
    on(window, "online", () => { violation("network_online"); heartbeat(); toast("Back online", "success"); });

    return () => off.forEach((fn) => fn());
  }, [phase, paper, violation, saveCode, heartbeat, toast]);

  useEffect(() => () => { document.body.classList.remove("exam-mode", "no-select"); }, []);

  /* ── Navigation ──────────────────────────────────────────────────── */
  const go = useCallback((next) => {
    const items = R.current.paper.items;
    const clamped = Math.max(0, Math.min(items.length - 1, next));
    saveCode(false);
    setIndex(clamped);
    setVisited((v) => new Set(v).add(items[clamped].item_id));
  }, [saveCode]);

  const item = paper?.items[index];

  /* ── Render: non-running phases ──────────────────────────────────── */
  if (phase === "loading") return <div className="pre-start"><Loading /></div>;

  if (phase === "done") {
    return (
      <div className="pre-start" style={{ textAlign: "center", paddingTop: 80 }}>
        <div className="card">
          <h1>{doneMsg}</h1>
          <p className="muted">You can close this window. Your results will be shared with you.</p>
          <div className="row" style={{ justifyContent: "center" }}>
            {boardOn && <button className="btn" onClick={() => setShowBoard(true)}>View leaderboard</button>}
            <Link className="btn primary"
                  to={attemptRef.current ? `/student?result=${attemptRef.current}` : "/student"}>
              Go to dashboard
            </Link>
          </div>
        </div>
        {showBoard && <LeaderboardModal examId={Number(examId)} onClose={closeBoard} />}
      </div>
    );
  }

  if (phase === "locked") {
    return (
      <div className="pre-start" style={{ textAlign: "center", paddingTop: 80 }}>
        <div className="card">
          <h1>{lock.title}</h1>
          <p>{lock.text}</p>
          <Link className="btn" to="/student">Back to dashboard</Link>
        </div>
      </div>
    );
  }

  if (phase === "prestart") {
    if (error) {
      return (
        <div className="pre-start">
          <div className="card empty">
            <span className="big">{error}</span>
            <Link to="/student">Back to dashboard</Link>
          </div>
        </div>
      );
    }
    const i = info;
    const resuming = i.attempt && i.attempt.status === "in_progress";
    const canStart = resuming || i.window === "live";
    const totalQs = i.sections.reduce((n, s) => n + s.questions, 0);

    return (
      <div className="pre-start">
        <OrgBrand branding={user?.college?.branding} sub="Proctored exam" />
        <Link to="/student" className="small">← Dashboard</Link>
        <div className="page-head" style={{ marginTop: 10 }}>
          <h1>{i.title}</h1>
          <p className="lede">{fmtDate(i.start_at)} → {fmtDate(i.end_at)}</p>
        </div>

        <div className="grid cols-4" style={{ margin: "18px 0" }}>
          <div className="stat">
            <div className="label">Duration</div>
            <div className="value">{i.duration_minutes}<span className="muted" style={{ fontSize: 14 }}> min</span></div>
          </div>
          <div className="stat plain"><div className="label">Questions</div><div className="value">{totalQs}</div></div>
          <div className="stat plain"><div className="label">Total marks</div><div className="value">{i.max_score}</div></div>
          <div className={"stat " + (resuming ? "amber" : i.window === "live" ? "green" : "red")}>
            <div className="label">{resuming ? "Time left" : "Status"}</div>
            <div className="value" style={{ fontSize: 20 }}>
              {resuming ? fmtDuration(i.attempt.seconds_left)
                : i.window === "live" ? "Open"
                : i.window === "upcoming" ? "Not open yet" : "Closed"}
            </div>
          </div>
        </div>

        <div className="card">
          <h3>Sections</h3>
          <div className="table-wrap compact">
            <table>
              <thead><tr><th>Section</th><th className="num">Questions</th><th className="num">Marks</th></tr></thead>
              <tbody>
                {i.sections.map((s) => (
                  <tr key={s.section}>
                    <td><strong>{s.section}</strong></td>
                    <td className="num">{s.questions}</td>
                    <td className="num">{s.marks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <h3>Rules</h3>
          <ul style={{ margin: 0, paddingLeft: 19, color: "var(--text-soft)" }}>
            <li>The timer starts when you click Start and keeps running even if you close the browser. The exam is submitted automatically when time runs out.</li>
            {i.require_fullscreen && <li>The exam runs in <strong>fullscreen</strong>. Leaving fullscreen counts as a violation.</li>}
            <li>Switching tabs, switching windows or minimising the browser counts as a violation.</li>
            {i.block_copy_paste && <li>Copy, paste and right-click are disabled. Trying to paste counts as a violation.</li>}
            <li>After <strong>{i.max_violations} violations</strong> your exam is submitted automatically.</li>
            <li>You can open the exam in only one browser tab or device at a time.</li>
            {i.negative_marking
              ? <li><strong>Negative marking</strong> applies to wrong MCQ answers. Unanswered questions get zero.</li>
              : <li>There is no negative marking.</li>}
            <li>Answers are saved automatically as you go.{i.has_coding && <> For coding questions, use <strong>Submit code</strong> to score against hidden test cases; unsubmitted code is graded when the exam ends.</>}</li>
            <li>Every action is logged and reviewed by the exam organizers.</li>
          </ul>
        </div>

        {i.instructions && (
          <div className="card">
            <h3>Instructions</h3>
            <Markdown>{i.instructions}</Markdown>
          </div>
        )}

        <div className="card">
          <label className="check">
            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
            I have read the rules and will not use unfair means.
          </label>
          <div className="small" style={{ color: "var(--danger)", minHeight: 18, fontWeight: 550 }}>
            {startErr}
          </div>
          <button className="btn primary lg" disabled={!agreed || !canStart || starting} onClick={start}>
            {starting ? <><Spinner /> Starting</> : resuming ? "Resume exam" : "Start exam"}
          </button>
          {!canStart && (
            <p className="muted small" style={{ margin: "10px 0 0" }}>
              {i.window === "upcoming"
                ? "The exam hasn't opened yet. Reload this page once it opens."
                : "This exam has closed."}
            </p>
          )}
        </div>
      </div>
    );
  }

  /* ── Render: running ─────────────────────────────────────────────── */
  const sections = paper.sections;
  const answeredCount = paper.items.filter((it) => isAnswered(it, mcq, code)).length;
  const maxViol = paper.exam.max_violations;

  return (
    <>
      <div className="exam-shell">
        <div className="exam-head">
          <button className="btn sm menu-toggle" onClick={() => setPaletteOpen((o) => !o)}
                  aria-label="Questions">☰</button>
          <div className="title">{paper.exam.title}</div>
          <span className="small muted">{user.name} · {user.roll_no}</span>
          {violations
            ? <Badge color={violations >= maxViol - 1 ? "red" : "amber"}>⚠ {violations}/{maxViol} violations</Badge>
            : <Badge color="green">No violations</Badge>}
          <span className={"timer" + (left <= 300 ? " low" : left <= 600 ? " warn" : "")}>
            {fmtDuration(left)}
          </span>
          <button className="btn sm" onClick={() => setShowInstr(true)}>Instructions</button>
          <button className="btn danger solid sm" disabled={submitting}
                  onClick={async () => { await saveCode(true); setConfirmSubmit(true); }}>
            Submit exam
          </button>
        </div>

        <div className="exam-body">
          <aside className={"palette" + (paletteOpen ? " open" : "")}>
            {sections.map((sec) => (
              <div key={sec}>
                <h4>{sec}</h4>
                <div className="pal-grid">
                  {paper.items.map((it, i) => it.section !== sec ? null : (
                    <button
                      key={it.item_id}
                      className={[
                        "pal-btn",
                        isAnswered(it, mcq, code) ? "answered" : visited.has(it.item_id) ? "visited" : "",
                        it.type === "mcq" && mcq[it.item_id]?.review ? "review" : "",
                        i === index ? "current" : "",
                      ].filter(Boolean).join(" ")}
                      onClick={() => { go(i); setPaletteOpen(false); }}
                    >
                      {it.number}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            <div className="legend">
              <span style={{ "--c": "var(--success)" }}>Answered ({answeredCount})</span>
              <span style={{ "--c": "var(--danger-soft)" }}>
                Not answered ({paper.items.filter((it) => visited.has(it.item_id) && !isAnswered(it, mcq, code)).length})
              </span>
              <span style={{ "--c": "var(--surface-3)" }}>
                Not visited ({paper.items.filter((it) => !visited.has(it.item_id)).length})
              </span>
              <span style={{ "--c": "var(--violet)" }}>
                For review ({paper.items.filter((it) => it.type === "mcq" && mcq[it.item_id]?.review).length})
              </span>
            </div>
          </aside>

          <section className={"content" + (item.type === "coding" ? " is-coding" : "")}>
            <div className="q-wrap">
              <div className="q-head">
                <div>
                  <span className="q-num">Question {item.number} / {paper.items.length}</span>
                  <div className="strong" style={{ fontSize: 15, marginTop: 1 }}>{item.section}</div>
                </div>
                <div className="row tight small">
                  <Badge color="green">+{item.marks} marks</Badge>
                  {item.type === "mcq" && item.negative_marks > 0 &&
                    <Badge color="red">−{item.negative_marks} if wrong</Badge>}
                  {item.type === "mcq" && item.is_multi && <Badge color="blue">Select all that apply</Badge>}
                </div>
              </div>

              {item.type === "mcq" ? (
                <div className="card">
                  <Markdown style={{ fontSize: 15.5, lineHeight: 1.6 }}>{item.question_text}</Markdown>
                  <ul className="options">
                    {item.options.map((o, i) => {
                      const st = mcq[item.item_id];
                      const checked = st.selected.includes(o.id);
                      return (
                        <li key={o.id}>
                          <label className={checked ? "chosen" : ""}>
                            <input
                              type={item.is_multi ? "checkbox" : "radio"}
                              name={`opt-${item.item_id}`}
                              checked={checked}
                              onChange={(e) => {
                                const prev = mcq[item.item_id];
                                const selected = item.is_multi
                                  ? (e.target.checked
                                      ? [...prev.selected, o.id]
                                      : prev.selected.filter((x) => x !== o.id))
                                  : [o.id];
                                const next = { ...prev, selected };
                                setMcq((m) => ({ ...m, [item.item_id]: next }));
                                saveMcq(item.item_id, next);
                              }}
                            />
                            <span><strong>{String.fromCharCode(65 + i)}.</strong> {o.text}</span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ) : (
                <CodingPanel
                  key={item.item_id}
                  item={item}
                  state={code[item.item_id]}
                  langs={paper.exam.allowed_languages}
                  blockPaste={paper.exam.block_copy_paste}
                  saveLabel={saveLabel}
                  onPasteBlocked={() => violation("paste_attempt", "Paste into code editor")}
                  onChange={(value) =>
                    setCode((c) => {
                      const st = c[item.item_id];
                      return {
                        ...c,
                        [item.item_id]: {
                          ...st,
                          touched: true,
                          dirty: true,
                          drafts: { ...st.drafts, [st.language]: value },
                        },
                      };
                    })
                  }
                  onLanguageChange={(lang) =>
                    setCode((c) => {
                      const st = c[item.item_id];
                      const next = st.drafts[lang] ?? item.starter_code?.[lang] ?? DEFAULT_CODE[lang] ?? "";
                      return {
                        ...c,
                        [item.item_id]: {
                          ...st, language: lang, dirty: true,
                          drafts: { ...st.drafts, [lang]: next },
                        },
                      };
                    })
                  }
                  onRun={async (language, value, customInput) => {
                    const body = { language, code: value };
                    if (customInput !== null) body.custom_input = customInput;
                    return examApi("POST", `/code/${item.item_id}/run`, body);
                  }}
                  onSubmit={async (language, value) => {
                    const r = await examApi("POST", `/code/${item.item_id}/submit`, { language, code: value });
                    setCode((c) => ({
                      ...c,
                      [item.item_id]: { ...c[item.item_id], result: r, dirty: false, touched: true },
                    }));
                    return r;
                  }}
                />
              )}
            </div>
          </section>
        </div>

        <div className="q-actions">
          <div className="row tight">
            <button className="btn" disabled={index === 0} onClick={() => go(index - 1)}>‹ Previous</button>
            {item.type === "mcq" && (
              <>
                <button className="btn" onClick={() => {
                  const next = { ...mcq[item.item_id], selected: [] };
                  setMcq((m) => ({ ...m, [item.item_id]: next }));
                  saveMcq(item.item_id, next);
                }}>Clear response</button>
                <button className="btn" onClick={() => {
                  const prev = mcq[item.item_id];
                  const next = { ...prev, review: !prev.review };
                  setMcq((m) => ({ ...m, [item.item_id]: next }));
                  saveMcq(item.item_id, next);
                  if (next.review && index < paper.items.length - 1) go(index + 1);
                }}>
                  {mcq[item.item_id]?.review ? "Unmark review" : "Mark for review & next"}
                </button>
              </>
            )}
          </div>
          <button className="btn primary" onClick={() => {
            saveCode(false);
            if (index < paper.items.length - 1) go(index + 1);
            else toast("Saved", "success", 1500);
          }}>
            {index === paper.items.length - 1 ? "Save" : "Save & next ›"}
          </button>
        </div>
      </div>

      <div className="watermark" aria-hidden="true">
        {Array.from({ length: 40 }, (_, i) => <span key={i}>{user.roll_no}</span>)}
      </div>

      {showFsOverlay && (
        <div className="overlay">
          <div className="box">
            <h2>⚠ You left fullscreen</h2>
            <p>This has been recorded as a violation (<strong>{violations}/{maxViol}</strong>).
               Your timer is still running.</p>
            <p>Return to fullscreen to continue your exam.</p>
            <button className="btn primary" onClick={async () => {
              try { await enterFullscreen(); }
              catch { toast("Fullscreen was blocked by the browser. Try again.", "error"); }
            }}>Return to fullscreen</button>
          </div>
        </div>
      )}

      {warning && (
        <Modal title="Warning: violation recorded" narrow onClose={() => setWarning(null)}
               actions={<button className="btn primary" onClick={() => setWarning(null)}>I understand</button>}>
          <p><strong>{VIOLATION_TEXT[warning.type] || warning.type}.</strong></p>
          <p>
            This has been recorded and reported to your college.{" "}
            {warning.left > 0 && (
              <><strong>{warning.left}</strong> more violation{warning.left === 1 ? "" : "s"} and your
              exam will be submitted automatically.</>
            )}
          </p>
        </Modal>
      )}

      {showInstr && (
        <Modal title="Instructions" onClose={() => setShowInstr(false)}>
          <Markdown>{paper.exam.instructions || "No additional instructions."}</Markdown>
          <p className="muted small">Violations so far: {violations} of {maxViol} allowed.</p>
        </Modal>
      )}

      {confirmSubmit && (
        <SubmitConfirm
          paper={paper} mcq={mcq} code={code} submitting={submitting}
          onCancel={() => setConfirmSubmit(null)}
          onConfirm={async () => {
            setSubmitting(true);
            try {
              await savingRef.current.catch(() => {});
              await examApi("POST", "/submit");
              finish("Your exam has been submitted.");
            } catch (err) {
              if (!finishedRef.current) { toast(err.message, "error"); setSubmitting(false); setConfirmSubmit(null); }
            }
          }}
        />
      )}
    </>
  );
}

function SubmitConfirm({ paper, mcq, code, submitting, onCancel, onConfirm }) {
  const items = paper.items;
  const answered = items.filter((it) => isAnswered(it, mcq, code)).length;
  const review = items.filter((it) => it.type === "mcq" && mcq[it.item_id]?.review).length;
  const ungraded = items.filter(
    (it) => it.type === "coding" && isAnswered(it, mcq, code) && !code[it.item_id]?.result
  ).length;

  return (
    <Modal
      title="Submit exam?"
      onClose={onCancel}
      actions={
        <>
          <button className="btn" onClick={onCancel} disabled={submitting}>Keep working</button>
          <button className="btn danger solid" onClick={onConfirm} disabled={submitting}>
            {submitting ? <><Spinner /> Submitting</> : "Submit exam"}
          </button>
        </>
      }
    >
      <div className="table-wrap compact">
        <table>
          <thead><tr><th>Section</th><th className="num">Answered</th><th className="num">Not answered</th></tr></thead>
          <tbody>
            {paper.sections.map((sec) => {
              const its = items.filter((i) => i.section === sec);
              const a = its.filter((it) => isAnswered(it, mcq, code)).length;
              return (
                <tr key={sec}><td>{sec}</td><td className="num">{a}</td><td className="num">{its.length - a}</td></tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p>{answered} of {items.length} answered{review ? ` · ${review} marked for review` : ""}.</p>
      {ungraded > 0 && (
        <p className="small" style={{ color: "var(--warning)" }}>
          {ungraded} coding answer(s) were not submitted with "Submit code". They will be graded
          automatically now.
        </p>
      )}
      <p><strong>You can't change your answers after submitting.</strong></p>
    </Modal>
  );
}
