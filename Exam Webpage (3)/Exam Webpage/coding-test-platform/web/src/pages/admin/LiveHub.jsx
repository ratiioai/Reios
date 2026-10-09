import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api } from "../../lib/api.js";
import { Badge, Empty, Loading, useToast } from "../../components/ui.jsx";
import { useAdmin, windowBadgeProps } from "./context.jsx";

/** Sidebar shortcut: jump straight into Live Monitor without hunting through the Exams list. */
export default function LiveHub() {
  const { collegeId, cq } = useAdmin();
  const toast = useToast();
  const [exams, setExams] = useState(null);

  useEffect(() => {
    setExams(null);
    api("GET", "/api/reios/admin/exams" + cq())
      .then(setExams)
      .catch((err) => { toast(err.message, "error", 6000); setExams([]); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collegeId]);

  if (!exams) return <Loading />;

  const active = exams.filter((e) => e.is_published && (e.window === "live" || e.window === "paused"));

  if (active.length === 1) {
    return <Navigate to={`/console/exams/${active[0].id}/live`} replace />;
  }

  return (
    <>
      <div className="page-head">
        <h1>Live Monitor</h1>
        <p className="lede">Pick which exam to watch right now.</p>
      </div>

      {active.length === 0 ? (
        <Empty title="Nothing running right now"
               hint="Once you start or publish a live exam, it'll show up here." />
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Exam</th><th>Status</th><th className="num">Writing</th><th /></tr></thead>
            <tbody>
              {active.map((e) => {
                const wb = windowBadgeProps(e);
                return (
                  <tr key={e.id}>
                    <td><strong>{e.title}</strong></td>
                    <td><Badge color={wb.color}>{wb.text}</Badge></td>
                    <td className="num">{e.attempts.in_progress}</td>
                    <td>
                      <Link className="btn sm success" to={`/console/exams/${e.id}/live`}>Open Live Monitor</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
