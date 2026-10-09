import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api.js";
import { fmtDate } from "../../lib/format.js";
import {
  Badge, Field, Loading, Modal, ModalButton, useConfirm, useToast,
} from "../../components/ui.jsx";
import { useAdmin, windowBadgeProps } from "./context.jsx";
import ExamSettings, { EXAM_TYPES } from "./ExamSettings.jsx";
import ExamSets from "./ExamSets.jsx";

export default function ExamBuilder() {
  const { examId } = useParams();
  const { collegeId, cq } = useAdmin();
  const toast = useToast();
  const confirm = useConfirm();
  const navigate = useNavigate();

  const [meta, setMeta] = useState(null);
  const [exam, setExam] = useState(null);
  const [items, setItems] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [settings, setSettings] = useState(false);
  const [picker, setPicker] = useState(null);   // "mcq" | "coding" | "random"

  // quiet: refresh counts after a set changes without discarding unsaved edits to the question list
  const load = useCallback(async (quiet = false) => {
    if (!quiet) setExam(null);
    try {
      const e = await api("GET", `/api/reios/admin/exams/${examId}` + cq());
      setExam(e);
      if (quiet) return;
      setItems(e.items.map((i) => ({
        item_type: i.item_type, question_id: i.question_id, section: i.section,
        marks: i.marks, title: i.title, difficulty: i.difficulty,
        effective_marks: i.effective_marks,
      })));
      setDirty(false);
    } catch (err) {
      toast(err.message, "error", 6000);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [examId, collegeId]);

  useEffect(() => {
    load();
    api("GET", "/api/reios/admin/meta").then(setMeta).catch(() => {});
  }, [load]);

  if (!exam || !meta) return <Loading />;

  const locked = exam.attempts.in_progress + exam.attempts.submitted > 0;
  const allowMcq = exam.exam_type !== "coding";
  const allowCoding = exam.exam_type !== "mcq";
  const typeLabel = EXAM_TYPES.find((t) => t.id === exam.exam_type)?.label || exam.exam_type;
  const wb = windowBadgeProps(exam);
  const sections = [];
  items.forEach((i) => { if (!sections.includes(i.section)) sections.push(i.section); });
  const totalMarks = Math.round(
    items.reduce((s, i) => s + Number(i.marks || i.effective_marks || 0), 0) * 100
  ) / 100;

  /** Skips anything already in the paper, then regroups so sections stay together. */
  function addItems(newOnes) {
    let added = 0;
    const next = [...items];
    newOnes.forEach((n) => {
      if (!next.some((i) => i.item_type === n.item_type && i.question_id === n.question_id)) {
        next.push(n);
        added++;
      }
    });
    const order = [];
    next.forEach((i) => { if (!order.includes(i.section)) order.push(i.section); });
    next.sort((a, b) => order.indexOf(a.section) - order.indexOf(b.section));
    if (added) {
      setItems(next);
      setDirty(true);
      toast(`${added} added`, "success");
    } else {
      toast("Already in the exam");
    }
    setPicker(null);
  }

  function move(idx, dir) {
    let j = idx + dir;
    while (j >= 0 && j < items.length && items[j].section !== items[idx].section) j += dir;
    if (j < 0 || j >= items.length) return;
    const next = [...items];
    [next[idx], next[j]] = [next[j], next[idx]];
    setItems(next);
    setDirty(true);
  }

  async function saveItems() {
    try {
      await api("PUT", `/api/reios/admin/exams/${examId}/items` + cq(), {
        items: items.map((i) => ({
          item_type: i.item_type, question_id: i.question_id,
          section: i.section, marks: i.marks || null,
        })),
      });
      toast("Questions saved", "success");
      load();
    } catch (err) { toast(err.message, "error"); }
  }

  async function togglePublish() {
    if (dirty) return toast("Save the question list first", "error");
    try {
      await api("POST", `/api/reios/admin/exams/${examId}/publish` + cq({ publish: !exam.is_published }));
      toast(exam.is_published ? "Unpublished" : "Published. Eligible students can now see it", "success");
      load();
    } catch (err) { toast(err.message, "error"); }
  }

  async function duplicate() {
    try {
      const c = await api("POST", `/api/reios/admin/exams/${examId}/duplicate` + cq());
      toast("Copy created", "success");
      navigate(`/console/exams/${c.id}`);
    } catch (err) { toast(err.message, "error"); }
  }

  async function remove() {
    const n = exam.attempts?.submitted || 0;
    const msg = n > 0
      ? `This exam has ${n} submitted attempt${n > 1 ? "s" : ""}. Deleting it also permanently deletes ` +
        "their answers and results — download the results first if you need them. This can't be undone."
      : "Delete this exam permanently?";
    if (!(await confirm("Delete exam", msg, "Delete", true))) return;
    try {
      await api("DELETE", `/api/reios/admin/exams/${examId}` + cq({ force: true }));
      toast("Exam deleted", "success");
      navigate("/console/exams");
    } catch (err) { toast(err.message, "error"); }
  }

  const audience = [
    exam.branch_filter && "Branches " + exam.branch_filter,
    exam.batch_filter && "Batch " + exam.batch_filter,
    exam.section_filter && "Sections " + exam.section_filter,
  ].filter(Boolean).join(" · ") || "All students";

  const antiCheat = [
    exam.require_fullscreen && "Fullscreen",
    exam.block_copy_paste && "No copy/paste",
    exam.shuffle_questions && "Shuffled questions",
    exam.shuffle_options && "Shuffled options",
    `auto-submit at ${exam.max_violations} violations`,
  ].filter(Boolean).join(" · ");

  return (
    <>
      <div className="row between">
        <div>
          <Link to="/console/exams" className="small">← Exams</Link>
          <h1 style={{ marginTop: 4 }}>{exam.title} <Badge color={wb.color}>{wb.text}</Badge></h1>
        </div>
        <div className="row tight">
          <Link className="btn" to={`/console/exams/${examId}/preview`}>Preview test</Link>
          <button className="btn" onClick={() => setSettings(true)}>Settings</button>
          <button className="btn" onClick={duplicate}>Duplicate</button>
          {exam.attempts.in_progress === 0 && <button className="btn danger" onClick={remove}>Delete</button>}
          <button className={"btn" + (exam.is_published ? "" : " primary")} onClick={togglePublish}>
            {exam.is_published ? "Unpublish" : "Publish"}
          </button>
        </div>
      </div>

      <div className="card">
        <dl className="kv">
          <dt>Type</dt><dd>{typeLabel}{exam.set_count ? ` · ${exam.set_count} sets` : ""}</dd>
          <dt>Window</dt><dd>{fmtDate(exam.start_at)} → {fmtDate(exam.end_at)}</dd>
          <dt>Duration</dt><dd>{exam.duration_minutes} minutes</dd>
          <dt>Audience</dt><dd>{audience}</dd>
          <dt>Anti-cheat</dt><dd>{antiCheat}</dd>
          <dt>Scoring</dt>
          <dd>
            {exam.negative_marking ? "Negative marking on" : "No negative marking"} · pass
            at {exam.pass_percentage}%
          </dd>
        </dl>
      </div>

      <div className="card">
        <div className="row between">
          <h2 style={{ margin: 0 }}>
            {exam.set_count ? "Common questions" : "Questions"}{" "}
            <span className="muted small">
              {items.length} questions · {totalMarks} marks{exam.set_count ? " · every student gets these" : ""}
            </span>
          </h2>
          {locked ? (
            <Badge color="amber">Locked: students have started</Badge>
          ) : (
            <div className="row tight">
              {allowMcq && <button className="btn sm" onClick={() => setPicker("mcq")}>+ MCQs from bank</button>}
              {allowMcq && <button className="btn sm" onClick={() => setPicker("random")}>+ Random MCQs</button>}
              {allowCoding && <button className="btn sm" onClick={() => setPicker("coding")}>+ Coding</button>}
              <button className="btn sm primary" disabled={!dirty} onClick={saveItems}>
                Save questions
              </button>
            </div>
          )}
        </div>

        <div style={{ marginTop: 12 }}>
          {items.length === 0 ? (
            <div className="empty">
              {exam.set_count
                ? "No common questions. That's fine: each student gets only their set."
                : allowMcq && allowCoding ? "No questions yet. Add MCQs and coding problems, or upload sets below."
                : allowMcq ? "No questions yet. Add MCQs from the bank, or upload sets (Word / PDF / Excel) below."
                : "No questions yet. Add coding problems."}
            </div>
          ) : sections.map((sec) => (
            <div key={sec}>
              <h3 style={{ marginTop: 14 }}>
                {sec}{" "}
                <span className="muted small">
                  {items.filter((i) => i.section === sec).length} questions
                </span>
              </h3>
              <div className="table-wrap compact">
                <table>
                  <tbody>
                    {items.map((i, idx) => i.section !== sec ? null : (
                      <tr key={`${i.item_type}-${i.question_id}`}>
                        <td style={{ width: 70 }}>
                          <Badge color={i.item_type === "mcq" ? "" : "blue"}>
                            {i.item_type === "mcq" ? "MCQ" : "Code"}
                          </Badge>
                        </td>
                        <td>{i.title} <span className="muted small">{i.difficulty || ""}</span></td>
                        <td style={{ width: 150, whiteSpace: "nowrap" }}>
                          {locked ? (
                            <span className="muted small">{i.marks || i.effective_marks} marks</span>
                          ) : (
                            <>
                              <input type="number" step="0.25" min="0.25" style={{ width: 80 }}
                                     placeholder={i.effective_marks} value={i.marks ?? ""}
                                     title="Marks (blank = question default)"
                                     onChange={(e) => {
                                       const v = e.target.value;
                                       setItems((xs) => xs.map((x, k) =>
                                         k === idx ? { ...x, marks: v ? Number(v) : null } : x));
                                       setDirty(true);
                                     }} /> marks
                            </>
                          )}
                        </td>
                        <td style={{ width: 120, whiteSpace: "nowrap" }}>
                          {!locked && (
                            <>
                              <button className="btn sm ghost" title="Move up"
                                      onClick={() => move(idx, -1)}>↑</button>
                              <button className="btn sm ghost" title="Move down"
                                      onClick={() => move(idx, 1)}>↓</button>
                              <button className="btn sm ghost" title="Remove"
                                      onClick={() => {
                                        setItems((xs) => xs.filter((_, k) => k !== idx));
                                        setDirty(true);
                                      }}>✕</button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      </div>

      {allowMcq && <ExamSets exam={exam} cq={cq} onChanged={() => load(true)} />}

      {settings && (
        <ExamSettings meta={meta} exam={exam} cq={cq}
                      onClose={() => setSettings(false)}
                      onSaved={() => { setSettings(false); load(); }} />
      )}

      {picker === "mcq" && (
        <PickMcqs meta={meta} cq={cq} onClose={() => setPicker(null)} onAdd={addItems} />
      )}
      {picker === "coding" && (
        <PickProblems cq={cq} onClose={() => setPicker(null)} onAdd={addItems} />
      )}
      {picker === "random" && (
        <RandomMcqs meta={meta} examId={examId} cq={cq}
                    onClose={() => setPicker(null)} onAdd={addItems} />
      )}
    </>
  );
}

function PickMcqs({ meta, cq, onClose, onAdd }) {
  const toast = useToast();
  const [f, setF] = useState({ q: "", section: "", difficulty: "" });
  const [data, setData] = useState(null);
  const [picked, setPicked] = useState(() => new Set());

  const load = useCallback(async (filters) => {
    setData(null);
    try {
      setData(await api("GET", "/api/reios/admin/mcqs" + cq({ ...filters, page: 1, page_size: 100 })));
    } catch (err) { toast(err.message, "error"); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { load(f); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Modal
      title="Add MCQs"
      wide
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={() =>
            onAdd((data?.items || []).filter((q) => picked.has(q.id)).map((q) => ({
              item_type: "mcq", question_id: q.id, section: q.section, marks: null,
              title: q.question_text.slice(0, 140), difficulty: q.difficulty,
              effective_marks: q.marks,
            })))
          }>Add selected</button>
        </>
      }
    >
      <div className="toolbar">
        <input placeholder="Search" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
        <select value={f.section} onChange={(e) => setF({ ...f, section: e.target.value })}>
          <option value="">All sections</option>
          {meta.sections.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={f.difficulty} onChange={(e) => setF({ ...f, difficulty: e.target.value })}>
          <option value="">Any difficulty</option>
          {meta.difficulties.map((d) => <option key={d}>{d}</option>)}
        </select>
        <button className="btn" onClick={() => load(f)}>Search</button>
      </div>

      {!data ? <Loading /> : (
        <>
          <div className="table-wrap compact">
            <table>
              <thead>
                <tr>
                  <th>
                    <input type="checkbox"
                           checked={data.items.length > 0 && picked.size === data.items.length}
                           onChange={(e) =>
                             setPicked(e.target.checked ? new Set(data.items.map((q) => q.id)) : new Set())} />
                  </th>
                  <th>Question</th><th>Section</th><th>Level</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr><td colSpan={4} className="empty">No questions</td></tr>
                ) : data.items.map((q) => (
                  <tr key={q.id}>
                    <td>
                      <input type="checkbox" checked={picked.has(q.id)} onChange={() =>
                        setPicked((s) => {
                          const n = new Set(s);
                          if (n.has(q.id)) n.delete(q.id); else n.add(q.id);
                          return n;
                        })} />
                    </td>
                    <td>{q.question_text.slice(0, 160)}</td>
                    <td>{q.section}</td>
                    <td>{q.difficulty}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            {data.total} matching{data.total > 100 ? " (showing first 100, refine the search)" : ""}
          </p>
        </>
      )}
    </Modal>
  );
}

function PickProblems({ cq, onClose, onAdd }) {
  const toast = useToast();
  const [problems, setProblems] = useState(null);
  const [picked, setPicked] = useState(() => new Set());

  useEffect(() => {
    api("GET", "/api/reios/admin/problems" + cq())
      .then(setProblems)
      .catch((e) => { toast(e.message, "error"); setProblems([]); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Modal
      title="Add coding problems"
      wide
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={() =>
            onAdd((problems || []).filter((p) => picked.has(p.id)).map((p) => ({
              item_type: "coding", question_id: p.id, section: "Coding", marks: null,
              title: p.title, difficulty: p.difficulty, effective_marks: p.marks,
            })))
          }>Add selected</button>
        </>
      }
    >
      {!problems ? <Loading /> : (
        <div className="table-wrap compact">
          <table>
            <thead>
              <tr>
                <th /><th>Problem</th><th>Level</th>
                <th className="num">Marks</th><th className="num">Hidden tests</th>
              </tr>
            </thead>
            <tbody>
              {problems.length === 0 ? (
                <tr><td colSpan={5} className="empty">
                  No coding problems. Add some under Coding Problems.
                </td></tr>
              ) : problems.map((p) => (
                <tr key={p.id}>
                  <td>
                    <input type="checkbox" checked={picked.has(p.id)} onChange={() =>
                      setPicked((s) => {
                        const n = new Set(s);
                        if (n.has(p.id)) n.delete(p.id); else n.add(p.id);
                        return n;
                      })} />
                  </td>
                  <td>{p.title}</td>
                  <td>{p.difficulty}</td>
                  <td className="num">{p.marks}</td>
                  <td className="num">{p.hidden_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}

function RandomMcqs({ meta, examId, cq, onClose, onAdd }) {
  const toast = useToast();
  const pickable = meta.sections.filter((s) => s !== "Coding");
  const [f, setF] = useState({ section: pickable[0], count: 10, difficulty: "" });

  async function add() {
    try {
      const qs_ = await api("POST", `/api/reios/admin/exams/${examId}/random-mcqs` + cq(), {
        section: f.section, count: Number(f.count), difficulty: f.difficulty || null,
      });
      if (!qs_.length) { toast("No matching questions in the bank", "error"); return; }
      onAdd(qs_.map((q) => ({
        item_type: "mcq", question_id: q.id, section: q.section, marks: null,
        title: q.question_text.slice(0, 140), difficulty: q.difficulty, effective_marks: q.marks,
      })));
    } catch (err) { toast(err.message, "error"); }
  }

  return (
    <Modal
      title="Add random MCQs from the bank"
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <ModalButton cls="primary" onClick={add}>Add</ModalButton>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Section">
          <select value={f.section} onChange={(e) => setF({ ...f, section: e.target.value })}>
            {pickable.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="How many">
          <input type="number" min="1" value={f.count}
                 onChange={(e) => setF({ ...f, count: e.target.value })} />
        </Field>
        <Field label="Difficulty">
          <select value={f.difficulty} onChange={(e) => setF({ ...f, difficulty: e.target.value })}>
            <option value="">Any</option>
            {meta.difficulties.map((d) => <option key={d}>{d}</option>)}
          </select>
        </Field>
      </div>
    </Modal>
  );
}
