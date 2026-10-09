import { useCallback, useEffect, useState } from "react";
import { api, downloadCSV } from "../../lib/api.js";
import { fmtDate } from "../../lib/format.js";
import {
  Badge, Field, Loading, Modal, ModalButton, useConfirm, useToast,
} from "../../components/ui.jsx";
import { nullIfBlank, useAdmin } from "./context.jsx";
import { CredentialsModal, Pager } from "./shared.jsx";
import AttemptDetail from "./AttemptDetail.jsx";

const PAGE_SIZE = 50;

export default function Students() {
  const { collegeId, cq, isEvent, org } = useAdmin();
  const toast = useToast();
  const confirm = useConfirm();
  const noun = isEvent ? "team" : "student";
  const [deletingAll, setDeletingAll] = useState(false);

  const [filters, setFilters] = useState({ q: "", branch: "", section: "", batch_year: "", logged_in: "", page: 1 });
  const [draft, setDraft] = useState({ q: "", branch: "", section: "", batch_year: "", logged_in: "" });
  const [data, setData] = useState(null);
  const [branches, setBranches] = useState([]);
  const [selected, setSelected] = useState(() => new Set());

  const [editing, setEditing] = useState(null);
  const [importing, setImporting] = useState(false);
  const [creds, setCreds] = useState(null);
  const [report, setReport] = useState(null);
  const [attemptId, setAttemptId] = useState(null);

  useEffect(() => {
    api("GET", "/api/reios/admin/stats" + cq())
      .then((s) => setBranches(s.branches))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collegeId]);

  const load = useCallback(async () => {
    setData(null);
    setSelected(new Set());
    try {
      setData(await api("GET", "/api/reios/admin/students" + cq({ ...filters, page_size: PAGE_SIZE })));
    } catch (err) {
      toast(err.message, "error", 6000);
      setData({ items: [], total: 0, page: 1 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collegeId, filters]);

  useEffect(() => { load(); }, [load]);

  const applyFilters = () => setFilters({ ...draft, page: 1 });
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  function toggle(id) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function bulk(action) {
    const ids = [...selected];
    if (!ids.length) return;
    try {
      if (action === "reset") {
        if (!(await confirm("Reset passwords", `Generate new passwords for ${ids.length} ${noun}s?`))) return;
        const r = await api("POST", "/api/reios/admin/students/bulk-reset-passwords" + cq(), { ids });
        setCreds({ title: "New passwords", creds: r.credentials });
      } else if (action === "reset-login") {
        if (!(await confirm("Reset login",
          `Sign ${ids.length} ${noun}${ids.length > 1 ? "s" : ""} out everywhere right now? They'll need to ` +
          "log in again, but can do so immediately, even if they're signed in somewhere else.",
          "Reset login", true))) return;
        const r = await api("POST", "/api/reios/admin/students/bulk-reset-login" + cq(), { ids });
        toast(`${r.updated} signed out`, "success");
      } else {
        await api("POST", "/api/reios/admin/students/bulk-status" + cq({ active: action === "activate" }), { ids });
        toast("Updated", "success");
      }
      load();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function resetLoginAll() {
    const ok = await confirm("Reset login for everyone",
      `Sign out every ${noun} in this ${isEvent ? "event" : "college"} right now, all at once? They'll need ` +
      "to log in again, but can do so immediately.", "Reset everyone", true);
    if (!ok) return;
    try {
      const r = await api("POST", "/api/reios/admin/students/reset-login-all" + cq());
      toast(`${r.updated} signed out`, "success");
      load();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function resetOne(s) {
    if (!(await confirm("Reset password", `Generate a new temporary password for this ${noun}?`))) return;
    try {
      const r = await api("POST", `/api/reios/admin/students/${s.id}/reset-password` + cq());
      setCreds({ title: "Password reset", creds: [{ roll_no: r.roll_no, name: s.name, password: r.temporary_password }] });
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function remove(s) {
    const ok = await confirm(`Delete ${noun}`, `Delete this ${noun} permanently?`, "Delete", true);
    if (!ok) return;
    try {
      await api("DELETE", `/api/reios/admin/students/${s.id}` + cq());
      toast(`${noun[0].toUpperCase()}${noun.slice(1)} deleted`, "success");
      load();
    } catch (err) {
      if (err.status !== 409) return toast(err.message, "error");
      // Has exam attempts: offer to wipe those along with the account
      const force = await confirm(
        `Delete ${noun} and its results`,
        `This ${noun} has exam attempts. Deleting it will also erase those results permanently — this ` +
          "can't be undone. Deactivating instead keeps the account disabled but its results intact.",
        "Delete everything", true
      );
      if (!force) return;
      try {
        await api("DELETE", `/api/reios/admin/students/${s.id}` + cq({ force: true }));
        toast(`${noun[0].toUpperCase()}${noun.slice(1)} and its results deleted`, "success");
        load();
      } catch (err2) {
        toast(err2.message, "error");
      }
    }
  }

  async function openReport(id) {
    try {
      setReport(await api("GET", `/api/reios/admin/students/${id}/report` + cq()));
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <>
      <div className="row between" style={{ marginBottom: 10 }}>
        <h1 style={{ margin: 0 }}>{isEvent ? "Teams" : "Students"}</h1>
        <div className="row tight">
          <button className="btn" onClick={() => setImporting(true)}>
            {isEvent ? "Upload teams" : "Upload student list"}
          </button>
          <button className="btn primary" onClick={() => setEditing({})}>
            {isEvent ? "+ Add team" : "+ Add student"}
          </button>
          {data?.total > 0 && (
            <>
              <button className="btn" onClick={resetLoginAll}>Reset login for everyone</button>
              <button className="btn danger" onClick={() => setDeletingAll(true)}>
                Delete all {noun}s
              </button>
            </>
          )}
        </div>
      </div>

      {data && (
        <div className="grid cols-2" style={{ marginBottom: 14, maxWidth: 420 }}>
          <button type="button" className="stat green"
                  style={{
                    textAlign: "left", cursor: "pointer", font: "inherit", width: "100%",
                    outline: filters.logged_in === "true" ? "2px solid var(--success)" : "none",
                  }}
                  onClick={() => { const v = filters.logged_in === "true" ? "" : "true";
                                    setDraft((d) => ({ ...d, logged_in: v })); setFilters((f) => ({ ...f, logged_in: v, page: 1 })); }}>
            <div className="label">Logged in</div>
            <div className="value">{data.logged_in_count}</div>
          </button>
          <button type="button" className="stat amber"
                  style={{
                    textAlign: "left", cursor: "pointer", font: "inherit", width: "100%",
                    outline: filters.logged_in === "false" ? "2px solid var(--warning)" : "none",
                  }}
                  onClick={() => { const v = filters.logged_in === "false" ? "" : "false";
                                    setDraft((d) => ({ ...d, logged_in: v })); setFilters((f) => ({ ...f, logged_in: v, page: 1 })); }}>
            <div className="label">Not logged in yet</div>
            <div className="value">{data.not_logged_in_count}</div>
          </button>
        </div>
      )}

      <div className="toolbar">
        <input placeholder={isEvent ? "Search team name or code" : "Search name, roll no, email"} value={draft.q}
               onChange={(e) => setDraft((d) => ({ ...d, q: e.target.value }))}
               onKeyDown={(e) => e.key === "Enter" && applyFilters()} />
        {!isEvent && (
          <>
            <select value={draft.branch} onChange={(e) => setDraft((d) => ({ ...d, branch: e.target.value }))}>
              <option value="">All branches</option>
              {branches.map((b) => <option key={b}>{b}</option>)}
            </select>
            <input placeholder="Section" style={{ minWidth: 90, width: 90 }} value={draft.section}
                   onChange={(e) => setDraft((d) => ({ ...d, section: e.target.value }))} />
            <input placeholder="Batch year" style={{ minWidth: 110, width: 110 }} value={draft.batch_year}
                   onChange={(e) => setDraft((d) => ({ ...d, batch_year: e.target.value }))} />
          </>
        )}
        <button className="btn" onClick={applyFilters}>Filter</button>
        <span className="grow" />
        {selected.size > 0 && (
          <span className="row tight">
            <span className="muted small">{selected.size} selected</span>
            <button className="btn sm" onClick={() => bulk("reset-login")}>Reset login</button>
            <button className="btn sm" onClick={() => bulk("reset")}>Reset passwords</button>
            <button className="btn sm" onClick={() => bulk("activate")}>Activate</button>
            <button className="btn sm danger" onClick={() => bulk("deactivate")}>Deactivate</button>
          </span>
        )}
      </div>

      {!data ? <Loading /> : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>
                    <input type="checkbox"
                           checked={data.items.length > 0 && selected.size === data.items.length}
                           onChange={(e) =>
                             setSelected(e.target.checked ? new Set(data.items.map((s) => s.id)) : new Set())} />
                  </th>
                  <th>{isEvent ? "Team code" : "Roll no"}</th><th>{isEvent ? "Team name" : "Name"}</th>
                  {!isEvent && <><th>Branch</th><th>Section</th><th>Batch</th></>}
                  <th>Status</th><th />
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr><td colSpan={isEvent ? 5 : 8} className="empty">No {noun}s found</td></tr>
                ) : data.items.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggle(s.id)} />
                    </td>
                    <td><strong>{s.roll_no}</strong></td>
                    <td>{s.name}{s.email && <div className="muted small">{s.email}</div>}</td>
                    {!isEvent && <><td>{s.branch || "—"}</td><td>{s.section || "—"}</td><td>{s.batch_year || "—"}</td></>}
                    <td>
                      {!s.is_active ? <Badge color="red">Disabled</Badge>
                        : s.must_change_password ? <Badge color="amber">Not logged in yet</Badge>
                        : <Badge color="green">Active</Badge>}
                    </td>
                    <td>
                      <div className="row tight">
                        <button className="btn sm" onClick={() => openReport(s.id)}>Report</button>
                        <button className="btn sm" onClick={() => setEditing(s)}>Edit</button>
                        <button className="btn sm" onClick={() => resetOne(s)}>Reset pwd</button>
                        <button className="btn sm danger" onClick={() => remove(s)}>Delete</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={data.page} pages={pages} total={data.total} noun={`${noun}s`}
                 onPage={(p) => setFilters((f) => ({ ...f, page: p }))} />
        </>
      )}

      {editing && (
        <StudentForm
          student={editing.id ? editing : null}
          cq={cq}
          isEvent={isEvent}
          onClose={() => setEditing(null)}
          onCreds={setCreds}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}

      {importing && (
        <ImportStudents cq={cq} isEvent={isEvent} onClose={() => setImporting(false)} onCreds={setCreds} onDone={load} />
      )}

      {deletingAll && (
        <DeleteAllStudents cq={cq} isEvent={isEvent} org={org} total={data?.total || 0}
                           onClose={() => setDeletingAll(false)}
                           onDeleted={() => { setDeletingAll(false); load(); }} />
      )}

      {creds && <CredentialsModal {...creds} onClose={() => setCreds(null)} />}

      {report && (
        <StudentReport report={report} isEvent={isEvent} onClose={() => setReport(null)} onAttempt={setAttemptId} />
      )}

      {attemptId && (
        <AttemptDetail attemptId={attemptId} cq={cq} onClose={() => setAttemptId(null)} />
      )}
    </>
  );
}

/** Typing the college/event code guards against wiping the wrong one by mistake. */
function DeleteAllStudents({ cq, isEvent, org, total, onClose, onDeleted }) {
  const toast = useToast();
  const confirm = useConfirm();
  const noun = isEvent ? "team" : "student";
  const [typed, setTyped] = useState("");
  const code = org?.code || "";
  const matches = typed.trim().toUpperCase() === code.toUpperCase();

  async function remove(force = false) {
    const url = "/api/reios/admin/students" + cq({ confirm: typed.trim(), ...(force ? { force: true } : {}) });
    try {
      const r = await api("DELETE", url);
      toast(`${r.deleted} ${noun}${r.deleted === 1 ? "" : "s"} deleted`, "success", 6000);
      onDeleted();
    } catch (err) {
      if (err.status !== 409 || force) return toast(err.message, "error", 6000);
      if (await confirm("End exams and delete all",
        err.message + " — end them and delete everyone anyway?", "Delete everyone", true)) {
        remove(true);
      }
    }
  }

  return (
    <Modal
      title={`Delete all ${noun}s?`}
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          {matches
            ? <ModalButton cls="danger solid" onClick={() => remove()}>Delete all {total} {noun}s</ModalButton>
            : <button className="btn danger solid" disabled>Delete all {total} {noun}s</button>}
        </>
      }
    >
      <div className="banner danger" style={{ marginBottom: 14 }}>
        <span>
          This permanently deletes all <strong>{total} {noun}s</strong> in this {isEvent ? "event" : "college"},
          along with every result and answer they have. It can't be undone. Export any results you need first.
        </span>
      </div>
      <Field label={`Type the ${isEvent ? "event" : "college"} code ${code} to confirm`}>
        <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={code}
               style={{ textTransform: "uppercase" }} autoFocus />
      </Field>
      {!matches && typed && <p className="small" style={{ color: "var(--danger)" }}>That doesn't match.</p>}
    </Modal>
  );
}

function StudentForm({ student, cq, isEvent, onClose, onSaved, onCreds }) {
  const toast = useToast();
  const [f, setF] = useState(() => ({
    roll_no: student?.roll_no || "", name: student?.name || "", email: student?.email || "",
    phone: student?.phone || "", branch: student?.branch || "", section: student?.section || "",
    batch_year: student?.batch_year || "", password: "",
    is_active: student ? student.is_active : true,
  }));
  const set = (k) => (e) =>
    setF((v) => ({ ...v, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const noun = isEvent ? "team" : "student";

  async function save() {
    const body = isEvent
      ? { name: f.name }
      : {
          name: f.name, email: nullIfBlank(f.email), phone: nullIfBlank(f.phone),
          branch: nullIfBlank(f.branch), section: nullIfBlank(f.section),
          batch_year: f.batch_year ? Number(f.batch_year) : null,
        };
    try {
      if (student) {
        await api("PATCH", `/api/reios/admin/students/${student.id}` + cq(), { ...body, is_active: f.is_active });
        toast("Saved", "success");
      } else {
        const r = await api("POST", "/api/reios/admin/students" + cq(),
          { ...body, roll_no: f.roll_no, password: isEvent ? null : nullIfBlank(f.password) });
        onCreds({
          title: `${isEvent ? "Team" : "Student"} added`,
          creds: [{ roll_no: r.roll_no, name: r.name, password: r.temporary_password }],
          note: isEvent ? "The team name is their sign-in password." : undefined,
        });
      }
      onSaved();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <Modal
      title={student ? `Edit ${noun}` : `Add ${noun}`}
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <ModalButton cls="primary" onClick={save}>Save</ModalButton>
        </>
      }
    >
      <div className="form-grid">
        <Field label={isEvent ? "Team code *" : "Roll number *"}>
          <input value={f.roll_no} onChange={set("roll_no")} disabled={!!student} />
        </Field>
        <Field label={isEvent ? "Team name *" : "Full name *"}>
          <input value={f.name} onChange={set("name")} />
        </Field>
        {!isEvent && (
          <>
            <Field label="Email"><input type="email" value={f.email} onChange={set("email")} /></Field>
            <Field label="Phone"><input value={f.phone} onChange={set("phone")} /></Field>
            <Field label="Branch (e.g. CSE, ECE)"><input value={f.branch} onChange={set("branch")} /></Field>
            <Field label="Section"><input value={f.section} onChange={set("section")} /></Field>
            <Field label="Batch / passing year">
              <input type="number" value={f.batch_year} onChange={set("batch_year")} />
            </Field>
            {!student && (
              <Field label="Password (blank = generate)">
                <input value={f.password} onChange={set("password")} />
              </Field>
            )}
          </>
        )}
      </div>
      {isEvent && !student && (
        <p className="muted small">The team name doubles as the sign-in password.</p>
      )}
      {student && (
        <label className="check">
          <input type="checkbox" checked={f.is_active} onChange={set("is_active")} /> Account active
        </label>
      )}
    </Modal>
  );
}

const TEMPLATE_COLS = ["roll_no", "name", "email", "phone", "branch", "section", "batch_year", "password"];
const EVENT_TEMPLATE_COLS = ["team_code", "team_name"];

function ImportStudents({ cq, isEvent, onClose, onCreds, onDone }) {
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const noun = isEvent ? "team" : "student";

  async function upload() {
    if (!file) return toast("Choose a file", "error");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api("POST", "/api/reios/admin/students/import" + cq(), fd);
      setResult(r);
      if (r.credentials.length) {
        onCreds({
          title: `${r.created} ${noun}s imported`, creds: r.credentials,
          note: isEvent ? "Each team's name is also its sign-in password." : undefined,
        });
      }
      onDone();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <Modal
      title={isEvent ? "Upload team logins" : "Upload student logins"}
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Close</button>
          <ModalButton cls="primary" onClick={upload}>Upload</ModalButton>
        </>
      }
    >
      {isEvent ? (
        <>
          <p>
            Upload an <strong>Excel (.xlsx)</strong>, <strong>CSV</strong> or a <strong>Word</strong> file
            with a table. The first row is the header. Each team's <strong>Team Name is also its
            sign-in password</strong> — nothing else to generate or share.
          </p>
          <p className="small muted">
            Only the team code and team name are required. Common header names work: "Team Code",
            "Team ID", "Team Name". PDF lists work only if the table's columns are clearly separated;
            Excel or CSV is more reliable.
          </p>
          <pre>{`team_code,team_name\nTS-001,REBELS\nTS-002,Neon Paradox`}</pre>
          <button className="btn sm" onClick={() => downloadCSV("teams_template.csv", EVENT_TEMPLATE_COLS,
            [["TS-001", "REBELS"], ["TS-002", "Neon Paradox"]])}>
            Download template
          </button>
        </>
      ) : (
        <>
          <p>
            Upload an <strong>Excel (.xlsx)</strong>, <strong>CSV</strong> or a <strong>Word</strong> file
            with a table. The first row is the header. Students sign in with their roll number (username)
            and the password from the sheet; leave the password blank and Reios generates one.
            They must change it at first sign-in.
          </p>
          <p className="small muted">
            Only roll number and name are required. Common header names work: "Roll Number",
            "Username", "Hall Ticket", "Student Name", "Department", "Password". PDF lists work only if
            the table's columns are clearly separated; Excel or CSV is more reliable.
          </p>
          <pre>{`roll_no,name,email,phone,branch,section,batch_year,password
21A91A0501,Anil Kumar,anil@example.com,9876543210,CSE,A,2025,
21A91A0502,Bhavya Sri,,,CSE,A,2025,`}</pre>
          <button className="btn sm" onClick={() => downloadCSV("students_template.csv", TEMPLATE_COLS,
            [["21A91A0501", "Anil Kumar", "anil@example.com", "9876543210", "CSE", "A", "2025", ""]])}>
            Download template
          </button>
        </>
      )}
      <Field label={isEvent ? "Team list" : "Student list"} style={{ marginTop: 14 }}>
        <input type="file" accept=".xlsx,.csv,.docx,.pdf" onChange={(e) => setFile(e.target.files[0])} />
      </Field>
      {result && (
        <>
          <p><strong>{result.created}</strong> created, <strong>{result.failed}</strong> failed.</p>
          {result.errors.length > 0 && (
            <div className="table-wrap compact">
              <table>
                <thead><tr><th>Line</th><th>{isEvent ? "Team code" : "Roll no"}</th><th>Error</th></tr></thead>
                <tbody>
                  {result.errors.map((e, i) => (
                    <tr key={i}><td>{e.line}</td><td>{e.roll_no || ""}</td><td>{e.error}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Modal>
  );
}

function StudentReport({ report: r, isEvent, onClose, onAttempt }) {
  const s = r.student;
  return (
    <Modal title={`${s.name} (${s.roll_no})`} wide onClose={onClose}>
      <dl className="kv">
        {!isEvent && (
          <>
            <dt>Branch</dt><dd>{s.branch || "—"} {s.section || ""}</dd>
            <dt>Batch</dt><dd>{s.batch_year || "—"}</dd>
            <dt>Email</dt><dd>{s.email || "—"}</dd>
          </>
        )}
        <dt>Last login</dt><dd>{fmtDate(s.last_login_at)}</dd>
      </dl>
      <h3 style={{ marginTop: 16 }}>Exam history</h3>
      <div className="table-wrap compact">
        <table>
          <thead>
            <tr>
              <th>Exam</th><th>Date</th><th>Status</th><th className="num">Score</th>
              <th className="num">%</th><th className="num">Violations</th><th />
            </tr>
          </thead>
          <tbody>
            {r.attempts.length === 0 ? (
              <tr><td colSpan={7} className="empty">No exams taken yet</td></tr>
            ) : r.attempts.map((a) => (
              <tr key={a.attempt_id}>
                <td>{a.exam_title}</td>
                <td>{fmtDate(a.started_at)}</td>
                <td>{a.status.replace("_", " ")}</td>
                <td className="num">{a.total_score} / {a.max_score}</td>
                <td className="num">{a.percentage}</td>
                <td className="num">{a.violations}</td>
                <td><button className="btn sm" onClick={() => onAttempt(a.attempt_id)}>View</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}
