import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, download } from "../../lib/api.js";
import { fmtDuration } from "../../lib/format.js";
import { Badge, Loading, Modal, useConfirm, useToast } from "../../components/ui.jsx";
import { Stat, useAdmin, windowBadgeProps } from "./context.jsx";
import AttemptDetail, { reasonText } from "./AttemptDetail.jsx";

export default function Results() {
  const { examId } = useParams();
  const { collegeId, cq } = useAdmin();
  const toast = useToast();
  const confirmBox = useConfirm();
  const [orgFeatures, setOrgFeatures] = useState([]);

  useEffect(() => {
    api("GET", "/api/reios/admin/stats" + cq()).then((s) => setOrgFeatures(s.college.features || [])).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collegeId]);

  async function emailResults() {
    if (!(await confirmBox("Email results",
      "Send every student who finished their score, rank and pass/fail by email? Students without an email are skipped.",
      "Send emails"))) return;
    try {
      const r = await api("POST", `/api/reios/admin/exams/${examId}/email-results` + cq());
      toast(`Sent ${r.sent} emails` + (r.skipped ? `, ${r.skipped} students have no email` : "")
            + (r.failed.length ? `, ${r.failed.length} failed` : ""), r.failed.length ? "error" : "success", 7000);
    } catch (err) { toast(err.message, "error", 7000); }
  }
  const confirm = useConfirm();

  const [data, setData] = useState(null);
  const [tab, setTab] = useState("ranked");
  const [search, setSearch] = useState("");
  const [attemptId, setAttemptId] = useState(null);
  const [similarity, setSimilarity] = useState(null);

  const load = useCallback(async () => {
    setData(null);
    try {
      setData(await api("GET", `/api/reios/admin/exams/${examId}/results` + cq()));
    } catch (err) {
      toast(err.message, "error", 6000);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [examId, collegeId]);

  useEffect(() => { load(); }, [load]);

  const hasSets = !!data?.results.some((r) => r.set_name);
  const sections = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.results.flatMap((r) => Object.keys(r.section_scores)))].sort();
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.toLowerCase();
    return data.results.filter((r) => (r.name + " " + r.roll_no).toLowerCase().includes(q));
  }, [data, search]);

  if (!data) return <Loading />;

  const s = data.summary;
  const wb = windowBadgeProps(data.exam);

  async function allowRetake(id) {
    const ok = await confirm(
      "Allow retake",
      "This deletes the student's attempt and all their answers so they can take the exam again. Continue?",
      "Delete attempt", true
    );
    if (!ok) return;
    try {
      await api("DELETE", `/api/reios/admin/attempts/${id}` + cq());
      toast("Attempt deleted", "success");
      load();
    } catch (err) { toast(err.message, "error"); }
  }

  async function openSimilarity() {
    try {
      setSimilarity(await api("GET", `/api/reios/admin/exams/${examId}/similarity` + cq()));
    } catch (err) { toast(err.message, "error"); }
  }

  return (
    <>
      <div className="row between">
        <div>
          <Link to="/console/exams" className="small">← Exams</Link>
          <h1 style={{ marginTop: 4 }}>
            {data.exam.title} · Results <Badge color={wb.color}>{wb.text}</Badge>
          </h1>
        </div>
        <div className="row tight">
          {data.exam.window === "live" && (
            <Link className="btn success" to={`/console/exams/${examId}/live`}>Live monitor</Link>
          )}
          <Link className="btn" to="/console/leaderboard">Leaderboard</Link>
          {orgFeatures.includes("email_results") && (
            <button className="btn" onClick={emailResults}>Email results</button>
          )}
          {data.exam.coding_count > 0 && <button className="btn" onClick={openSimilarity}>Code similarity</button>}
          <button className="btn primary" onClick={() =>
            download(`/api/reios/admin/exams/${examId}/export` + cq(),
                     `${data.exam.title.replace(/\W+/g, "_")}_results.csv`).catch((e) => toast(e.message, "error"))
          }>Export CSV</button>
        </div>
      </div>

      <div className="grid cols-4" style={{ margin: "16px 0" }}>
        <Stat label="Eligible" value={s.eligible} tone="plain" />
        <Stat label="Completed" value={s.completed} sub={s.in_progress ? `${s.in_progress} still writing` : ""} />
        <Stat label="Absent" value={s.not_attempted} tone={s.not_attempted ? "amber" : "plain"} />
        <Stat label="Average"
              value={s.average_percentage === null ? "—" : s.average_percentage + "%"}
              sub={s.highest_percentage !== null ? `top ${s.highest_percentage}%` : ""} />
        <Stat label="Passed" value={s.pass_count} sub={`pass mark ${data.exam.pass_percentage}%`} tone="green" />
        <Stat label="Flagged" value={s.flagged} sub="had violations" tone={s.flagged ? "red" : "plain"} />
      </div>

      <div className="tabs">
        <button className={tab === "ranked" ? "active" : ""} onClick={() => setTab("ranked")}>Ranked list</button>
        <button className={tab === "absent" ? "active" : ""} onClick={() => setTab("absent")}>
          Absent ({data.absentees.length})
        </button>
      </div>

      {tab === "ranked" ? (
        <>
          <div className="toolbar">
            <input placeholder="Filter by name or roll no" value={search}
                   onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="num">#</th><th>Student</th><th>Branch</th>{hasSets && <th>Set</th>}
                  {sections.map((x) => <th key={x} className="num">{x}</th>)}
                  <th className="num">Total</th><th className="num">%</th><th>Result</th>
                  <th className="num">Violations</th><th>Time</th><th />
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td colSpan={9 + sections.length + (hasSets ? 1 : 0)} className="empty">No attempts yet</td></tr>
                ) : filtered.map((r) => (
                  <tr key={r.attempt_id}>
                    <td className="num">{r.rank || "—"}</td>
                    <td><strong>{r.name}</strong><div className="muted small">{r.roll_no}</div></td>
                    <td>{r.branch || ""} {r.section || ""}</td>
                    {hasSets && <td>{r.set_name || "—"}</td>}
                    {sections.map((x) => <td key={x} className="num">{r.section_scores[x] ?? 0}</td>)}
                    <td className="num"><strong>{r.total_score}</strong> / {r.max_score}</td>
                    <td className="num">{r.percentage}</td>
                    <td>
                      {r.status === "in_progress" ? <Badge color="blue">Writing</Badge>
                        : r.passed ? <Badge color="green">Pass</Badge>
                        : <Badge color="red">Fail</Badge>}
                      {r.status === "auto_submitted" && (
                        <div className="muted small">{reasonText(r.submit_reason)}</div>
                      )}
                    </td>
                    <td className="num">
                      {r.violations ? <Badge color="amber">{r.violations}</Badge> : 0}
                    </td>
                    <td className="small">
                      {r.time_taken_seconds ? fmtDuration(r.time_taken_seconds) : "—"}
                    </td>
                    <td>
                      <div className="row tight">
                        <button className="btn sm" onClick={() => setAttemptId(r.attempt_id)}>View</button>
                        <button className="btn sm danger" onClick={() => allowRetake(r.attempt_id)}
                                title="Delete the attempt so the student can retake">Allow retake</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Roll no</th><th>Name</th><th>Branch</th></tr></thead>
            <tbody>
              {data.absentees.length === 0 ? (
                <tr><td colSpan={3} className="empty">Everyone eligible has attempted</td></tr>
              ) : data.absentees.map((a) => (
                <tr key={a.roll_no}>
                  <td>{a.roll_no}</td><td>{a.name}</td><td>{a.branch || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {attemptId && (
        <AttemptDetail attemptId={attemptId} cq={cq}
                       onClose={() => setAttemptId(null)} onChanged={load} />
      )}

      {similarity && (
        <Modal title="Code similarity (possible copying)" wide onClose={() => setSimilarity(null)}>
          <p className="muted">
            Pairs of students whose code for the same problem is at least {similarity.threshold}%
            similar after ignoring comments and whitespace. Review the code before taking action:
            short problems can have naturally similar solutions.
          </p>
          <div className="table-wrap compact">
            <table>
              <thead>
                <tr><th>Problem</th><th>Student A</th><th>Student B</th><th className="num">Similarity</th></tr>
              </thead>
              <tbody>
                {similarity.pairs.length === 0 ? (
                  <tr><td colSpan={4} className="empty">No suspicious pairs found</td></tr>
                ) : similarity.pairs.map((p, i) => (
                  <tr key={i}>
                    <td>{p.problem}</td>
                    <td>{p.student_a.name} <span className="muted small">{p.student_a.roll_no}</span></td>
                    <td>{p.student_b.name} <span className="muted small">{p.student_b.roll_no}</span></td>
                    <td className="num">
                      <Badge color={p.similarity >= 95 ? "red" : "amber"}>{p.similarity}%</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Modal>
      )}
    </>
  );
}
