import { useMemo, useState } from "react";
import { api, downloadCSV } from "../../lib/api.js";
import { Badge, Field, Modal, Spinner, useToast } from "../../components/ui.jsx";

const LETTER = (i) => String.fromCharCode(65 + i);
const ACCEPT = ".docx,.pdf,.csv,.xlsx,.txt";
const TEMPLATE_COLS = ["section", "topic", "difficulty", "question", "option_a", "option_b",
  "option_c", "option_d", "correct", "marks", "negative_marks", "explanation"];

/**
 * Upload a Word / PDF / Excel / CSV file, review what was read, fix answers, then save.
 * `onSave(name, questions)` decides where they go (the bank, or a new set on an exam).
 */
export default function QuestionImport({ title, askName = false, defaultName = "", onSave, onClose }) {
  const toast = useToast();
  const [file, setFile] = useState(null);
  const [name, setName] = useState(defaultName);
  const [section, setSection] = useState("General");
  const [marks, setMarks] = useState(1);
  const [negative, setNegative] = useState(0);
  const [parsing, setParsing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [parsed, setParsed] = useState(null); // {questions, warnings, filename}

  async function parse() {
    if (!file) return toast("Choose a file first", "error");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("default_section", section || "General");
    fd.append("marks", marks || 1);
    fd.append("negative_marks", negative || 0);
    setParsing(true);
    try {
      const r = await api("POST", "/api/reios/admin/questions/parse", fd);
      setParsed({ ...r, questions: r.questions.map((q) => ({ ...q, include: !q.problems.length })) });
      if (!name && askName) setName(file.name.replace(/\.[^.]+$/, ""));
    } catch (err) {
      toast(err.message, "error", 6000);
    } finally {
      setParsing(false);
    }
  }

  const update = (i, patch) =>
    setParsed((p) => ({ ...p, questions: p.questions.map((q, k) => (k === i ? { ...q, ...patch } : q)) }));

  const chosen = useMemo(
    () => (parsed ? parsed.questions.filter((q) => q.include && !problemsOf(q).length) : []),
    [parsed]
  );

  async function save() {
    if (askName && !name.trim()) return toast("Give the set a name", "error");
    if (!chosen.length) return toast("No complete questions selected", "error");
    setSaving(true);
    try {
      await onSave(name.trim(), chosen.map((q) => ({
        section: q.section || "General", topic: q.topic || null, difficulty: q.difficulty || "medium",
        question_text: q.question_text, options: q.options, correct_options: q.correct_options,
        is_multi: q.correct_options.length > 1, explanation: q.explanation || null,
        marks: Number(q.marks) || 1, negative_marks: Number(q.negative_marks) || 0,
      })), parsed.filename);
    } catch (err) {
      toast(err.message, "error", 6000);
      setSaving(false);
    }
  }

  const footer = parsed ? (
    <>
      <span className="muted small grow">
        {chosen.length} of {parsed.questions.length} questions will be saved
      </span>
      <button className="btn" onClick={() => setParsed(null)} disabled={saving}>← Choose another file</button>
      <button className="btn primary" onClick={save} disabled={saving || !chosen.length}>
        {saving ? <><Spinner /> Saving</> : `Save ${chosen.length} question${chosen.length === 1 ? "" : "s"}`}
      </button>
    </>
  ) : (
    <>
      <button className="btn" onClick={onClose}>Cancel</button>
      <button className="btn primary" onClick={parse} disabled={parsing || !file}>
        {parsing ? <><Spinner /> Reading file</> : "Read questions"}
      </button>
    </>
  );

  return (
    <Modal title={title} wide onClose={onClose} actions={footer}>
      {!parsed ? (
        <>
          {askName && (
            <Field label="Set name *" hint="Students see questions only; the name is for you (e.g. Set 1, Set A).">
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Set 1" />
            </Field>
          )}
          <Field label="File" hint="Word (.docx), PDF, Excel (.xlsx), CSV or plain text">
            <input type="file" accept={ACCEPT} onChange={(e) => setFile(e.target.files[0] || null)} />
          </Field>
          <div className="form-grid">
            <Field label="Section, if the file doesn't name one">
              <input value={section} onChange={(e) => setSection(e.target.value)} placeholder="General Knowledge" />
            </Field>
            <Field label="Marks per question">
              <input type="number" step="0.25" min="0.25" value={marks} onChange={(e) => setMarks(e.target.value)} />
            </Field>
            <Field label="Negative marks (if the exam uses them)">
              <input type="number" step="0.25" min="0" value={negative} onChange={(e) => setNegative(e.target.value)} />
            </Field>
          </div>

          <div className="banner" style={{ flexDirection: "column", gap: 6 }}>
            <h3>How to lay out a Word or PDF file</h3>
            <pre style={{ margin: 0, background: "transparent", border: 0, padding: 0 }}>{`Section: General Knowledge        (optional, applies to the questions below it)
1. Which planet is the Red Planet?
A) Venus
B) Mars
C) Jupiter
Answer: B                          (or "Ans: (b)", or put * after the right option)
Explanation: ...                   (optional)`}</pre>
            <span className="small muted">
              Word's automatic numbering works too, and so does an "Answer Key" list at the end
              (1. B  2. C …). Scanned PDFs (photos of paper) can't be read; upload the original file.
            </span>
          </div>
          <button className="btn sm" style={{ marginTop: 10 }} onClick={() => downloadCSV("mcq_template.csv", TEMPLATE_COLS, [
            ["General Knowledge", "Space", "easy", "Which planet is the Red Planet?", "Venus", "Mars", "Jupiter", "Saturn", "B", "1", "0.25", ""],
            ["Technical", "OOP", "easy", "Which of these are OOP principles?", "Encapsulation", "Compilation", "Inheritance", "Recursion", "A,C", "2", "0", ""],
          ])}>Download Excel/CSV template</button>
        </>
      ) : (
        <>
          {parsed.warnings.map((w, i) => (
            <div key={i} className="banner warn" style={{ marginBottom: 10 }}>{w}</div>
          ))}
          {askName && (
            <Field label="Set name *">
              <input value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
          )}
          <p className="muted small">
            Read <strong>{parsed.questions.length}</strong> questions from {parsed.filename}. Check
            the answers: click an option to mark it correct. Questions with problems are left
            unticked until you fix them.
          </p>
          <ReviewQuestions questions={parsed.questions} onUpdate={update} />
        </>
      )}
    </Modal>
  );
}

/** Re-check a question after the admin edits it in the review list. */
export function problemsOf(q) {
  const out = [];
  if (!q.question_text.trim()) out.push("Question text is empty");
  if (q.options.length < 2) out.push("Needs at least 2 options");
  if (!q.correct_options.length) out.push("Pick the correct answer");
  return out;
}

/** Parsed questions with tick-to-include and click-to-mark-correct. */
export function ReviewQuestions({ questions, onUpdate }) {
  const parsed = { questions };
  const update = onUpdate;
  return (
    <>
            {parsed.questions.map((q, i) => {
              const problems = problemsOf(q);
              return (
                <div key={i} className="card pad-sm" style={{
                  marginBottom: 8, opacity: q.include ? 1 : 0.6,
                  borderColor: problems.length ? "var(--danger)" : undefined,
                }}>
                  <div className="row between" style={{ marginBottom: 6 }}>
                    <label className="check" style={{ margin: 0 }}>
                      <input type="checkbox" checked={q.include} disabled={!!problems.length}
                             onChange={(e) => update(i, { include: e.target.checked })} />
                      <strong>Q{i + 1}</strong>
                    </label>
                    <div className="row tight">
                      <input value={q.section} onChange={(e) => update(i, { section: e.target.value })}
                             style={{ width: 200, padding: "4px 8px", fontSize: 12.5 }} title="Section" />
                      {q.is_multi && <Badge color="blue">Multiple correct</Badge>}
                    </div>
                  </div>
                  <textarea rows={2} value={q.question_text}
                            onChange={(e) => update(i, { question_text: e.target.value })} />
                  <div style={{ marginTop: 6 }}>
                    {q.options.map((o, oi) => {
                      const ok = q.correct_options.includes(oi);
                      return (
                        <button key={oi} type="button" className="btn sm" title="Click to mark correct"
                                style={{
                                  margin: "0 6px 6px 0", whiteSpace: "normal", textAlign: "left",
                                  ...(ok ? { background: "var(--success-soft)", borderColor: "var(--success)", color: "var(--success)" } : {}),
                                }}
                                onClick={(e) => {
                                  const multi = e.shiftKey || e.ctrlKey || e.metaKey || q.is_multi;
                                  let next = multi
                                    ? (ok ? q.correct_options.filter((x) => x !== oi) : [...q.correct_options, oi])
                                    : [oi];
                                  next = [...new Set(next)].sort((a, b) => a - b);
                                  const fixed = problemsOf({ ...q, correct_options: next }).length === 0;
                                  update(i, { correct_options: next, is_multi: next.length > 1,
                                              include: fixed ? true : q.include });
                                }}>
                          {ok && "✓ "}<strong>{LETTER(oi)}.</strong> {o}
                        </button>
                      );
                    })}
                  </div>
                  {problems.length > 0 && (
                    <div className="small" style={{ color: "var(--danger)", fontWeight: 550 }}>
                      {problems.join(" · ")}
                    </div>
                  )}
                  {q.explanation && <div className="small muted">Explanation: {q.explanation}</div>}
                </div>
              );
            })}
            <p className="muted small">Tip: hold Ctrl (or Shift) while clicking to mark more than one correct option.</p>
    </>
  );
}
