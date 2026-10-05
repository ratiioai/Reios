/* Reios exam client: question navigation, autosave, code editor and anti-cheat */
(function () {
  const { api, esc, fmtDate, fmtDuration, toast, modal, confirmBox } = Reios;
  const user = Reios.requireRole(["student"]);
  const app = document.getElementById("app");
  const examId = Number(new URLSearchParams(location.search).get("exam"));

  const LANG_LABELS = { python: "Python 3", cpp: "C++17", c: "C", java: "Java", javascript: "JavaScript (Node)" };
  const CM_MODES = { python: "python", cpp: "text/x-c++src", c: "text/x-csrc", java: "text/x-java", javascript: "javascript" };
  const DEFAULT_CODE = {
    python: "# Read input from stdin and print the answer\n",
    cpp: "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n",
    c: "#include <stdio.h>\n\nint main() {\n    \n    return 0;\n}\n",
    java: "import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        \n    }\n}\n",
    javascript: "const lines = require('fs').readFileSync(0, 'utf8').trim().split('\\n');\n",
  };
  const VIOLATION_TEXT = {
    fullscreen_exit: "You left fullscreen mode", tab_switch: "You switched to another tab or window",
    window_blur: "The exam window lost focus", paste_attempt: "Pasting is not allowed", devtools_open: "Developer tools are not allowed",
  };

  const S = {
    info: null, paper: null, session: null, index: 0, visited: new Set(), mcq: {}, code: {}, deadline: 0,
    violations: 0, finished: false, started: false, editor: null, timers: [], listeners: [], saving: Promise.resolve(),
    fsOverlay: null, lastBlurReport: 0,
  };

  function hdr() { return { headers: { "X-Exam-Session": S.session } }; }
  function badge(text, color) { return `<span class="badge ${color || ""}">${esc(text)}</span>`; }

  function examApi(method, path, body) {
    return api(method, `/api/reios/student/attempts/${S.paper.attempt_id}${path}`, body, hdr()).catch(err => {
      if (err.status === 409) handleConflict(err.message);
      throw err;
    });
  }

  function handleConflict(message) {
    if (S.finished) return;
    if (/another window|another device|one session/i.test(message)) {
      lockScreen("Exam opened somewhere else", "This exam was opened in another tab or device, so this window has been locked. Only one session is allowed at a time.");
    } else {
      finish(message);
    }
  }

  // ── Pre-start screen ────────────────────────────────────────────────────
  async function init() {
    if (!examId) { app.innerHTML = `<div class="pre-start card empty">No exam selected. <a href="student.html">Back to dashboard</a></div>`; return; }
    try {
      S.info = await api("GET", `/api/reios/student/exams/${examId}`);
    } catch (err) {
      app.innerHTML = `<div class="pre-start"><div class="card empty">${esc(err.message)}<br><a href="student.html">Back to dashboard</a></div></div>`;
      return;
    }
    const i = S.info;
    if (i.must_change_password) { location.href = "student.html"; return; }
    if (i.attempt && i.attempt.status !== "in_progress") { doneScreen("You have already submitted this exam.", i.attempt.id); return; }
    const resuming = i.attempt && i.attempt.status === "in_progress";
    const canStart = resuming || i.window === "live";
    document.title = `Reios — ${i.title}`;
    app.innerHTML = `
      <div class="pre-start">
        <div class="brand">
          <svg class="mark" viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="9" fill="url(#g)"/>
            <circle cx="16" cy="16" r="8" fill="none" stroke="#fff" stroke-width="2.6" opacity=".5"/>
            <circle cx="16" cy="16" r="3.6" fill="#fff"/>
            <defs><linearGradient id="g" x1="0" y1="0" x2="32" y2="32"><stop stop-color="#6366f1"/><stop offset="1" stop-color="#4338ca"/></linearGradient></defs>
          </svg>
          <span class="wordmark">Reios<span class="sub">Proctored exam</span></span>
        </div>
        <a href="student.html" class="small">← Dashboard</a>
        <div class="page-head" style="margin-top:10px">
          <h1>${esc(i.title)}</h1>
          <p class="lede">${fmtDate(i.start_at)} → ${fmtDate(i.end_at)}</p>
        </div>
        <div class="grid cols-4" style="margin:18px 0">
          <div class="stat"><div class="label">Duration</div><div class="value">${i.duration_minutes}<span class="muted" style="font-size:14px"> min</span></div></div>
          <div class="stat plain"><div class="label">Questions</div><div class="value">${i.sections.reduce((n, s) => n + s.questions, 0)}</div></div>
          <div class="stat plain"><div class="label">Total marks</div><div class="value">${i.max_score}</div></div>
          <div class="stat ${resuming ? "amber" : i.window === "live" ? "green" : "red"}">
            <div class="label">${resuming ? "Time left" : "Status"}</div>
            <div class="value" style="font-size:20px">${resuming ? fmtDuration(i.attempt.seconds_left) : i.window === "live" ? "Open" : i.window === "upcoming" ? "Not open yet" : "Closed"}</div></div>
        </div>
        <div class="card">
          <h3>Sections</h3>
          <div class="table-wrap compact"><table><thead><tr><th>Section</th><th class="num">Questions</th><th class="num">Marks</th></tr></thead>
            <tbody>${i.sections.map(s => `<tr><td><strong>${esc(s.section)}</strong></td><td class="num">${s.questions}</td><td class="num">${s.marks}</td></tr>`).join("")}</tbody></table></div>
        </div>
        <div class="card">
          <h3>Rules</h3>
          <ul style="margin:0;padding-left:19px;color:var(--text-soft)">
            <li>The timer starts when you click Start and keeps running even if you close the browser. The exam is submitted automatically when time runs out.</li>
            ${i.require_fullscreen ? "<li>The exam runs in <strong>fullscreen</strong>. Leaving fullscreen counts as a violation.</li>" : ""}
            <li>Switching tabs, switching windows or minimising the browser counts as a violation.</li>
            ${i.block_copy_paste ? "<li>Copy, paste and right-click are disabled. Trying to paste counts as a violation.</li>" : ""}
            <li>After <strong>${i.max_violations} violations</strong> your exam is submitted automatically.</li>
            <li>You can open the exam in only one browser tab or device at a time.</li>
            ${i.negative_marking ? "<li><strong>Negative marking</strong> applies to wrong MCQ answers. Unanswered questions get zero.</li>" : "<li>There is no negative marking.</li>"}
            <li>Answers are saved automatically as you go. For coding questions, use <strong>Submit code</strong> to score against hidden test cases; unsubmitted code is graded when the exam ends.</li>
            <li>Every action is logged and reviewed by your college.</li>
          </ul>
        </div>
        ${i.instructions ? `<div class="card"><h3>Instructions from your college</h3><div class="md">${Reios.markdown(i.instructions)}</div></div>` : ""}
        <div class="card">
          <label class="check"><input type="checkbox" id="agree"> I have read the rules and will not use unfair means.</label>
          <div id="start-error" class="small" style="color:var(--danger);min-height:18px;font-weight:550"></div>
          <button class="btn primary lg" id="start" disabled>${resuming ? "Resume exam" : "Start exam"}</button>
          ${canStart ? "" : `<p class="muted small" style="margin:10px 0 0">${i.window === "upcoming" ? "The exam hasn't opened yet. This page will let you start once it opens." : "This exam has closed."}</p>`}
        </div>
      </div>`;
    const agree = document.getElementById("agree");
    const btn = document.getElementById("start");
    agree.onchange = () => { btn.disabled = !agree.checked || !canStart; };
    btn.onclick = start;
    if (!canStart && i.window === "upcoming") {
      const t = setInterval(() => { if (Date.now() >= new Date(i.start_at).getTime()) { clearInterval(t); init(); } }, 5000);
    }
  }

  async function enterFullscreen() {
    const el = document.documentElement;
    const req = el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen;
    if (!req) throw new Error("Your browser doesn't support fullscreen. Use the latest Chrome, Edge or Firefox.");
    await req.call(el);
  }

  function isFullscreen() { return !!(document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement); }

  async function start() {
    const errEl = document.getElementById("start-error");
    const btn = document.getElementById("start");
    errEl.textContent = "";
    if (window.screen && window.screen.isExtended) {
      errEl.textContent = "Multiple displays detected. Disconnect extra monitors and reload this page to start.";
      return;
    }
    btn.disabled = true;
    try {
      if (S.info.require_fullscreen) await enterFullscreen();
    } catch (err) {
      errEl.textContent = err.message || "Allow fullscreen to start the exam.";
      btn.disabled = false;
      return;
    }
    try {
      const paper = await api("POST", `/api/reios/student/exams/${examId}/start`);
      S.paper = paper;
      S.session = paper.session;
      enterExam();
    } catch (err) {
      errEl.textContent = err.message;
      btn.disabled = false;
      if (isFullscreen()) document.exitFullscreen().catch(() => {});
    }
  }

  // ── Exam UI ─────────────────────────────────────────────────────────────
  function enterExam() {
    const p = S.paper;
    S.started = true;
    S.violations = p.violations;
    S.deadline = Date.now() + p.seconds_left * 1000;
    p.items.forEach(item => {
      if (item.type === "mcq") S.mcq[item.item_id] = { selected: item.answer.selected.slice(), review: item.answer.marked_for_review };
      else {
        const lang = item.answer ? item.answer.language : p.exam.allowed_languages[0];
        S.code[item.item_id] = {
          language: lang,
          drafts: Object.assign({}, item.answer ? { [item.answer.language]: item.answer.code } : {}),
          dirty: false,
          touched: !!(item.answer && item.answer.code.trim()),
          result: item.answer && item.answer.graded ? { passed_tests: item.answer.passed_tests, total_tests: item.answer.total_tests } : null,
        };
      }
    });
    // Resume where they left off: first unanswered question
    const firstOpen = p.items.findIndex(it => !isAnswered(it));
    S.index = firstOpen >= 0 ? firstOpen : 0;
    p.items.forEach((it, idx) => { if (isAnswered(it) || idx < S.index) S.visited.add(it.item_id); });

    document.body.classList.add("exam-mode");
    if (p.exam.block_copy_paste) document.body.classList.add("no-select");
    app.innerHTML = `
      <div class="exam-shell">
        <div class="exam-head">
          <button class="btn sm menu-toggle" id="pal-toggle" style="display:none">☰</button>
          <div class="title">${esc(p.exam.title)}</div>
          <span class="small muted">${esc(user.name)} · ${esc(user.roll_no)}</span>
          <span id="viol" title="Violations"></span>
          <span class="timer" id="timer">--:--</span>
          <button class="btn sm" id="instr">Instructions</button>
          <button class="btn danger solid sm" id="submit-exam">Submit exam</button>
        </div>
        <div class="exam-body">
          <aside class="palette" id="palette"></aside>
          <section class="content" id="content"></section>
        </div>
      </div>
      <div class="watermark" aria-hidden="true">${Array(40).fill(`<span>${esc(user.roll_no)}</span>`).join("")}</div>`;
    if (matchMedia("(max-width: 900px)").matches) {
      const t = document.getElementById("pal-toggle"); t.style.display = "inline-flex";
      t.onclick = () => document.getElementById("palette").classList.toggle("open");
    }
    document.getElementById("submit-exam").onclick = confirmSubmit;
    document.getElementById("instr").onclick = () => modal({ title: "Instructions", body: `<div class="md">${Reios.markdown(p.exam.instructions || "No additional instructions.")}</div>
      <p class="muted small">Violations so far: ${S.violations} of ${p.exam.max_violations} allowed.</p>` });
    updateViolations();
    renderPalette();
    renderQuestion();
    installAntiCheat();
    S.timers.push(setInterval(tickTimer, 500));
    S.timers.push(setInterval(heartbeat, 20000));
    S.timers.push(setInterval(() => saveCode(false), 15000));
    tickTimer();
  }

  function isAnswered(item) {
    if (item.type === "mcq") return S.mcq[item.item_id].selected.length > 0;
    const c = S.code[item.item_id];
    return c.touched && !!(c.drafts[c.language] || "").trim();
  }

  function renderPalette() {
    const p = S.paper;
    const pal = document.getElementById("palette");
    const counts = { answered: 0, review: 0, visited: 0, fresh: 0 };
    pal.innerHTML = p.sections.map(sec => `
      <h4>${esc(sec)}</h4>
      <div class="pal-grid">${p.items.map((it, idx) => {
        if (it.section !== sec) return "";
        const answered = isAnswered(it);
        const review = it.type === "mcq" && S.mcq[it.item_id].review;
        const cls = [answered ? "answered" : S.visited.has(it.item_id) ? "visited" : "", review ? "review" : "", idx === S.index ? "current" : ""].join(" ");
        if (answered) counts.answered++; else if (S.visited.has(it.item_id)) counts.visited++; else counts.fresh++;
        if (review) counts.review++;
        return `<button class="pal-btn ${cls}" data-go="${idx}" title="${it.type === "coding" ? "Coding" : "MCQ"}">${it.number}</button>`;
      }).join("")}</div>`).join("") + `
      <div class="legend">
        <span style="--c:var(--success)">Answered (${counts.answered})</span>
        <span style="--c:var(--danger-soft)">Not answered (${counts.visited})</span>
        <span style="--c:var(--surface-2)">Not visited (${counts.fresh})</span>
        <span style="--c:#7c4dff">For review (${counts.review})</span>
      </div>`;
    pal.querySelectorAll("[data-go]").forEach(b => b.onclick = () => { go(Number(b.dataset.go)); pal.classList.remove("open"); });
  }

  function go(idx) {
    if (idx < 0 || idx >= S.paper.items.length) return;
    saveCode(false);
    S.index = idx;
    renderQuestion();
    renderPalette();
  }

  function renderQuestion() {
    const item = S.paper.items[S.index];
    S.visited.add(item.item_id);
    const content = document.getElementById("content");
    content.scrollTop = 0;
    S.editor = null;
    const head = `<div class="q-head">
        <div><span class="q-num">Question ${item.number} / ${S.paper.items.length}</span>
          <div class="strong" style="font-size:15px;margin-top:1px">${esc(item.section)}</div></div>
        <div class="row tight small">${badge(`+${item.marks} marks`, "green")} ${item.type === "mcq" && item.negative_marks ? badge(`−${item.negative_marks} if wrong`, "red") : ""}
        ${item.type === "mcq" && item.is_multi ? badge("Select all that apply", "blue") : ""}</div></div>`;
    const nav = `<div class="q-actions">
        <div class="row"><button class="btn" id="prev" ${S.index === 0 ? "disabled" : ""}>‹ Previous</button>
        ${item.type === "mcq" ? `<button class="btn" id="clear">Clear response</button><button class="btn" id="review">${S.mcq[item.item_id].review ? "Unmark review" : "Mark for review & next"}</button>` : ""}</div>
        <button class="btn primary" id="next">${S.index === S.paper.items.length - 1 ? "Save" : "Save & next ›"}</button></div>`;
    if (item.type === "mcq") {
      const st = S.mcq[item.item_id];
      content.innerHTML = `<div class="q-wrap">` + head + `
        <div class="card"><div class="md" style="font-size:15.5px;line-height:1.6">${Reios.markdown(item.question_text)}</div>
        <ul class="options">${item.options.map((o, i) => `<li><label class="${st.selected.includes(o.id) ? "chosen" : ""}">
          <input type="${item.is_multi ? "checkbox" : "radio"}" name="opt" value="${o.id}" ${st.selected.includes(o.id) ? "checked" : ""}>
          <span><strong>${String.fromCharCode(65 + i)}.</strong> ${esc(o.text)}</span></label></li>`).join("")}</ul></div></div>` + nav;
      content.querySelectorAll("[name=opt]").forEach(inp => inp.onchange = () => {
        st.selected = [...content.querySelectorAll("[name=opt]:checked")].map(x => Number(x.value));
        content.querySelectorAll(".options label").forEach(l => l.classList.toggle("chosen", l.querySelector("input").checked));
        saveMcq(item);
      });
      document.getElementById("clear").onclick = () => { st.selected = []; saveMcq(item); renderQuestion(); renderPalette(); };
      document.getElementById("review").onclick = () => {
        st.review = !st.review; saveMcq(item);
        if (st.review) go(S.index + 1); else { renderQuestion(); renderPalette(); }
        if (st.review && S.index === S.paper.items.length - 1) renderPalette();
      };
    } else {
      renderCoding(content, item, head, nav);
    }
    document.getElementById("prev").onclick = () => go(S.index - 1);
    document.getElementById("next").onclick = () => { saveCode(false); if (S.index < S.paper.items.length - 1) go(S.index + 1); else { renderPalette(); toast("Saved", "success", 1500); } };
  }

  function saveMcq(item) {
    const st = S.mcq[item.item_id];
    renderPalette();
    S.saving = S.saving.then(() => examApi("PUT", `/mcq/${item.item_id}`, { selected: st.selected, marked_for_review: st.review }))
      .catch(err => { if (err.status !== 409) toast("Couldn't save your answer: " + err.message + ". It will retry.", "error"); retryLater(() => saveMcq(item)); });
  }

  let retryTimer = null;
  function retryLater(fn) { clearTimeout(retryTimer); retryTimer = setTimeout(() => { if (!S.finished) fn(); }, 5000); }

  // ── Coding question ─────────────────────────────────────────────────────
  function renderCoding(content, item, head, nav) {
    const st = S.code[item.item_id];
    const langs = S.paper.exam.allowed_languages;
    if (!langs.includes(st.language)) st.language = langs[0];
    const samples = item.sample_tests.map((t, i) => `
      <div style="margin-bottom:10px"><strong class="small">Sample ${i + 1}</strong>
        <div class="grid cols-2" style="gap:8px"><div><label>Input</label><pre>${esc(t.input)}</pre></div><div><label>Output</label><pre>${esc(t.output)}</pre></div></div>
        ${t.explanation ? `<div class="small muted">${esc(t.explanation)}</div>` : ""}</div>`).join("");
    content.innerHTML = head + `
      <div class="coding">
        <div class="card" style="margin:0">
          <h2>${esc(item.title)} <span class="badge">${esc(item.difficulty)}</span></h2>
          <div class="md">${Reios.markdown(item.statement)}</div>
          ${item.input_format ? `<h3>Input format</h3><div class="md">${Reios.markdown(item.input_format)}</div>` : ""}
          ${item.output_format ? `<h3>Output format</h3><div class="md">${Reios.markdown(item.output_format)}</div>` : ""}
          ${item.constraints ? `<h3>Constraints</h3><div class="md">${Reios.markdown(item.constraints)}</div>` : ""}
          <h3>Examples</h3>${samples}
          <p class="muted small">Time limit ${item.time_limit_seconds}s per test · ${item.hidden_test_count} hidden tests decide your score.</p>
        </div>
        <div>
          <div class="row between" style="margin-bottom:8px">
            <select id="lang" style="width:auto">${langs.map(l => `<option value="${l}" ${l === st.language ? "selected" : ""}>${LANG_LABELS[l] || l}</option>`).join("")}</select>
            <span class="small muted" id="save-state"></span>
          </div>
          <div id="editor"></div>
          <label class="check"><input type="checkbox" id="use-custom"> Test with custom input</label>
          <textarea id="custom" class="mono hidden" rows="3" placeholder="Custom input"></textarea>
          <div class="row" style="margin-top:8px">
            <button class="btn" id="run">▶ Run sample tests</button>
            <button class="btn success" id="submit-code">Submit code</button>
            <span id="grade" class="small"></span>
          </div>
          <div id="run-out" class="run-out"></div>
        </div>
      </div>` + nav;
    const starter = item.starter_code || {};
    const initial = st.drafts[st.language] ?? starter[st.language] ?? DEFAULT_CODE[st.language] ?? "";
    st.drafts[st.language] = initial;
    const dark = document.documentElement.getAttribute("data-theme") === "dark" ||
      (!document.documentElement.getAttribute("data-theme") && matchMedia("(prefers-color-scheme: dark)").matches);
    const cm = CodeMirror(document.getElementById("editor"), {
      value: initial, mode: CM_MODES[st.language], lineNumbers: true, indentUnit: 4, tabSize: 4, indentWithTabs: false,
      autoCloseBrackets: true, matchBrackets: true, theme: dark ? "material-darker" : "default",
      extraKeys: { Tab: c => c.somethingSelected() ? c.indentSelection("add") : c.replaceSelection("    ", "end") },
    });
    S.editor = cm;
    cm.on("beforeChange", (c, change) => {
      if (S.paper.exam.block_copy_paste && (change.origin === "paste" || change.origin === "drop")) {
        change.cancel();
        violation("paste_attempt", "Paste into code editor");
      }
    });
    cm.on("change", (c, change) => { if (change.origin !== "setValue") st.touched = true; st.drafts[st.language] = cm.getValue(); st.dirty = true; setSaveState("Unsaved changes"); renderPaletteDebounced(); });
    showGrade(st.result);

    document.getElementById("lang").onchange = e => {
      st.drafts[st.language] = cm.getValue();
      st.language = e.target.value;
      const code = st.drafts[st.language] ?? starter[st.language] ?? DEFAULT_CODE[st.language] ?? "";
      st.drafts[st.language] = code;
      cm.setOption("mode", CM_MODES[st.language]);
      cm.setValue(code);
      st.dirty = true; saveCode(false);
    };
    document.getElementById("use-custom").onchange = e => document.getElementById("custom").classList.toggle("hidden", !e.target.checked);
    document.getElementById("run").onclick = () => runCode(item, false);
    document.getElementById("submit-code").onclick = () => runCode(item, true);
  }

  let palTimer;
  function renderPaletteDebounced() { clearTimeout(palTimer); palTimer = setTimeout(renderPalette, 600); }

  function setSaveState(text) { const el = document.getElementById("save-state"); if (el) el.textContent = text; }

  function showGrade(result) {
    const el = document.getElementById("grade");
    if (!el) return;
    if (!result) { el.innerHTML = ""; return; }
    const all = result.total_tests && result.passed_tests === result.total_tests;
    el.innerHTML = `${badge(`${result.passed_tests}/${result.total_tests} hidden tests passed`, all ? "green" : result.passed_tests ? "amber" : "red")}`;
  }

  function saveCode(force) {
    const item = S.paper && S.paper.items[S.index];
    if (!item || item.type !== "coding" || S.finished) return S.saving;
    const st = S.code[item.item_id];
    if (S.editor) st.drafts[st.language] = S.editor.getValue();
    if (!st.dirty && !force) return S.saving;
    st.dirty = false;
    const body = { language: st.language, code: st.drafts[st.language] || "" };
    setSaveState("Saving…");
    S.saving = S.saving.then(() => examApi("PUT", `/code/${item.item_id}`, body))
      .then(() => { if (S.paper.items[S.index] === item) setSaveState("Saved " + new Date().toLocaleTimeString()); })
      .catch(err => { st.dirty = true; setSaveState("Not saved"); if (err.status !== 409) retryLater(() => saveCode(false)); });
    return S.saving;
  }

  async function runCode(item, submit) {
    const st = S.code[item.item_id];
    st.drafts[st.language] = S.editor.getValue();
    const code = st.drafts[st.language];
    const out = document.getElementById("run-out");
    const btns = [document.getElementById("run"), document.getElementById("submit-code")];
    if (!code.trim()) return toast("Write some code first", "error");
    const custom = document.getElementById("use-custom").checked;
    btns.forEach(b => b.disabled = true);
    out.innerHTML = `<span class="spinner"></span> ${submit ? "Running hidden tests…" : "Running…"}`;
    try {
      if (submit) {
        const r = await examApi("POST", `/code/${item.item_id}/submit`, { language: st.language, code });
        st.result = r; st.dirty = false;
        showGrade(r);
        out.innerHTML = r.all_passed
          ? `<div class="card" style="background:var(--success-soft);border-color:transparent;padding:12px">All hidden tests passed. Full marks for this question.</div>`
          : `<div class="card" style="background:var(--warning-soft);border-color:transparent;padding:12px">${r.passed_tests} of ${r.total_tests} hidden tests passed. You get partial marks; you can keep improving and submit again.</div>`;
      } else {
        const body = { language: st.language, code };
        if (custom) body.custom_input = document.getElementById("custom").value;
        const r = await examApi("POST", `/code/${item.item_id}/run`, body);
        st.dirty = false;
        if (r.mode === "custom") {
          out.innerHTML = `<label>Output (${r.time_ms} ms)</label><pre>${esc(r.stdout) || "<span class='muted'>(no output)</span>"}</pre>${r.stderr ? `<label>Errors</label><pre style="color:var(--danger)">${esc(r.stderr)}</pre>` : ""}`;
        } else {
          out.innerHTML = `<p><strong>${r.passed}/${r.total}</strong> sample tests passed</p>` + r.results.map((t, i) => `
            <div class="card" style="padding:10px;margin-bottom:6px">${t.passed ? badge("Pass", "green") : badge("Fail", "red")} <span class="small muted">Sample ${i + 1} · ${t.time_ms} ms</span>
              ${t.passed ? "" : `<div class="grid cols-2" style="gap:8px;margin-top:6px"><div><label>Expected</label><pre>${esc(t.expected)}</pre></div><div><label>Your output</label><pre>${esc(t.actual)}</pre></div></div>`}
              ${t.stderr ? `<pre style="color:var(--danger)">${esc(t.stderr)}</pre>` : ""}</div>`).join("");
        }
      }
      renderPalette();
    } catch (err) {
      out.innerHTML = `<div style="color:var(--danger)">${esc(err.message)}</div>`;
    } finally {
      btns.forEach(b => { if (b) b.disabled = false; });
    }
  }

  // ── Timer, heartbeat and submit ─────────────────────────────────────────
  let autoSubmitting = false;
  function tickTimer() {
    if (S.finished) return;
    const left = Math.max(0, (S.deadline - Date.now()) / 1000);
    const el = document.getElementById("timer");
    if (el) {
      el.textContent = fmtDuration(left);
      el.classList.toggle("low", left <= 300);
      el.classList.toggle("warn", left > 300 && left <= 600);
    }
    if (left <= 0 && !autoSubmitting) {
      autoSubmitting = true;
      saveCode(true).finally(() => examApi("POST", "/submit").then(() => finish("Time is up. Your exam was submitted automatically."))
        .catch(() => heartbeat()));
    }
  }

  async function heartbeat() {
    if (S.finished) return;
    try {
      const r = await api("POST", `/api/reios/student/attempts/${S.paper.attempt_id}/heartbeat`, null, hdr());
      if (r.status !== "in_progress") return finish(r.status === "auto_submitted" ? "Your exam was submitted." : "Exam submitted.");
      if (!r.session_valid) return handleConflict("opened in another window");
      S.deadline = Date.now() + r.seconds_left * 1000;
      if (r.violations !== S.violations) { S.violations = r.violations; updateViolations(); }
    } catch (err) { /* offline: keep going, the next heartbeat will sync */ }
  }

  async function confirmSubmit() {
    await saveCode(true);
    const items = S.paper.items;
    const answered = items.filter(isAnswered).length;
    const review = items.filter(it => it.type === "mcq" && S.mcq[it.item_id].review).length;
    const ungraded = items.filter(it => it.type === "coding" && isAnswered(it) && !S.code[it.item_id].result).length;
    const perSection = S.paper.sections.map(sec => {
      const its = items.filter(i => i.section === sec);
      return `<tr><td>${esc(sec)}</td><td class="num">${its.filter(isAnswered).length}</td><td class="num">${its.length - its.filter(isAnswered).length}</td></tr>`;
    }).join("");
    const ok = await new Promise(resolve => {
      let done = false;
      modal({
        title: "Submit exam?",
        body: `<div class="table-wrap"><table><thead><tr><th>Section</th><th class="num">Answered</th><th class="num">Not answered</th></tr></thead><tbody>${perSection}</tbody></table></div>
          <p>${answered} of ${items.length} answered${review ? ` · ${review} marked for review` : ""}.</p>
          ${ungraded ? `<p class="small" style="color:var(--warning)">${ungraded} coding answer(s) were not submitted with "Submit code". They will be graded automatically now.</p>` : ""}
          <p><strong>You can't change your answers after submitting.</strong></p>`,
        actions: [{ label: "Keep working", onClick: c => { done = true; resolve(false); c(); } },
                  { label: "Submit exam", cls: "danger solid", onClick: c => { done = true; resolve(true); c(); } }],
        onClose: () => { if (!done) resolve(false); },
      });
    });
    if (!ok) return;
    const btn = document.getElementById("submit-exam");
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Submitting';
    try {
      await S.saving.catch(() => {});
      await examApi("POST", "/submit");
      finish("Your exam has been submitted.");
    } catch (err) {
      if (!S.finished) { toast(err.message, "error"); btn.disabled = false; btn.textContent = "Submit exam"; }
    }
  }

  function cleanup() {
    S.timers.forEach(clearInterval);
    S.listeners.forEach(([target, type, fn, opts]) => target.removeEventListener(type, fn, opts));
    S.listeners = [];
    document.body.classList.remove("exam-mode", "no-select");
    if (S.fsOverlay) { S.fsOverlay.remove(); S.fsOverlay = null; }
    if (isFullscreen()) (document.exitFullscreen || document.webkitExitFullscreen || (() => Promise.resolve())).call(document);
  }

  function finish(message) {
    if (S.finished) return;
    S.finished = true;
    cleanup();
    doneScreen(message, S.paper && S.paper.attempt_id);
  }

  function doneScreen(message, attemptId) {
    document.querySelectorAll(".modal-backdrop").forEach(m => m.remove());
    app.innerHTML = `<div class="pre-start" style="text-align:center;padding-top:80px">
      <div class="card"><h1>${esc(message)}</h1>
        <p class="muted">You can close this window. Your college will review the results.</p>
        <div class="row" style="justify-content:center">
          <a class="btn primary" href="student.html${attemptId ? `?result=${attemptId}` : ""}">Go to dashboard</a>
        </div></div></div>`;
  }

  function lockScreen(title, text) {
    S.finished = true;
    cleanup();
    app.innerHTML = `<div class="pre-start" style="text-align:center;padding-top:80px"><div class="card"><h1>${esc(title)}</h1><p>${esc(text)}</p>
      <a class="btn" href="student.html">Back to dashboard</a></div></div>`;
  }

  // ── Anti-cheat ──────────────────────────────────────────────────────────
  function on(target, type, fn, opts) { target.addEventListener(type, fn, opts); S.listeners.push([target, type, fn, opts]); }

  function updateViolations() {
    const el = document.getElementById("viol");
    if (!el) return;
    const max = S.paper.exam.max_violations;
    const ov = document.getElementById("fs-count");
    if (ov) ov.textContent = `${S.violations}/${max}`;
    el.innerHTML = S.violations ? badge(`⚠ ${S.violations}/${max} violations`, S.violations >= max - 1 ? "red" : "amber") : badge("No violations", "green");
  }

  async function violation(type, details) {
    if (S.finished || !S.started) return;
    try {
      const r = await api("POST", `/api/reios/student/attempts/${S.paper.attempt_id}/violation`, { type, details }, hdr());
      S.violations = r.violations;
      updateViolations();
      if (r.auto_submitted) return finish("Your exam was submitted automatically because of repeated violations.");
      if (r.counted) warn(type, r);
    } catch (err) {
      if (err.status === 409) handleConflict(err.message);
    }
  }

  function warn(type, r) {
    const left = r.max_violations - r.violations;
    if (type === "fullscreen_exit" && S.paper.exam.require_fullscreen) return; // the fullscreen overlay already explains it
    modal({
      title: "Warning: violation recorded",
      body: `<p><strong>${esc(VIOLATION_TEXT[type] || type)}.</strong></p>
             <p>This has been recorded and reported to your college. ${left > 0 ? `<strong>${left}</strong> more violation${left === 1 ? "" : "s"} and your exam will be submitted automatically.` : ""}</p>`,
      actions: [{ label: "I understand", cls: "primary" }],
    });
  }

  function showFullscreenOverlay() {
    if (S.fsOverlay || S.finished) return;
    S.fsOverlay = document.createElement("div");
    S.fsOverlay.className = "overlay";
    S.fsOverlay.innerHTML = `<div class="box"><h2>⚠ You left fullscreen</h2>
      <p>This has been recorded as a violation (<strong id="fs-count">${S.violations}/${S.paper.exam.max_violations}</strong>). Your timer is still running.</p>
      <p>Return to fullscreen to continue your exam.</p>
      <button class="btn primary" id="refs">Return to fullscreen</button></div>`;
    document.body.appendChild(S.fsOverlay);
    S.fsOverlay.querySelector("#refs").onclick = async () => {
      try { await enterFullscreen(); } catch (e) { toast("Fullscreen was blocked by the browser. Try again.", "error"); }
    };
  }

  function installAntiCheat() {
    const ex = S.paper.exam;

    if (ex.require_fullscreen) {
      const onFs = () => {
        if (S.finished) return;
        if (isFullscreen()) {
          if (S.fsOverlay) { S.fsOverlay.remove(); S.fsOverlay = null; }
          if (S.editor) S.editor.refresh();
        } else {
          showFullscreenOverlay();
          violation("fullscreen_exit");
        }
      };
      ["fullscreenchange", "webkitfullscreenchange", "MSFullscreenChange"].forEach(t => on(document, t, onFs));
      if (!isFullscreen()) showFullscreenOverlay(); // resumed after a reload
    }

    on(document, "visibilitychange", () => { if (document.hidden) violation("tab_switch", "Page hidden"); });
    on(window, "blur", () => {
      // Clicking into the code editor iframe-less textarea doesn't blur the window; alt-tab / other apps do
      setTimeout(() => { if (!document.hasFocus() && !document.hidden) violation("window_blur", "Focus moved to another window"); }, 300);
    });

    if (ex.block_copy_paste) {
      on(document, "copy", e => { e.preventDefault(); violation("copy_attempt"); }, true);
      on(document, "cut", e => { e.preventDefault(); violation("copy_attempt", "cut"); }, true);
      on(document, "paste", e => {
        // CodeMirror handles its own paste via beforeChange; this catches everything else
        if (!e.target.closest || !e.target.closest(".CodeMirror")) { e.preventDefault(); violation("paste_attempt"); }
      }, true);
      on(document, "contextmenu", e => { e.preventDefault(); violation("right_click"); }, true);
      on(document, "dragstart", e => e.preventDefault(), true);
      on(document, "drop", e => { if (!e.target.closest || !e.target.closest(".CodeMirror")) e.preventDefault(); }, true);
      on(document, "keydown", e => {
        const k = (e.key || "").toLowerCase();
        const ctrl = e.ctrlKey || e.metaKey;
        if (k === "f12" || (ctrl && e.shiftKey && ["i", "j", "c", "k"].includes(k)) || (ctrl && ["u", "s", "p"].includes(k))) {
          e.preventDefault();
          violation(k === "f12" || e.shiftKey ? "devtools_open" : "keyboard_shortcut", `${ctrl ? "Ctrl+" : ""}${e.shiftKey ? "Shift+" : ""}${e.key}`);
        }
        if (k === "printscreen") { violation("print_screen"); }
      }, true);
      on(document, "keyup", e => { if ((e.key || "").toLowerCase() === "printscreen") { navigator.clipboard && navigator.clipboard.writeText("").catch(() => {}); } }, true);
    }

    on(window, "beforeunload", e => { if (!S.finished) { saveCode(true); e.preventDefault(); e.returnValue = ""; } });
    on(window, "offline", () => toast("You're offline. Keep working; answers will sync when you reconnect.", "error", 6000));
    on(window, "online", () => { violation("network_online"); heartbeat(); toast("Back online", "success"); });
  }

  init();
})();
