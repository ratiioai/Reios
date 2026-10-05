import { useCallback, useEffect, useMemo, useState } from "react";
import { api, download } from "../../lib/api.js";
import {
  Badge, Field, Loading, Markdown, Modal, ModalButton, useConfirm, useToast,
} from "../../components/ui.jsx";
import BulkSetUpload from "./BulkSetUpload.jsx";

/**
 * Sets are paper variants. Every student sits the exam's common questions plus one set.
 */
export default function ExamSets({ exam, cq, onChanged }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [data, setData] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [viewing, setViewing] = useState(null);

  const load = useCallback(async () => {
    try {
      setData(await api("GET", `/api/reios/admin/exams/${exam.id}/sets` + cq()));
    } catch (err) { toast(err.message, "error"); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exam.id]);

  useEffect(() => { load(); }, [load]);

  async function remove(s) {
    const ok = await confirm("Delete set", `Delete "${s.name}" and its ${s.question_count} questions? ` +
      "Students assigned to it will be unassigned.", "Delete", true);
    if (!ok) return;
    try {
      await api("DELETE", `/api/reios/admin/exams/${exam.id}/sets/${s.id}` + cq());
      toast("Set deleted", "success");
      load(); onChanged?.();
    } catch (err) { toast(err.message, "error"); }
  }

  async function view(s) {
    try {
      setViewing(await api("GET", `/api/reios/admin/exams/${exam.id}/sets/${s.id}` + cq()));
    } catch (err) { toast(err.message, "error"); }
  }

  if (!data) return <div className="card"><Loading /></div>;
  const sets = data.sets;

  return (
    <>
      <div className="card">
        <div className="card-head">
          <div>
            <h2>Question sets <span className="muted small">{sets.length ? `${sets.length} sets` : "optional"}</span></h2>
            <p className="muted small" style={{ margin: 0 }}>
              Upload different papers (Set 1, Set 2, …). Each student gets the common questions above
              plus one set. With 10 sets and 30 students, each set goes to 3 students.
            </p>
          </div>
          {data.locked ? <Badge color="amber">Locked: students have started</Badge> : (
            <button className="btn primary sm" onClick={() => setUploading(true)}>+ Upload sets</button>
          )}
        </div>

        {sets.length === 0 ? (
          <div className="empty">
            <span className="big">No sets</span>
            <span className="small">
              Every student gets the same paper. Upload one Word, PDF or Excel file per set; pick
              them all at once and they become Set 1, Set 2, … automatically.
            </span>
          </div>
        ) : (
          <div className="table-wrap compact">
            <table>
              <thead>
                <tr><th>Set</th><th className="num">Questions</th><th className="num">Marks</th>
                  <th>Sections</th><th className="num">Students</th><th /></tr>
              </thead>
              <tbody>
                {sets.map((s) => (
                  <tr key={s.id}>
                    <td><strong>{s.name}</strong>
                      {s.source_filename && <div className="muted small">{s.source_filename}</div>}</td>
                    <td className="num">{s.question_count}</td>
                    <td className="num">{s.marks}</td>
                    <td className="small">{s.sections.join(", ")}</td>
                    <td className="num">{s.assigned}</td>
                    <td>
                      <div className="row tight">
                        <button className="btn sm" onClick={() => view(s)}>View</button>
                        {!data.locked && <button className="btn sm danger" onClick={() => remove(s)}>Delete</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {sets.length > 1 && new Set(sets.map((s) => s.marks)).size > 1 && (
          <p className="small" style={{ color: "var(--warning)", margin: "10px 0 0" }}>
            Sets have different total marks. Rankings use percentages, so this stays fair, but
            equal sets are easier to compare.
          </p>
        )}
      </div>

      {sets.length > 0 && <SetAssignments exam={exam} cq={cq} sets={sets} onChanged={load} />}

      {uploading && (
        <BulkSetUpload
          examId={exam.id}
          cq={cq}
          existingNames={sets.map((s) => s.name)}
          onClose={() => setUploading(false)}
          onSaved={() => { load(); onChanged?.(); }}
        />
      )}

      {viewing && (
        <Modal title={viewing.name} wide onClose={() => setViewing(null)}>
          {viewing.questions.map((q, i) => (
            <div key={q.id} className="card pad-sm" style={{ marginBottom: 8 }}>
              <div className="row between"><strong className="small">Q{i + 1} · {q.section}</strong>
                <span className="small muted">+{q.marks}{q.negative_marks ? ` / −${q.negative_marks}` : ""}</span></div>
              <Markdown>{q.question_text}</Markdown>
              <ol className="option-list">
                {q.options.map((o, oi) => (
                  <li key={oi} className={q.correct_options.includes(oi) ? "correct" : ""}>{o}</li>
                ))}
              </ol>
            </div>
          ))}
        </Modal>
      )}
    </>
  );
}

function SetAssignments({ exam, cq, sets, onChanged }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [data, setData] = useState(null);
  const [draft, setDraft] = useState({});   // student_id -> set_id (unsaved edits)
  const [filter, setFilter] = useState("");
  const [importing, setImporting] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await api("GET", `/api/reios/admin/exams/${exam.id}/set-assignments` + cq()));
      setDraft({});
    } catch (err) { toast(err.message, "error"); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exam.id]);

  useEffect(() => { load(); }, [load, sets.length]);

  const shown = useMemo(() => {
    if (!data) return [];
    const q = filter.toLowerCase();
    return data.students.filter((s) => !q || `${s.roll_no} ${s.name} ${s.branch || ""}`.toLowerCase().includes(q));
  }, [data, filter]);

  async function auto(overwrite) {
    if (overwrite && !(await confirm("Re-rotate every student",
      "Every student who hasn't started will be reassigned in roll-number order (Set 1, Set 2, …, then repeat). Continue?",
      "Re-rotate"))) return;
    try {
      const r = await api("POST", `/api/reios/admin/exams/${exam.id}/set-assignments/auto` + cq(), { overwrite });
      toast(r.assigned ? `${r.assigned} students assigned` : "Everyone already has a set", "success");
      load(); onChanged?.();
    } catch (err) { toast(err.message, "error"); }
  }

  async function setAuto(on) {
    try {
      const r = await api("PUT", `/api/reios/admin/exams/${exam.id}/set-options` + cq(), { auto_assign: on });
      setData(r);
      setDraft({});
      toast(on ? "Sets will be assigned automatically" : "Automatic assignment off", "success");
      onChanged?.();
    } catch (err) { toast(err.message, "error"); }
  }

  async function saveDraft() {
    const assignments = Object.entries(draft).map(([sid, setId]) => ({
      student_id: Number(sid), set_id: setId === "" ? null : Number(setId),
    }));
    try {
      const r = await api("PUT", `/api/reios/admin/exams/${exam.id}/set-assignments` + cq(), { assignments });
      toast(`${r.changed} updated${data.auto_assign ? ". Automatic assignment is now off so your choices stay" : ""}`, "success");
      load(); onChanged?.();
    } catch (err) { toast(err.message, "error"); }
  }

  if (!data) return <div className="card"><Loading /></div>;
  const pending = Object.keys(draft).length;
  const setName = Object.fromEntries(data.sets.map((s) => [s.id, s.name]));
  const n = data.sets.length;
  const total = data.students.length;
  const per = n ? Math.floor(total / n) : 0;
  const extra = n ? total % n : 0;

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h2>Who gets which set</h2>
          <p className="muted small" style={{ margin: 0 }}>
            {total} eligible students ·{" "}
            {data.unassigned ? <strong style={{ color: "var(--warning)" }}>{data.unassigned} without a set</strong>
              : "everyone has a set"}
          </p>
        </div>
        <div className="row tight">
          {!data.auto_assign && data.unassigned > 0 && (
            <button className="btn sm primary" onClick={() => auto(false)}>Give the unassigned a set</button>
          )}
          {!data.auto_assign && <button className="btn sm" onClick={() => auto(true)}>Re-rotate everyone</button>}
          <button className="btn sm" onClick={() => setImporting(true)}>Upload sheet</button>
          <button className="btn sm" onClick={() => download(
            `/api/reios/admin/exams/${exam.id}/set-assignments/export` + cq(), "set_assignments.csv",
          ).catch((e) => toast(e.message, "error"))}>Export</button>
        </div>
      </div>

      <div className="banner" style={{ marginBottom: 14, alignItems: "center" }}>
        <label className="check" style={{ margin: 0, flex: "none" }}>
          <input type="checkbox" checked={!!data.auto_assign} onChange={(e) => setAuto(e.target.checked)} />
          <strong>Assign automatically</strong>
        </label>
        <span className="small">
          {data.auto_assign ? (
            <>In roll-number order: students 1–{n} get {data.sets.map((s) => s.name).join(", ")}, then it
              repeats from {data.sets[0]?.name} for students {n + 1}–{2 * n}, and so on.{" "}
              {total > 0 && <>With {total} students, each set goes to {per}{extra ? `–${per + 1}` : ""} students.</>}{" "}
              Re-applied whenever you add or remove a set.</>
          ) : (
            <>Off: sets stay exactly as you've set them below. Students left without a set get the
              least-used one when they start.</>
          )}
        </span>
      </div>

      <div className="toolbar">
        <input placeholder="Find a student" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <span className="grow" />
        {pending > 0 && (
          <>
            <span className="small muted">{pending} unsaved change{pending > 1 ? "s" : ""}</span>
            <button className="btn sm" onClick={() => setDraft({})}>Discard</button>
            <button className="btn sm primary" onClick={saveDraft}>Save changes</button>
          </>
        )}
      </div>

      <div className="table-wrap compact" style={{ maxHeight: 420, overflowY: "auto" }}>
        <table>
          <thead><tr><th>Roll no</th><th>Name</th><th>Branch</th><th style={{ width: 200 }}>Set</th></tr></thead>
          <tbody>
            {shown.length === 0 ? (
              <tr><td colSpan={4} className="empty">
                No eligible students. Check the exam's branch / batch / section filters.
              </td></tr>
            ) : shown.map((s) => {
              const value = draft[s.student_id] ?? (s.set_id ?? "");
              return (
                <tr key={s.student_id}>
                  <td><strong>{s.roll_no}</strong></td>
                  <td>{s.name}</td>
                  <td>{s.branch || "—"} {s.section || ""}</td>
                  <td>
                    {s.started ? (
                      <span className="small">{setName[s.set_id] || "—"} <Badge>started</Badge></span>
                    ) : (
                      <select value={value} style={{ padding: "4px 30px 4px 8px", fontSize: 13 }}
                              onChange={(e) => setDraft((d) => ({ ...d, [s.student_id]: e.target.value }))}>
                        <option value="">— not assigned —</option>
                        {data.sets.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                      </select>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {importing && (
        <ImportAssignments exam={exam} cq={cq} sets={data.sets}
                           onClose={() => setImporting(false)}
                           onDone={() => { load(); onChanged?.(); }} />
      )}
    </div>
  );
}

function ImportAssignments({ exam, cq, sets, onClose, onDone }) {
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);

  async function upload() {
    if (!file) return toast("Choose a file", "error");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api("POST", `/api/reios/admin/exams/${exam.id}/set-assignments/import` + cq(), fd);
      setResult(r);
      toast(`${r.changed} students updated`, "success");
      onDone();
    } catch (err) { toast(err.message, "error", 6000); }
  }

  return (
    <Modal title="Assign sets from a sheet" onClose={onClose}
           actions={<><button className="btn" onClick={onClose}>Close</button>
             <ModalButton cls="primary" onClick={upload}>Upload</ModalButton></>}>
      <p>
        An Excel, CSV or Word table with a roll number column and a <code>set</code> column. The set
        can be its name ({sets.map((s) => `"${s.name}"`).join(", ")}), its number (1, 2, …) or a
        letter (A, B, …).
      </p>
      <pre>{`roll_no,set\n21CS001,Set 1\n21CS002,2\n21CS003,B`}</pre>
      <Field label="File">
        <input type="file" accept=".xlsx,.csv,.docx" onChange={(e) => setFile(e.target.files[0])} />
      </Field>
      {result?.errors.length > 0 && (
        <div className="table-wrap compact">
          <table>
            <thead><tr><th>Line</th><th>Roll no</th><th>Problem</th></tr></thead>
            <tbody>{result.errors.map((e, i) => (
              <tr key={i}><td>{e.line ?? "—"}</td><td>{e.roll_no}</td><td>{e.error}</td></tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}
