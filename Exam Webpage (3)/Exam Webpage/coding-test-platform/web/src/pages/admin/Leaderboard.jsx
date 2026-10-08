import { useCallback, useEffect, useState } from "react";
import { api, downloadCSV } from "../../lib/api.js";
import { fmtDuration } from "../../lib/format.js";
import { Badge, Empty, Loading, useToast } from "../../components/ui.jsx";
import { useAdmin } from "./context.jsx";

const MEDALS = ["🥇", "🥈", "🥉"];
const REFRESH_MS = 10000;

export default function Leaderboard() {
  const { collegeId, cq } = useAdmin();
  const toast = useToast();
  const [examId, setExamId] = useState("");
  const [branch, setBranch] = useState("");
  const [branches, setBranches] = useState([]);
  const [data, setData] = useState(null);
  const [lastAt, setLastAt] = useState(null);

  useEffect(() => {
    api("GET", "/api/reios/admin/stats" + cq()).then((s) => setBranches(s.branches)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collegeId]);

  const load = useCallback(async (silent = false) => {
    if (!silent) setData(null);
    try {
      setData(await api("GET", "/api/reios/admin/leaderboard" + cq({ exam_id: examId, branch, limit: 500 })));
      setLastAt(new Date());
    } catch (err) { toast(err.message, "error"); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collegeId, examId, branch]);

  useEffect(() => { load(); }, [load]);

  // Ranks can shift as teams keep submitting, so keep the board current on its own.
  useEffect(() => {
    const t = setInterval(() => load(true), REFRESH_MS);
    return () => clearInterval(t);
  }, [load]);

  const overall = data?.mode === "overall";

  function exportCsv() {
    if (!data) return;
    const name = overall ? "overall_leaderboard.csv" : `${data.exam.title.replace(/\W+/g, "_")}_leaderboard.csv`;
    if (overall) {
      downloadCSV(name, ["Rank", "Roll no", "Name", "Branch", "Exams taken", "Average %", "Best %"],
        data.rows.map((r) => [r.rank, r.roll_no, r.name, r.branch, r.exams_taken, r.average_percentage, r.best_percentage]));
    } else {
      downloadCSV(name, ["Rank", "Roll no", "Name", "Branch", "Set", "Score", "Max", "%", "Time"],
        data.rows.map((r) => [r.rank, r.roll_no, r.name, r.branch, r.set_name || "", r.total_score,
          r.max_score, r.percentage, r.time_taken_seconds ? fmtDuration(r.time_taken_seconds) : ""]));
    }
  }

  const value = (r) => (overall ? r.average_percentage : r.percentage);

  return (
    <>
      <div className="row between" style={{ marginBottom: 6 }}>
        <div className="page-head" style={{ margin: 0 }}>
          <h1>Leaderboard</h1>
          <p className="lede">
            {overall ? "Students ranked by average percentage across every exam they've finished."
              : "Ranked by percentage, then by who finished faster."}
          </p>
        </div>
        <button className="btn" onClick={exportCsv} disabled={!data?.rows.length}>Export CSV</button>
      </div>
      <p className="muted small" style={{ marginTop: -8, marginBottom: 10 }}>
        Auto-refreshes every 10 seconds{lastAt && ` · last ${lastAt.toLocaleTimeString()}`}
      </p>

      <div className="toolbar">
        <select value={examId} onChange={(e) => setExamId(e.target.value)} style={{ minWidth: 260 }}>
          <option value="">All exams (overall)</option>
          {(data?.exams || []).map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
        </select>
        <select value={branch} onChange={(e) => setBranch(e.target.value)}>
          <option value="">All branches</option>
          {branches.map((b) => <option key={b}>{b}</option>)}
        </select>
        {data && <span className="muted small">{data.participants} ranked</span>}
      </div>

      {!data ? <Loading /> : data.rows.length === 0 ? (
        <Empty title="Nobody ranked yet" hint="Rankings appear once students finish an exam." />
      ) : (
        <>
          <div className="grid" style={{ marginBottom: 18, gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", maxWidth: 760 }}>
            {data.rows.slice(0, 3).map((r, i) => (
              <div key={r.student_id} className={"stat " + (i === 0 ? "amber" : "plain")} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 30, lineHeight: 1 }}>{MEDALS[i]}</div>
                <div className="strong" style={{ marginTop: 6, fontSize: 15 }}>{r.name}</div>
                <div className="sub">{r.roll_no}{r.branch ? ` · ${r.branch}` : ""}</div>
                <div className="value" style={{ marginTop: 6 }}>{value(r)}%</div>
              </div>
            ))}
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="num">Rank</th><th>Student</th><th>Branch</th>
                  {overall ? (
                    <><th className="num">Exams</th><th className="num">Average %</th><th className="num">Best %</th></>
                  ) : (
                    <><th>Set</th><th className="num">Score</th><th className="num">%</th><th>Time</th><th>Result</th></>
                  )}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.student_id}>
                    <td className="num"><strong>{r.rank <= 3 ? MEDALS[r.rank - 1] : r.rank}</strong></td>
                    <td><strong>{r.name}</strong><div className="muted small">{r.roll_no}</div></td>
                    <td>{r.branch || "—"} {r.section || ""}</td>
                    {overall ? (
                      <>
                        <td className="num">{r.exams_taken}</td>
                        <td className="num"><strong>{r.average_percentage}</strong></td>
                        <td className="num">{r.best_percentage}</td>
                      </>
                    ) : (
                      <>
                        <td>{r.set_name || "—"}</td>
                        <td className="num">{r.total_score} / {r.max_score}</td>
                        <td className="num"><strong>{r.percentage}</strong></td>
                        <td className="small">{r.time_taken_seconds ? fmtDuration(r.time_taken_seconds) : "—"}</td>
                        <td>{r.passed ? <Badge color="green">Pass</Badge> : <Badge color="red">Fail</Badge>}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
