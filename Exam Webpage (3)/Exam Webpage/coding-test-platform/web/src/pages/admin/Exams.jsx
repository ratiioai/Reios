import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api.js";
import { fmtDate } from "../../lib/format.js";
import { Badge, Loading, useConfirm, useToast } from "../../components/ui.jsx";
import { useAdmin, windowBadgeProps } from "./context.jsx";
import ExamSettings, { EXAM_TYPES } from "./ExamSettings.jsx";

export default function Exams() {
  const { collegeId, cq } = useAdmin();
  const toast = useToast();
  const confirm = useConfirm();
  const navigate = useNavigate();

  const [exams, setExams] = useState(null);
  const [meta, setMeta] = useState(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setExams(null);
    try {
      setExams(await api("GET", "/api/reios/admin/exams" + cq()));
    } catch (err) {
      toast(err.message, "error", 6000);
      setExams([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collegeId]);

  useEffect(() => {
    load();
    api("GET", "/api/reios/admin/meta").then(setMeta).catch(() => {});
  }, [load]);

  async function control(e, action) {
    if (action === "end" && e.attempts.in_progress > 0) {
      const ok = await confirm("End exam now",
        `${e.attempts.in_progress} student${e.attempts.in_progress > 1 ? "s" : ""} still writing will be ` +
        "submitted immediately with whatever they've answered so far. This can't be undone.",
        "End exam", true);
      if (!ok) return;
    }
    try {
      const updated = await api("POST", `/api/reios/admin/exams/${e.id}/control` + cq({ action }));
      setExams((xs) => xs.map((x) => (x.id === e.id ? updated : x)));
    } catch (err) {
      toast(err.message, "error", 6000);
    }
  }

  if (!exams) return <Loading />;

  return (
    <>
      <div className="row between" style={{ marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>Exams</h1>
        <button className="btn primary" disabled={!meta} onClick={() => setCreating(true)}>
          + Create exam
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Exam</th><th>Window</th><th>Duration</th><th>Questions</th>
              <th>Status</th><th>Attempts</th><th />
            </tr>
          </thead>
          <tbody>
            {exams.length === 0 ? (
              <tr><td colSpan={7} className="empty">No exams yet</td></tr>
            ) : exams.map((e) => {
              const wb = windowBadgeProps(e);
              return (
                <tr key={e.id}>
                  <td>
                    <strong>{e.title}</strong>{" "}
                    <Badge color="outline">{EXAM_TYPES.find((t) => t.id === e.exam_type)?.label || e.exam_type}</Badge>
                    {e.set_count > 0 && <> <Badge color="violet">{e.set_count} sets</Badge></>}
                    {e.branch_filter && <div className="muted small">Branches: {e.branch_filter}</div>}
                  </td>
                  <td className="small">{fmtDate(e.start_at)}<br />→ {fmtDate(e.end_at)}</td>
                  <td>{e.duration_minutes} min</td>
                  <td>
                    {[e.mcq_count && `${e.mcq_count} MCQ`, e.coding_count && `${e.coding_count} coding`].filter(Boolean).join(" · ") || "No questions"}
                    <div className="muted small">{e.max_score} marks</div>
                  </td>
                  <td><Badge color={wb.color}>{wb.text}</Badge></td>
                  <td>
                    {e.attempts.submitted} done
                    {e.attempts.in_progress > 0 && (
                      <> · <strong>{e.attempts.in_progress} writing</strong></>
                    )}
                  </td>
                  <td>
                    <div className="row tight" style={{ flexWrap: "wrap", rowGap: 4 }}>
                      <Link className="btn sm" to={`/console/exams/${e.id}`}>Edit</Link>
                      {e.is_published && e.window !== "ended" && (
                        <>
                          {(e.window === "upcoming") && (
                            <button className="btn sm success" onClick={() => control(e, "start")}>Start exam</button>
                          )}
                          {e.window === "live" && (
                            <button className="btn sm" onClick={() => control(e, "pause")}>Pause exam</button>
                          )}
                          {e.window === "paused" && (
                            <button className="btn sm success" onClick={() => control(e, "resume")}>Resume</button>
                          )}
                          <button className="btn sm danger" onClick={() => control(e, "end")}>End exam</button>
                        </>
                      )}
                      {e.is_published && (e.window === "live" || e.window === "paused") && (
                        <Link className="btn sm success" to={`/console/exams/${e.id}/live`}>Live</Link>
                      )}
                      <Link className="btn sm" to={`/console/exams/${e.id}/results`}>Results</Link>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {creating && meta && (
        <ExamSettings
          meta={meta}
          exam={null}
          cq={cq}
          onClose={() => setCreating(false)}
          onSaved={(saved) => { setCreating(false); navigate(`/console/exams/${saved.id}`); }}
        />
      )}
    </>
  );
}
