import { useCallback, useEffect, useState } from "react";
import { api, qs } from "../../lib/api.js";
import {
  Badge, Field, Loading, Modal, ModalButton, useConfirm, useToast,
} from "../../components/ui.jsx";
import { nullIfBlank, useAdmin } from "./context.jsx";
import { Pager } from "./shared.jsx";
import QuestionImport from "./QuestionImport.jsx";

const PAGE_SIZE = 50;
const LETTER = (i) => String.fromCharCode(65 + i);

export default function Mcqs() {
  const { isSuper } = useAdmin();
  const toast = useToast();
  const confirm = useConfirm();

  const [meta, setMeta] = useState(null);
  const [filters, setFilters] = useState({ q: "", section: "", difficulty: "", source: "all", page: 1 });
  const [draft, setDraft] = useState({ q: "", section: "", difficulty: "", source: "all" });
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null);   // {q, readOnly}
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    api("GET", "/api/reios/admin/meta").then(setMeta).catch((e) => toast(e.message, "error"));
  }, [toast]);

  const load = useCallback(async () => {
    setData(null);
    try {
      setData(await api("GET", "/api/reios/admin/mcqs" + qs({ ...filters, page_size: PAGE_SIZE })));
    } catch (err) {
      toast(err.message, "error", 6000);
      setData({ items: [], total: 0, page: 1 });
    }
  }, [filters, toast]);

  useEffect(() => { load(); }, [load]);

  const canEdit = (q) => isSuper || !q.is_global;
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  async function remove(id) {
    const ok = await confirm(
      "Delete question",
      "Delete this question? If it's used in an exam it will be hidden from the bank instead.",
      "Delete", true
    );
    if (!ok) return;
    try {
      await api("DELETE", `/api/reios/admin/mcqs/${id}`);
      toast("Deleted", "success");
      load();
    } catch (err) { toast(err.message, "error"); }
  }

  if (!meta) return <Loading />;

  return (
    <>
      <div className="row between" style={{ marginBottom: 6 }}>
        <div className="page-head" style={{ margin: 0 }}>
          <h1>{isSuper ? "Global MCQ bank" : "MCQ questions"}</h1>
          <p className="lede">
            {isSuper
              ? "Questions here are shared with every college."
              : "Your college's questions plus the shared global bank. Global questions can be used in exams but only edited by the super admin."}
          </p>
        </div>
        <div className="row tight">
          <button className="btn" onClick={() => setImporting(true)}>Import Word / PDF / Excel</button>
          <button className="btn primary" onClick={() => setEditing({ q: null })}>+ Add MCQ</button>
        </div>
      </div>

      <div className="toolbar">
        <input placeholder="Search question text" value={draft.q}
               onChange={(e) => setDraft((d) => ({ ...d, q: e.target.value }))}
               onKeyDown={(e) => e.key === "Enter" && setFilters({ ...draft, page: 1 })} />
        <select value={draft.section} onChange={(e) => setDraft((d) => ({ ...d, section: e.target.value }))}>
          <option value="">All sections</option>
          {meta.sections.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={draft.difficulty} onChange={(e) => setDraft((d) => ({ ...d, difficulty: e.target.value }))}>
          <option value="">Any difficulty</option>
          {meta.difficulties.map((d) => <option key={d}>{d}</option>)}
        </select>
        {!isSuper && (
          <select value={draft.source} onChange={(e) => setDraft((d) => ({ ...d, source: e.target.value }))}>
            <option value="all">Own + global</option>
            <option value="own">Own only</option>
            <option value="global">Global only</option>
          </select>
        )}
        <button className="btn" onClick={() => setFilters({ ...draft, page: 1 })}>Filter</button>
      </div>

      {!data ? <Loading /> : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Question</th><th>Section</th><th>Level</th><th className="num">Marks</th><th /></tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr><td colSpan={5} className="empty">No questions yet</td></tr>
                ) : data.items.map((q) => (
                  <tr key={q.id}>
                    <td style={{ maxWidth: 560 }}>
                      {q.question_text.slice(0, 220)}{q.question_text.length > 220 ? "…" : ""}
                      <div className="muted small">
                        Answer: {q.correct_options.map(LETTER).join(", ")}
                        {q.is_multi && " · multiple correct"}
                        {q.is_global && !isSuper && <> · <Badge color="blue">Global</Badge></>}
                      </div>
                    </td>
                    <td>{q.section}{q.topic && <div className="muted small">{q.topic}</div>}</td>
                    <td>{q.difficulty}</td>
                    <td className="num">+{q.marks}{q.negative_marks ? ` / −${q.negative_marks}` : ""}</td>
                    <td>
                      <div className="row tight">
                        {canEdit(q) ? (
                          <>
                            <button className="btn sm" onClick={() => setEditing({ q })}>Edit</button>
                            <button className="btn sm danger" onClick={() => remove(q.id)}>Delete</button>
                          </>
                        ) : (
                          <button className="btn sm" onClick={() => setEditing({ q, readOnly: true })}>View</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={data.page} pages={pages} total={data.total} noun="questions"
                 onPage={(p) => setFilters((f) => ({ ...f, page: p }))} />
        </>
      )}

      {editing && (
        <McqForm
          meta={meta}
          initial={editing.q}
          readOnly={editing.readOnly}
          defaultSection={filters.section || meta.sections[0]}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}

      {importing && (
        <QuestionImport
          title="Import questions into the bank"
          onClose={() => setImporting(false)}
          onSave={async (_name, questions) => {
            const r = await api("POST", "/api/reios/admin/mcqs/bulk", { questions });
            toast(`${r.created} questions added`, "success");
            setImporting(false);
            load();
          }}
        />
      )}
    </>
  );
}

function McqForm({ meta, initial, readOnly, defaultSection, onClose, onSaved }) {
  const toast = useToast();
  const q = initial || {
    section: defaultSection, difficulty: "medium", options: ["", "", "", ""],
    correct_options: [0], is_multi: false, marks: 1, negative_marks: 0,
  };

  const [f, setF] = useState({
    section: q.section, topic: q.topic || "", difficulty: q.difficulty,
    marks: q.marks, negative_marks: q.negative_marks,
    question_text: q.question_text || "", explanation: q.explanation || "",
    is_multi: q.is_multi,
  });
  const [options, setOptions] = useState(() => q.options.slice());
  const [correct, setCorrect] = useState(() => new Set(q.correct_options));

  const set = (k) => (e) =>
    setF((v) => ({ ...v, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  function setMulti(on) {
    setF((v) => ({ ...v, is_multi: on }));
    if (!on) setCorrect((c) => new Set([...c].slice(0, 1)));
  }

  function toggleCorrect(i) {
    setCorrect((c) => {
      if (!f.is_multi) return new Set([i]);
      const next = new Set(c);
      if (next.has(i)) next.delete(i); else next.add(i);
      return next;
    });
  }

  function removeOption(i) {
    setOptions((o) => o.filter((_, idx) => idx !== i));
    setCorrect((c) => new Set([...c].filter((x) => x !== i).map((x) => (x > i ? x - 1 : x))));
  }

  async function save() {
    const body = {
      section: f.section.trim(), topic: nullIfBlank(f.topic), difficulty: f.difficulty,
      question_text: f.question_text, options,
      correct_options: [...correct].sort((a, b) => a - b),
      is_multi: f.is_multi, explanation: nullIfBlank(f.explanation),
      marks: Number(f.marks), negative_marks: Number(f.negative_marks || 0),
    };
    try {
      if (q.id) await api("PUT", `/api/reios/admin/mcqs/${q.id}`, body);
      else await api("POST", "/api/reios/admin/mcqs", body);
      toast("Saved", "success");
      onSaved();
    } catch (err) { toast(err.message, "error"); }
  }

  return (
    <Modal
      title={readOnly ? "Global question" : q.id ? "Edit MCQ" : "Add MCQ"}
      wide
      onClose={onClose}
      actions={readOnly ? (
        <button className="btn primary" onClick={onClose}>Close</button>
      ) : (
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <ModalButton cls="primary" onClick={save}>Save</ModalButton>
        </>
      )}
    >
      <fieldset disabled={readOnly} style={{ border: 0, padding: 0, margin: 0 }}>
        <div className="form-grid">
          <Field label="Section *">
            <input list="sections" value={f.section} onChange={set("section")} />
            <datalist id="sections">
              {meta.sections.map((s) => <option key={s} value={s} />)}
            </datalist>
          </Field>
          <Field label="Topic">
            <input value={f.topic} onChange={set("topic")} placeholder="e.g. Percentages, Arrays" />
          </Field>
          <Field label="Difficulty">
            <select value={f.difficulty} onChange={set("difficulty")}>
              {meta.difficulties.map((d) => <option key={d}>{d}</option>)}
            </select>
          </Field>
          <Field label="Marks">
            <input type="number" step="0.25" min="0.25" value={f.marks} onChange={set("marks")} />
          </Field>
          <Field label="Negative marks (if exam uses negative marking)">
            <input type="number" step="0.25" min="0" value={f.negative_marks}
                   onChange={set("negative_marks")} />
          </Field>
        </div>

        <Field label="Question * (Markdown supported)">
          <textarea rows={4} value={f.question_text} onChange={set("question_text")} />
        </Field>

        <label className="check">
          <input type="checkbox" checked={f.is_multi} onChange={(e) => setMulti(e.target.checked)} />
          More than one correct option
        </label>

        <label>Options (tick the correct one{f.is_multi ? "s" : ""})</label>
        {options.map((o, i) => (
          <div key={i} className="row" style={{ marginBottom: 6, flexWrap: "nowrap" }}>
            <input type={f.is_multi ? "checkbox" : "radio"} name="correct"
                   checked={correct.has(i)} onChange={() => toggleCorrect(i)} />
            <strong style={{ width: 18 }}>{LETTER(i)}</strong>
            <input value={o} onChange={(e) =>
              setOptions((os) => os.map((x, idx) => (idx === i ? e.target.value : x)))} />
            <button className="btn sm ghost" type="button" disabled={options.length <= 2}
                    onClick={() => removeOption(i)}>✕</button>
          </div>
        ))}
        {options.length < 8 && (
          <button className="btn sm" type="button" onClick={() => setOptions((o) => [...o, ""])}>
            + Option
          </button>
        )}

        <Field label="Explanation (shown in review if enabled)" style={{ marginTop: 12 }}>
          <textarea rows={2} value={f.explanation} onChange={set("explanation")} />
        </Field>
      </fieldset>
    </Modal>
  );
}
