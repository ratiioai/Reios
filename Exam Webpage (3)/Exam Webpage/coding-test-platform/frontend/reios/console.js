/* Reios admin console: used by super admins and college admins */
(function () {
  const { api, qs, esc, fmtDate, fmtDuration, toLocalInput, fromLocalInput, toast, modal, confirmBox, download, downloadCSV } = Reios;
  const user = Reios.requireRole(["super_admin", "college_admin"]);
  const isSuper = user.role === "super_admin";
  const view = document.getElementById("view");
  const state = { collegeId: isSuper ? Number(Reios.store.get("reios_console_college")) || null : user.college.id,
                  colleges: [], meta: null, liveTimer: null };

  const LANG_LABELS = { python: "Python", cpp: "C++", c: "C", java: "Java", javascript: "JavaScript" };

  // ── Shell ───────────────────────────────────────────────────────────────
  document.getElementById("who").textContent = `${user.name} · ${isSuper ? "Super Admin" : user.college.name}`;
  document.getElementById("brand-text").textContent = isSuper ? "Super Admin" : "College Admin";
  document.getElementById("menu-toggle").onclick = () => document.getElementById("sidebar").classList.toggle("open");

  const ICONS = {
    overview: '<path d="M3 9.5 10 4l7 5.5V16a1 1 0 0 1-1 1h-3v-5H7v5H4a1 1 0 0 1-1-1V9.5Z"/>',
    colleges: '<path d="M10 3 3 6.5 10 10l7-3.5L10 3Z"/><path d="M4.5 9v4.5c0 1 2.5 2.5 5.5 2.5s5.5-1.5 5.5-2.5V9"/>',
    students: '<circle cx="7.5" cy="7" r="2.6"/><path d="M3 16c0-2.5 2-4.2 4.5-4.2S12 13.5 12 16"/><circle cx="14.5" cy="8" r="2"/><path d="M13 16c0-1.9 1-3.1 2.6-3.1 1.1 0 1.9.5 2.4 1.3"/>',
    exams: '<path d="M5 3h7l3.5 3.5V17H5V3Z"/><path d="M12 3v3.5h3.5"/><path d="m7.8 11.4 1.4 1.4 3-3.2"/>',
    announcements: '<path d="M4 8v4h2.5L11 15.5v-11L6.5 8H4Z"/><path d="M14 8.2a3 3 0 0 1 0 3.6"/>',
    mcqs: '<circle cx="5.5" cy="6" r="2"/><circle cx="5.5" cy="14" r="2"/><path d="M10 6h7M10 14h7"/>',
    problems: '<path d="m7 7-3.5 3L7 13"/><path d="m13 7 3.5 3L13 13"/>',
    account: '<circle cx="10" cy="7" r="3"/><path d="M4 17c0-3.1 2.7-5 6-5s6 1.9 6 5"/>',
  };
  const icon = id => `<svg class="ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[id] || ""}</svg>`;

  const NAV = [
    { group: "General" },
    { id: "overview", label: "Overview" },
    ...(isSuper ? [{ id: "colleges", label: "Colleges & Admins" }] : []),
    { group: isSuper ? "Selected college" : "College" },
    { id: "students", label: "Students", college: true },
    { id: "exams", label: "Exams & Results", college: true },
    { id: "announcements", label: "Announcements", college: !isSuper },
    { group: isSuper ? "Global question bank" : "Question bank" },
    { id: "mcqs", label: "MCQ Questions" },
    { id: "problems", label: "Coding Problems" },
    { group: "Account" },
    { id: "account", label: "Change password" },
  ];

  function renderNav(active) {
    document.getElementById("nav").innerHTML = NAV.map(n => n.group
      ? `<div class="group">${esc(n.group)}</div>`
      : `<a href="#${n.id}" class="${n.id === active ? "active" : ""}">${icon(n.id)}${esc(n.label)}</a>`).join("");
  }

  async function loadColleges() {
    if (!isSuper) return;
    state.colleges = await api("GET", "/api/reios/super/colleges");
    const picker = document.getElementById("college-picker");
    document.getElementById("college-picker-wrap").classList.remove("hidden");
    if (state.collegeId && !state.colleges.find(c => c.id === state.collegeId)) state.collegeId = null;
    if (!state.collegeId && state.colleges.length) state.collegeId = state.colleges[0].id;
    picker.innerHTML = state.colleges.length
      ? state.colleges.map(c => `<option value="${c.id}" ${c.id === state.collegeId ? "selected" : ""}>${esc(c.name)} (${esc(c.code)})</option>`).join("")
      : `<option value="">No colleges yet</option>`;
    picker.onchange = () => { setCollege(Number(picker.value)); route(); };
  }

  function setCollege(id) {
    state.collegeId = id;
    Reios.store.set("reios_console_college", String(id));
    const picker = document.getElementById("college-picker");
    if (picker) picker.value = String(id);
  }

  // Adds ?college_id= for super admins on college-scoped endpoints
  function cq(params = {}) {
    return qs(isSuper ? Object.assign({ college_id: state.collegeId }, params) : params);
  }

  function needCollege() {
    if (isSuper && !state.collegeId) {
      view.innerHTML = `<div class="card empty">Create a college first under <a href="#colleges">Colleges &amp; Admins</a>.</div>`;
      return true;
    }
    return false;
  }

  function badge(text, color) { return `<span class="badge ${color || ""}">${esc(text)}</span>`; }

  function windowBadge(exam) {
    if (!exam.is_published) return badge("Draft");
    return { live: badge("Live", "green"), upcoming: badge("Scheduled", "blue"), ended: badge("Ended") }[exam.window];
  }

  function handleError(err) { if (err.message !== "redirecting") toast(err.message, "error", 6000); }

  function credentialsModal(title, creds, note) {
    const rows = creds.map(c => `<tr><td>${esc(c.roll_no || c.email || "")}</td><td>${esc(c.name || "")}</td><td><code>${esc(c.password)}</code></td></tr>`).join("");
    modal({
      title, wide: true,
      body: `<p class="muted">${esc(note || "Share these passwords with the users. They must change them at first login. They won't be shown again.")}</p>
             <div class="table-wrap"><table><thead><tr><th>Login</th><th>Name</th><th>Temporary password</th></tr></thead><tbody>${rows}</tbody></table></div>`,
      actions: [
        { label: "Download CSV", onClick: () => downloadCSV("credentials.csv", ["Login", "Name", "Password"], creds.map(c => [c.roll_no || c.email, c.name, c.password])) },
        { label: "Done", cls: "primary" },
      ],
    });
  }

  function formValues(root) {
    const out = {};
    root.querySelectorAll("[name]").forEach(el => {
      if (el.type === "checkbox") out[el.name] = el.checked;
      else out[el.name] = el.value;
    });
    return out;
  }

  function nullIfBlank(v) { return v === undefined || v === null || String(v).trim() === "" ? null : String(v).trim(); }

  // ── Router ──────────────────────────────────────────────────────────────
  async function route() {
    clearInterval(state.liveTimer);
    document.getElementById("sidebar").classList.remove("open");
    const [name, arg] = (location.hash.slice(1) || "overview").split("/");
    const navId = { exam: "exams", results: "exams", live: "exams" }[name] || name;
    renderNav(navId);
    view.innerHTML = `<div class="muted"><span class="spinner"></span> Loading…</div>`;
    try {
      const handler = VIEWS[name] || VIEWS.overview;
      await handler(arg);
    } catch (err) {
      handleError(err);
      view.innerHTML = `<div class="card empty">${esc(err.message)}</div>`;
    }
  }

  // ── Overview ────────────────────────────────────────────────────────────
  async function overviewView() {
    let html = "";
    if (isSuper) {
      const s = await api("GET", "/api/reios/super/stats");
      html += `<h1>Platform overview</h1>
        <div class="grid cols-4" style="margin-bottom:20px">
          ${stat("Colleges", `${s.active_colleges} / ${s.colleges}`, "active / total")}
          ${stat("College admins", s.college_admins)}
          ${stat("Students", s.students)}
          ${stat("Exams", s.exams)}
          ${stat("Attempts", s.attempts)}
          ${stat("Writing now", s.live_attempts)}
          ${stat("Global MCQs", s.global_mcqs)}
          ${stat("Global coding problems", s.global_problems)}
        </div>`;
    }
    if (!isSuper || state.collegeId) {
      const c = await api("GET", "/api/reios/admin/stats" + cq());
      html += `<h2>${esc(c.college.name)} <span class="muted small">code ${esc(c.college.code)}</span></h2>
        <div class="grid cols-4">
          ${stat("Students", c.college.max_students ? `${c.students} / ${c.college.max_students}` : c.students, `${c.active_students} active`)}
          ${stat("Exams", c.exams, `${c.live_exams} live · ${c.upcoming_exams} scheduled`)}
          ${stat("Writing now", c.live_attempts)}
          ${stat("Completed attempts", c.completed_attempts)}
          ${stat("Average score", c.average_percentage === null ? "—" : c.average_percentage + "%")}
          ${stat("MCQs available", c.mcqs)}
          ${stat("Coding problems", c.problems)}
          ${stat("Branches", c.branches.length, c.branches.join(", "))}
        </div>
        <div class="card" style="margin-top:20px">
          <h3>Getting started</h3>
          <ol class="muted" style="margin:0;padding-left:18px">
            <li>Add students under <a href="#students">Students</a> (one by one or CSV import).</li>
            <li>Build your question bank: <a href="#mcqs">MCQs</a> (aptitude, reasoning, verbal, technical) and <a href="#problems">coding problems</a>.</li>
            <li>Create an exam under <a href="#exams">Exams</a>, add questions, set the schedule and anti-cheat rules, then publish.</li>
            <li>Watch students live during the exam, then review results, export CSV and check code similarity.</li>
          </ol>
        </div>`;
    }
    view.innerHTML = html || `<div class="card empty">Create your first college under <a href="#colleges">Colleges &amp; Admins</a>.</div>`;
  }

  function stat(label, value, sub) {
    return `<div class="stat"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div>${sub ? `<div class="muted small">${esc(sub)}</div>` : ""}</div>`;
  }

  // ── Colleges (super admin) ──────────────────────────────────────────────
  async function collegesView() {
    await loadColleges();
    const rows = state.colleges.map(c => `
      <tr>
        <td><strong>${esc(c.name)}</strong><div class="muted small">${esc(c.city || "")}</div></td>
        <td><code>${esc(c.code)}</code></td>
        <td class="num">${c.student_count}${c.max_students ? ` / ${c.max_students}` : ""}</td>
        <td class="num">${c.admin_count}</td>
        <td class="num">${c.exam_count}</td>
        <td>${c.is_active ? badge("Active", "green") : badge("Disabled", "red")}</td>
        <td class="row" style="gap:6px">
          <button class="btn sm" data-admins="${c.id}">Admins</button>
          <button class="btn sm" data-edit="${c.id}">Edit</button>
          <button class="btn sm" data-open="${c.id}">Open</button>
        </td>
      </tr>`).join("");
    view.innerHTML = `
      <div class="row between"><h1>Colleges</h1><button class="btn primary" id="add-college">+ Add college</button></div>
      <p class="muted">Each college gets its own admins, students, exams and results. Students log in with the college code.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>College</th><th>Code</th><th class="num">Students</th><th class="num">Admins</th><th class="num">Exams</th><th>Status</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="7" class="empty">No colleges yet</td></tr>`}</tbody>
      </table></div>`;
    document.getElementById("add-college").onclick = () => collegeForm();
    view.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => collegeForm(state.colleges.find(c => c.id == b.dataset.edit)));
    view.querySelectorAll("[data-admins]").forEach(b => b.onclick = () => collegeAdmins(state.colleges.find(c => c.id == b.dataset.admins)));
    view.querySelectorAll("[data-open]").forEach(b => b.onclick = () => { setCollege(Number(b.dataset.open)); location.hash = "overview"; });
  }

  function collegeForm(college) {
    const c = college || {};
    const form = document.createElement("div");
    form.innerHTML = `
      <div class="form-grid">
        <div class="field"><label>College name *</label><input name="name" value="${esc(c.name || "")}"></div>
        <div class="field"><label>College code * (students type this at login)</label><input name="code" value="${esc(c.code || "")}" ${college ? "disabled" : ""} style="text-transform:uppercase"></div>
        <div class="field"><label>City</label><input name="city" value="${esc(c.city || "")}"></div>
        <div class="field"><label>Student limit (blank = unlimited)</label><input name="max_students" type="number" min="1" value="${esc(c.max_students || "")}"></div>
        <div class="field"><label>Contact email</label><input name="contact_email" value="${esc(c.contact_email || "")}"></div>
        <div class="field"><label>Contact phone</label><input name="contact_phone" value="${esc(c.contact_phone || "")}"></div>
      </div>
      ${college ? `<label class="check"><input type="checkbox" name="is_active" ${c.is_active ? "checked" : ""}> College is active (unticking blocks all its users from logging in)</label>` : ""}`;
    modal({
      title: college ? "Edit college" : "Add college", body: form,
      actions: [{ label: "Cancel" }, {
        label: "Save", cls: "primary", onClick: async close => {
          const v = formValues(form);
          const body = { name: v.name, city: nullIfBlank(v.city), contact_email: nullIfBlank(v.contact_email),
                         contact_phone: nullIfBlank(v.contact_phone), max_students: v.max_students ? Number(v.max_students) : null };
          try {
            if (college) await api("PATCH", `/api/reios/super/colleges/${college.id}`, Object.assign(body, { is_active: v.is_active }));
            else { const created = await api("POST", "/api/reios/super/colleges", Object.assign(body, { code: v.code })); setCollege(created.id); }
            close(); toast("College saved", "success"); collegesView();
          } catch (err) { handleError(err); }
        },
      }],
    });
  }

  async function collegeAdmins(college) {
    const body = document.createElement("div");
    const m = modal({ title: `Admins · ${college.name}`, body, wide: true });
    async function render() {
      const admins = await api("GET", `/api/reios/super/colleges/${college.id}/admins`);
      body.innerHTML = `
        <div class="table-wrap"><table>
          <thead><tr><th>Name</th><th>Email</th><th>Last login</th><th>Status</th><th></th></tr></thead>
          <tbody>${admins.map(a => `<tr>
            <td>${esc(a.name)}</td><td>${esc(a.email)}</td><td>${fmtDate(a.last_login_at)}</td>
            <td>${a.is_active ? badge("Active", "green") : badge("Disabled", "red")}</td>
            <td class="row" style="gap:6px">
              <button class="btn sm" data-reset="${a.id}">Reset password</button>
              <button class="btn sm ${a.is_active ? "danger" : ""}" data-toggle="${a.id}" data-active="${a.is_active}">${a.is_active ? "Disable" : "Enable"}</button>
            </td></tr>`).join("") || `<tr><td colspan="5" class="empty">No admins yet</td></tr>`}</tbody>
        </table></div>
        <h3 style="margin-top:18px">Add college admin</h3>
        <div class="form-grid" id="new-admin">
          <div class="field"><label>Name *</label><input name="name"></div>
          <div class="field"><label>Email * (login)</label><input name="email" type="email"></div>
          <div class="field"><label>Phone</label><input name="phone"></div>
          <div class="field"><label>Password (blank = generate)</label><input name="password" type="text" minlength="8"></div>
        </div>
        <button class="btn primary" id="create-admin">Create admin</button>`;
      body.querySelector("#create-admin").onclick = async () => {
        const v = formValues(body.querySelector("#new-admin"));
        try {
          const created = await api("POST", `/api/reios/super/colleges/${college.id}/admins`,
            { name: v.name, email: v.email, phone: nullIfBlank(v.phone), password: nullIfBlank(v.password) });
          credentialsModal("College admin created", [{ email: created.email, name: created.name, password: created.temporary_password }],
            `Share these login details with the admin. Login page: ${location.origin}${location.pathname.replace("console.html", "index.html")}?as=admin`);
          render();
        } catch (err) { handleError(err); }
      };
      body.querySelectorAll("[data-reset]").forEach(b => b.onclick = async () => {
        if (!await confirmBox("Reset password", "Generate a new temporary password for this admin?")) return;
        try {
          const r = await api("POST", `/api/reios/super/admins/${b.dataset.reset}/reset-password`);
          const a = admins.find(x => x.id == b.dataset.reset);
          credentialsModal("Password reset", [{ email: a.email, name: a.name, password: r.temporary_password }]);
        } catch (err) { handleError(err); }
      });
      body.querySelectorAll("[data-toggle]").forEach(b => b.onclick = async () => {
        try { await api("PATCH", `/api/reios/super/admins/${b.dataset.toggle}`, { is_active: b.dataset.active !== "true" }); render(); }
        catch (err) { handleError(err); }
      });
    }
    try { await render(); } catch (err) { handleError(err); m.close(); }
  }

  // ── Students ────────────────────────────────────────────────────────────
  const studentFilters = { q: "", branch: "", section: "", batch_year: "", page: 1 };

  async function studentsView() {
    if (needCollege()) return;
    const stats = await api("GET", "/api/reios/admin/stats" + cq());
    view.innerHTML = `
      <div class="row between"><h1>Students</h1>
        <div class="row">
          <button class="btn" id="import">Import CSV</button>
          <button class="btn primary" id="add">+ Add student</button>
        </div>
      </div>
      <div class="toolbar">
        <input id="f-q" placeholder="Search name, roll no, email" value="${esc(studentFilters.q)}">
        <select id="f-branch"><option value="">All branches</option>${stats.branches.map(b => `<option ${b === studentFilters.branch ? "selected" : ""}>${esc(b)}</option>`).join("")}</select>
        <input id="f-section" placeholder="Section" value="${esc(studentFilters.section)}" style="min-width:90px;width:90px">
        <input id="f-batch" placeholder="Batch year" value="${esc(studentFilters.batch_year)}" style="min-width:110px;width:110px">
        <button class="btn" id="apply">Filter</button>
        <span class="grow"></span>
        <span id="bulk" class="row hidden">
          <span class="muted small" id="bulk-count"></span>
          <button class="btn sm" data-bulk="reset">Reset passwords</button>
          <button class="btn sm" data-bulk="activate">Activate</button>
          <button class="btn sm danger" data-bulk="deactivate">Deactivate</button>
        </span>
      </div>
      <div id="students-table"></div>`;
    document.getElementById("add").onclick = () => studentForm();
    document.getElementById("import").onclick = importStudents;
    const apply = () => {
      Object.assign(studentFilters, { q: document.getElementById("f-q").value, branch: document.getElementById("f-branch").value,
        section: document.getElementById("f-section").value, batch_year: document.getElementById("f-batch").value, page: 1 });
      loadStudents();
    };
    document.getElementById("apply").onclick = apply;
    document.getElementById("f-q").addEventListener("keydown", e => { if (e.key === "Enter") apply(); });
    view.querySelectorAll("[data-bulk]").forEach(b => b.onclick = () => bulkStudents(b.dataset.bulk));
    await loadStudents();
  }

  function selectedStudentIds() { return [...view.querySelectorAll("[data-sel]:checked")].map(c => Number(c.dataset.sel)); }

  function updateBulkBar() {
    const n = selectedStudentIds().length;
    document.getElementById("bulk").classList.toggle("hidden", !n);
    document.getElementById("bulk-count").textContent = `${n} selected`;
  }

  async function loadStudents() {
    const pageSize = 50;
    const data = await api("GET", "/api/reios/admin/students" + cq({ ...studentFilters, page_size: pageSize }));
    const pages = Math.max(1, Math.ceil(data.total / pageSize));
    const rows = data.items.map(s => `
      <tr>
        <td><input type="checkbox" data-sel="${s.id}"></td>
        <td><strong>${esc(s.roll_no)}</strong></td>
        <td>${esc(s.name)}<div class="muted small">${esc(s.email || "")}</div></td>
        <td>${esc(s.branch || "—")}</td><td>${esc(s.section || "—")}</td><td>${esc(s.batch_year || "—")}</td>
        <td>${s.is_active ? (s.must_change_password ? badge("Not logged in yet", "amber") : badge("Active", "green")) : badge("Disabled", "red")}</td>
        <td class="row" style="gap:4px">
          <button class="btn sm" data-report="${s.id}">Report</button>
          <button class="btn sm" data-edit="${s.id}">Edit</button>
          <button class="btn sm" data-reset="${s.id}">Reset pwd</button>
          <button class="btn sm danger" data-del="${s.id}">Delete</button>
        </td>
      </tr>`).join("");
    const box = document.getElementById("students-table");
    box.innerHTML = `
      <div class="table-wrap"><table>
        <thead><tr><th><input type="checkbox" id="sel-all"></th><th>Roll no</th><th>Name</th><th>Branch</th><th>Section</th><th>Batch</th><th>Status</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="8" class="empty">No students found</td></tr>`}</tbody>
      </table></div>
      <div class="row between" style="margin-top:10px">
        <span class="muted small">${data.total} students</span>
        <span class="row"><button class="btn sm" id="prev" ${data.page <= 1 ? "disabled" : ""}>‹ Prev</button>
        <span class="small">Page ${data.page} of ${pages}</span>
        <button class="btn sm" id="next" ${data.page >= pages ? "disabled" : ""}>Next ›</button></span>
      </div>`;
    box.querySelector("#prev").onclick = () => { studentFilters.page--; loadStudents(); };
    box.querySelector("#next").onclick = () => { studentFilters.page++; loadStudents(); };
    box.querySelector("#sel-all").onchange = e => { box.querySelectorAll("[data-sel]").forEach(c => c.checked = e.target.checked); updateBulkBar(); };
    box.querySelectorAll("[data-sel]").forEach(c => c.onchange = updateBulkBar);
    box.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => studentForm(data.items.find(s => s.id == b.dataset.edit)));
    box.querySelectorAll("[data-report]").forEach(b => b.onclick = () => studentReport(b.dataset.report));
    box.querySelectorAll("[data-reset]").forEach(b => b.onclick = async () => {
      if (!await confirmBox("Reset password", "Generate a new temporary password for this student?")) return;
      try {
        const r = await api("POST", `/api/reios/admin/students/${b.dataset.reset}/reset-password` + cq());
        const s = data.items.find(x => x.id == b.dataset.reset);
        credentialsModal("Password reset", [{ roll_no: r.roll_no, name: s.name, password: r.temporary_password }]);
      } catch (err) { handleError(err); }
    });
    box.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      if (!await confirmBox("Delete student", "Delete this student permanently? Students with exam attempts can only be deactivated.", "Delete", true)) return;
      try { await api("DELETE", `/api/reios/admin/students/${b.dataset.del}` + cq()); toast("Student deleted", "success"); loadStudents(); }
      catch (err) { handleError(err); }
    });
    updateBulkBar();
  }

  async function bulkStudents(action) {
    const ids = selectedStudentIds();
    if (!ids.length) return;
    try {
      if (action === "reset") {
        if (!await confirmBox("Reset passwords", `Generate new passwords for ${ids.length} students?`)) return;
        const r = await api("POST", "/api/reios/admin/students/bulk-reset-passwords" + cq(), { ids });
        credentialsModal("New passwords", r.credentials);
      } else {
        await api("POST", "/api/reios/admin/students/bulk-status" + cq({ active: action === "activate" }), { ids });
        toast("Updated", "success");
      }
      loadStudents();
    } catch (err) { handleError(err); }
  }

  function studentForm(student) {
    const s = student || {};
    const form = document.createElement("div");
    form.innerHTML = `
      <div class="form-grid">
        <div class="field"><label>Roll number *</label><input name="roll_no" value="${esc(s.roll_no || "")}" ${student ? "disabled" : ""}></div>
        <div class="field"><label>Full name *</label><input name="name" value="${esc(s.name || "")}"></div>
        <div class="field"><label>Email</label><input name="email" type="email" value="${esc(s.email || "")}"></div>
        <div class="field"><label>Phone</label><input name="phone" value="${esc(s.phone || "")}"></div>
        <div class="field"><label>Branch (e.g. CSE, ECE)</label><input name="branch" value="${esc(s.branch || "")}"></div>
        <div class="field"><label>Section</label><input name="section" value="${esc(s.section || "")}"></div>
        <div class="field"><label>Batch / passing year</label><input name="batch_year" type="number" value="${esc(s.batch_year || "")}"></div>
        ${student ? "" : `<div class="field"><label>Password (blank = generate)</label><input name="password"></div>`}
      </div>
      ${student ? `<label class="check"><input type="checkbox" name="is_active" ${s.is_active ? "checked" : ""}> Account active</label>` : ""}`;
    modal({
      title: student ? "Edit student" : "Add student", body: form,
      actions: [{ label: "Cancel" }, {
        label: "Save", cls: "primary", onClick: async close => {
          const v = formValues(form);
          const body = { name: v.name, email: nullIfBlank(v.email), phone: nullIfBlank(v.phone), branch: nullIfBlank(v.branch),
                         section: nullIfBlank(v.section), batch_year: v.batch_year ? Number(v.batch_year) : null };
          try {
            if (student) { await api("PATCH", `/api/reios/admin/students/${student.id}` + cq(), Object.assign(body, { is_active: v.is_active })); toast("Saved", "success"); }
            else {
              const r = await api("POST", "/api/reios/admin/students" + cq(), Object.assign(body, { roll_no: v.roll_no, password: nullIfBlank(v.password) }));
              credentialsModal("Student added", [{ roll_no: r.roll_no, name: r.name, password: r.temporary_password }]);
            }
            close(); loadStudents();
          } catch (err) { handleError(err); }
        },
      }],
    });
  }

  function importStudents() {
    const form = document.createElement("div");
    form.innerHTML = `
      <p>Upload a CSV with these columns. Only <code>roll_no</code> and <code>name</code> are required; a blank password gets a generated one.</p>
      <pre>roll_no,name,email,phone,branch,section,batch_year,password
21A91A0501,Anil Kumar,anil@example.com,9876543210,CSE,A,2025,
21A91A0502,Bhavya Sri,,,CSE,A,2025,</pre>
      <button class="btn sm" id="tpl">Download template</button>
      <div class="field" style="margin-top:14px"><label>CSV file</label><input type="file" accept=".csv,text/csv" id="file"></div>
      <div id="import-result"></div>`;
    form.querySelector("#tpl").onclick = () => downloadCSV("students_template.csv",
      ["roll_no", "name", "email", "phone", "branch", "section", "batch_year", "password"],
      [["21A91A0501", "Anil Kumar", "anil@example.com", "9876543210", "CSE", "A", "2025", ""]]);
    modal({
      title: "Import students", body: form,
      actions: [{ label: "Close" }, {
        label: "Upload", cls: "primary", onClick: async () => {
          const file = form.querySelector("#file").files[0];
          if (!file) return toast("Choose a CSV file", "error");
          const fd = new FormData(); fd.append("file", file);
          try {
            const r = await api("POST", "/api/reios/admin/students/import" + cq(), fd);
            form.querySelector("#import-result").innerHTML = `
              <p><strong>${r.created}</strong> created, <strong>${r.failed}</strong> failed.</p>
              ${r.errors.length ? `<div class="table-wrap"><table><thead><tr><th>Line</th><th>Roll no</th><th>Error</th></tr></thead><tbody>
                ${r.errors.map(e => `<tr><td>${e.line}</td><td>${esc(e.roll_no || "")}</td><td>${esc(e.error)}</td></tr>`).join("")}</tbody></table></div>` : ""}`;
            if (r.credentials.length) credentialsModal(`${r.created} students imported`, r.credentials);
            loadStudents();
          } catch (err) { handleError(err); }
        },
      }],
    });
  }

  async function studentReport(id) {
    try {
      const r = await api("GET", `/api/reios/admin/students/${id}/report` + cq());
      const s = r.student;
      modal({
        title: `${s.name} (${s.roll_no})`, wide: true,
        body: `<dl class="kv"><dt>Branch</dt><dd>${esc(s.branch || "—")} ${esc(s.section || "")}</dd><dt>Batch</dt><dd>${esc(s.batch_year || "—")}</dd>
                 <dt>Email</dt><dd>${esc(s.email || "—")}</dd><dt>Last login</dt><dd>${fmtDate(s.last_login_at)}</dd></dl>
               <h3 style="margin-top:16px">Exam history</h3>
               <div class="table-wrap"><table><thead><tr><th>Exam</th><th>Date</th><th>Status</th><th class="num">Score</th><th class="num">%</th><th class="num">Violations</th><th></th></tr></thead>
               <tbody>${r.attempts.map(a => `<tr><td>${esc(a.exam_title)}</td><td>${fmtDate(a.started_at)}</td><td>${esc(a.status.replace("_", " "))}</td>
                 <td class="num">${a.total_score} / ${a.max_score}</td><td class="num">${a.percentage}</td><td class="num">${a.violations}</td>
                 <td><button class="btn sm" data-attempt="${a.attempt_id}">View</button></td></tr>`).join("") || `<tr><td colspan="7" class="empty">No exams taken yet</td></tr>`}</tbody></table></div>`,
      }).el.querySelectorAll("[data-attempt]").forEach(b => b.onclick = () => attemptDetail(b.dataset.attempt));
    } catch (err) { handleError(err); }
  }

  // ── MCQ bank ────────────────────────────────────────────────────────────
  const mcqFilters = { q: "", section: "", difficulty: "", source: "all", page: 1 };

  async function mcqsView() {
    state.meta = state.meta || await api("GET", "/api/reios/admin/meta");
    view.innerHTML = `
      <div class="row between"><h1>${isSuper ? "Global MCQ bank" : "MCQ questions"}</h1>
        <div class="row"><button class="btn" id="import">Import CSV</button><button class="btn primary" id="add">+ Add MCQ</button></div></div>
      <p class="muted">${isSuper ? "Questions here are shared with every college." : "Your college's questions plus the shared global bank. Global questions can be used in exams but only edited by the super admin."}</p>
      <div class="toolbar">
        <input id="q" placeholder="Search question text" value="${esc(mcqFilters.q)}">
        <select id="section"><option value="">All sections</option>${state.meta.sections.map(s => `<option ${s === mcqFilters.section ? "selected" : ""}>${esc(s)}</option>`).join("")}</select>
        <select id="difficulty"><option value="">Any difficulty</option>${state.meta.difficulties.map(d => `<option ${d === mcqFilters.difficulty ? "selected" : ""}>${d}</option>`).join("")}</select>
        ${isSuper ? "" : `<select id="source"><option value="all">Own + global</option><option value="own" ${mcqFilters.source === "own" ? "selected" : ""}>Own only</option><option value="global" ${mcqFilters.source === "global" ? "selected" : ""}>Global only</option></select>`}
        <button class="btn" id="apply">Filter</button>
      </div>
      <div id="mcq-table"></div>`;
    const apply = () => {
      Object.assign(mcqFilters, { q: document.getElementById("q").value, section: document.getElementById("section").value,
        difficulty: document.getElementById("difficulty").value, source: isSuper ? "all" : document.getElementById("source").value, page: 1 });
      loadMcqs();
    };
    document.getElementById("apply").onclick = apply;
    document.getElementById("q").addEventListener("keydown", e => { if (e.key === "Enter") apply(); });
    document.getElementById("add").onclick = () => mcqForm();
    document.getElementById("import").onclick = importMcqs;
    await loadMcqs();
  }

  async function loadMcqs() {
    const pageSize = 50;
    const data = await api("GET", "/api/reios/admin/mcqs" + qs({ ...mcqFilters, page_size: pageSize }));
    const pages = Math.max(1, Math.ceil(data.total / pageSize));
    const canEdit = q => isSuper || !q.is_global;
    const box = document.getElementById("mcq-table");
    box.innerHTML = `
      <div class="table-wrap"><table>
        <thead><tr><th>Question</th><th>Section</th><th>Level</th><th class="num">Marks</th><th></th></tr></thead>
        <tbody>${data.items.map(q => `<tr>
          <td style="max-width:560px">${esc(q.question_text.slice(0, 220))}${q.question_text.length > 220 ? "…" : ""}
            <div class="muted small">Answer: ${q.correct_options.map(i => String.fromCharCode(65 + i)).join(", ")} ${q.is_multi ? "· multiple correct" : ""} ${q.is_global && !isSuper ? "· " + badge("Global", "blue") : ""}</div></td>
          <td>${esc(q.section)}<div class="muted small">${esc(q.topic || "")}</div></td>
          <td>${esc(q.difficulty)}</td>
          <td class="num">+${q.marks}${q.negative_marks ? ` / −${q.negative_marks}` : ""}</td>
          <td class="row" style="gap:4px">${canEdit(q) ? `<button class="btn sm" data-edit="${q.id}">Edit</button><button class="btn sm danger" data-del="${q.id}">Delete</button>` : `<button class="btn sm" data-view="${q.id}">View</button>`}</td>
        </tr>`).join("") || `<tr><td colspan="5" class="empty">No questions yet</td></tr>`}</tbody>
      </table></div>
      <div class="row between" style="margin-top:10px"><span class="muted small">${data.total} questions</span>
        <span class="row"><button class="btn sm" id="prev" ${data.page <= 1 ? "disabled" : ""}>‹ Prev</button><span class="small">Page ${data.page} of ${pages}</span>
        <button class="btn sm" id="next" ${data.page >= pages ? "disabled" : ""}>Next ›</button></span></div>`;
    box.querySelector("#prev").onclick = () => { mcqFilters.page--; loadMcqs(); };
    box.querySelector("#next").onclick = () => { mcqFilters.page++; loadMcqs(); };
    box.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => mcqForm(data.items.find(q => q.id == b.dataset.edit)));
    box.querySelectorAll("[data-view]").forEach(b => b.onclick = () => mcqForm(data.items.find(q => q.id == b.dataset.view), true));
    box.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      if (!await confirmBox("Delete question", "Delete this question? If it's used in an exam it will be hidden from the bank instead.", "Delete", true)) return;
      try { await api("DELETE", `/api/reios/admin/mcqs/${b.dataset.del}`); toast("Deleted", "success"); loadMcqs(); } catch (err) { handleError(err); }
    });
  }

  function mcqForm(q, readOnly) {
    q = q || { section: mcqFilters.section || state.meta.sections[0], difficulty: "medium", options: ["", "", "", ""], correct_options: [0], is_multi: false, marks: 1, negative_marks: 0 };
    const form = document.createElement("div");
    form.innerHTML = `
      <div class="form-grid">
        <div class="field"><label>Section *</label><input name="section" list="sections" value="${esc(q.section)}">
          <datalist id="sections">${state.meta.sections.map(s => `<option>${esc(s)}</option>`).join("")}</datalist></div>
        <div class="field"><label>Topic</label><input name="topic" value="${esc(q.topic || "")}" placeholder="e.g. Percentages, Arrays"></div>
        <div class="field"><label>Difficulty</label><select name="difficulty">${state.meta.difficulties.map(d => `<option ${d === q.difficulty ? "selected" : ""}>${d}</option>`).join("")}</select></div>
        <div class="field"><label>Marks</label><input name="marks" type="number" step="0.25" min="0.25" value="${q.marks}"></div>
        <div class="field"><label>Negative marks (if exam uses negative marking)</label><input name="negative_marks" type="number" step="0.25" min="0" value="${q.negative_marks}"></div>
      </div>
      <div class="field"><label>Question * (Markdown supported)</label><textarea name="question_text" rows="4">${esc(q.question_text || "")}</textarea></div>
      <label class="check"><input type="checkbox" name="is_multi" ${q.is_multi ? "checked" : ""}> More than one correct option</label>
      <label>Options (tick the correct one${"(s)"})</label>
      <div id="opts"></div>
      <button class="btn sm" id="add-opt" type="button">+ Option</button>
      <div class="field" style="margin-top:12px"><label>Explanation (shown in review if enabled)</label><textarea name="explanation" rows="2">${esc(q.explanation || "")}</textarea></div>`;
    const opts = form.querySelector("#opts");
    let options = q.options.slice();
    let correct = new Set(q.correct_options);
    function renderOpts() {
      const multi = form.querySelector("[name=is_multi]").checked;
      opts.innerHTML = options.map((o, i) => `
        <div class="row" style="margin-bottom:6px;flex-wrap:nowrap">
          <input type="${multi ? "checkbox" : "radio"}" name="correct" data-i="${i}" ${correct.has(i) ? "checked" : ""}>
          <strong style="width:18px">${String.fromCharCode(65 + i)}</strong>
          <input data-opt="${i}" value="${esc(o)}">
          <button class="btn sm ghost" type="button" data-rm="${i}" ${options.length <= 2 ? "disabled" : ""}>✕</button>
        </div>`).join("");
      opts.querySelectorAll("[data-opt]").forEach(inp => inp.oninput = () => { options[inp.dataset.opt] = inp.value; });
      opts.querySelectorAll("[name=correct]").forEach(c => c.onchange = () => {
        if (!multi) correct = new Set();
        const i = Number(c.dataset.i);
        if (c.checked) correct.add(i); else correct.delete(i);
        if (!multi) renderOpts();
      });
      opts.querySelectorAll("[data-rm]").forEach(b => b.onclick = () => {
        const i = Number(b.dataset.rm);
        options.splice(i, 1);
        correct = new Set([...correct].filter(x => x !== i).map(x => x > i ? x - 1 : x));
        renderOpts();
      });
    }
    form.querySelector("[name=is_multi]").onchange = () => { if (!form.querySelector("[name=is_multi]").checked) correct = new Set([...correct].slice(0, 1)); renderOpts(); };
    form.querySelector("#add-opt").onclick = () => { if (options.length < 8) { options.push(""); renderOpts(); } };
    renderOpts();
    if (readOnly) form.querySelectorAll("input,select,textarea,button").forEach(el => el.disabled = true);
    modal({
      title: readOnly ? "Global question" : (q.id ? "Edit MCQ" : "Add MCQ"), body: form, wide: true,
      actions: readOnly ? [{ label: "Close" }] : [{ label: "Cancel" }, {
        label: "Save", cls: "primary", onClick: async close => {
          const v = formValues(form);
          const body = { section: v.section.trim(), topic: nullIfBlank(v.topic), difficulty: v.difficulty, question_text: v.question_text,
            options, correct_options: [...correct].sort(), is_multi: v.is_multi, explanation: nullIfBlank(v.explanation),
            marks: Number(v.marks), negative_marks: Number(v.negative_marks || 0) };
          try {
            if (q.id) await api("PUT", `/api/reios/admin/mcqs/${q.id}`, body); else await api("POST", "/api/reios/admin/mcqs", body);
            close(); toast("Saved", "success"); loadMcqs();
          } catch (err) { handleError(err); }
        },
      }],
    });
  }

  function importMcqs() {
    const form = document.createElement("div");
    form.innerHTML = `
      <p>CSV columns (option_e … option_h are optional). <code>correct</code> is a letter, or several letters like <code>A,C</code> for multiple-correct questions.</p>
      <pre>section,topic,difficulty,question,option_a,option_b,option_c,option_d,correct,marks,negative_marks,explanation
Quantitative Aptitude,Percentages,easy,What is 20% of 150?,20,25,30,35,C,1,0.25,20/100 x 150 = 30</pre>
      <button class="btn sm" id="tpl">Download template</button>
      <div class="field" style="margin-top:14px"><label>CSV file</label><input type="file" accept=".csv,text/csv" id="file"></div>
      <div id="import-result"></div>`;
    form.querySelector("#tpl").onclick = () => downloadCSV("mcq_template.csv",
      ["section", "topic", "difficulty", "question", "option_a", "option_b", "option_c", "option_d", "correct", "marks", "negative_marks", "explanation"],
      [["Quantitative Aptitude", "Percentages", "easy", "What is 20% of 150?", "20", "25", "30", "35", "C", "1", "0.25", "20/100 x 150 = 30"],
       ["Logical Reasoning", "Series", "medium", "Find the next number: 3, 9, 27, ?", "54", "81", "72", "90", "B", "1", "0.25", "Multiply by 3"],
       ["Technical", "OOP", "easy", "Which of these are OOP principles?", "Encapsulation", "Compilation", "Inheritance", "Recursion", "A,C", "2", "0", ""]]);
    modal({
      title: "Import MCQs", body: form,
      actions: [{ label: "Close" }, {
        label: "Upload", cls: "primary", onClick: async () => {
          const file = form.querySelector("#file").files[0];
          if (!file) return toast("Choose a CSV file", "error");
          const fd = new FormData(); fd.append("file", file);
          try {
            const r = await api("POST", "/api/reios/admin/mcqs/import", fd);
            form.querySelector("#import-result").innerHTML = `<p><strong>${r.created}</strong> imported, <strong>${r.failed}</strong> failed.</p>
              ${r.errors.map(e => `<div class="small" style="color:var(--danger)">Line ${e.line}: ${esc(e.error)}</div>`).join("")}`;
            loadMcqs();
          } catch (err) { handleError(err); }
        },
      }],
    });
  }

  // ── Coding problems ─────────────────────────────────────────────────────
  async function problemsView() {
    state.meta = state.meta || await api("GET", "/api/reios/admin/meta");
    const problems = await api("GET", "/api/reios/admin/problems");
    view.innerHTML = `
      <div class="row between"><h1>${isSuper ? "Global coding problems" : "Coding problems"}</h1><button class="btn primary" id="add">+ Add problem</button></div>
      <p class="muted">Each problem has visible sample tests (students can run against them) and hidden tests (used for scoring; marks are given in proportion to hidden tests passed).</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Title</th><th>Level</th><th class="num">Marks</th><th class="num">Sample</th><th class="num">Hidden</th><th>Time limit</th><th></th></tr></thead>
        <tbody>${problems.map(p => `<tr>
          <td><strong>${esc(p.title)}</strong> ${p.is_global && !isSuper ? badge("Global", "blue") : ""}</td><td>${esc(p.difficulty)}</td>
          <td class="num">${p.marks}</td><td class="num">${p.sample_count}</td>
          <td class="num">${p.hidden_count || `<span class="badge amber">0</span>`}</td><td>${p.time_limit_seconds}s</td>
          <td class="row" style="gap:4px">
            <button class="btn sm" data-verify="${p.id}">Test solution</button>
            ${isSuper || !p.is_global ? `<button class="btn sm" data-edit="${p.id}">Edit</button><button class="btn sm danger" data-del="${p.id}">Delete</button>` : ""}
          </td></tr>`).join("") || `<tr><td colspan="7" class="empty">No coding problems yet</td></tr>`}</tbody>
      </table></div>`;
    document.getElementById("add").onclick = () => problemForm();
    view.querySelectorAll("[data-edit]").forEach(b => b.onclick = async () => problemForm(await api("GET", `/api/reios/admin/problems/${b.dataset.edit}`)));
    view.querySelectorAll("[data-verify]").forEach(b => b.onclick = () => verifyProblem(b.dataset.verify));
    view.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      if (!await confirmBox("Delete problem", "Delete this problem? If it's used in an exam it will be hidden instead.", "Delete", true)) return;
      try { await api("DELETE", `/api/reios/admin/problems/${b.dataset.del}`); toast("Deleted", "success"); problemsView(); } catch (err) { handleError(err); }
    });
  }

  function testRows(tests, kind) {
    return tests.map((t, i) => `
      <div class="card" style="padding:10px;margin-bottom:8px" data-test="${kind}">
        <div class="row between"><strong class="small">${kind === "sample" ? "Sample" : "Hidden"} test ${i + 1}</strong><button class="btn sm ghost" type="button" data-rm-test>✕</button></div>
        <div class="grid cols-2" style="gap:8px">
          <div><label>Input</label><textarea class="mono" data-in rows="3">${esc(t.input || "")}</textarea></div>
          <div><label>Expected output</label><textarea class="mono" data-out rows="3">${esc(t.output || "")}</textarea></div>
        </div>
        ${kind === "sample" ? `<label style="margin-top:6px">Explanation</label><input data-expl value="${esc(t.explanation || "")}">` : ""}
      </div>`).join("");
  }

  function problemForm(p) {
    p = p || { difficulty: "medium", marks: 10, time_limit_seconds: 5, sample_tests: [{ input: "", output: "" }], hidden_tests: [{ input: "", output: "" }], starter_code: {} };
    const form = document.createElement("div");
    form.innerHTML = `
      <div class="form-grid">
        <div class="field"><label>Title *</label><input name="title" value="${esc(p.title || "")}"></div>
        <div class="field"><label>Difficulty</label><select name="difficulty">${state.meta.difficulties.map(d => `<option ${d === p.difficulty ? "selected" : ""}>${d}</option>`).join("")}</select></div>
        <div class="field"><label>Marks</label><input name="marks" type="number" min="1" value="${p.marks}"></div>
        <div class="field"><label>Time limit per test (seconds)</label><input name="time_limit_seconds" type="number" min="1" max="20" value="${p.time_limit_seconds}"></div>
      </div>
      <div class="field"><label>Problem statement * (Markdown)</label><textarea name="statement" rows="6">${esc(p.statement || "")}</textarea></div>
      <div class="grid cols-2" style="gap:0 14px">
        <div class="field"><label>Input format</label><textarea name="input_format" rows="2">${esc(p.input_format || "")}</textarea></div>
        <div class="field"><label>Output format</label><textarea name="output_format" rows="2">${esc(p.output_format || "")}</textarea></div>
      </div>
      <div class="field"><label>Constraints</label><textarea name="constraints" rows="2">${esc(p.constraints || "")}</textarea></div>
      <h3>Sample tests <span class="muted small">(visible to students)</span></h3>
      <div id="samples">${testRows(p.sample_tests, "sample")}</div><button class="btn sm" type="button" id="add-sample">+ Sample test</button>
      <h3 style="margin-top:16px">Hidden tests <span class="muted small">(used for scoring)</span></h3>
      <div id="hidden">${testRows(p.hidden_tests, "hidden")}</div><button class="btn sm" type="button" id="add-hidden">+ Hidden test</button>
      <h3 style="margin-top:16px">Starter code <span class="muted small">(optional, per language)</span></h3>
      <div class="tabs" id="starter-tabs">${state.meta.languages.map((l, i) => `<button type="button" data-lang="${l}" class="${i ? "" : "active"}">${LANG_LABELS[l]}</button>`).join("")}</div>
      <textarea class="mono" id="starter" rows="6"></textarea>`;
    const starter = Object.assign({}, p.starter_code || {});
    let lang = state.meta.languages[0];
    const starterEl = form.querySelector("#starter");
    starterEl.value = starter[lang] || "";
    starterEl.oninput = () => { starter[lang] = starterEl.value; };
    form.querySelectorAll("#starter-tabs button").forEach(b => b.onclick = () => {
      lang = b.dataset.lang; starterEl.value = starter[lang] || "";
      form.querySelectorAll("#starter-tabs button").forEach(x => x.classList.toggle("active", x === b));
    });
    const bindRemove = () => form.querySelectorAll("[data-rm-test]").forEach(b => b.onclick = () => b.closest("[data-test]").remove());
    bindRemove();
    form.querySelector("#add-sample").onclick = () => { form.querySelector("#samples").insertAdjacentHTML("beforeend", testRows([{}], "sample")); bindRemove(); };
    form.querySelector("#add-hidden").onclick = () => { form.querySelector("#hidden").insertAdjacentHTML("beforeend", testRows([{}], "hidden")); bindRemove(); };
    const collect = kind => [...form.querySelectorAll(`[data-test="${kind}"]`)].map(c => {
      const t = { input: c.querySelector("[data-in]").value, output: c.querySelector("[data-out]").value };
      const e = c.querySelector("[data-expl]"); if (e && e.value.trim()) t.explanation = e.value.trim();
      return t;
    }).filter(t => t.output.trim() !== "" || t.input.trim() !== "");
    modal({
      title: p.id ? "Edit coding problem" : "Add coding problem", body: form, wide: true,
      actions: [{ label: "Cancel" }, {
        label: "Save", cls: "primary", onClick: async close => {
          const v = {};
          ["title", "difficulty", "marks", "time_limit_seconds", "statement", "input_format", "output_format", "constraints"]
            .forEach(n => v[n] = form.querySelector(`[name=${n}]`).value);
          const body = { title: v.title, difficulty: v.difficulty, marks: Number(v.marks), time_limit_seconds: Number(v.time_limit_seconds),
            statement: v.statement, input_format: nullIfBlank(v.input_format), output_format: nullIfBlank(v.output_format),
            constraints: nullIfBlank(v.constraints), sample_tests: collect("sample"), hidden_tests: collect("hidden"),
            starter_code: Object.fromEntries(Object.entries(starter).filter(([, c]) => c && c.trim())) };
          try {
            if (p.id) await api("PUT", `/api/reios/admin/problems/${p.id}`, body); else await api("POST", "/api/reios/admin/problems", body);
            close(); toast("Saved", "success"); problemsView();
          } catch (err) { handleError(err); }
        },
      }],
    });
  }

  function verifyProblem(id) {
    const form = document.createElement("div");
    form.innerHTML = `
      <p class="muted">Paste a correct reference solution to check that every sample and hidden test has the right expected output.</p>
      <div class="field"><label>Language</label><select id="lang">${state.meta.languages.map(l => `<option value="${l}">${LANG_LABELS[l]}</option>`).join("")}</select></div>
      <textarea class="mono" id="code" rows="12" placeholder="Reference solution"></textarea>
      <div id="verify-result" style="margin-top:12px"></div>`;
    modal({
      title: "Test with reference solution", body: form, wide: true,
      actions: [{ label: "Close" }, {
        label: "Run all tests", cls: "primary", onClick: async () => {
          const out = form.querySelector("#verify-result");
          out.innerHTML = `<span class="spinner"></span> Running…`;
          try {
            const r = await api("POST", `/api/reios/admin/problems/${id}/verify`, { language: form.querySelector("#lang").value, code: form.querySelector("#code").value });
            out.innerHTML = `<p><strong>${r.passed} / ${r.total}</strong> tests passed</p>` + r.results.map((t, i) => `
              <div class="card" style="padding:10px;margin-bottom:6px">
                ${t.passed ? badge("Pass", "green") : badge("Fail", "red")} <span class="small muted">${t.kind} test · ${t.time_ms} ms</span>
                ${t.passed ? "" : `<div class="grid cols-2" style="gap:8px"><div><label>Expected</label><pre>${esc(t.expected)}</pre></div><div><label>Got</label><pre>${esc(t.actual)}${t.stderr ? "\n" + esc(t.stderr) : ""}</pre></div></div>`}
              </div>`).join("");
          } catch (err) { out.innerHTML = ""; handleError(err); }
        },
      }],
    });
  }

  // ── Exams ───────────────────────────────────────────────────────────────
  async function examsView() {
    if (needCollege()) return;
    const exams = await api("GET", "/api/reios/admin/exams" + cq());
    view.innerHTML = `
      <div class="row between"><h1>Exams</h1><button class="btn primary" id="add">+ Create exam</button></div>
      <div class="table-wrap"><table>
        <thead><tr><th>Exam</th><th>Window</th><th>Duration</th><th>Questions</th><th>Status</th><th>Attempts</th><th></th></tr></thead>
        <tbody>${exams.map(e => `<tr>
          <td><strong>${esc(e.title)}</strong>${e.branch_filter ? `<div class="muted small">Branches: ${esc(e.branch_filter)}</div>` : ""}</td>
          <td class="small">${fmtDate(e.start_at)}<br>→ ${fmtDate(e.end_at)}</td>
          <td>${e.duration_minutes} min</td>
          <td>${e.mcq_count} MCQ · ${e.coding_count} coding<div class="muted small">${e.max_score} marks</div></td>
          <td>${windowBadge(e)}</td>
          <td>${e.attempts.submitted} done${e.attempts.in_progress ? ` · <strong>${e.attempts.in_progress} writing</strong>` : ""}</td>
          <td class="row" style="gap:4px">
            <a class="btn sm" href="#exam/${e.id}">Edit</a>
            ${e.is_published && e.window === "live" ? `<a class="btn sm success" href="#live/${e.id}">Live</a>` : ""}
            <a class="btn sm" href="#results/${e.id}">Results</a>
          </td></tr>`).join("") || `<tr><td colspan="7" class="empty">No exams yet</td></tr>`}</tbody>
      </table></div>`;
    document.getElementById("add").onclick = () => examSettingsForm();
  }

  function examSettingsForm(exam) {
    const now = new Date();
    const e = exam || { duration_minutes: 60, start_at: new Date(now.getTime() + 3600e3), end_at: new Date(now.getTime() + 3 * 3600e3),
      shuffle_questions: true, shuffle_options: true, negative_marking: false, require_fullscreen: true, block_copy_paste: true,
      max_violations: 3, show_results: true, show_answers: false, pass_percentage: 40, allowed_languages: null };
    const langs = e.allowed_languages || state.meta.languages;
    const form = document.createElement("div");
    form.innerHTML = `
      <div class="field"><label>Title *</label><input name="title" value="${esc(e.title || "")}" placeholder="e.g. TCS NQT Mock Test 1"></div>
      <div class="field"><label>Description</label><input name="description" value="${esc(e.description || "")}"></div>
      <div class="form-grid">
        <div class="field"><label>Opens at *</label><input name="start_at" type="datetime-local" value="${toLocalInput(e.start_at)}"></div>
        <div class="field"><label>Closes at *</label><input name="end_at" type="datetime-local" value="${toLocalInput(e.end_at)}"></div>
        <div class="field"><label>Duration (minutes) *</label><input name="duration_minutes" type="number" min="1" value="${e.duration_minutes}"></div>
        <div class="field"><label>Pass percentage</label><input name="pass_percentage" type="number" min="0" max="100" value="${e.pass_percentage}"></div>
      </div>
      <p class="muted small" style="margin-top:-6px">Students can start any time between "opens" and "closes". Each student gets the full duration, but never past the closing time.</p>
      <h3>Who can take it <span class="muted small">(comma-separated, blank = all students)</span></h3>
      <div class="form-grid">
        <div class="field"><label>Branches</label><input name="branch_filter" value="${esc(e.branch_filter || "")}" placeholder="CSE, ECE"></div>
        <div class="field"><label>Batch years</label><input name="batch_filter" value="${esc(e.batch_filter || "")}" placeholder="2025"></div>
        <div class="field"><label>Sections</label><input name="section_filter" value="${esc(e.section_filter || "")}" placeholder="A, B"></div>
      </div>
      <h3>Anti-cheat</h3>
      <label class="check"><input type="checkbox" name="require_fullscreen" ${e.require_fullscreen ? "checked" : ""}> Require fullscreen (leaving fullscreen is a violation)</label>
      <label class="check"><input type="checkbox" name="block_copy_paste" ${e.block_copy_paste ? "checked" : ""}> Block copy, paste, right-click and developer tools</label>
      <label class="check"><input type="checkbox" name="shuffle_questions" ${e.shuffle_questions ? "checked" : ""}> Shuffle question order per student</label>
      <label class="check"><input type="checkbox" name="shuffle_options" ${e.shuffle_options ? "checked" : ""}> Shuffle MCQ options per student</label>
      <div class="field" style="max-width:280px;margin-top:8px"><label>Auto-submit after this many violations</label><input name="max_violations" type="number" min="1" max="50" value="${e.max_violations}"></div>
      <h3>Scoring & results</h3>
      <label class="check"><input type="checkbox" name="negative_marking" ${e.negative_marking ? "checked" : ""}> Negative marking for wrong MCQ answers</label>
      <label class="check"><input type="checkbox" name="show_results" ${e.show_results ? "checked" : ""}> Show score to students after they submit</label>
      <label class="check"><input type="checkbox" name="show_answers" ${e.show_answers ? "checked" : ""}> Show correct answers and explanations in the review</label>
      <h3>Coding languages allowed</h3>
      <div class="pill-list">${state.meta.languages.map(l => `<label class="check" style="margin-right:10px"><input type="checkbox" data-lang="${l}" ${langs.includes(l) ? "checked" : ""}> ${LANG_LABELS[l]}</label>`).join("")}</div>
      <div class="field" style="margin-top:12px"><label>Instructions shown before the exam (Markdown)</label>
        <textarea name="instructions" rows="5">${esc(e.instructions || "")}</textarea></div>`;
    modal({
      title: exam ? "Exam settings" : "Create exam", body: form, wide: true,
      actions: [{ label: "Cancel" }, {
        label: exam ? "Save" : "Create & add questions", cls: "primary", onClick: async close => {
          const v = formValues(form);
          const allowed = [...form.querySelectorAll("[data-lang]:checked")].map(c => c.dataset.lang);
          const body = { title: v.title, description: nullIfBlank(v.description), instructions: nullIfBlank(v.instructions),
            start_at: fromLocalInput(v.start_at), end_at: fromLocalInput(v.end_at), duration_minutes: Number(v.duration_minutes),
            branch_filter: nullIfBlank(v.branch_filter), batch_filter: nullIfBlank(v.batch_filter), section_filter: nullIfBlank(v.section_filter),
            shuffle_questions: v.shuffle_questions, shuffle_options: v.shuffle_options, negative_marking: v.negative_marking,
            require_fullscreen: v.require_fullscreen, block_copy_paste: v.block_copy_paste, max_violations: Number(v.max_violations),
            show_results: v.show_results, show_answers: v.show_answers, pass_percentage: Number(v.pass_percentage),
            allowed_languages: allowed.length === state.meta.languages.length ? null : allowed };
          if (!allowed.length) return toast("Allow at least one language", "error");
          try {
            const saved = exam ? await api("PUT", `/api/reios/admin/exams/${exam.id}` + cq(), body) : await api("POST", "/api/reios/admin/exams" + cq(), body);
            close(); toast("Saved", "success");
            if (location.hash === `#exam/${saved.id}`) route(); else location.hash = `exam/${saved.id}`;
          } catch (err) { handleError(err); }
        },
      }],
    });
  }

  async function examBuilderView(id) {
    if (needCollege()) return;
    state.meta = state.meta || await api("GET", "/api/reios/admin/meta");
    const exam = await api("GET", `/api/reios/admin/exams/${id}` + cq());
    const locked = exam.attempts.in_progress + exam.attempts.submitted > 0;
    let items = exam.items.map(i => ({ item_type: i.item_type, question_id: i.question_id, section: i.section, marks: i.marks,
      title: i.title, difficulty: i.difficulty, effective_marks: i.effective_marks }));
    let dirty = false;

    view.innerHTML = `
      <div class="row between">
        <div><a href="#exams" class="small">← Exams</a><h1 style="margin-top:4px">${esc(exam.title)} ${windowBadge(exam)}</h1></div>
        <div class="row">
          <button class="btn" id="settings">Settings</button>
          <button class="btn" id="dup">Duplicate</button>
          ${exam.attempts.in_progress + exam.attempts.submitted ? "" : `<button class="btn danger" id="del">Delete</button>`}
          <button class="btn ${exam.is_published ? "" : "primary"}" id="publish">${exam.is_published ? "Unpublish" : "Publish"}</button>
        </div>
      </div>
      <div class="card">
        <dl class="kv">
          <dt>Window</dt><dd>${fmtDate(exam.start_at)} → ${fmtDate(exam.end_at)}</dd>
          <dt>Duration</dt><dd>${exam.duration_minutes} minutes</dd>
          <dt>Audience</dt><dd>${esc([exam.branch_filter && "Branches " + exam.branch_filter, exam.batch_filter && "Batch " + exam.batch_filter, exam.section_filter && "Sections " + exam.section_filter].filter(Boolean).join(" · ") || "All students")}</dd>
          <dt>Anti-cheat</dt><dd>${[exam.require_fullscreen && "Fullscreen", exam.block_copy_paste && "No copy/paste", exam.shuffle_questions && "Shuffled questions", exam.shuffle_options && "Shuffled options", `auto-submit at ${exam.max_violations} violations`].filter(Boolean).join(" · ")}</dd>
          <dt>Scoring</dt><dd>${exam.negative_marking ? "Negative marking on" : "No negative marking"} · pass at ${exam.pass_percentage}%</dd>
        </dl>
      </div>
      <div class="card">
        <div class="row between"><h2 style="margin:0">Questions <span class="muted small" id="totals"></span></h2>
          ${locked ? `<span class="badge amber">Locked: students have started</span>` : `<div class="row">
            <button class="btn sm" id="add-mcq">+ MCQs</button><button class="btn sm" id="add-random">+ Random MCQs</button>
            <button class="btn sm" id="add-coding">+ Coding</button><button class="btn sm primary" id="save-items" disabled>Save questions</button></div>`}
        </div>
        <div id="items" style="margin-top:12px"></div>
      </div>`;

    const itemsBox = document.getElementById("items");
    function renderItems() {
      const sections = [];
      items.forEach(i => { if (!sections.includes(i.section)) sections.push(i.section); });
      const total = items.reduce((s, i) => s + Number(i.marks || i.effective_marks || 0), 0);
      document.getElementById("totals").textContent = `${items.length} questions · ${Math.round(total * 100) / 100} marks`;
      itemsBox.innerHTML = items.length ? sections.map(sec => `
        <h3 style="margin-top:14px">${esc(sec)} <span class="muted small">${items.filter(i => i.section === sec).length} questions</span></h3>
        <div class="table-wrap"><table><tbody>${items.map((i, idx) => i.section !== sec ? "" : `
          <tr><td style="width:70px">${badge(i.item_type === "mcq" ? "MCQ" : "Code", i.item_type === "mcq" ? "" : "blue")}</td>
          <td>${esc(i.title)} <span class="muted small">${esc(i.difficulty || "")}</span></td>
          <td style="width:150px;white-space:nowrap">${locked ? `<span class="muted small">${i.marks || i.effective_marks} marks</span>` :
            `<input type="number" step="0.25" min="0.25" placeholder="${i.effective_marks}" value="${i.marks || ""}" data-marks="${idx}" style="width:80px" title="Marks (blank = question default)"> marks`}</td>
          <td style="width:120px;white-space:nowrap">${locked ? "" : `<button class="btn sm ghost" data-up="${idx}" title="Move up">↑</button><button class="btn sm ghost" data-down="${idx}" title="Move down">↓</button><button class="btn sm ghost" data-rm="${idx}" title="Remove">✕</button>`}</td></tr>`).join("")}
        </tbody></table></div>`).join("") : `<div class="empty">No questions yet. Add MCQs (aptitude, reasoning, verbal, technical) and coding problems.</div>`;
      itemsBox.querySelectorAll("[data-marks]").forEach(inp => inp.oninput = () => { items[inp.dataset.marks].marks = inp.value ? Number(inp.value) : null; markDirty(); });
      itemsBox.querySelectorAll("[data-rm]").forEach(b => b.onclick = () => { items.splice(Number(b.dataset.rm), 1); markDirty(); renderItems(); });
      itemsBox.querySelectorAll("[data-up],[data-down]").forEach(b => b.onclick = () => {
        const idx = Number(b.dataset.up ?? b.dataset.down);
        const dir = b.dataset.up !== undefined ? -1 : 1;
        let j = idx + dir;
        while (j >= 0 && j < items.length && items[j].section !== items[idx].section) j += dir;
        if (j < 0 || j >= items.length) return;
        [items[idx], items[j]] = [items[j], items[idx]];
        markDirty(); renderItems();
      });
    }
    function markDirty() { dirty = true; const b = document.getElementById("save-items"); if (b) b.disabled = false; }
    function addItems(newOnes) {
      let added = 0;
      newOnes.forEach(n => { if (!items.some(i => i.item_type === n.item_type && i.question_id === n.question_id)) { items.push(n); added++; } });
      // keep sections grouped
      const order = []; items.forEach(i => { if (!order.includes(i.section)) order.push(i.section); });
      items.sort((a, b) => order.indexOf(a.section) - order.indexOf(b.section));
      if (added) { markDirty(); renderItems(); toast(`${added} added`, "success"); }
      else toast("Already in the exam");
    }
    renderItems();

    document.getElementById("settings").onclick = () => examSettingsForm(exam);
    document.getElementById("publish").onclick = async () => {
      if (dirty) return toast("Save the question list first", "error");
      try { await api("POST", `/api/reios/admin/exams/${id}/publish` + cq({ publish: !exam.is_published }));
        toast(exam.is_published ? "Unpublished" : "Published. Eligible students can now see it", "success"); route(); }
      catch (err) { handleError(err); }
    };
    document.getElementById("dup").onclick = async () => {
      try { const c = await api("POST", `/api/reios/admin/exams/${id}/duplicate` + cq()); toast("Copy created", "success"); location.hash = `exam/${c.id}`; }
      catch (err) { handleError(err); }
    };
    const del = document.getElementById("del");
    if (del) del.onclick = async () => {
      if (!await confirmBox("Delete exam", "Delete this exam permanently?", "Delete", true)) return;
      try { await api("DELETE", `/api/reios/admin/exams/${id}` + cq()); location.hash = "exams"; } catch (err) { handleError(err); }
    };
    if (locked) return;

    document.getElementById("save-items").onclick = async () => {
      try {
        await api("PUT", `/api/reios/admin/exams/${id}/items` + cq(), { items: items.map(i => ({ item_type: i.item_type, question_id: i.question_id, section: i.section, marks: i.marks || null })) });
        dirty = false; toast("Questions saved", "success"); route();
      } catch (err) { handleError(err); }
    };
    document.getElementById("add-mcq").onclick = () => pickMcqs(addItems);
    document.getElementById("add-coding").onclick = () => pickProblems(addItems);
    document.getElementById("add-random").onclick = () => {
      const form = document.createElement("div");
      form.innerHTML = `<div class="form-grid">
        <div class="field"><label>Section</label><select id="r-sec">${state.meta.sections.filter(s => s !== "Coding").map(s => `<option>${esc(s)}</option>`).join("")}</select></div>
        <div class="field"><label>How many</label><input id="r-count" type="number" min="1" value="10"></div>
        <div class="field"><label>Difficulty</label><select id="r-diff"><option value="">Any</option>${state.meta.difficulties.map(d => `<option>${d}</option>`).join("")}</select></div></div>`;
      modal({ title: "Add random MCQs from the bank", body: form, actions: [{ label: "Cancel" }, { label: "Add", cls: "primary", onClick: async close => {
        try {
          const qs_ = await api("POST", `/api/reios/admin/exams/${id}/random-mcqs` + cq(), { section: form.querySelector("#r-sec").value,
            count: Number(form.querySelector("#r-count").value), difficulty: form.querySelector("#r-diff").value || null });
          if (!qs_.length) return toast("No matching questions in the bank", "error");
          addItems(qs_.map(q => ({ item_type: "mcq", question_id: q.id, section: q.section, marks: null, title: q.question_text.slice(0, 140), difficulty: q.difficulty, effective_marks: q.marks })));
          close();
        } catch (err) { handleError(err); }
      } }] });
    };
  }

  function pickMcqs(onAdd) {
    const body = document.createElement("div");
    const f = { q: "", section: "", difficulty: "", page: 1 };
    body.innerHTML = `<div class="toolbar">
        <input id="pq" placeholder="Search"><select id="psec"><option value="">All sections</option>${state.meta.sections.map(s => `<option>${esc(s)}</option>`).join("")}</select>
        <select id="pdiff"><option value="">Any difficulty</option>${state.meta.difficulties.map(d => `<option>${d}</option>`).join("")}</select>
        <button class="btn" id="pgo">Search</button></div><div id="plist"></div>`;
    let current = [];
    async function load() {
      const d = await api("GET", "/api/reios/admin/mcqs" + cq({ ...f, page_size: 100 }));
      current = d.items;
      body.querySelector("#plist").innerHTML = `<div class="table-wrap"><table><thead><tr><th><input type="checkbox" id="pall"></th><th>Question</th><th>Section</th><th>Level</th></tr></thead><tbody>
        ${d.items.map(q => `<tr><td><input type="checkbox" data-pick="${q.id}"></td><td>${esc(q.question_text.slice(0, 160))}</td><td>${esc(q.section)}</td><td>${esc(q.difficulty)}</td></tr>`).join("") || `<tr><td colspan="4" class="empty">No questions</td></tr>`}
        </tbody></table></div><p class="muted small">${d.total} matching${d.total > 100 ? " (showing first 100, refine the search)" : ""}</p>`;
      body.querySelector("#pall").onchange = e => body.querySelectorAll("[data-pick]").forEach(c => c.checked = e.target.checked);
    }
    body.querySelector("#pgo").onclick = () => { f.q = body.querySelector("#pq").value; f.section = body.querySelector("#psec").value; f.difficulty = body.querySelector("#pdiff").value; load().catch(handleError); };
    load().catch(handleError);
    modal({ title: "Add MCQs", body, wide: true, actions: [{ label: "Cancel" }, { label: "Add selected", cls: "primary", onClick: close => {
      const ids = [...body.querySelectorAll("[data-pick]:checked")].map(c => Number(c.dataset.pick));
      onAdd(current.filter(q => ids.includes(q.id)).map(q => ({ item_type: "mcq", question_id: q.id, section: q.section, marks: null,
        title: q.question_text.slice(0, 140), difficulty: q.difficulty, effective_marks: q.marks })));
      close();
    } }] });
  }

  async function pickProblems(onAdd) {
    try {
      const problems = await api("GET", "/api/reios/admin/problems" + cq());
      const body = `<div class="table-wrap"><table><thead><tr><th></th><th>Problem</th><th>Level</th><th class="num">Marks</th><th class="num">Hidden tests</th></tr></thead><tbody>
        ${problems.map(p => `<tr><td><input type="checkbox" data-pick="${p.id}"></td><td>${esc(p.title)}</td><td>${esc(p.difficulty)}</td><td class="num">${p.marks}</td><td class="num">${p.hidden_count}</td></tr>`).join("") || `<tr><td colspan="5" class="empty">No coding problems. Add some under Coding Problems.</td></tr>`}
        </tbody></table></div>`;
      const m = modal({ title: "Add coding problems", body, wide: true, actions: [{ label: "Cancel" }, { label: "Add selected", cls: "primary", onClick: close => {
        const ids = [...m.el.querySelectorAll("[data-pick]:checked")].map(c => Number(c.dataset.pick));
        onAdd(problems.filter(p => ids.includes(p.id)).map(p => ({ item_type: "coding", question_id: p.id, section: "Coding", marks: null,
          title: p.title, difficulty: p.difficulty, effective_marks: p.marks })));
        close();
      } }] });
    } catch (err) { handleError(err); }
  }

  // ── Results ─────────────────────────────────────────────────────────────
  async function resultsView(id) {
    if (needCollege()) return;
    const data = await api("GET", `/api/reios/admin/exams/${id}/results` + cq());
    const s = data.summary;
    const sections = [...new Set(data.results.flatMap(r => Object.keys(r.section_scores)))].sort();
    view.innerHTML = `
      <div class="row between">
        <div><a href="#exams" class="small">← Exams</a><h1 style="margin-top:4px">${esc(data.exam.title)} · Results ${windowBadge(data.exam)}</h1></div>
        <div class="row">
          ${data.exam.window === "live" ? `<a class="btn success" href="#live/${id}">Live monitor</a>` : ""}
          <button class="btn" id="similarity">Code similarity</button>
          <button class="btn primary" id="export">Export CSV</button>
        </div>
      </div>
      <div class="grid cols-4" style="margin-bottom:16px">
        ${stat("Eligible", s.eligible)} ${stat("Completed", s.completed, s.in_progress ? `${s.in_progress} still writing` : "")}
        ${stat("Absent", s.not_attempted)} ${stat("Average", s.average_percentage === null ? "—" : s.average_percentage + "%", s.highest_percentage !== null ? `top ${s.highest_percentage}%` : "")}
        ${stat("Passed", s.pass_count, `pass mark ${data.exam.pass_percentage}%`)} ${stat("Flagged", s.flagged, "had violations")}
      </div>
      <div class="tabs"><button class="active" data-t="ranked">Ranked list</button><button data-t="absent">Absent (${data.absentees.length})</button></div>
      <div id="t-ranked"><div class="toolbar"><input id="rsearch" placeholder="Filter by name or roll no"></div>
      <div class="table-wrap"><table>
        <thead><tr><th class="num">#</th><th>Student</th><th>Branch</th>${sections.map(x => `<th class="num">${esc(x)}</th>`).join("")}<th class="num">Total</th><th class="num">%</th><th>Result</th><th class="num">Violations</th><th>Time</th><th></th></tr></thead>
        <tbody id="rbody">${data.results.map(r => `<tr data-row="${esc((r.name + " " + r.roll_no).toLowerCase())}">
          <td class="num">${r.rank || "—"}</td>
          <td><strong>${esc(r.name)}</strong><div class="muted small">${esc(r.roll_no)}</div></td>
          <td>${esc(r.branch || "")} ${esc(r.section || "")}</td>
          ${sections.map(x => `<td class="num">${r.section_scores[x] ?? 0}</td>`).join("")}
          <td class="num"><strong>${r.total_score}</strong> / ${r.max_score}</td><td class="num">${r.percentage}</td>
          <td>${r.status === "in_progress" ? badge("Writing", "blue") : r.passed ? badge("Pass", "green") : badge("Fail", "red")}
            ${r.status === "auto_submitted" ? `<div class="muted small">${esc(reasonText(r.submit_reason))}</div>` : ""}</td>
          <td class="num">${r.violations ? badge(r.violations, "amber") : 0}</td>
          <td class="small">${r.time_taken_seconds ? fmtDuration(r.time_taken_seconds) : "—"}</td>
          <td class="row" style="gap:4px"><button class="btn sm" data-view="${r.attempt_id}">View</button><button class="btn sm danger" data-reset="${r.attempt_id}" title="Delete the attempt so the student can retake">Allow retake</button></td>
        </tr>`).join("") || `<tr><td colspan="${9 + sections.length}" class="empty">No attempts yet</td></tr>`}</tbody>
      </table></div></div>
      <div id="t-absent" class="hidden"><div class="table-wrap"><table><thead><tr><th>Roll no</th><th>Name</th><th>Branch</th></tr></thead><tbody>
        ${data.absentees.map(a => `<tr><td>${esc(a.roll_no)}</td><td>${esc(a.name)}</td><td>${esc(a.branch || "")}</td></tr>`).join("") || `<tr><td colspan="3" class="empty">Everyone eligible has attempted</td></tr>`}
      </tbody></table></div></div>`;
    view.querySelectorAll(".tabs button").forEach(b => b.onclick = () => {
      view.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("active", x === b));
      document.getElementById("t-ranked").classList.toggle("hidden", b.dataset.t !== "ranked");
      document.getElementById("t-absent").classList.toggle("hidden", b.dataset.t !== "absent");
    });
    document.getElementById("rsearch").oninput = e => {
      const q = e.target.value.toLowerCase();
      view.querySelectorAll("[data-row]").forEach(tr => tr.classList.toggle("hidden", !tr.dataset.row.includes(q)));
    };
    document.getElementById("export").onclick = () => download(`/api/reios/admin/exams/${id}/export` + cq(), `${data.exam.title.replace(/\W+/g, "_")}_results.csv`).catch(handleError);
    document.getElementById("similarity").onclick = () => similarityReport(id);
    view.querySelectorAll("[data-view]").forEach(b => b.onclick = () => attemptDetail(b.dataset.view));
    view.querySelectorAll("[data-reset]").forEach(b => b.onclick = async () => {
      if (!await confirmBox("Allow retake", "This deletes the student's attempt and all their answers so they can take the exam again. Continue?", "Delete attempt", true)) return;
      try { await api("DELETE", `/api/reios/admin/attempts/${b.dataset.reset}` + cq()); toast("Attempt deleted", "success"); route(); } catch (err) { handleError(err); }
    });
  }

  function reasonText(reason) {
    return { time_up: "Time ran out", max_violations: "Too many violations", admin_force_submit: "Submitted by admin", student_submitted: "Submitted" }[reason] || reason || "";
  }

  async function similarityReport(examId) {
    try {
      const r = await api("GET", `/api/reios/admin/exams/${examId}/similarity` + cq());
      modal({
        title: "Code similarity (possible copying)", wide: true,
        body: `<p class="muted">Pairs of students whose code for the same problem is at least ${r.threshold}% similar after ignoring comments and whitespace. Review the code before taking action: short problems can have naturally similar solutions.</p>
          <div class="table-wrap"><table><thead><tr><th>Problem</th><th>Student A</th><th>Student B</th><th class="num">Similarity</th></tr></thead><tbody>
          ${r.pairs.map(p => `<tr><td>${esc(p.problem)}</td><td>${esc(p.student_a.name)} <span class="muted small">${esc(p.student_a.roll_no)}</span></td>
            <td>${esc(p.student_b.name)} <span class="muted small">${esc(p.student_b.roll_no)}</span></td><td class="num">${badge(p.similarity + "%", p.similarity >= 95 ? "red" : "amber")}</td></tr>`).join("")
            || `<tr><td colspan="4" class="empty">No suspicious pairs found</td></tr>`}</tbody></table></div>`,
      });
    } catch (err) { handleError(err); }
  }

  async function attemptDetail(attemptId) {
    try {
      const a = await api("GET", `/api/reios/admin/attempts/${attemptId}` + cq());
      const q = a.questions.map((x, i) => x.type === "mcq" ? `
        <div class="card" style="padding:12px;margin-bottom:8px">
          <div class="row between"><strong>Q${i + 1} · ${esc(x.section)}</strong><span>${x.is_correct === null ? badge("Not answered") : x.is_correct ? badge("Correct", "green") : badge("Wrong", "red")} ${x.marks_awarded} / ${x.marks}</span></div>
          <div class="md">${Reios.markdown(x.question)}</div>
          <ol class="option-list">${x.options.map((o, oi) => `<li class="${x.correct_options.includes(oi) ? "correct" : x.selected.includes(oi) ? "wrong" : ""}">${esc(o)}${x.selected.includes(oi) ? " ← chosen" : ""}</li>`).join("")}</ol>
        </div>` : `
        <div class="card" style="padding:12px;margin-bottom:8px">
          <div class="row between"><strong>Q${i + 1} · ${esc(x.title)}</strong><span>${x.passed_tests}/${x.total_tests} tests · ${x.marks_awarded} / ${x.marks}</span></div>
          <div class="muted small">${x.language ? LANG_LABELS[x.language] : "No code"} · ran ${x.run_count} times</div>
          ${x.code ? `<pre>${esc(x.code)}</pre>` : ""}
        </div>`).join("");
      const m = modal({
        title: `${a.student.name} (${a.student.roll_no})`, wide: true,
        body: `
          <div class="grid cols-4" style="margin-bottom:12px">
            ${stat("Score", `${a.total_score} / ${a.max_score}`)} ${stat("MCQ", a.mcq_score)} ${stat("Coding", a.coding_score)} ${stat("Violations", a.violations)}
          </div>
          <dl class="kv"><dt>Status</dt><dd>${esc(a.status.replace("_", " "))} ${a.submit_reason ? "· " + esc(reasonText(a.submit_reason)) : ""}</dd>
            <dt>Started</dt><dd>${fmtDate(a.started_at)}</dd><dt>Submitted</dt><dd>${fmtDate(a.submitted_at)}</dd>
            <dt>IP address</dt><dd>${esc(a.ip_address || "—")}</dd><dt>Browser</dt><dd class="small">${esc(a.user_agent || "—")}</dd></dl>
          <div class="tabs" style="margin-top:14px"><button class="active" data-t="answers">Answers</button><button data-t="events">Proctoring log (${a.events.length})</button></div>
          <div data-pane="answers">${q}</div>
          <div data-pane="events" class="hidden"><div class="table-wrap"><table><thead><tr><th>Time</th><th>Event</th><th>Details</th></tr></thead><tbody>
            ${a.events.map(e => `<tr><td class="small">${fmtDate(e.at)}</td><td>${e.counted ? badge(e.type, "red") : esc(e.type)}</td><td class="small">${esc(e.details || "")}</td></tr>`).join("")}
          </tbody></table></div></div>`,
        actions: a.status === "in_progress" ? [
          { label: "Forgive violations", onClick: async close => { try { await api("POST", `/api/reios/admin/attempts/${attemptId}/forgive-violations` + cq()); toast("Violations cleared", "success"); close(); } catch (err) { handleError(err); } } },
          { label: "Extend time", onClick: close => { close(); extendTime(attemptId); } },
          { label: "Force submit", cls: "danger solid", onClick: async close => { if (!await confirmBox("Force submit", "Submit this student's exam now?", "Submit", true)) return; try { await api("POST", `/api/reios/admin/attempts/${attemptId}/force-submit` + cq()); toast("Submitted", "success"); close(); route(); } catch (err) { handleError(err); } } },
        ] : [{ label: "Close" }],
      });
      m.el.querySelectorAll(".tabs button").forEach(b => b.onclick = () => {
        m.el.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("active", x === b));
        m.el.querySelectorAll("[data-pane]").forEach(p => p.classList.toggle("hidden", p.dataset.pane !== b.dataset.t));
      });
    } catch (err) { handleError(err); }
  }

  function extendTime(attemptId) {
    const form = document.createElement("div");
    form.innerHTML = `<div class="field"><label>Extra minutes</label><input type="number" id="mins" min="1" max="240" value="10"></div>`;
    modal({ title: "Extend time", body: form, actions: [{ label: "Cancel" }, { label: "Extend", cls: "primary", onClick: async close => {
      try { await api("POST", `/api/reios/admin/attempts/${attemptId}/extend` + cq(), { minutes: Number(form.querySelector("#mins").value) }); toast("Time extended", "success"); close(); route(); }
      catch (err) { handleError(err); }
    } }] });
  }

  // ── Live monitor ────────────────────────────────────────────────────────
  async function liveView(id) {
    if (needCollege()) return;
    async function refresh() {
      const d = await api("GET", `/api/reios/admin/exams/${id}/live` + cq());
      const writing = d.attempts.filter(a => a.status === "in_progress");
      view.innerHTML = `
        <div class="row between">
          <div><a href="#results/${id}" class="small">← Results</a><h1 style="margin-top:4px">${esc(d.exam.title)} · Live ${windowBadge(d.exam)}</h1></div>
          <span class="muted small">Auto-refreshes every 10 seconds · last ${new Date().toLocaleTimeString()}</span>
        </div>
        <div class="grid cols-4" style="margin-bottom:16px">
          ${stat("Writing now", writing.length)} ${stat("Online", writing.filter(a => a.online).length, "heartbeat in last 45s")}
          ${stat("Submitted", d.attempts.length - writing.length)} ${stat("With violations", d.attempts.filter(a => a.violations).length)}
        </div>
        <div class="grid" style="grid-template-columns:minmax(0,2fr) minmax(260px,1fr);align-items:start">
          <div class="table-wrap"><table>
            <thead><tr><th></th><th>Student</th><th>Progress</th><th class="num">Violations</th><th>Time left</th><th>Last event</th><th></th></tr></thead>
            <tbody>${d.attempts.map(a => `<tr>
              <td title="${a.online ? "Online" : "Offline"}"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${a.status !== "in_progress" ? "var(--muted)" : a.online ? "var(--success)" : "var(--danger)"}"></span></td>
              <td><strong>${esc(a.name)}</strong><div class="muted small">${esc(a.roll_no)} · ${esc(a.ip_address || "")}</div></td>
              <td style="min-width:120px"><div class="progress"><span style="width:${a.total ? Math.round(a.answered / a.total * 100) : 0}%"></span></div><span class="small muted">${a.answered}/${a.total}</span></td>
              <td class="num">${a.violations >= a.max_violations - 1 && a.violations ? badge(`${a.violations}/${a.max_violations}`, "red") : a.violations ? badge(`${a.violations}/${a.max_violations}`, "amber") : "0"}</td>
              <td>${a.status === "in_progress" ? fmtDuration(a.seconds_left) : badge(a.status === "submitted" ? "Submitted" : "Auto-submitted")}</td>
              <td class="small">${a.last_event ? esc(a.last_event.type) + "<br>" + new Date(a.last_event.at).toLocaleTimeString() : ""}</td>
              <td><button class="btn sm" data-view="${a.attempt_id}">Manage</button></td></tr>`).join("") || `<tr><td colspan="7" class="empty">Nobody has started yet</td></tr>`}</tbody>
          </table></div>
          <div class="card" style="margin:0"><h3>Recent violations</h3>
            ${d.recent_violations.map(v => `<div style="padding:6px 0;border-bottom:1px solid var(--border)"><strong class="small">${esc(v.name)}</strong> <span class="muted small">${esc(v.roll_no)}</span>
              <div class="small">${badge(v.type, "red")} ${new Date(v.at).toLocaleTimeString()}</div></div>`).join("") || `<p class="muted small">None so far</p>`}
          </div>
        </div>`;
      view.querySelectorAll("[data-view]").forEach(b => b.onclick = () => attemptDetail(b.dataset.view));
    }
    await refresh();
    state.liveTimer = setInterval(() => {
      if (document.querySelector(".modal-backdrop")) return; // don't redraw under an open dialog
      refresh().catch(handleError);
    }, 10000);
  }

  // ── Announcements ───────────────────────────────────────────────────────
  async function announcementsView() {
    if (needCollege()) return;
    const list = await api("GET", "/api/reios/admin/announcements" + cq());
    view.innerHTML = `
      <h1>Announcements</h1>
      <div class="card">
        <h3>New announcement</h3>
        <div class="field"><label>Title</label><input id="a-title"></div>
        <div class="field"><label>Message</label><textarea id="a-body" rows="3"></textarea></div>
        ${isSuper ? `<label class="check"><input type="checkbox" id="a-all"> Send to all colleges</label>` : ""}
        <button class="btn primary" id="a-post">Post to students</button>
      </div>
      <div class="card">${list.map(a => `<div style="padding:10px 0;border-bottom:1px solid var(--border)">
        <div class="row between"><strong>${esc(a.title)}</strong><span class="row small muted">${a.is_global ? badge("All colleges", "blue") : ""} ${fmtDate(a.created_at)}
          ${!a.is_global || isSuper ? `<button class="btn sm ghost" data-del="${a.id}">✕</button>` : ""}</span></div>
        <div style="white-space:pre-wrap">${esc(a.body)}</div></div>`).join("") || `<p class="muted">No announcements yet</p>`}</div>`;
    document.getElementById("a-post").onclick = async () => {
      const all = isSuper && document.getElementById("a-all").checked;
      try {
        await api("POST", "/api/reios/admin/announcements" + (all ? qs({ all_colleges: true }) : cq()),
          { title: document.getElementById("a-title").value, body: document.getElementById("a-body").value });
        toast("Posted", "success"); announcementsView();
      } catch (err) { handleError(err); }
    };
    view.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      try { await api("DELETE", `/api/reios/admin/announcements/${b.dataset.del}`); announcementsView(); } catch (err) { handleError(err); }
    });
  }

  // ── Account ─────────────────────────────────────────────────────────────
  function accountView(forced) {
    view.innerHTML = `
      <h1>Change password</h1>
      ${forced ? `<div class="card" style="background:var(--warning-soft);border-color:transparent;margin-bottom:16px">You're using a temporary password. Set your own password to continue.</div>` : ""}
      <div class="card" style="max-width:440px">
        <div class="field"><label>Current password</label><input type="password" id="cur" autocomplete="current-password"></div>
        <div class="field"><label>New password (min 8 characters)</label><input type="password" id="new1" autocomplete="new-password"></div>
        <div class="field"><label>Confirm new password</label><input type="password" id="new2" autocomplete="new-password"></div>
        <button class="btn primary" id="save">Update password</button>
      </div>`;
    document.getElementById("save").onclick = async () => {
      const n1 = document.getElementById("new1").value;
      if (n1 !== document.getElementById("new2").value) return toast("Passwords don't match", "error");
      try {
        const r = await api("POST", "/api/reios/auth/change-password", { current_password: document.getElementById("cur").value, new_password: n1 });
        Reios.auth.save(r.access_token, r.user);
        toast("Password updated", "success");
        location.hash = "overview"; if (forced) location.reload();
      } catch (err) { handleError(err); }
    };
  }

  const VIEWS = {
    overview: overviewView, colleges: collegesView, students: studentsView, mcqs: mcqsView, problems: problemsView,
    exams: examsView, exam: examBuilderView, results: resultsView, live: liveView, announcements: announcementsView,
    account: () => accountView(false),
  };

  // ── Boot ────────────────────────────────────────────────────────────────
  (async function boot() {
    try {
      const me = await api("GET", "/api/reios/auth/me");
      if (me.must_change_password) { renderNav("account"); accountView(true); return; }
      state.meta = await api("GET", "/api/reios/admin/meta");
      await loadColleges();
      window.addEventListener("hashchange", route);
      route();
    } catch (err) { handleError(err); }
  })();
})();
