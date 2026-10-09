import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api.js";
import { LANG_LABELS, fmtDate } from "../../lib/format.js";
import {
  Badge, Field, Loading, Markdown, Modal, ModalButton, useConfirm, useToast,
} from "../../components/ui.jsx";
import { Stat } from "./context.jsx";

export const REASON_TEXT = {
  time_up: "Time ran out",
  max_violations: "Too many violations",
  admin_force_submit: "Submitted by admin",
  student_submitted: "Submitted",
};
export const reasonText = (r) => REASON_TEXT[r] || r || "";

export default function AttemptDetail({ attemptId, cq, onClose, onChanged }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [a, setA] = useState(null);
  const [tab, setTab] = useState("answers");
  const [extending, setExtending] = useState(false);

  const load = useCallback(async () => {
    try {
      setA(await api("GET", `/api/reios/admin/attempts/${attemptId}` + cq()));
    } catch (err) {
      toast(err.message, "error");
      onClose();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attemptId]);

  useEffect(() => { load(); }, [load]);

  if (!a) {
    return <Modal title="Attempt" wide onClose={onClose}><Loading /></Modal>;
  }

  const live = a.status === "in_progress";
  const canReopen = !live && (a.submit_reason === "max_violations" || a.submit_reason === "time_up");

  async function forgive() {
    try {
      await api("POST", `/api/reios/admin/attempts/${attemptId}/forgive-violations` + cq());
      toast("Violations cleared", "success");
      onChanged?.();
      load();
    } catch (err) { toast(err.message, "error"); }
  }

  async function forceSubmit() {
    if (!(await confirm("Force submit", "Submit this student's exam now?", "Submit", true))) return;
    try {
      await api("POST", `/api/reios/admin/attempts/${attemptId}/force-submit` + cq());
      toast("Submitted", "success");
      onChanged?.();
      onClose();
    } catch (err) { toast(err.message, "error"); }
  }

  const [reopening, setReopening] = useState(false);

  return (
    <>
      <Modal
        title={`${a.student.name} (${a.student.roll_no})`}
        wide
        onClose={onClose}
        actions={live ? (
          <>
            <button className="btn" onClick={forgive}>Forgive violations</button>
            <button className="btn" onClick={() => setExtending(true)}>Extend time</button>
            <button className="btn danger solid" onClick={forceSubmit}>Force submit</button>
          </>
        ) : canReopen ? (
          <>
            <button className="btn" onClick={onClose}>Close</button>
            <button className="btn primary" onClick={() => setReopening(true)}>Reopen · give another chance</button>
          </>
        ) : <button className="btn primary" onClick={onClose}>Close</button>}
      >
        <div className="grid cols-4" style={{ marginBottom: 12 }}>
          <Stat label="Score" value={`${a.total_score} / ${a.max_score}`} />
          <Stat label="MCQ" value={a.mcq_score} tone="plain" />
          <Stat label="Coding" value={a.coding_score} tone="plain" />
          <Stat label="Violations" value={a.violations} tone={a.violations ? "red" : "plain"} />
        </div>

        <dl className="kv">
          <dt>Status</dt>
          <dd>{a.status.replace("_", " ")}{a.submit_reason ? ` · ${reasonText(a.submit_reason)}` : ""}</dd>
          <dt>Started</dt><dd>{fmtDate(a.started_at)}</dd>
          <dt>Submitted</dt><dd>{fmtDate(a.submitted_at)}</dd>
          <dt>IP address</dt><dd>{a.ip_address || "—"}</dd>
          <dt>Browser</dt><dd className="small">{a.user_agent || "—"}</dd>
        </dl>

        <div className="tabs" style={{ marginTop: 14 }}>
          <button className={tab === "answers" ? "active" : ""} onClick={() => setTab("answers")}>
            Answers
          </button>
          <button className={tab === "events" ? "active" : ""} onClick={() => setTab("events")}>
            Proctoring log ({a.events.length})
          </button>
        </div>

        {tab === "answers" ? (
          a.questions.map((x, i) => x.type === "mcq" ? (
            <div key={i} className="card pad-sm" style={{ marginBottom: 8 }}>
              <div className="row between">
                <strong>Q{i + 1} · {x.section}</strong>
                <span>
                  {x.is_correct === null ? <Badge>Not answered</Badge>
                    : x.is_correct ? <Badge color="green">Correct</Badge>
                    : <Badge color="red">Wrong</Badge>}{" "}
                  {x.marks_awarded} / {x.marks}
                </span>
              </div>
              <Markdown>{x.question}</Markdown>
              <ol className="option-list">
                {x.options.map((o, oi) => (
                  <li key={oi} className={
                    x.correct_options.includes(oi) ? "correct" : x.selected.includes(oi) ? "wrong" : ""
                  }>
                    {o}{x.selected.includes(oi) && " ← chosen"}
                  </li>
                ))}
              </ol>
            </div>
          ) : (
            <div key={i} className="card pad-sm" style={{ marginBottom: 8 }}>
              <div className="row between">
                <strong>Q{i + 1} · {x.title}</strong>
                <span>{x.passed_tests}/{x.total_tests} tests · {x.marks_awarded} / {x.marks}</span>
              </div>
              <div className="muted small">
                {x.language ? LANG_LABELS[x.language] : "No code"} · ran {x.run_count} times
              </div>
              {x.code && <pre>{x.code}</pre>}
            </div>
          ))
        ) : (
          <div className="table-wrap compact">
            <table>
              <thead><tr><th>Time</th><th>Event</th><th>Details</th></tr></thead>
              <tbody>
                {a.events.length === 0 ? (
                  <tr><td colSpan={3} className="empty">No events</td></tr>
                ) : a.events.map((e, i) => (
                  <tr key={i}>
                    <td className="small">{fmtDate(e.at)}</td>
                    <td>{e.counted ? <Badge color="red">{e.type}</Badge> : e.type}</td>
                    <td className="small">{e.details || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Modal>

      {extending && (
        <ExtendTime attemptId={attemptId} cq={cq}
                    onClose={() => setExtending(false)}
                    onDone={() => { setExtending(false); onChanged?.(); load(); }} />
      )}

      {reopening && (
        <ReopenModal attemptId={attemptId} cq={cq} reason={a.submit_reason}
                    onClose={() => setReopening(false)}
                    onDone={() => { setReopening(false); onChanged?.(); onClose(); }} />
      )}
    </>
  );
}

function ReopenModal({ attemptId, cq, reason, onClose, onDone }) {
  const toast = useToast();
  const [mins, setMins] = useState(60);

  async function reopen() {
    try {
      await api("POST", `/api/reios/admin/attempts/${attemptId}/reopen` + cq(), { minutes: Number(mins) });
      toast("Reopened — the student can resume", "success");
      onDone();
    } catch (err) { toast(err.message, "error"); }
  }

  return (
    <Modal
      title="Reopen attempt"
      narrow
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <ModalButton cls="primary" onClick={reopen}>Reopen</ModalButton>
        </>
      }
    >
      <p className="small muted" style={{ marginTop: 0 }}>
        {reason === "max_violations"
          ? "This was auto-submitted for hitting the violation limit."
          : "This was auto-submitted because time ran out."}{" "}
        Reopening clears their violations and puts them back in progress with the time below.
      </p>
      <Field label="Minutes to give them">
        <input type="number" min="1" max="240" value={mins} onChange={(e) => setMins(e.target.value)} />
      </Field>
    </Modal>
  );
}

function ExtendTime({ attemptId, cq, onClose, onDone }) {
  const toast = useToast();
  const [mins, setMins] = useState(10);

  async function extend() {
    try {
      await api("POST", `/api/reios/admin/attempts/${attemptId}/extend` + cq(), { minutes: Number(mins) });
      toast("Time extended", "success");
      onDone();
    } catch (err) { toast(err.message, "error"); }
  }

  return (
    <Modal
      title="Extend time"
      narrow
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <ModalButton cls="primary" onClick={extend}>Extend</ModalButton>
        </>
      }
    >
      <Field label="Extra minutes">
        <input type="number" min="1" max="240" value={mins} onChange={(e) => setMins(e.target.value)} />
      </Field>
    </Modal>
  );
}
