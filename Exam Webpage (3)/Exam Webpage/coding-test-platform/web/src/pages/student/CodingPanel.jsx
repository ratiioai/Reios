import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { EditorView } from "@codemirror/view";
import { python } from "@codemirror/lang-python";
import { cpp } from "@codemirror/lang-cpp";
import { java } from "@codemirror/lang-java";
import { javascript } from "@codemirror/lang-javascript";
import { githubDark, githubLight } from "@uiw/codemirror-theme-github";
import { Badge, Markdown, Spinner } from "../../components/ui.jsx";
import { DEFAULT_CODE, LANG_LABELS } from "./examState.js";

const LANG_EXT = {
  python: python, cpp: cpp, c: cpp, java: java, javascript: javascript,
};

function useIsDark() {
  const [dark, setDark] = useState(() => {
    const attr = document.documentElement.getAttribute("data-theme");
    if (attr) return attr === "dark";
    return matchMedia("(prefers-color-scheme: dark)").matches;
  });
  useEffect(() => {
    const obs = new MutationObserver(() => {
      const attr = document.documentElement.getAttribute("data-theme");
      setDark(attr ? attr === "dark" : matchMedia("(prefers-color-scheme: dark)").matches);
    });
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);
  return dark;
}

function Samples({ tests }) {
  return tests.map((t, i) => (
    <div key={i} style={{ marginBottom: 10 }}>
      <strong className="small">Sample {i + 1}</strong>
      <div className="grid cols-2" style={{ gap: 8 }}>
        <div><label>Input</label><pre>{t.input}</pre></div>
        <div><label>Output</label><pre>{t.output}</pre></div>
      </div>
      {t.explanation && <div className="small muted">{t.explanation}</div>}
    </div>
  ));
}

function RunOutput({ state }) {
  if (!state) return null;
  if (state.kind === "busy") {
    return <div><Spinner /> {state.label}</div>;
  }
  if (state.kind === "error") {
    return <div style={{ color: "var(--danger)" }}>{state.message}</div>;
  }
  if (state.kind === "submitted") {
    const r = state.data;
    return (
      <div
        className="card pad-sm"
        style={{
          background: r.all_passed ? "var(--success-soft)" : "var(--warning-soft)",
          borderColor: "transparent",
        }}
      >
        {r.all_passed
          ? "All hidden tests passed. Full marks for this question."
          : `${r.passed_tests} of ${r.total_tests} hidden tests passed. You get partial marks; you can keep improving and submit again.`}
      </div>
    );
  }
  const r = state.data;
  if (r.mode === "custom") {
    return (
      <>
        <label>Output ({r.time_ms} ms)</label>
        <pre>{r.stdout || "(no output)"}</pre>
        {r.stderr && (<><label>Errors</label><pre style={{ color: "var(--danger)" }}>{r.stderr}</pre></>)}
      </>
    );
  }
  return (
    <>
      <p><strong>{r.passed}/{r.total}</strong> sample tests passed</p>
      {r.results.map((t, i) => (
        <div key={i} className="card pad-sm" style={{ marginBottom: 6 }}>
          {t.passed ? <Badge color="green">Pass</Badge> : <Badge color="red">Fail</Badge>}{" "}
          <span className="small muted">Sample {i + 1} · {t.time_ms} ms</span>
          {!t.passed && (
            <div className="grid cols-2" style={{ gap: 8, marginTop: 6 }}>
              <div><label>Expected</label><pre>{t.expected}</pre></div>
              <div><label>Your output</label><pre>{t.actual}</pre></div>
            </div>
          )}
          {t.stderr && <pre style={{ color: "var(--danger)" }}>{t.stderr}</pre>}
        </div>
      ))}
    </>
  );
}

export default function CodingPanel({
  item, state, langs, blockPaste, onChange, onLanguageChange, onRun, onSubmit, onPasteBlocked, saveLabel,
}) {
  const dark = useIsDark();
  const [useCustom, setUseCustom] = useState(false);
  const [customInput, setCustomInput] = useState("");
  const [out, setOut] = useState(null);
  const [busy, setBusy] = useState(false);
  const pasteRef = useRef(onPasteBlocked);
  pasteRef.current = onPasteBlocked;

  const language = state.language;
  const value = state.drafts[language] ?? item.starter_code?.[language] ?? DEFAULT_CODE[language] ?? "";

  // Cancel pastes inside the editor and record them, same as the rest of the page.
  const extensions = useMemo(() => {
    const ext = [(LANG_EXT[language] || python)()];
    if (blockPaste) {
      ext.push(
        EditorView.domEventHandlers({
          paste: (e) => { e.preventDefault(); pasteRef.current?.(); return true; },
          drop: (e) => { e.preventDefault(); return true; },
        })
      );
    }
    return ext;
  }, [language, blockPaste]);

  const run = useCallback(async (submit) => {
    if (!value.trim()) { setOut({ kind: "error", message: "Write some code first" }); return; }
    setBusy(true);
    setOut({ kind: "busy", label: submit ? "Running hidden tests…" : "Running…" });
    try {
      const data = submit
        ? await onSubmit(language, value)
        : await onRun(language, value, useCustom ? customInput : null);
      setOut({ kind: submit ? "submitted" : "ran", data });
    } catch (err) {
      setOut({ kind: "error", message: err.message });
    } finally {
      setBusy(false);
    }
  }, [value, language, useCustom, customInput, onRun, onSubmit]);

  const grade = state.result;

  return (
    <div className="coding">
      <div className="card" style={{ margin: 0 }}>
        <h2>{item.title} <Badge>{item.difficulty}</Badge></h2>
        <Markdown>{item.statement}</Markdown>
        {item.input_format && (<><h3>Input format</h3><Markdown>{item.input_format}</Markdown></>)}
        {item.output_format && (<><h3>Output format</h3><Markdown>{item.output_format}</Markdown></>)}
        {item.constraints && (<><h3>Constraints</h3><Markdown>{item.constraints}</Markdown></>)}
        <h3>Examples</h3>
        <Samples tests={item.sample_tests} />
        <p className="muted small">
          Time limit {item.time_limit_seconds}s per test · {item.hidden_test_count} hidden tests
          decide your score.
        </p>
      </div>

      <div>
        <div className="row between" style={{ marginBottom: 8 }}>
          <select style={{ width: "auto" }} value={language}
                  onChange={(e) => onLanguageChange(e.target.value)}>
            {langs.map((l) => <option key={l} value={l}>{LANG_LABELS[l] || l}</option>)}
          </select>
          <span className="small muted">{saveLabel}</span>
        </div>

        <CodeMirror
          value={value}
          height="430px"
          theme={dark ? githubDark : githubLight}
          extensions={extensions}
          onChange={onChange}
          basicSetup={{ lineNumbers: true, autocompletion: false, highlightActiveLine: true }}
        />

        <label className="check">
          <input type="checkbox" checked={useCustom} onChange={(e) => setUseCustom(e.target.checked)} />
          Test with custom input
        </label>
        {useCustom && (
          <textarea className="mono" rows={3} placeholder="Custom input" value={customInput}
                    onChange={(e) => setCustomInput(e.target.value)} />
        )}

        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn" disabled={busy} onClick={() => run(false)}>▶ Run sample tests</button>
          <button className="btn success" disabled={busy} onClick={() => run(true)}>Submit code</button>
          {grade && (
            <Badge color={
              grade.total_tests && grade.passed_tests === grade.total_tests ? "green"
                : grade.passed_tests ? "amber" : "red"
            }>
              {grade.passed_tests}/{grade.total_tests} hidden tests passed
            </Badge>
          )}
        </div>

        <div className="run-out"><RunOutput state={out} /></div>
      </div>
    </div>
  );
}
