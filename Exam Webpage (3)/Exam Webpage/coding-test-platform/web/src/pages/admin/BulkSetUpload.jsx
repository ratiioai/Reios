import { useState } from "react";
import { api } from "../../lib/api.js";
import { Badge, Field, Modal, Spinner, useToast } from "../../components/ui.jsx";
import { ReviewQuestions, problemsOf } from "./QuestionImport.jsx";

const ACCEPT = ".docx,.pdf,.csv,.xlsx,.txt";

// "set10.docx" sorts after "set2.docx"
const naturalCompare = (a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });

/** "Set 3 - GK.docx" -> 3; nothing found -> null */
function setNumberFrom(filename) {
  const m = filename.match(/set[\s_-]*(\d+)/i) || filename.match(/^(\d+)[\s_.-]/);
  return m ? Number(m[1]) : null;
}

/**
 * Upload many set files at once. Each file becomes one set, named "Set 1", "Set 2", …
 * (or the number already in its filename), and can be reviewed before saving.
 */
export default function BulkSetUpload({ examId, cq, existingNames, onClose, onSaved }) {
  const toast = useToast();
  const [files, setFiles] = useState([]);
  const [section, setSection] = useState("General");
  const [marks, setMarks] = useState(1);
  const [negative, setNegative] = useState(0);
  const [rows, setRows] = useState(null);   // [{file, name, status, parsed, error}]
  const [reviewing, setReviewing] = useState(null);
  const [saving, setSaving] = useState(false);

  /**
   * Name each row: the set heading inside the file ("Set 3") first, then a number in the
   * filename, then the next free "Set N".
   */
  function nameRows(list) {
    const taken = new Set(existingNames.map((n) => n.toLowerCase()));
    let next = existingNames.length + 1;
    return list.map((row) => {
      if (row.name && row.status === "saved") return row;
      const n = setNumberFrom(row.file.name);
      let name = row.label && !taken.has(row.label.toLowerCase()) ? row.label
        : n && !row.label && !taken.has(`set ${n}`) ? `Set ${n}` : null;
      while (!name) {
        if (!taken.has(`set ${next}`)) name = `Set ${next}`;
        next++;
      }
      taken.add(name.toLowerCase());
      return { ...row, name };
    });
  }

  async function readAll() {
    if (!files.length) return toast("Choose the set files", "error");
    const sorted = [...files].sort((a, b) => naturalCompare(a.name, b.name));
    const done = [];
    let filesRead = 0;
    const show = () => setRows(nameRows([
      ...done,
      ...sorted.slice(filesRead).map((file, k) => ({
        file, label: null, status: k === 0 ? "reading" : "waiting", parsed: null, error: null,
      })),
    ]));
    show();
    for (const file of sorted) {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("default_section", section || "General");
      fd.append("marks", marks || 1);
      fd.append("negative_marks", negative || 0);
      try {
        const parsed = await api("POST", "/api/reios/admin/questions/parse", fd);
        const questions = parsed.questions.map((q) => ({ ...q, include: !q.problems.length }));
        // One file can hold several sets ("Set 1" … "Set 10" headings): one row per set
        const groups = new Map();
        questions.forEach((q) => {
          const key = q.set || "";
          if (!groups.has(key)) groups.set(key, []);
          groups.get(key).push(q);
        });
        for (const [label, qs] of groups) {
          done.push({ file, label: label || null, status: "read", parsed: { ...parsed, questions: qs }, error: null });
        }
      } catch (err) {
        done.push({ file, label: null, status: "failed", parsed: null, error: err.message });
      }
      filesRead++;
      show();
    }
  }

  const ready = (r) => (r.parsed ? r.parsed.questions.filter((q) => q.include && !problemsOf(q).length) : []);
  const toSave = rows ? rows.filter((r) => r.status === "read" && ready(r).length) : [];

  async function saveAll() {
    const names = toSave.map((r) => r.name.trim().toLowerCase());
    if (names.some((n) => !n)) return toast("Every set needs a name", "error");
    if (new Set(names).size !== names.length) return toast("Two sets have the same name", "error");
    setSaving(true);
    let saved = 0;
    for (const r of toSave) {
      try {
        await api("POST", `/api/reios/admin/exams/${examId}/sets` + cq(), {
          name: r.name.trim(), source_filename: r.file.name,
          questions: ready(r).map((q) => ({
            section: q.section || "General", topic: q.topic || null, difficulty: q.difficulty || "medium",
            question_text: q.question_text, options: q.options, correct_options: q.correct_options,
            is_multi: q.correct_options.length > 1, explanation: q.explanation || null,
            marks: Number(q.marks) || 1, negative_marks: Number(q.negative_marks) || 0,
          })),
        });
        saved++;
        setRows((rs) => rs.map((x) => (x === r ? { ...x, status: "saved" } : x)));
      } catch (err) {
        setRows((rs) => rs.map((x) => (x === r ? { ...x, status: "failed", error: err.message } : x)));
      }
    }
    setSaving(false);
    if (saved) toast(`${saved} set${saved > 1 ? "s" : ""} added`, "success");
    onSaved();
    if (saved === toSave.length) onClose();
  }

  const updateRow = (i, patch) => setRows((rs) => rs.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  const reading = rows?.some((r) => r.status === "reading" || r.status === "waiting");

  return (
    <>
      <Modal
        title="Upload question sets"
        wide
        onClose={onClose}
        actions={rows ? (
          <>
            <span className="muted small grow">
              {toSave.length} set{toSave.length === 1 ? "" : "s"} ready ·{" "}
              {toSave.reduce((n, r) => n + ready(r).length, 0)} questions
            </span>
            <button className="btn" onClick={() => setRows(null)} disabled={saving || reading}>← Choose other files</button>
            <button className="btn primary" onClick={saveAll} disabled={saving || reading || !toSave.length}>
              {saving ? <><Spinner /> Saving</> : `Save ${toSave.length} set${toSave.length === 1 ? "" : "s"}`}
            </button>
          </>
        ) : (
          <>
            <button className="btn" onClick={onClose}>Cancel</button>
            <button className="btn primary" onClick={readAll} disabled={!files.length}>
              Read {files.length || ""} file{files.length === 1 ? "" : "s"}
            </button>
          </>
        )}
      >
        {!rows ? (
          <>
            <Field label="Set files" hint="One file with every set inside it, or one file per set (select them all at once).">
              <input type="file" multiple accept={ACCEPT} onChange={(e) => setFiles([...e.target.files])} />
            </Field>
            <div className="banner" style={{ marginBottom: 14, flexDirection: "column", gap: 4 }}>
              <span className="small">
                <strong>All sets in one file:</strong> start each set with a heading such as
                <code>Set 1</code> or <code>Section: General Knowledge – Set 1</code>. Reios splits
                them into Set 1, Set 2, … automatically.
              </span>
              <span className="small">
                <strong>One file per set:</strong> they're named Set 1, Set 2, … in file-name order (a
                number already in the name, like "Set 7.docx", is kept).
              </span>
            </div>
            <div className="form-grid">
              <Field label="Section, if a file doesn't name one">
                <input value={section} onChange={(e) => setSection(e.target.value)} />
              </Field>
              <Field label="Marks per question">
                <input type="number" step="0.25" min="0.25" value={marks} onChange={(e) => setMarks(e.target.value)} />
              </Field>
              <Field label="Negative marks">
                <input type="number" step="0.25" min="0" value={negative} onChange={(e) => setNegative(e.target.value)} />
              </Field>
            </div>
          </>
        ) : (
          <div className="table-wrap compact">
            <table>
              <thead>
                <tr><th style={{ width: 170 }}>Set name</th><th>File</th><th className="num">Questions</th><th>Status</th><th /></tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const total = r.parsed?.questions.length || 0;
                  const ok = ready(r).length;
                  return (
                    <tr key={i}>
                      <td>
                        <input value={r.name} disabled={r.status === "saved"}
                               style={{ padding: "4px 8px", fontSize: 13 }}
                               onChange={(e) => updateRow(i, { name: e.target.value })} />
                      </td>
                      <td className="small">{r.file.name}</td>
                      <td className="num">{r.parsed ? `${ok} / ${total}` : "—"}</td>
                      <td>
                        {r.status === "waiting" && <span className="muted small">Waiting</span>}
                        {r.status === "reading" && <span className="small"><Spinner /> Reading</span>}
                        {r.status === "saved" && <Badge color="green">Saved</Badge>}
                        {r.status === "failed" && <span className="small" style={{ color: "var(--danger)" }}>{r.error}</span>}
                        {r.status === "read" && (ok === total && total > 0
                          ? <Badge color="green">Ready</Badge>
                          : <Badge color="amber">{total - ok} need fixing</Badge>)}
                      </td>
                      <td>
                        {r.status === "read" && (
                          <button className="btn sm" onClick={() => setReviewing(i)}>Review</button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Modal>

      {reviewing !== null && rows?.[reviewing] && (
        <Modal title={`${rows[reviewing].name} · ${rows[reviewing].file.name}`} wide
               onClose={() => setReviewing(null)}
               actions={<button className="btn primary" onClick={() => setReviewing(null)}>Done</button>}>
          {rows[reviewing].parsed.warnings.map((w, k) => (
            <div key={k} className="banner warn" style={{ marginBottom: 10 }}>{w}</div>
          ))}
          <ReviewQuestions
            questions={rows[reviewing].parsed.questions}
            onUpdate={(qi, patch) => setRows((rs) => rs.map((r, k) => (k !== reviewing ? r : {
              ...r, parsed: { ...r.parsed, questions: r.parsed.questions.map((q, j) => (j === qi ? { ...q, ...patch } : q)) },
            })))}
          />
        </Modal>
      )}
    </>
  );
}
