import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api.js";
import { LANG_LABELS } from "../../lib/format.js";
import {
  Badge, Field, Loading, Modal, ModalButton, Spinner, useConfirm, useToast,
} from "../../components/ui.jsx";
import { nullIfBlank, useAdmin } from "./context.jsx";

export default function Problems() {
  const { isSuper } = useAdmin();
  const toast = useToast();
  const confirm = useConfirm();

  const [meta, setMeta] = useState(null);
  const [problems, setProblems] = useState(null);
  const [editing, setEditing] = useState(null);
  const [verifying, setVerifying] = useState(null);

  const load = useCallback(async () => {
    try {
      setProblems(await api("GET", "/api/reios/admin/problems"));
    } catch (err) {
      toast(err.message, "error", 6000);
      setProblems([]);
    }
  }, [toast]);

  useEffect(() => {
    api("GET", "/api/reios/admin/meta").then(setMeta).catch((e) => toast(e.message, "error"));
    load();
  }, [load, toast]);

  async function remove(id) {
    const ok = await confirm("Delete problem",
      "Delete this problem? If it's used in an exam it will be hidden instead.", "Delete", true);
    if (!ok) return;
    try {
      await api("DELETE", `/api/reios/admin/problems/${id}`);
      toast("Deleted", "success");
      load();
    } catch (err) { toast(err.message, "error"); }
  }

  async function edit(id) {
    try {
      setEditing(await api("GET", `/api/reios/admin/problems/${id}`));
    } catch (err) { toast(err.message, "error"); }
  }

  if (!meta || !problems) return <Loading />;

  return (
    <>
      <div className="row between" style={{ marginBottom: 6 }}>
        <div className="page-head" style={{ margin: 0 }}>
          <h1>{isSuper ? "Global coding problems" : "Coding problems"}</h1>
          <p className="lede">
            Each problem has visible sample tests (students can run against them) and hidden tests
            (used for scoring; marks are given in proportion to hidden tests passed).
          </p>
        </div>
        <button className="btn primary" onClick={() => setEditing({})}>+ Add problem</button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Title</th><th>Level</th><th className="num">Marks</th>
              <th className="num">Sample</th><th className="num">Hidden</th><th>Time limit</th><th />
            </tr>
          </thead>
          <tbody>
            {problems.length === 0 ? (
              <tr><td colSpan={7} className="empty">No coding problems yet</td></tr>
            ) : problems.map((p) => (
              <tr key={p.id}>
                <td>
                  <strong>{p.title}</strong>{" "}
                  {p.is_global && !isSuper && <Badge color="blue">Global</Badge>}
                </td>
                <td>{p.difficulty}</td>
                <td className="num">{p.marks}</td>
                <td className="num">{p.sample_count}</td>
                <td className="num">
                  {p.hidden_count ? p.hidden_count : <Badge color="amber">0</Badge>}
                </td>
                <td>{p.time_limit_seconds}s</td>
                <td>
                  <div className="row tight">
                    <button className="btn sm" onClick={() => setVerifying(p)}>Test solution</button>
                    {(isSuper || !p.is_global) && (
                      <>
                        <button className="btn sm" onClick={() => edit(p.id)}>Edit</button>
                        <button className="btn sm danger" onClick={() => remove(p.id)}>Delete</button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <ProblemForm meta={meta} initial={editing.id ? editing : null}
                     onClose={() => setEditing(null)}
                     onSaved={() => { setEditing(null); load(); }} />
      )}

      {verifying && (
        <VerifyProblem meta={meta} problem={verifying} onClose={() => setVerifying(null)} />
      )}
    </>
  );
}

function TestEditor({ tests, kind, onChange }) {
  const label = kind === "sample" ? "Sample" : "Hidden";
  const update = (i, patch) =>
    onChange(tests.map((t, idx) => (idx === i ? { ...t, ...patch } : t)));

  return (
    <>
      {tests.map((t, i) => (
        <div key={i} className="card pad-sm" style={{ marginBottom: 8 }}>
          <div className="row between">
            <strong className="small">{label} test {i + 1}</strong>
            <button className="btn sm ghost" type="button"
                    onClick={() => onChange(tests.filter((_, idx) => idx !== i))}>✕</button>
          </div>
          <div className="grid cols-2" style={{ gap: 8 }}>
            <div>
              <label>Input</label>
              <textarea className="mono" rows={3} value={t.input || ""}
                        onChange={(e) => update(i, { input: e.target.value })} />
            </div>
            <div>
              <label>Expected output</label>
              <textarea className="mono" rows={3} value={t.output || ""}
                        onChange={(e) => update(i, { output: e.target.value })} />
            </div>
          </div>
          {kind === "sample" && (
            <>
              <label style={{ marginTop: 6 }}>Explanation</label>
              <input value={t.explanation || ""}
                     onChange={(e) => update(i, { explanation: e.target.value })} />
            </>
          )}
        </div>
      ))}
      <button className="btn sm" type="button"
              onClick={() => onChange([...tests, { input: "", output: "" }])}>
        + {label} test
      </button>
    </>
  );
}

function ProblemForm({ meta, initial, onClose, onSaved }) {
  const toast = useToast();
  const p = initial || {
    difficulty: "medium", marks: 10, time_limit_seconds: 5,
    sample_tests: [{ input: "", output: "" }], hidden_tests: [{ input: "", output: "" }],
    starter_code: {},
  };

  const [f, setF] = useState({
    title: p.title || "", difficulty: p.difficulty, marks: p.marks,
    time_limit_seconds: p.time_limit_seconds, statement: p.statement || "",
    input_format: p.input_format || "", output_format: p.output_format || "",
    constraints: p.constraints || "",
  });
  const [samples, setSamples] = useState(() => p.sample_tests.slice());
  const [hidden, setHidden] = useState(() => p.hidden_tests.slice());
  const [starter, setStarter] = useState(() => ({ ...(p.starter_code || {}) }));
  const [lang, setLang] = useState(meta.languages[0]);

  const set = (k) => (e) => setF((v) => ({ ...v, [k]: e.target.value }));
  const keep = (ts) => ts.filter((t) => (t.output || "").trim() !== "" || (t.input || "").trim() !== "");

  async function save() {
    const body = {
      title: f.title, difficulty: f.difficulty, marks: Number(f.marks),
      time_limit_seconds: Number(f.time_limit_seconds), statement: f.statement,
      input_format: nullIfBlank(f.input_format), output_format: nullIfBlank(f.output_format),
      constraints: nullIfBlank(f.constraints),
      sample_tests: keep(samples), hidden_tests: keep(hidden),
      starter_code: Object.fromEntries(Object.entries(starter).filter(([, c]) => c && c.trim())),
    };
    try {
      if (p.id) await api("PUT", `/api/reios/admin/problems/${p.id}`, body);
      else await api("POST", "/api/reios/admin/problems", body);
      toast("Saved", "success");
      onSaved();
    } catch (err) { toast(err.message, "error"); }
  }

  return (
    <Modal
      title={p.id ? "Edit coding problem" : "Add coding problem"}
      wide
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <ModalButton cls="primary" onClick={save}>Save</ModalButton>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Title *"><input value={f.title} onChange={set("title")} /></Field>
        <Field label="Difficulty">
          <select value={f.difficulty} onChange={set("difficulty")}>
            {meta.difficulties.map((d) => <option key={d}>{d}</option>)}
          </select>
        </Field>
        <Field label="Marks">
          <input type="number" min="1" value={f.marks} onChange={set("marks")} />
        </Field>
        <Field label="Time limit per test (seconds)">
          <input type="number" min="1" max="20" value={f.time_limit_seconds}
                 onChange={set("time_limit_seconds")} />
        </Field>
      </div>

      <Field label="Problem statement * (Markdown)">
        <textarea rows={6} value={f.statement} onChange={set("statement")} />
      </Field>

      <div className="grid cols-2" style={{ gap: "0 14px" }}>
        <Field label="Input format">
          <textarea rows={2} value={f.input_format} onChange={set("input_format")} />
        </Field>
        <Field label="Output format">
          <textarea rows={2} value={f.output_format} onChange={set("output_format")} />
        </Field>
      </div>
      <Field label="Constraints">
        <textarea rows={2} value={f.constraints} onChange={set("constraints")} />
      </Field>

      <h3>Sample tests <span className="muted small">(visible to students)</span></h3>
      <TestEditor tests={samples} kind="sample" onChange={setSamples} />

      <h3 style={{ marginTop: 16 }}>Hidden tests <span className="muted small">(used for scoring)</span></h3>
      <TestEditor tests={hidden} kind="hidden" onChange={setHidden} />

      <h3 style={{ marginTop: 16 }}>
        Starter code <span className="muted small">(optional, per language)</span>
      </h3>
      <div className="tabs">
        {meta.languages.map((l) => (
          <button key={l} type="button" className={l === lang ? "active" : ""}
                  onClick={() => setLang(l)}>{LANG_LABELS[l] || l}</button>
        ))}
      </div>
      <textarea className="mono" rows={6} value={starter[lang] || ""}
                onChange={(e) => setStarter((s) => ({ ...s, [lang]: e.target.value }))} />
    </Modal>
  );
}

function VerifyProblem({ meta, problem, onClose }) {
  const toast = useToast();
  const [lang, setLang] = useState(meta.languages[0]);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  async function run() {
    setBusy(true);
    setResult(null);
    try {
      setResult(await api("POST", `/api/reios/admin/problems/${problem.id}/verify`, { language: lang, code }));
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Test with reference solution"
      wide
      onClose={onClose}
      actions={
        <>
          <button className="btn" onClick={onClose}>Close</button>
          <button className="btn primary" onClick={run} disabled={busy}>
            {busy ? <><Spinner /> Running</> : "Run all tests"}
          </button>
        </>
      }
    >
      <p className="muted">
        Paste a correct reference solution to check that every sample and hidden test has the right
        expected output.
      </p>
      <Field label="Language">
        <select value={lang} onChange={(e) => setLang(e.target.value)}>
          {meta.languages.map((l) => <option key={l} value={l}>{LANG_LABELS[l] || l}</option>)}
        </select>
      </Field>
      <textarea className="mono" rows={12} placeholder="Reference solution" value={code}
                onChange={(e) => setCode(e.target.value)} />

      {result && (
        <div style={{ marginTop: 12 }}>
          <p><strong>{result.passed} / {result.total}</strong> tests passed</p>
          {result.results.map((t, i) => (
            <div key={i} className="card pad-sm" style={{ marginBottom: 6 }}>
              {t.passed ? <Badge color="green">Pass</Badge> : <Badge color="red">Fail</Badge>}{" "}
              <span className="small muted">{t.kind} test · {t.time_ms} ms</span>
              {!t.passed && (
                <div className="grid cols-2" style={{ gap: 8 }}>
                  <div><label>Expected</label><pre>{t.expected}</pre></div>
                  <div>
                    <label>Got</label>
                    <pre>{t.actual}{t.stderr ? "\n" + t.stderr : ""}</pre>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
