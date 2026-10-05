import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/api.js";
import { Badge, Loading, Markdown, useToast } from "../../components/ui.jsx";
import { useAdmin } from "./context.jsx";

/** The paper exactly as a student sees it, per set. Nothing is recorded. */
export default function Preview() {
  const { examId } = useParams();
  const { collegeId, cq } = useAdmin();
  const toast = useToast();

  const [setId, setSetId] = useState(null);
  const [paper, setPaper] = useState(null);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState({});        // item_id -> [option ids]
  const [showAnswers, setShowAnswers] = useState(false);

  const load = useCallback(async (sid) => {
    try {
      const p = await api("GET", `/api/reios/admin/exams/${examId}/preview` + cq(sid ? { set_id: sid } : {}));
      setPaper(p);
      setSetId(p.set_id);
      setIndex(0);
      setPicked({});
    } catch (err) { toast(err.message, "error", 6000); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [examId, collegeId]);

  useEffect(() => { load(null); }, [load]);

  if (!paper) return <Loading />;
  const item = paper.items[index];

  function choose(it, optId) {
    setPicked((p) => {
      const cur = p[it.item_id] || [];
      const next = it.is_multi ? (cur.includes(optId) ? cur.filter((x) => x !== optId) : [...cur, optId]) : [optId];
      return { ...p, [it.item_id]: next };
    });
  }

  const score = paper.items.reduce((sum, it) => {
    if (it.type !== "mcq") return sum;
    const sel = [...(picked[it.item_id] || [])].sort().join(",");
    if (!sel) return sum;
    return sum + (sel === [...it.correct_options].sort().join(",") ? it.marks : -(it.negative_marks || 0));
  }, 0);

  return (
    <>
      <div className="row between" style={{ marginBottom: 12 }}>
        <div>
          <Link to={`/console/exams/${examId}`} className="small">← Back to exam</Link>
          <h1 style={{ marginTop: 4 }}>{paper.exam.title} · Preview</h1>
        </div>
        <div className="row tight">
          {paper.sets.length > 0 && (
            <div className="segment" role="tablist" aria-label="Set">
              {paper.sets.map((s) => (
                <button key={s.id} className={s.id === setId ? "active" : ""} onClick={() => load(s.id)}>
                  {s.name}
                </button>
              ))}
            </div>
          )}
          <label className="check" style={{ margin: 0 }}>
            <input type="checkbox" checked={showAnswers} onChange={(e) => setShowAnswers(e.target.checked)} />
            Show answers
          </label>
        </div>
      </div>

      <div className="banner" style={{ marginBottom: 16 }}>
        <span>
          This is how students see the paper{paper.sets.length ? " for this set" : ""}: {paper.items.length} questions,{" "}
          {paper.max_score} marks, {paper.exam.duration_minutes} minutes. Nothing you do here is saved.
          {paper.exam.shuffle_questions && " Students get the questions in a shuffled order within each section"}
          {paper.exam.shuffle_options && (paper.exam.shuffle_questions ? " and" : " Students get") + " shuffled options"}
          {(paper.exam.shuffle_questions || paper.exam.shuffle_options) && "."}
        </span>
      </div>

      {paper.items.length === 0 ? (
        <div className="card empty"><span className="big">No questions yet</span></div>
      ) : (
        <div className="grid" style={{ gridTemplateColumns: "250px minmax(0, 1fr)", alignItems: "start" }}>
          <div className="card pad-sm" style={{ margin: 0, position: "sticky", top: 12 }}>
            {paper.sections.map((sec) => (
              <div key={sec}>
                <h4 className="tiny faint" style={{ textTransform: "uppercase", letterSpacing: ".07em", margin: "10px 0 6px" }}>{sec}</h4>
                <div className="pal-grid">
                  {paper.items.map((it, i) => it.section !== sec ? null : (
                    <button key={it.item_id}
                            className={"pal-btn" + ((picked[it.item_id] || []).length ? " answered" : "") + (i === index ? " current" : "")}
                            onClick={() => setIndex(i)}>{it.number}</button>
                  ))}
                </div>
              </div>
            ))}
            {paper.exam.exam_type !== "coding" && (
              <p className="small muted" style={{ marginTop: 12, marginBottom: 0 }}>
                Your practice score: <strong>{Math.round(score * 100) / 100}</strong> / {paper.max_score}
              </p>
            )}
          </div>

          <div>
            <div className="q-head">
              <div>
                <span className="q-num">Question {item.number} / {paper.items.length}</span>
                <div className="strong" style={{ fontSize: 15 }}>{item.section}</div>
              </div>
              <div className="row tight small">
                <Badge color="green">+{item.marks} marks</Badge>
                {item.type === "mcq" && item.negative_marks > 0 && <Badge color="red">−{item.negative_marks} if wrong</Badge>}
                {item.type === "mcq" && item.is_multi && <Badge color="blue">Select all that apply</Badge>}
                {item.set_id && <Badge color="violet">from set</Badge>}
              </div>
            </div>

            {item.type === "mcq" ? (
              <div className="card">
                <Markdown style={{ fontSize: 15.5, lineHeight: 1.6 }}>{item.question_text}</Markdown>
                <ul className="options">
                  {item.options.map((o, i) => {
                    const chosen = (picked[item.item_id] || []).includes(o.id);
                    const correct = showAnswers && item.correct_options.includes(o.id);
                    return (
                      <li key={o.id}>
                        <label className={chosen ? "chosen" : ""}
                               style={correct ? { borderColor: "var(--success)", background: "var(--success-soft)" } : undefined}>
                          <input type={item.is_multi ? "checkbox" : "radio"} name={`p-${item.item_id}`}
                                 checked={chosen} onChange={() => choose(item, o.id)} />
                          <span><strong>{String.fromCharCode(65 + i)}.</strong> {o.text}{correct && "  ✓"}</span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
                {showAnswers && item.explanation && (
                  <div className="small muted"><strong>Explanation:</strong> {item.explanation}</div>
                )}
              </div>
            ) : (
              <div className="card">
                <h2>{item.title} <Badge>{item.difficulty}</Badge></h2>
                <Markdown>{item.statement}</Markdown>
                {item.input_format && (<><h3>Input format</h3><Markdown>{item.input_format}</Markdown></>)}
                {item.output_format && (<><h3>Output format</h3><Markdown>{item.output_format}</Markdown></>)}
                {item.constraints && (<><h3>Constraints</h3><Markdown>{item.constraints}</Markdown></>)}
                <h3>Examples</h3>
                {item.sample_tests.map((t, i) => (
                  <div key={i} className="grid cols-2" style={{ gap: 8, marginBottom: 8 }}>
                    <div><label>Input</label><pre>{t.input}</pre></div>
                    <div><label>Output</label><pre>{t.output}</pre></div>
                  </div>
                ))}
                <p className="muted small">
                  Time limit {item.time_limit_seconds}s per test · {item.hidden_test_count} hidden tests ·
                  languages: {paper.exam.allowed_languages.join(", ")}. Use "Test solution" on the
                  Coding Problems page to check a solution.
                </p>
              </div>
            )}

            <div className="row between" style={{ marginTop: 12 }}>
              <button className="btn" disabled={index === 0} onClick={() => setIndex(index - 1)}>‹ Previous</button>
              <button className="btn primary" disabled={index === paper.items.length - 1}
                      onClick={() => setIndex(index + 1)}>Next ›</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
