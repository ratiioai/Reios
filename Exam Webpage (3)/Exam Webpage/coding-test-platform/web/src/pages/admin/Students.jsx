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
  const { collegeId, cq } = useAdmin();
  const toast = useToast();
  const confirm = useConfirm();

  const [filters, setFilters] = useState({ q: "", branch: "", section: "", batch_year: "", page: 1 });
  const [draft, setDraft] = useState({ q: "", branch: "", section: "", batch_year: "" });
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
        if (!(await confirm("Reset passwords", `Generate new passwords for ${ids.length} students?`))) return;
        const r = await api("POST", "/api/reios/admin/students/bulk-reset-passwords" + cq(), { ids });
        setCreds({ title: "New passwords", creds: r.credentials });
      } else {
        await api("POST", "/api/reios/admin/students/bulk-status" + cq({ active: action === "activate" }), { ids });
        toast("Updated", "success");
      }
      load();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function resetOne(s) {
    if (!(await confirm("Reset password", "Generate a new temporary password for this student?"))) return;
    try {
      const r = await api("POST", `/api/reios/admin/students/${s.id}/reset-password` + cq());
      setCreds({ title: "Password reset", creds: [{ roll_no: r.roll_no, name: s.name, password: r.temporary_password }] });
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function remove(s) {
    const ok = await confirm(
      "Delete student",
      "Delete this student permanently? Students with exam attempts can only be deactivated.",
      "Delete", true
    );
    if (!ok) return;
    try {
      await api("DELETE", `/api/reios/admin/students/${s.id}` + cq());
      toast("Student deleted", "success");
      load();
    } catch (err) {
      toast(err.message, "error");
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
        <h1 style={{ margin: 0 }}>Students</h1>
        <div className="row tight">
          <button className="btn" onClick={() => setImporting(true)}>Upload student list</button>
          <button className="btn primary" onClick={() => setEditing({})}>+ Add student</button>
        </div>
      </div>

      <div className="toolbar">
        <input placeholder="Search name, roll no, email" value={draft.q}
               onChange={(e) => setDraft((d) => ({ ...d, q: e.target.value }))}
               onKeyDown={(e) => e.key === "Enter" && applyFilters()} />
        <select value={draft.branch} onChange={(e) => setDraft((d) => ({ ...d, branch: e.target.value }))}>
          <option value="">All branches</option>
          {branches.map((b) => <option key={b}>{b}</option>)}
        </select>
        <input placeholder="Section" style={{ minWidth: 90, width: 90 }} value={draft.section}
               onChange={(e) => setDraft((d) => ({ ...d, section: e.target.value }))} />
        <input placeholder="Batch year" style={{ minWidth: 110, width: 110 }} value={draft.batch_year}
               onChange={(e) => setDraft((d) => ({ ...d, batch_year: e.target.value }))} />
        <button className="btn" onClick={applyFilters}>Filter</button>
        <span className="grow" />
        {selected.size > 0 && (
          <span className="row tight">
            <span className="muted small">{selected.size} selected</span>
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
                  <th>Roll no</th><th>Name</th><th>Branch</th><th>Section</th>
                  <th>Batch</th><th>Status</th><th />
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr><td colSpan={8} className="empty">No students found</td></tr>
                ) : data.items.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggle(s.id)} />
                    </td>
                    <td><strong>{s.roll_no}</strong></td>
                    <td>{s.name}{s.email && <div className="muted small">{s.email}</div>}</td>
                    <td>{s.branch || "—"}</td>
                    <td>{s.section || "—"}</td>
                    <td>{s.batch_year || "—"}</td>
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
          <Pager page={data.page} pages={pages} total={data.total} noun="students"
                 onPage={(p) => setFilters((f) => ({ ...f, page: p }))} />
        </>
      )}

      {editing && (
        <StudentForm
          student={editing.id ? editing : null}
          cq={cq}
          onClose={() => setEditing(null)}
          onCreds={setCreds}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}

      {importing && (
        <ImportStudents cq={cq} onClose={() => setImporting(false)} onCreds={setCreds} onDone={load} />
      )}

      {creds && <CredentialsModal {...creds} onClose={() => setCreds(null)} />}

      {report && (
        <StudentReport report={report} onClose={() => setReport(null)} onAttempt={setAttemptId} />
      )}

      {attemptId && (
        <AttemptDetail attemptId={attemptId} cq={cq} onClose={() => setAttemptId(null)} />
      )}
    </>
  );
}

function StudentForm({ student, cq, onClose, onSaved, onCreds }) {
  const toast = useToast();
  const [f, setF] = useState(() => ({
    roll_no: student?.roll_no || "", name: student?.name || "", email: student?.email || "",
    phone: student?.phone || "", branch: student?.branch || "", section: student?.section || "",
    batch_year: student?.batch_year || "", password: "",
    is_active: student ? student.is_active : true,
  }));
  const set = (k) => (e) =>
    setF((v) => ({ ...v, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  async function save() {
    const body = {
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
          { ...body, roll_no: f.roll_no, password: nullIfBlank(f.password) });
        onCreds({
          title: "Student added",
          creds: [{ roll_no: r.roll_no, name: r.name, password: r.temporary_password }],
        });
      }
      onSaved();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <Modal
      title={student ? "Edit student" : "Add student"}
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <ModalButton cls="primary" onClick={save}>Save</ModalButton>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Roll number *">
          <input value={f.roll_no} onChange={set("roll_no")} disabled={!!student} />
        </Field>
        <Field label="Full name *"><input value={f.name} onChange={set("name")} /></Field>
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
      </div>
      {student && (
        <label className="check">
          <input type="checkbox" checked={f.is_active} onChange={set("is_active")} /> Account active
        </label>
      )}
    </Modal>
  );
}

const TEMPLATE_COLS = ["roll_no", "name", "email", "phone", "branch", "section", "batch_year", "password"];

function ImportStudents({ cq, onClose, onCreds, onDone }) {
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);

  async function upload() {
    if (!file) return toast("Choose a file", "error");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api("POST", "/api/reios/admin/students/import" + cq(), fd);
      setResult(r);
      if (r.credentials.length) {
        onCreds({ title: `${r.created} students imported`, creds: r.credentials });
      }
      onDone();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <Modal
      title="Upload student logins"
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Close</button>
          <ModalButton cls="primary" onClick={upload}>Upload</ModalButton>
        </>
      }
    >
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
      <Field label="Student list" style={{ marginTop: 14 }}>
        <input type="file" accept=".xlsx,.csv,.docx,.pdf" onChange={(e) => setFile(e.target.files[0])} />
      </Field>
      {result && (
        <>
          <p><strong>{result.created}</strong> created, <strong>{result.failed}</strong> failed.</p>
          {result.errors.length > 0 && (
            <div className="table-wrap compact">
              <table>
                <thead><tr><th>Line</th><th>Roll no</th><th>Error</th></tr></thead>
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

function StudentReport({ report: r, onClose, onAttempt }) {
  const s = r.student;
  return (
    <Modal title={`${s.name} (${s.roll_no})`} wide onClose={onClose}>
      <dl className="kv">
        <dt>Branch</dt><dd>{s.branch || "—"} {s.section || ""}</dd>
        <dt>Batch</dt><dd>{s.batch_year || "—"}</dd>
        <dt>Email</dt><dd>{s.email || "—"}</dd>
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
