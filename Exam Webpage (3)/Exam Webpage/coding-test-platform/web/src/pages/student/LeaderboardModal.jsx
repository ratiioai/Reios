import { useEffect, useState } from "react";
import { api } from "../../lib/api.js";
import { Loading, Modal, useToast } from "../../components/ui.jsx";

const MEDALS = ["🥇", "🥈", "🥉"];

export default function LeaderboardModal({ examId, onClose }) {
  const toast = useToast();
  const [data, setData] = useState(null);

  useEffect(() => {
    api("GET", `/api/reios/student/exams/${examId}/leaderboard`)
      .then(setData)
      .catch((err) => { toast(err.message, "error"); onClose(); });
  }, [examId, toast, onClose]);

  const Row = ({ r, highlight }) => (
    <tr style={highlight ? { background: "var(--primary-soft)" } : undefined}>
      <td className="num"><strong>{r.rank <= 3 ? MEDALS[r.rank - 1] : r.rank}</strong></td>
      <td><strong>{r.name}</strong>{r.is_me && " (you)"}</td>
      <td>{r.branch || "—"}</td>
      <td className="num"><strong>{r.percentage}%</strong></td>
    </tr>
  );

  return (
    <Modal title={data ? `${data.exam.title} · Leaderboard` : "Leaderboard"} onClose={onClose}>
      {!data ? <Loading /> : (
        <>
          {data.me && (
            <div className="grid cols-2" style={{ marginBottom: 14 }}>
              <div className="stat"><div className="label">Your rank</div>
                <div className="value">{data.me.rank}<span className="muted" style={{ fontSize: 15 }}> / {data.participants}</span></div></div>
              <div className="stat green"><div className="label">Your score</div>
                <div className="value">{data.me.percentage}%</div></div>
            </div>
          )}
          <div className="table-wrap compact">
            <table>
              <thead><tr><th className="num">Rank</th><th>Name</th><th>Branch</th><th className="num">Score</th></tr></thead>
              <tbody>
                {data.top.map((r) => <Row key={r.rank} r={r} highlight={r.is_me} />)}
                {data.me && data.me.rank > data.top.length && (
                  <>
                    <tr><td colSpan={4} className="muted small" style={{ textAlign: "center" }}>⋯</td></tr>
                    <Row r={data.me} highlight />
                  </>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Modal>
  );
}
