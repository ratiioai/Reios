import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../lib/api.js";
import { useAuth } from "../../lib/auth.jsx";
import { fmtDate, fmtDuration } from "../../lib/format.js";
import { Badge, Credit, Empty, Loading, OrgBrand, ThemeToggle, useToast } from "../../components/ui.jsx";
import ChangePassword from "./ChangePassword.jsx";
import ResultModal from "./ResultModal.jsx";
import LeaderboardModal from "./LeaderboardModal.jsx";

const ORDER = { in_progress: 0, live: 1, upcoming: 2, completed: 3, missed: 4 };

function Countdown({ target, onElapsed }) {
  const [left, setLeft] = useState(() => (target - Date.now()) / 1000);
  useEffect(() => {
    const t = setInterval(() => {
      const next = (target - Date.now()) / 1000;
      setLeft(next);
      if (next <= 0) onElapsed?.();
    }, 1000);
    return () => clearInterval(t);
  }, [target, onElapsed]);
  return (
    <span className="muted small nums">
      {left > 86400 ? `Opens ${fmtDate(target)}` : `Opens in ${fmtDuration(left)}`}
    </span>
  );
}

function ExamCard({ e, onResult, onElapsed, onLeaderboard }) {
  let status = null;
  let action = null;

  switch (e.state) {
    case "live":
      status = <Badge color="green" dot>Open now</Badge>;
      action = <Link className="btn primary lg" to={`/exam/${e.id}`}>Start exam</Link>;
      break;
    case "in_progress":
      status = <Badge color="amber" dot>In progress</Badge>;
      action = <Link className="btn primary lg" to={`/exam/${e.id}`}>Resume exam</Link>;
      break;
    case "upcoming":
      status = <Badge color="blue">Scheduled</Badge>;
      action = <Countdown target={new Date(e.start_at).getTime()} onElapsed={onElapsed} />;
      break;
    case "completed":
      status = <Badge color="green">Completed</Badge>;
      action = e.result_available ? (
        <div className="row tight">
          {e.leaderboard_available && (
            <button className="btn" onClick={() => onLeaderboard(e.id)}>Leaderboard</button>
          )}
          <button className="btn" onClick={() => onResult(e.attempt_id)}>
            View result{e.score !== null ? ` · ${e.score}/${e.max_score}` : ""}
          </button>
        </div>
      ) : (
        <span className="muted small">Results will be shared by the organizers</span>
      );
      break;
    case "missed":
      status = <Badge color="red">Missed</Badge>;
      action = <span className="muted small">Window closed</span>;
      break;
    default:
      break;
  }

  return (
    <div className={`card hoverable exam-card s-${e.state}`}>
      <div className="grow">
        <h3>{e.title} {status}</h3>
        <div className="meta">
          {fmtDate(e.start_at)} → {fmtDate(e.end_at)} · {e.duration_minutes} min ·{" "}
          {e.question_count} questions · {e.max_score} marks
        </div>
        {e.sections?.length > 0 && (
          <div className="pill-list" style={{ marginTop: 8 }}>
            {e.sections.map((s) => <Badge key={s} color="outline">{s}</Badge>)}
          </div>
        )}
        {e.description && (
          <div className="small muted" style={{ marginTop: 7 }}>{e.description}</div>
        )}
      </div>
      <div>{action}</div>
    </div>
  );
}

export default function Dashboard() {
  const { user, logout } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();

  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [mustChange, setMustChange] = useState(false);
  const [showPwd, setShowPwd] = useState(false);
  const [result, setResult] = useState(null);
  const [boardExam, setBoardExam] = useState(null);
  const closeBoard = useCallback(() => setBoardExam(null), []);

  const load = useCallback(async () => {
    try {
      const me = await api("GET", "/api/reios/auth/me");
      setMustChange(!!me.must_change_password);
      setData(await api("GET", "/api/reios/student/dashboard"));
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openResult = useCallback(async (attemptId) => {
    try {
      setResult(await api("GET", `/api/reios/student/attempts/${attemptId}/result`));
    } catch (err) {
      toast(err.message, "error");
    }
  }, [toast]);

  // Deep link from the exam page: /student?result=<attemptId>
  useEffect(() => {
    const id = params.get("result");
    if (id) { openResult(id); setParams({}, { replace: true }); }
  }, [params, setParams, openResult]);

  const exams = (data?.exams || []).slice().sort(
    (a, b) => ORDER[a.state] - ORDER[b.state] || new Date(a.start_at) - new Date(b.start_at)
  );
  const active = exams.filter((e) => ["in_progress", "live", "upcoming"].includes(e.state));
  const past = exams.filter((e) => ["completed", "missed"].includes(e.state));
  const isEvent = user?.college?.org_type === "event";
  const liveCount = active.filter((e) => e.state === "live" || e.state === "in_progress").length;

  useEffect(() => {
    if (isEvent && user?.college?.name) document.title = user.college.name;
    return () => { document.title = "Reios"; };
  }, [isEvent, user?.college?.name]);

  return (
    <div className="wrap">
      <header className="bar">
        <OrgBrand branding={user?.college?.branding} style={{ padding: 0 }}
                  sub={user?.college?.branding ? "Powered by Reios" : isEvent ? user?.college?.name : "Student"} />
        <div className="row tight">
          <span className="muted small">
            {user?.name} · {isEvent ? "Team ID" : "Roll no"} <strong>{user?.roll_no}</strong>
            {user?.college && <> · {isEvent ? "Event" : "College"} code <strong>{user.college.code}</strong></>}
          </span>
          <button className="btn sm" onClick={() => setShowPwd(true)}>Change password</button>
          <ThemeToggle className="btn ghost sm" />
          <button className="btn sm" onClick={logout}>Sign out</button>
        </div>
      </header>

      {error && <Empty title={error} />}
      {!data && !error && <Loading />}

      {data && (
        <>
          <div className="page-head">
            <h1>{isEvent ? `Welcome to ${user.college.name}` : `Hi, ${user?.name?.split(" ")[0]}`}</h1>
            <p className="lede">
              {isEvent && <>Signed in as <strong>{user?.name}</strong>. </>}
              {liveCount
                ? `You have ${liveCount} exam${liveCount > 1 ? "s" : ""} open right now.`
                : "Nothing open at the moment. Scheduled exams appear below."}
            </p>
          </div>

          <div className="grid cols-4" style={{ marginBottom: 24 }}>
            <div className="stat green">
              <div className="label">Exams completed</div>
              <div className="value">{data.stats.completed}</div>
            </div>
            <div className="stat">
              <div className="label">Average score</div>
              <div className="value">
                {data.stats.average_percentage === null ? "—" : data.stats.average_percentage + "%"}
              </div>
            </div>
            <div className="stat amber">
              <div className="label">Upcoming / open</div>
              <div className="value">{data.stats.upcoming}</div>
            </div>
            <div className="stat plain">
              <div className="label">{isEvent ? "Team ID" : "Branch"}</div>
              <div className="value" style={{ fontSize: 19 }}>
                {isEvent ? user?.roll_no : (user?.branch || "—")} {!isEvent && (user?.section || "")}
              </div>
              {!isEvent && <div className="sub">{user?.roll_no}</div>}
            </div>
          </div>

          {data.announcements?.length > 0 && (
            <div className="banner" style={{ marginBottom: 20, flexDirection: "column", gap: 9 }}>
              <h3 style={{ margin: 0 }}>Announcements</h3>
              {data.announcements.map((a) => (
                <div key={a.id}>
                  <strong>{a.title}</strong>{" "}
                  <span className="muted tiny">{fmtDate(a.created_at)}</span>
                  <div className="small" style={{ whiteSpace: "pre-wrap", marginTop: 2 }}>{a.body}</div>
                </div>
              ))}
            </div>
          )}

          <div className="section-title"><h2>Your exams</h2></div>
          {active.length > 0
            ? active.map((e) => (
                <ExamCard key={e.id} e={e} onResult={openResult} onElapsed={load} onLeaderboard={setBoardExam} />
              ))
            : <Empty title="No exams open" hint="Exams you're invited to will appear here." />}

          {past.length > 0 && (
            <>
              <div className="section-title"><h2>Past exams</h2></div>
              {past.map((e) => (
                <ExamCard key={e.id} e={e} onResult={openResult} onElapsed={load} onLeaderboard={setBoardExam} />
              ))}
            </>
          )}
        </>
      )}

      <Credit />
      {(showPwd || mustChange) && (
        <ChangePassword
          forced={mustChange}
          onClose={() => setShowPwd(false)}
          onDone={() => { setMustChange(false); setShowPwd(false); load(); }}
        />
      )}
      {result && <ResultModal result={result} onClose={() => setResult(null)} />}
      {boardExam && <LeaderboardModal examId={boardExam} onClose={closeBoard} />}
    </div>
  );
}
