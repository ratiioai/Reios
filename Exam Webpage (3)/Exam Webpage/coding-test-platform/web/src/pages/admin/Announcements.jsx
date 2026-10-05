import { useCallback, useEffect, useState } from "react";
import { api, qs } from "../../lib/api.js";
import { fmtDate } from "../../lib/format.js";
import { Badge, Empty, Field, Loading, Spinner, useConfirm, useToast } from "../../components/ui.jsx";
import { useAdmin } from "./context.jsx";

export default function Announcements() {
  const { isSuper, collegeId, cq, needCollege } = useAdmin();
  const toast = useToast();
  const confirm = useConfirm();

  const [list, setList] = useState(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [allColleges, setAllColleges] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (needCollege) { setList([]); return; }
    try {
      setList(await api("GET", "/api/reios/admin/announcements" + cq()));
    } catch (err) {
      toast(err.message, "error", 6000);
      setList([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collegeId, needCollege]);

  useEffect(() => { load(); }, [load]);

  async function post() {
    if (!title.trim() || !body.trim()) return toast("Add a title and a message", "error");
    setBusy(true);
    try {
      await api("POST", "/api/reios/admin/announcements" + (allColleges ? qs({ all_colleges: true }) : cq()),
                { title, body });
      setTitle(""); setBody(""); setAllColleges(false);
      toast("Posted", "success");
      load();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    if (!(await confirm("Delete announcement?", "Students will no longer see it.", "Delete", true))) return;
    try {
      await api("DELETE", `/api/reios/admin/announcements/${id}`);
      load();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  if (needCollege && !isSuper) return <Empty title="No college selected" />;

  return (
    <>
      <div className="page-head">
        <h1>Announcements</h1>
        <p className="lede">Shown on the student dashboard.</p>
      </div>

      <div className="card" style={{ maxWidth: 620 }}>
        <h3>New announcement</h3>
        <Field label="Title">
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="Message">
          <textarea rows={3} value={body} onChange={(e) => setBody(e.target.value)} />
        </Field>
        {isSuper && (
          <label className="check">
            <input type="checkbox" checked={allColleges}
                   onChange={(e) => setAllColleges(e.target.checked)} />
            Send to all colleges
          </label>
        )}
        <button className="btn primary" onClick={post} disabled={busy}>
          {busy ? <><Spinner /> Posting</> : "Post to students"}
        </button>
      </div>

      {list === null ? <Loading /> : list.length === 0 ? (
        <Empty title="No announcements yet" hint="Anything you post appears on every student's dashboard." />
      ) : (
        <div className="card">
          {list.map((a) => (
            <div key={a.id} style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
              <div className="row between">
                <strong>{a.title}</strong>
                <span className="row tight small muted">
                  {a.is_global && <Badge color="blue">All colleges</Badge>}
                  {fmtDate(a.created_at)}
                  {(!a.is_global || isSuper) && (
                    <button className="btn sm ghost" onClick={() => remove(a.id)} aria-label="Delete">✕</button>
                  )}
                </span>
              </div>
              <div style={{ whiteSpace: "pre-wrap" }}>{a.body}</div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
