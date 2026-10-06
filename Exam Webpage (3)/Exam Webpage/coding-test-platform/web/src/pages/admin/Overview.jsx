import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../../lib/api.js";
import { Empty, Loading, useToast } from "../../components/ui.jsx";
import { Stat, useAdmin } from "./context.jsx";

export default function Overview() {
  const { isSuper, collegeId, cq } = useAdmin();
  const toast = useToast();
  const [platform, setPlatform] = useState(null);
  const [college, setCollege] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        if (isSuper) {
          const s = await api("GET", "/api/reios/super/stats");
          if (!cancelled) setPlatform(s);
        }
        if (!isSuper || collegeId) {
          const c = await api("GET", "/api/reios/admin/stats" + cq());
          if (!cancelled) setCollege(c);
        } else if (!cancelled) {
          setCollege(null);
        }
      } catch (err) {
        if (!cancelled) toast(err.message, "error", 6000);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSuper, collegeId]);

  if (loading) return <Loading />;
  if (!platform && !college) {
    return <Empty title="No organizations yet" hint="Create your first one under Organizations." />;
  }

  return (
    <>
      {platform && (
        <>
          <div className="page-head"><h1>Platform overview</h1></div>
          <div className="grid cols-4" style={{ marginBottom: 24 }}>
            <Stat label="Organizations" value={`${platform.active_colleges} / ${platform.colleges}`} sub="active / total" />
            <Stat label="Organization admins" value={platform.college_admins} tone="plain" />
            <Stat label="Students" value={platform.students} tone="plain" />
            <Stat label="Exams" value={platform.exams} tone="plain" />
            <Stat label="Attempts" value={platform.attempts} tone="plain" />
            <Stat label="Writing now" value={platform.live_attempts} tone={platform.live_attempts ? "green" : "plain"} />
            <Stat label="Global MCQs" value={platform.global_mcqs} tone="plain" />
            <Stat label="Global coding problems" value={platform.global_problems} tone="plain" />
          </div>
        </>
      )}

      {college && (
        <>
          <h2>
            {college.college.name}{" "}
            <span className="muted small">code {college.college.code}</span>
          </h2>
          {college.college.access_until && (
            <p className="muted small" style={{ marginTop: -6 }}>
              Access until <strong>{new Date(college.college.access_until).toLocaleDateString()}</strong>
            </p>
          )}
          <div className="grid cols-4">
            <Stat
              label="Students"
              value={college.college.max_students
                ? `${college.students} / ${college.college.max_students}`
                : college.students}
              sub={`${college.active_students} active`}
            />
            <Stat label="Exams"
                  value={college.college.max_exams ? `${college.exams} / ${college.college.max_exams}` : college.exams}
                  sub={`${college.live_exams} live · ${college.upcoming_exams} scheduled`} />
            <Stat label="Writing now" value={college.live_attempts}
                  tone={college.live_attempts ? "green" : "plain"} />
            <Stat label="Completed attempts" value={college.completed_attempts} tone="plain" />
            <Stat label="Average score"
                  value={college.average_percentage === null ? "—" : college.average_percentage + "%"} />
            <Stat label="MCQs available" value={college.mcqs} tone="plain" />
            <Stat label="Coding problems" value={college.problems} tone="plain" />
            <Stat label="Branches" value={college.branches.length}
                  sub={college.branches.join(", ")} tone="plain" />
          </div>

          <div className="card" style={{ marginTop: 22 }}>
            <h3>Getting started</h3>
            <ol className="muted" style={{ margin: 0, paddingLeft: 18 }}>
              <li>Add students under <NavLink to="/console/students">Students</NavLink> (one by one or CSV import).</li>
              <li>Build your question bank: <NavLink to="/console/mcqs">MCQs</NavLink> (aptitude, reasoning, verbal, technical) and <NavLink to="/console/problems">coding problems</NavLink>.</li>
              <li>Create an exam under <NavLink to="/console/exams">Exams</NavLink>, add questions, set the schedule and anti-cheat rules, then publish.</li>
              <li>Watch students live during the exam, then review results, export CSV and check code similarity.</li>
            </ol>
          </div>
        </>
      )}
    </>
  );
}
