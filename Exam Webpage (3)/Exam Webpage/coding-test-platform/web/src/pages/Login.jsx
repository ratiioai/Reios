import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../lib/auth.jsx";
import { api, auth as tokenStore, homeFor, store } from "../lib/api.js";
import { firebaseConfigured, firebaseSignIn } from "../lib/firebase.js";
import { Brand, Mark, Spinner, ThemeToggle } from "../components/ui.jsx";

const FEATURES = [
  {
    title: "Proctored by default",
    body: "Fullscreen, tab-switch detection and shuffled papers.",
    icon: <><path d="M10 2 3 5v5c0 4 3 7 7 8 4-1 7-4 7-8V5l-7-3Z" /><path d="m7.5 10 2 2 3.5-4" /></>,
  },
  {
    title: "Real code execution",
    body: "Python, C, C++, Java and JavaScript against hidden tests.",
    icon: <><path d="m7 7-3.5 3L7 13" /><path d="m13 7 3.5 3L13 13" /></>,
  },
  {
    title: "Section-wise insight",
    body: "Ranks, topic gaps and exports for every batch.",
    icon: <path d="M3 16V9m4.5 7V4m4.5 12v-5m4.5 5V7" />,
  },
];

export default function Login() {
  const { user, login, loginWithFirebase } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [mode, setMode] = useState(params.get("as") === "admin" ? "admin" : "student");
  const [collegeCode, setCollegeCode] = useState(() => store.get("reios_college_code") || "");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(params.get("expired") ? "Your session expired. Please sign in again." : "");
  const [busy, setBusy] = useState(false);
  const [firebaseOn, setFirebaseOn] = useState(false);
  const [orgBrand, setOrgBrand] = useState(null);

  useEffect(() => {
    const code = collegeCode.trim();
    if (mode !== "student" || code.length < 2) { setOrgBrand(null); return; }
    const t = setTimeout(() => {
      api("GET", `/api/reios/auth/branding?code=${encodeURIComponent(code)}`, null, { noRedirect: true })
        .then(setOrgBrand).catch(() => setOrgBrand(null));
    }, 400);
    return () => clearTimeout(t);
  }, [collegeCode, mode]);

  useEffect(() => {
    if (!firebaseConfigured) return;
    api("GET", "/api/reios/auth/config", null, { noRedirect: true })
      .then((c) => setFirebaseOn(!!c.firebase_super_admin))
      .catch(() => {});
  }, []);

  // Already signed in and just landed here — go straight to the right home.
  useEffect(() => {
    if (tokenStore.token() && user && !params.get("expired")) {
      navigate(homeFor(user.role), { replace: true });
    }
  }, [user, navigate, params]);

  function switchMode(next) {
    setMode(next);
    setError("");
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    const body = { identifier: identifier.trim(), password };
    if (mode === "student") {
      if (!collegeCode.trim()) { setError("Enter your organization code"); return; }
      body.college_code = collegeCode.trim();
    }
    setBusy(true);
    try {
      let u;
      try {
        u = await login(body);
      } catch (err) {
        // Super admins sign in through Firebase: same email and password, sent there instead
        if (mode !== "admin" || !firebaseOn || !/Firebase/.test(err.message)) throw err;
        u = await loginWithFirebase(await firebaseSignIn("password", body.identifier, password));
      }
      if (mode === "student" && u.role !== "student") {
        throw new Error("Use the Staff tab to sign in as an admin");
      }
      if (body.college_code) store.set("reios_college_code", body.college_code.toUpperCase());
      navigate(homeFor(u.role), { replace: true });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="auth-split">
      <aside className="auth-aside">
        <Brand sub="Assessment platform" light />

        <div className="auth-pitch">
          <h2>Every test, from aptitude to code, in one place.</h2>
          <p>
            Reios runs proctored assessments for colleges — MCQ sections, live coding, and results
            your placement team can act on.
          </p>
          <ul className="auth-feats">
            {FEATURES.map((f) => (
              <li key={f.title}>
                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor"
                     strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{f.icon}</svg>
                <span><strong>{f.title}</strong><span>{f.body}</span></span>
              </li>
            ))}
          </ul>
        </div>

        <p className="auth-legal">
          Use of this platform is monitored. Sharing credentials is not permitted.
        </p>
      </aside>

      <main className="auth-main">
        <div className="auth-card">
          {orgBrand && (
            <div className="row" style={{ gap: 12, marginBottom: 14 }}>
              {orgBrand.logo && <img src={orgBrand.logo} alt="" style={{ height: 44, maxWidth: 140, objectFit: "contain" }} />}
              <strong style={{ fontSize: 18, color: orgBrand.color || undefined }}>{orgBrand.name}</strong>
            </div>
          )}
          <h1>Sign in</h1>
          <p className="lede">Welcome back. Choose how you're signing in.</p>

          <div className="card">
            <div className="tabs" role="tablist">
              <button className={mode === "student" ? "active" : ""} role="tab"
                      aria-selected={mode === "student"} onClick={() => switchMode("student")}>
                Student
              </button>
              <button className={mode === "admin" ? "active" : ""} role="tab"
                      aria-selected={mode === "admin"} onClick={() => switchMode("admin")}>
                Staff
              </button>
            </div>

            <form onSubmit={submit}>
              {mode === "student" && (
                <div className="field">
                  <label htmlFor="college_code">Organization code</label>
                  <input id="college_code" value={collegeCode} placeholder="e.g. JNTU"
                         autoComplete="organization" style={{ textTransform: "uppercase" }}
                         onChange={(e) => setCollegeCode(e.target.value)} />
                  <div className="hint">Given to you by your placement office.</div>
                </div>
              )}
              <div className="field">
                <label htmlFor="identifier">{mode === "admin" ? "Email" : "Roll number"}</label>
                <input id="identifier" required autoComplete="username"
                       type={mode === "admin" ? "email" : "text"} value={identifier}
                       onChange={(e) => setIdentifier(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="password">Password</label>
                <PasswordInput id="password" required value={password}
                               onChange={(e) => setPassword(e.target.value)} />
              </div>
              <div className="small" style={{ color: "var(--danger)", minHeight: 18, marginBottom: 4, fontWeight: 550 }}>
                {error}
              </div>
              <button className="btn primary block lg" type="submit" disabled={busy}>
                {busy ? <><Spinner /> Signing in</> : "Sign in"}
              </button>
            </form>

            {mode === "admin" && firebaseOn && (
              <SuperAdminFirebase
                onError={setError}
                onSignedIn={async (idToken) => {
                  const u = await loginWithFirebase(idToken);
                  navigate(homeFor(u.role), { replace: true });
                }}
              />
            )}
          </div>

          <div className="row between" style={{ marginTop: 15 }}>
            <p className="muted small" style={{ margin: 0 }}>
              Forgot your password? Ask your placement office.
            </p>
            <ThemeToggle />
          </div>
        </div>
      </main>
    </div>
  );
}

function SuperAdminFirebase({ onSignedIn, onError }) {
  const [showEmail, setShowEmail] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(null);

  async function go(method) {
    onError("");
    setBusy(method);
    try {
      await onSignedIn(await firebaseSignIn(method, email.trim(), password));
    } catch (err) {
      onError(err.message);
      setBusy(null);
    }
  }

  return (
    <div style={{ marginTop: 18, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
      <div className="small strong" style={{ marginBottom: 8 }}>Super admin</div>
      <button type="button" className="btn block" disabled={!!busy} onClick={() => go("google")}>
        {busy === "google" ? <><Spinner /> Waiting for Google</> : (
          <>
            <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/>
              <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
              <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/>
              <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/>
            </svg>
            Continue with Google
          </>
        )}
      </button>
      {!showEmail ? (
        <button type="button" className="btn ghost sm block" style={{ marginTop: 6 }} onClick={() => setShowEmail(true)}>
          Use Firebase email and password instead
        </button>
      ) : (
        <div style={{ marginTop: 10 }}>
          <div className="field">
            <label htmlFor="fb-email">Firebase email</label>
            <input id="fb-email" type="email" autoComplete="username" value={email}
                   onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="fb-pass">Firebase password</label>
            <PasswordInput id="fb-pass" value={password}
                           onChange={(e) => setPassword(e.target.value)}
                           onKeyDown={(e) => e.key === "Enter" && go("password")} />
          </div>
          <button type="button" className="btn primary block" disabled={!!busy || !email || !password}
                  onClick={() => go("password")}>
            {busy === "password" ? <><Spinner /> Signing in</> : "Sign in as super admin"}
          </button>
        </div>
      )}
    </div>
  );
}

export function PasswordInput(props) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <input autoComplete="current-password" {...props} type={show ? "text" : "password"}
             style={{ paddingRight: 64, ...(props.style || {}) }} />
      <button type="button" className="btn ghost sm" onClick={() => setShow((v) => !v)}
              aria-label={show ? "Hide password" : "Show password"}
              style={{ position: "absolute", right: 4, top: "50%", transform: "translateY(-50%)" }}>
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}
