import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/api.js";
import { fmtDuration } from "../../lib/format.js";
import { Badge, Loading, Progress, useConfirm, useToast } from "../../components/ui.jsx";
import { Stat, useAdmin, windowBadgeProps } from "./context.jsx";
import AttemptDetail from "./AttemptDetail.jsx";

const REFRESH_MS = 10000;

export default function Live() {
  const { examId } = useParams();
  const { collegeId, cq } = useAdmin();
  const toast = useToast();
  const confirm = useConfirm();

  const [data, setData] = useState(null);
  const [lastAt, setLastAt] = useState(null);
  const [attemptId, setAttemptId] = useState(null);
  const [selected, setSelected] = useState(() => new Set());
  const pausedRef = useRef(false);
  pausedRef.current = !!attemptId;

  const refresh = useCallback(async () => {
    try {
      setData(await api("GET", `/api/reios/admin/exams/${examId}/live` + cq()));
      setLastAt(new Date());
    } catch (err) {
      toast(err.message, "error", 6000);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [examId, collegeId]);

  useEffect(() => { refresh(); }, [refresh]);

  // Keep polling, but hold still while a dialog is open over the table.
  useEffect(() => {
    const t = setInterval(() => { if (!pausedRef.current) refresh(); }, REFRESH_MS);
    return () => clearInterval(t);
  }, [refresh]);

  function toggle(id) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function bulkForgive() {
    const ids = [...selected];
    if (!ids.length) return;
    try {
      await api("POST", `/api/reios/admin/attempts/bulk-forgive-violations` + cq(), { ids });
      toast(`Violations cleared for ${ids.length}`, "success");
      setSelected(new Set());
      refresh();
    } catch (err) { toast(err.message, "error"); }
  }

  async function bulkReopen() {
    const ids = [...selected];
    if (!ids.length) return;
    const eligible = data.attempts.filter((a) => ids.includes(a.attempt_id) && a.submit_reason === "max_violations");
    if (!eligible.length) return toast("None of the selected were auto-submitted for violations", "error");
    if (!(await confirm("Reopen selected",
      `Reopen ${eligible.length} attempt${eligible.length > 1 ? "s" : ""} auto-submitted for hitting the ` +
      "violation limit, clear their violations, and give each 10 more minutes?", "Reopen", true))) return;
    try {
      await Promise.all(eligible.map((a) =>
        api("POST", `/api/reios/admin/attempts/${a.attempt_id}/reopen` + cq(), { minutes: 10 })));
      toast(`Reopened ${eligible.length}`, "success");
      setSelected(new Set());
      refresh();
    } catch (err) { toast(err.message, "error"); }
  }

  if (!data) return <Loading />;

  const writing = data.attempts.filter((a) => a.status === "in_progress");
  const wb = windowBadgeProps(data.exam);

  return (
    <>
      <div className="row between">
        <div>
          <Link to={`/console/exams/${examId}/results`} className="small">← Results</Link>
          <h1 style={{ marginTop: 4 }}>
            {data.exam.title} · Live <Badge color={wb.color}>{wb.text}</Badge>
          </h1>
        </div>
        <span className="muted small">
          Auto-refreshes every 10 seconds
          {lastAt && ` · last ${lastAt.toLocaleTimeString()}`}
        </span>
      </div>

      <div className="grid cols-4" style={{ margin: "16px 0" }}>
        <Stat label="Writing now" value={writing.length} tone={writing.length ? "green" : "plain"} />
        <Stat label="Online" value={writing.filter((a) => a.online).length} sub="heartbeat in last 45s" />
        <Stat label="Submitted" value={data.attempts.length - writing.length} tone="plain" />
        <Stat label="With violations" value={data.attempts.filter((a) => a.violations).length}
              tone={data.attempts.some((a) => a.violations) ? "red" : "plain"} />
      </div>

      {selected.size > 0 && (
        <div className="toolbar" style={{ marginBottom: 10 }}>
          <span className="muted small">{selected.size} selected</span>
          <button className="btn sm" onClick={bulkForgive}>Forgive violations</button>
          <button className="btn sm" onClick={bulkReopen}>Reopen (give another chance)</button>
          <button className="btn sm ghost" onClick={() => setSelected(new Set())}>Clear</button>
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: "minmax(0,2fr) minmax(260px,1fr)", alignItems: "start" }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>
                  <input type="checkbox"
                         checked={data.attempts.length > 0 && selected.size === data.attempts.length}
                         onChange={(e) =>
                           setSelected(e.target.checked ? new Set(data.attempts.map((a) => a.attempt_id)) : new Set())} />
                </th>
                <th /><th>Student</th><th>Progress</th><th className="num">Violations</th>
                <th>Time left</th><th>Last event</th><th />
              </tr>
            </thead>
            <tbody>
              {data.attempts.length === 0 ? (
                <tr><td colSpan={8} className="empty">Nobody has started yet</td></tr>
              ) : data.attempts.map((a) => (
                <tr key={a.attempt_id}>
                  <td>
                    <input type="checkbox" checked={selected.has(a.attempt_id)} onChange={() => toggle(a.attempt_id)} />
                  </td>
                  <td title={a.online ? "Online" : "Offline"}>
                    <span className={"status-dot " + (
                      a.status !== "in_progress" ? "off" : a.online ? "on" : "live"
                    )} />
                  </td>
                  <td>
                    <strong>{a.name}</strong>
                    <div className="muted small">{a.roll_no} · {a.ip_address || ""}</div>
                  </td>
                  <td style={{ minWidth: 120 }}>
                    <Progress value={a.answered} max={a.total} />
                    <span className="small muted">{a.answered}/{a.total}</span>
                  </td>
                  <td className="num">
                    {a.violations
                      ? <Badge color={a.violations >= a.max_violations - 1 ? "red" : "amber"}>
                          {a.violations}/{a.max_violations}
                        </Badge>
                      : "0"}
                  </td>
                  <td>
                    {a.status === "in_progress"
                      ? <span className="nums">{fmtDuration(a.seconds_left)}</span>
                      : <Badge>{a.status === "submitted" ? "Submitted" : "Auto-submitted"}</Badge>}
                  </td>
                  <td className="small">
                    {a.last_event && (
                      <>{a.last_event.type}<br />{new Date(a.last_event.at).toLocaleTimeString()}</>
                    )}
                  </td>
                  <td>
                    <button className="btn sm" onClick={() => setAttemptId(a.attempt_id)}>Manage</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card" style={{ margin: 0 }}>
          <h3>Recent violations</h3>
          {data.recent_violations.length === 0 ? (
            <p className="muted small">None so far</p>
          ) : data.recent_violations.map((v, i) => (
            <div key={i} style={{ padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
              <strong className="small">{v.name}</strong>{" "}
              <span className="muted small">{v.roll_no}</span>
              <div className="small">
                <Badge color="red">{v.type}</Badge> {new Date(v.at).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      </div>

      {attemptId && (
        <AttemptDetail attemptId={attemptId} cq={cq}
                       onClose={() => setAttemptId(null)} onChanged={refresh} />
      )}
    </>
  );
}
