import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, store } from "../../lib/api.js";
import { useAuth } from "../../lib/auth.jsx";
import { Brand, Empty, Loading, ThemeToggle, useToast } from "../../components/ui.jsx";
import { AdminCtx, NavIcon, makeCq, useAdmin } from "./context.jsx";

import Overview from "./Overview.jsx";
import Colleges from "./Colleges.jsx";
import Students from "./Students.jsx";
import Mcqs from "./Mcqs.jsx";
import Problems from "./Problems.jsx";
import Exams from "./Exams.jsx";
import ExamBuilder from "./ExamBuilder.jsx";
import Results from "./Results.jsx";
import Live from "./Live.jsx";
import Announcements from "./Announcements.jsx";
import Account from "./Account.jsx";
import Preview from "./Preview.jsx";
import Leaderboard from "./Leaderboard.jsx";
import Usage from "./Usage.jsx";

export default function Console() {
  const { user, logout } = useAuth();
  const toast = useToast();
  const location = useLocation();
  const isSuper = user.role === "super_admin";

  const [colleges, setColleges] = useState([]);
  const [collegeId, setCollegeId] = useState(() =>
    isSuper ? Number(store.get("reios_console_college")) || null : user.college.id
  );
  const [ready, setReady] = useState(!isSuper);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [mustChange, setMustChange] = useState(false);

  // Super admins pick which college they are acting inside.
  useEffect(() => {
    if (!isSuper) return;
    (async () => {
      try {
        const list = await api("GET", "/api/reios/super/colleges");
        setColleges(list);
        setCollegeId((cur) => {
          const valid = cur && list.find((c) => c.id === cur) ? cur : (list[0]?.id ?? null);
          if (valid) store.set("reios_console_college", String(valid));
          return valid;
        });
      } catch (err) {
        toast(err.message, "error", 6000);
      } finally {
        setReady(true);
      }
    })();
  }, [isSuper, toast]);

  useEffect(() => {
    api("GET", "/api/reios/auth/me")
      .then((me) => setMustChange(!!me.must_change_password))
      .catch(() => {});
  }, []);

  useEffect(() => { setSidebarOpen(false); }, [location.pathname]);

  const pickCollege = useCallback((id) => {
    setCollegeId(id);
    store.set("reios_console_college", String(id));
  }, []);

  const ctx = useMemo(
    () => ({
      isSuper,
      collegeId,
      colleges,
      setColleges,
      pickCollege,
      cq: makeCq(isSuper, collegeId),
      needCollege: isSuper && !collegeId,
    }),
    [isSuper, collegeId, colleges, pickCollege]
  );

  const NAV = [
    { group: "General" },
    { id: "overview", to: "/console", end: true, label: "Overview" },
    ...(isSuper ? [{ id: "colleges", to: "/console/colleges", label: "Organizations" }, { id: "usage", to: "/console/usage", label: "Usage" }] : []),
    { group: isSuper ? "Selected organization" : "Organization" },
    { id: "students", to: "/console/students", label: "Students" },
    { id: "exams", to: "/console/exams", label: "Exams & Results" },
    { id: "leaderboard", to: "/console/leaderboard", label: "Leaderboard" },
    { id: "announcements", to: "/console/announcements", label: "Announcements" },
    { group: isSuper ? "Global question bank" : "Question bank" },
    { id: "mcqs", to: "/console/mcqs", label: "MCQ Questions" },
    { id: "problems", to: "/console/problems", label: "Coding Problems" },
    { group: "Account" },
    { id: "account", to: "/console/account", label: "Change password" },
  ];

  return (
    <AdminCtx.Provider value={ctx}>
      <div className="shell">
        <aside className={"sidebar" + (sidebarOpen ? " open" : "")}>
          <Brand sub={isSuper ? "Super Admin" : "Admin"} />
          <nav className="nav">
            {NAV.map((n, i) =>
              n.group ? (
                <div className="group" key={"g" + i}>{n.group}</div>
              ) : (
                <NavLink key={n.id} to={n.to} end={n.end}
                         className={({ isActive }) => (isActive ? "active" : "")}>
                  <NavIcon id={n.id} /> {n.label}
                </NavLink>
              )
            )}
          </nav>
          <div className="sidebar-foot">
            <div className="row between">
              <span className="tiny faint">Signed in</span>
              <div className="row tight">
                <ThemeToggle />
                <button className="btn ghost sm" onClick={logout}>Sign out</button>
              </div>
            </div>
          </div>
        </aside>

        <main className="main">
          <div className="topbar">
            <div className="row">
              <button className="btn sm menu-toggle" aria-label="Menu"
                      onClick={() => setSidebarOpen((o) => !o)}>☰</button>
              {isSuper && (
                <div className="row tight">
                  <label htmlFor="college-picker" style={{ margin: 0 }}>Organization</label>
                  <select id="college-picker" style={{ width: "auto", minWidth: 220 }}
                          value={collegeId ?? ""}
                          onChange={(e) => pickCollege(Number(e.target.value))}>
                    {colleges.length === 0
                      ? <option value="">No organizations yet</option>
                      : colleges.map((c) => (
                          <option key={c.id} value={c.id}>{c.name} ({c.code})</option>
                        ))}
                  </select>
                </div>
              )}
            </div>
            <div className="row tight">
              <span className="who">
                {user.name} · {isSuper ? "Super Admin" : user.college.name}
              </span>
            </div>
          </div>

          {mustChange && (
            <div className="banner warn" style={{ marginBottom: 18 }}>
              <div>
                <h3>Set your own password</h3>
                <span className="small">
                  You're still using a temporary password.{" "}
                  <NavLink to="/console/account">Change it now</NavLink>.
                </span>
              </div>
            </div>
          )}

          {!ready ? <Loading /> : (
            <Routes>
              <Route index element={<Overview />} />
              <Route path="colleges" element={isSuper ? <Colleges /> : <Navigate to="/console" replace />} />
              <Route path="students" element={<Scoped><Students /></Scoped>} />
              <Route path="mcqs" element={<Mcqs />} />
              <Route path="problems" element={<Problems />} />
              <Route path="exams" element={<Scoped><Exams /></Scoped>} />
              <Route path="exams/:examId" element={<Scoped><ExamBuilder /></Scoped>} />
              <Route path="exams/:examId/results" element={<Scoped><Results /></Scoped>} />
              <Route path="exams/:examId/live" element={<Scoped><Live /></Scoped>} />
              <Route path="exams/:examId/preview" element={<Scoped><Preview /></Scoped>} />
              <Route path="usage" element={isSuper ? <Usage /> : <Navigate to="/console" replace />} />
              <Route path="leaderboard" element={<Scoped><Leaderboard /></Scoped>} />
              <Route path="announcements" element={<Announcements />} />
              <Route path="account" element={<Account onChanged={() => setMustChange(false)} />} />
              <Route path="*" element={<Navigate to="/console" replace />} />
            </Routes>
          )}
        </main>
      </div>
    </AdminCtx.Provider>
  );
}

/** College-scoped screens need a college selected before they can load anything. */
function Scoped({ children }) {
  const { needCollege } = useAdmin();
  if (needCollege) {
    return (
      <Empty title="No organization selected"
             hint="Create one under Colleges & Admins, then pick it from the dropdown above." />
    );
  }
  return children;
}
