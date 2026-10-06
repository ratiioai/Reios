import { useState } from "react";
import { api } from "../../lib/api.js";
import { LANG_LABELS, fromLocalInput, toLocalInput } from "../../lib/format.js";
import { Field, Modal, ModalButton, useToast } from "../../components/ui.jsx";
import { nullIfBlank } from "./context.jsx";

export const EXAM_TYPES = [
  { id: "mcq", label: "MCQ only", hint: "Aptitude, GK, subject tests — any multiple-choice paper" },
  { id: "coding", label: "Coding only", hint: "Programming problems with hidden test cases" },
  { id: "mixed", label: "MCQ + Coding", hint: "Placement-style papers with both" },
];

/** Shared by "create exam" and the builder's settings dialog. */
export default function ExamSettings({ meta, exam, cq, onClose, onSaved }) {
  const toast = useToast();
  const now = Date.now();
  const e = exam || {
    duration_minutes: 60,
    start_at: new Date(now + 3600e3),
    end_at: new Date(now + 3 * 3600e3),
    shuffle_questions: true, shuffle_options: true, negative_marking: false,
    require_fullscreen: true, block_copy_paste: true, max_violations: 3,
    show_results: true, show_answers: false, pass_percentage: 40,
    allowed_languages: null, exam_type: "mcq", show_leaderboard: true,
  };

  const [f, setF] = useState({
    title: e.title || "", description: e.description || "", instructions: e.instructions || "",
    start_at: toLocalInput(e.start_at), end_at: toLocalInput(e.end_at),
    duration_minutes: e.duration_minutes, pass_percentage: e.pass_percentage,
    branch_filter: e.branch_filter || "", batch_filter: e.batch_filter || "",
    section_filter: e.section_filter || "",
    shuffle_questions: e.shuffle_questions, shuffle_options: e.shuffle_options,
    negative_marking: e.negative_marking, require_fullscreen: e.require_fullscreen,
    block_copy_paste: e.block_copy_paste, max_violations: e.max_violations,
    show_results: e.show_results, show_answers: e.show_answers,
    exam_type: e.exam_type || "mixed", show_leaderboard: !!e.show_leaderboard,
  });
  const [langs, setLangs] = useState(() => new Set(e.allowed_languages || meta.languages));

  const set = (k) => (ev) =>
    setF((v) => ({ ...v, [k]: ev.target.type === "checkbox" ? ev.target.checked : ev.target.value }));

  const Check = ({ name, children }) => (
    <label className="check">
      <input type="checkbox" checked={f[name]} onChange={set(name)} /> {children}
    </label>
  );

  async function save() {
    const allowed = [...langs];
    if (f.exam_type !== "mcq" && !allowed.length) { toast("Allow at least one language", "error"); return; }
    const body = {
      title: f.title, description: nullIfBlank(f.description), instructions: nullIfBlank(f.instructions),
      start_at: fromLocalInput(f.start_at), end_at: fromLocalInput(f.end_at),
      duration_minutes: Number(f.duration_minutes),
      branch_filter: nullIfBlank(f.branch_filter), batch_filter: nullIfBlank(f.batch_filter),
      section_filter: nullIfBlank(f.section_filter),
      shuffle_questions: f.shuffle_questions, shuffle_options: f.shuffle_options,
      negative_marking: f.negative_marking, require_fullscreen: f.require_fullscreen,
      block_copy_paste: f.block_copy_paste, max_violations: Number(f.max_violations),
      show_results: f.show_results, show_answers: f.show_answers,
      show_leaderboard: f.show_leaderboard, exam_type: f.exam_type,
      pass_percentage: Number(f.pass_percentage),
      // null means "every language the platform supports"
      allowed_languages: allowed.length === meta.languages.length ? null : allowed,
    };
    try {
      const saved = exam
        ? await api("PUT", `/api/reios/admin/exams/${exam.id}` + cq(), body)
        : await api("POST", "/api/reios/admin/exams" + cq(), body);
      toast("Saved", "success");
      onSaved(saved);
    } catch (err) { toast(err.message, "error"); }
  }

  return (
    <Modal
      title={exam ? "Exam settings" : "Create exam"}
      wide
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <ModalButton cls="primary" onClick={save}>
            {exam ? "Save" : "Create & add questions"}
          </ModalButton>
        </>
      }
    >
      <label>Exam type</label>
      <div className="grid cols-3" style={{ gap: 10, marginBottom: 16 }}>
        {EXAM_TYPES.map((t) => (
          <label key={t.id} className="card pad-sm" style={{
            margin: 0, cursor: "pointer",
            borderColor: f.exam_type === t.id ? "var(--primary)" : undefined,
            background: f.exam_type === t.id ? "var(--primary-soft)" : undefined,
          }}>
            <span className="row tight" style={{ color: "var(--text)", fontSize: 14 }}>
              <input type="radio" name="exam_type" checked={f.exam_type === t.id}
                     onChange={() => setF((v) => ({ ...v, exam_type: t.id }))} />
              <strong>{t.label}</strong>
            </span>
            <span className="small muted" style={{ display: "block", fontWeight: 500, marginTop: 4 }}>{t.hint}</span>
          </label>
        ))}
      </div>

      <Field label="Title *">
        <input value={f.title} onChange={set("title")} placeholder="e.g. TCS NQT Mock Test 1" />
      </Field>
      <Field label="Description">
        <input value={f.description} onChange={set("description")} />
      </Field>

      <div className="form-grid">
        <Field label="Opens at *">
          <input type="datetime-local" value={f.start_at} onChange={set("start_at")} />
        </Field>
        <Field label="Closes at *">
          <input type="datetime-local" value={f.end_at} onChange={set("end_at")} />
        </Field>
        <Field label="Duration (minutes) *">
          <input type="number" min="1" value={f.duration_minutes} onChange={set("duration_minutes")} />
        </Field>
        <Field label="Pass percentage">
          <input type="number" min="0" max="100" value={f.pass_percentage}
                 onChange={set("pass_percentage")} />
        </Field>
      </div>
      <p className="muted small" style={{ marginTop: -6 }}>
        Students can start any time between "opens" and "closes". Each student gets the full
        duration, but never past the closing time.
      </p>

      <h3>Who can take it <span className="muted small">(comma-separated, blank = all students)</span></h3>
      <div className="form-grid">
        <Field label="Branches">
          <input value={f.branch_filter} onChange={set("branch_filter")} placeholder="CSE, ECE" />
        </Field>
        <Field label="Batch years">
          <input value={f.batch_filter} onChange={set("batch_filter")} placeholder="2025" />
        </Field>
        <Field label="Sections">
          <input value={f.section_filter} onChange={set("section_filter")} placeholder="A, B" />
        </Field>
      </div>

      <h3>Anti-cheat</h3>
      <Check name="require_fullscreen">Require fullscreen (leaving fullscreen is a violation)</Check>
      <Check name="block_copy_paste">Block copy, paste, right-click and developer tools</Check>
      <Check name="shuffle_questions">Shuffle question order per student</Check>
      <Check name="shuffle_options">Shuffle MCQ options per student</Check>
      <Field label="Auto-submit after this many violations" style={{ maxWidth: 280, marginTop: 8 }}>
        <input type="number" min="1" max="50" value={f.max_violations} onChange={set("max_violations")} />
      </Field>

      <h3>Scoring &amp; results</h3>
      <Check name="negative_marking">Negative marking for wrong MCQ answers</Check>
      <Check name="show_results">Show score to students after they submit</Check>
      <Check name="show_answers">Show correct answers and explanations in the review</Check>
      <Check name="show_leaderboard">Show students a leaderboard (top 10 and their own rank) as soon as they submit</Check>

      {f.exam_type !== "mcq" && (<>
      <h3>Coding languages allowed</h3>
      <div className="pill-list">
        {meta.languages.map((l) => (
          <label key={l} className="check" style={{ marginRight: 10 }}>
            <input type="checkbox" checked={langs.has(l)} onChange={(ev) =>
              setLangs((s) => {
                const next = new Set(s);
                if (ev.target.checked) next.add(l); else next.delete(l);
                return next;
              })} />
            {LANG_LABELS[l] || l}
          </label>
        ))}
      </div>
      </>)}

      <Field label="Instructions shown before the exam (Markdown)" style={{ marginTop: 12 }}>
        <textarea rows={5} value={f.instructions} onChange={set("instructions")} />
      </Field>
    </Modal>
  );
}
