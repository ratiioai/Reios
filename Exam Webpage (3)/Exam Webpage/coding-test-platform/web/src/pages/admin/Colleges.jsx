import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api.js";
import { fmtDate } from "../../lib/format.js";
import {
  Badge, Empty, Field, Loading, Modal, ModalButton, useConfirm, useToast,
} from "../../components/ui.jsx";
import { nullIfBlank, useAdmin } from "./context.jsx";
import { CredentialsModal } from "./shared.jsx";

export default function Colleges() {
  const { colleges, setColleges, pickCollege } = useAdmin();
  const toast = useToast();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);   // college object, or {} for new
  const [adminsFor, setAdminsFor] = useState(null);
  const [creds, setCreds] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setColleges(await api("GET", "/api/reios/super/colleges"));
    } catch (err) {
      toast(err.message, "error", 6000);
    } finally {
      setLoading(false);
    }
  }, [setColleges, toast]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <div className="row between" style={{ marginBottom: 6 }}>
        <div className="page-head" style={{ margin: 0 }}>
          <h1>Organizations</h1>
          <p className="lede">
            Each college gets its own admins, students, exams and results. Students sign in with
            the college code.
          </p>
        </div>
        <button className="btn primary" onClick={() => setEditing({})}>+ Add organization</button>
      </div>

      {loading ? <Loading /> : colleges.length === 0 ? (
        <Empty title="No organizations yet" hint="Add a college, company or event that uses Reios." />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Organization</th><th>Code</th><th className="num">Students</th>
                <th className="num">Admins</th><th className="num">Exams</th><th>Status</th><th />
              </tr>
            </thead>
            <tbody>
              {colleges.map((c) => (
                <tr key={c.id}>
                  <td>
                    <strong>{c.name}</strong>{" "}
                    {c.org_type === "event" && <Badge color="violet">Event</Badge>}
                    {c.features?.length > 0 && (
                      <div className="muted small">Add-ons: {c.features.map((k) => k.replace("_", " ")).join(", ")}</div>
                    )}
                    {c.city && <div className="muted small">{c.city}</div>}
                  </td>
                  <td><code>{c.code}</code></td>
                  <td className="num">{c.student_count}{c.max_students ? ` / ${c.max_students}` : ""}</td>
                  <td className="num">{c.admin_count}</td>
                  <td className="num">{c.exam_count}{c.max_exams ? ` / ${c.max_exams}` : ""}</td>
                  <td>
                    {!c.is_active ? <Badge color="red">Disabled</Badge>
                      : c.expired ? <Badge color="red">Expired</Badge>
                      : <Badge color="green">Active</Badge>}
                    {c.access_until && (
                      <div className="muted small">
                        {c.expired ? "ended" : "until"} {new Date(c.access_until).toLocaleDateString()}
                      </div>
                    )}
                  </td>
                  <td>
                    <div className="row tight">
                      <button className="btn sm" onClick={() => setAdminsFor(c)}>Admins</button>
                      <button className="btn sm" onClick={() => setEditing(c)}>Edit</button>
                      <button className="btn sm" onClick={() => { pickCollege(c.id); navigate("/console"); }}>
                        Open
                      </button>
                      <button className="btn sm danger" onClick={() => setDeleting(c)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <CollegeForm
          college={editing.id ? editing : null}
          onClose={() => setEditing(null)}
          onSaved={(created) => { if (created) pickCollege(created.id); setEditing(null); load(); }}
        />
      )}

      {adminsFor && (
        <CollegeAdmins
          college={adminsFor}
          onClose={() => { setAdminsFor(null); load(); }}
          onCreds={setCreds}
        />
      )}

      {creds && (
        <CredentialsModal {...creds} onClose={() => setCreds(null)} />
      )}

      {deleting && (
        <DeleteCollege college={deleting} onClose={() => setDeleting(null)}
                       onDeleted={() => { setDeleting(null); load(); }} />
      )}
    </>
  );
}

/** Typing the college code guards against deleting the wrong one. */
function DeleteCollege({ college, onClose, onDeleted }) {
  const toast = useToast();
  const [typed, setTyped] = useState("");
  const matches = typed.trim().toUpperCase() === college.code.toUpperCase();

  async function remove() {
    try {
      const r = await api("DELETE", `/api/reios/super/colleges/${college.id}?confirm=${encodeURIComponent(typed.trim())}`);
      toast(`${college.name} deleted: ${r.students} students, ${r.exams} exams, ${r.attempts} attempts removed`, "success", 6000);
      onDeleted();
    } catch (err) { toast(err.message, "error", 6000); }
  }

  return (
    <Modal
      title={`Delete ${college.name}?`}
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          {matches
            ? <ModalButton cls="danger solid" onClick={remove}>Delete permanently</ModalButton>
            : <button className="btn danger solid" disabled>Delete permanently</button>}
        </>
      }
    >
      <div className="banner danger" style={{ marginBottom: 14 }}>
        <span>
          This permanently deletes the college with its <strong>{college.student_count} students</strong>,{" "}
          <strong>{college.admin_count} admins</strong>, <strong>{college.exam_count} exams</strong>, every result,
          answer and proctoring log, its question sets and its own question bank. It can't be undone.
          Export any results you need first. Questions in the global bank are kept.
        </span>
      </div>
      <Field label={`Type the college code ${college.code} to confirm`}>
        <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={college.code}
               style={{ textTransform: "uppercase" }} autoFocus />
      </Field>
      {!matches && typed && <p className="small" style={{ color: "var(--danger)" }}>That doesn't match.</p>}
    </Modal>
  );
}

function CollegeForm({ college, onClose, onSaved }) {
  const toast = useToast();
  const [f, setF] = useState(() => ({
    name: college?.name || "",
    code: college?.code || "",
    city: college?.city || "",
    max_students: college?.max_students || "",
    max_exams: college?.max_exams || "",
    org_type: college?.org_type || "college",
    features: college?.features || [],
    logo: college?.logo || "",
    brand_color: college?.brand_color || "#4f46e5",
    // stored as end of that day, local time
    access_until: college?.access_until ? toDateInput(college.access_until) : "",
    contact_email: college?.contact_email || "",
    contact_phone: college?.contact_phone || "",
    is_active: college ? college.is_active : true,
  }));
  const set = (k) => (e) =>
    setF((v) => ({ ...v, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  async function save() {
    const body = {
      name: f.name,
      city: nullIfBlank(f.city),
      contact_email: nullIfBlank(f.contact_email),
      contact_phone: nullIfBlank(f.contact_phone),
      max_students: f.max_students ? Number(f.max_students) : null,
      max_exams: f.max_exams ? Number(f.max_exams) : null,
      org_type: f.org_type,
      features: f.org_type === "event" ? f.features : [],
      logo: f.org_type === "event" && f.features.includes("branding") ? f.logo || null : null,
      brand_color: f.brand_color || null,
      access_until: f.access_until ? new Date(`${f.access_until}T23:59:59`).toISOString() : null,
    };
    try {
      if (college) {
        await api("PATCH", `/api/reios/super/colleges/${college.id}`, { ...body, is_active: f.is_active });
        toast("Organization saved", "success");
        onSaved(null);
      } else {
        const created = await api("POST", "/api/reios/super/colleges", { ...body, code: f.code });
        toast("Organization created", "success");
        onSaved(created);
      }
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <Modal
      title={college ? "Edit organization" : "Add organization"}
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <ModalButton cls="primary" onClick={save}>Save</ModalButton>
        </>
      }
    >
      <label>Type</label>
      <div className="segment" style={{ marginBottom: 14 }}>
        {[["college", "College"], ["event", "Event / paid client"]].map(([id, label]) => (
          <button key={id} type="button" className={f.org_type === id ? "active" : ""}
                  onClick={() => setF((v) => ({ ...v, org_type: id }))}>{label}</button>
        ))}
      </div>
      <div className="form-grid">
        <Field label="Organization name *">
          <input value={f.name} onChange={set("name")} />
        </Field>
        <Field label="Code * (students type this at login)">
          <input value={f.code} onChange={set("code")} disabled={!!college}
                 style={{ textTransform: "uppercase" }} />
        </Field>
        <Field label="City"><input value={f.city} onChange={set("city")} /></Field>
        <Field label="Student limit (blank = unlimited)">
          <input type="number" min="1" value={f.max_students} onChange={set("max_students")} />
        </Field>
        <Field label="Exam limit (blank = unlimited)">
          <input type="number" min="1" value={f.max_exams} onChange={set("max_exams")} />
        </Field>
        <Field label="Access until (blank = no end date)">
          <input type="date" value={f.access_until} onChange={set("access_until")} />
        </Field>
        <Field label="Contact email">
          <input type="email" value={f.contact_email} onChange={set("contact_email")} />
        </Field>
        <Field label="Contact phone">
          <input value={f.contact_phone} onChange={set("contact_phone")} />
        </Field>
      </div>
      {f.org_type === "event" && (
        <EventAddOns f={f} setF={setF} />
      )}
      {college && (
        <label className="check">
          <input type="checkbox" checked={f.is_active} onChange={set("is_active")} />
          College is active (unticking blocks all its users from signing in)
        </label>
      )}
    </Modal>
  );
}

function CollegeAdmins({ college, onClose, onCreds }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [admins, setAdmins] = useState(null);
  const [f, setF] = useState({ name: "", email: "", phone: "", password: "" });
  const set = (k) => (e) => setF((v) => ({ ...v, [k]: e.target.value }));

  const load = useCallback(async () => {
    try {
      setAdmins(await api("GET", `/api/reios/super/colleges/${college.id}/admins`));
    } catch (err) {
      toast(err.message, "error");
      setAdmins([]);
    }
  }, [college.id, toast]);

  useEffect(() => { load(); }, [load]);

  async function create() {
    try {
      const created = await api("POST", `/api/reios/super/colleges/${college.id}/admins`, {
        name: f.name, email: f.email,
        phone: nullIfBlank(f.phone), password: nullIfBlank(f.password),
      });
      setF({ name: "", email: "", phone: "", password: "" });
      onCreds({
        title: "Organization admin created",
        creds: [{ email: created.email, name: created.name, password: created.temporary_password }],
        note: `Share these sign-in details with the admin. Sign-in page: ${location.origin}${import.meta.env.BASE_URL}login?as=admin`,
      });
      load();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function reset(a) {
    if (!(await confirm("Reset password", "Generate a new temporary password for this admin?"))) return;
    try {
      const r = await api("POST", `/api/reios/super/admins/${a.id}/reset-password`);
      onCreds({
        title: "Password reset",
        creds: [{ email: a.email, name: a.name, password: r.temporary_password }],
      });
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function toggle(a) {
    try {
      await api("PATCH", `/api/reios/super/admins/${a.id}`, { is_active: !a.is_active });
      load();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <Modal title={`Admins · ${college.name}`} wide onClose={onClose}>
      {admins === null ? <Loading /> : (
        <div className="table-wrap compact">
          <table>
            <thead>
              <tr><th>Name</th><th>Email</th><th>Last login</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {admins.length === 0 ? (
                <tr><td colSpan={5} className="empty">No admins yet</td></tr>
              ) : admins.map((a) => (
                <tr key={a.id}>
                  <td>{a.name}</td>
                  <td>{a.email}</td>
                  <td>{fmtDate(a.last_login_at)}</td>
                  <td>{a.is_active ? <Badge color="green">Active</Badge> : <Badge color="red">Disabled</Badge>}</td>
                  <td>
                    <div className="row tight">
                      <button className="btn sm" onClick={() => reset(a)}>Reset password</button>
                      <button className={"btn sm" + (a.is_active ? " danger" : "")} onClick={() => toggle(a)}>
                        {a.is_active ? "Disable" : "Enable"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 style={{ marginTop: 18 }}>Add organization admin</h3>
      <div className="form-grid">
        <Field label="Name *"><input value={f.name} onChange={set("name")} /></Field>
        <Field label="Email * (login)"><input type="email" value={f.email} onChange={set("email")} /></Field>
        <Field label="Phone"><input value={f.phone} onChange={set("phone")} /></Field>
        <Field label="Password (blank = generate)">
          <input value={f.password} onChange={set("password")} minLength={8} />
        </Field>
      </div>
      <ModalButton cls="primary" onClick={create}>Create admin</ModalButton>
    </Modal>
  );
}

function toDateInput(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const ADD_ONS = [
  ["certificates", "Certificates", "PDF certificate for every student who passes"],
  ["branding", "Branding", "Their logo and colour on their students' sign-in, dashboard, exam and certificates"],
  ["email_results", "Email results", "Admin can email every student their score and rank"],
];

function EventAddOns({ f, setF }) {
  const toast = useToast();
  const toggle = (key) => setF((v) => ({
    ...v, features: v.features.includes(key) ? v.features.filter((k) => k !== key) : [...v.features, key],
  }));

  function pickLogo(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (!/^image\/(png|jpe?g)$/.test(file.type)) return toast("Use a PNG or JPG image", "error");
    if (file.size > 300 * 1024) return toast("The logo must be smaller than 300 KB", "error");
    const reader = new FileReader();
    reader.onload = () => setF((v) => ({ ...v, logo: reader.result }));
    reader.readAsDataURL(file);
  }

  return (
    <div className="card pad-sm" style={{ margin: "4px 0 14px" }}>
      <strong className="small">Paid add-ons for this event</strong>
      <p className="muted small" style={{ margin: "2px 0 8px" }}>Only what you tick is available to them.</p>
      {ADD_ONS.map(([key, label, hint]) => (
        <label key={key} className="check" style={{ alignItems: "flex-start" }}>
          <input type="checkbox" checked={f.features.includes(key)} onChange={() => toggle(key)} />
          <span><strong>{label}</strong> <span className="muted small">— {hint}</span></span>
        </label>
      ))}
      {f.features.includes("branding") && (
        <div className="row" style={{ marginTop: 10, gap: 16, alignItems: "flex-end" }}>
          <Field label="Logo (PNG or JPG, under 300 KB)">
            <input type="file" accept="image/png,image/jpeg" onChange={pickLogo} />
          </Field>
          {f.logo && <img src={f.logo} alt="Logo preview"
                          style={{ height: 44, maxWidth: 140, objectFit: "contain", marginBottom: 16 }} />}
          <Field label="Brand colour">
            <input type="color" value={f.brand_color} style={{ width: 64, padding: 2, height: 40 }}
                   onChange={(e) => setF((v) => ({ ...v, brand_color: e.target.value }))} />
          </Field>
        </div>
      )}
    </div>
  );
}
