import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api.js";
import { useAuth } from "../../lib/auth.jsx";
import { Field, Spinner, useToast } from "../../components/ui.jsx";
import { PasswordInput } from "../Login.jsx";
import { useAdmin } from "./context.jsx";

export default function Account({ onChanged }) {
  const { user, refresh } = useAuth();
  const { cq, isEvent, needCollege } = useAdmin();
  const toast = useToast();
  const [cur, setCur] = useState("");
  const [n1, setN1] = useState("");
  const [n2, setN2] = useState("");
  const [busy, setBusy] = useState(false);
  const [singleLogin, setSingleLogin] = useState(null);
  const noun = isEvent ? "team" : "student";

  const loadSettings = useCallback(async () => {
    if (needCollege) return;
    try {
      setSingleLogin((await api("GET", "/api/reios/admin/settings" + cq())).single_login);
    } catch (err) {
      toast(err.message, "error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cq, needCollege]);

  useEffect(() => { loadSettings(); }, [loadSettings]);

  async function toggleSingleLogin(next) {
    setSingleLogin(next);  // optimistic
    try {
      await api("PATCH", "/api/reios/admin/settings" + cq(), { single_login: next });
      toast(next ? "Single login turned on" : "Single login turned off", "success");
    } catch (err) {
      setSingleLogin(!next);
      toast(err.message, "error");
    }
  }

  async function submit(e) {
    e.preventDefault();
    if (n1 !== n2) return toast("Passwords don't match", "error");
    if (n1.length < 8) return toast("New password must be at least 8 characters", "error");
    setBusy(true);
    try {
      const r = await api("POST", "/api/reios/auth/change-password", {
        current_password: cur, new_password: n1,
      });
      refresh(r.access_token, r.user);
      setCur(""); setN1(""); setN2("");
      onChanged?.();
      toast("Password updated", "success");
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function logoutAll() {
    try {
      await api("POST", "/api/reios/auth/logout-all");
      toast("Signed out of all other devices", "success");
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Account</h1>
        <p className="lede">{user.name} · {user.email}</p>
      </div>

      <div className="card" style={{ maxWidth: 480 }}>
        <h3>Change password</h3>
        <form onSubmit={submit}>
          <Field label="Current password">
            <PasswordInput autoComplete="current-password" required
                   value={cur} onChange={(e) => setCur(e.target.value)} />
          </Field>
          <Field label="New password (min 8 characters)">
            <PasswordInput autoComplete="new-password" required
                   value={n1} onChange={(e) => setN1(e.target.value)} />
          </Field>
          <Field label="Confirm new password">
            <PasswordInput autoComplete="new-password" required
                   value={n2} onChange={(e) => setN2(e.target.value)} />
          </Field>
          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? <><Spinner /> Updating</> : "Update password"}
          </button>
        </form>
      </div>

      <div className="card" style={{ maxWidth: 480 }}>
        <h3>Other sessions</h3>
        <p className="muted small">
          Signs you out everywhere else. Useful if you used a shared computer.
        </p>
        <button className="btn" onClick={logoutAll}>Sign out of all other devices</button>
      </div>

      {!needCollege && (
        <div className="card" style={{ maxWidth: 480 }}>
          <h3>{isEvent ? "Event" : "College"} security</h3>
          {singleLogin === null ? (
            <p className="muted small">Loading…</p>
          ) : (
            <>
              <label className="check">
                <input type="checkbox" checked={singleLogin}
                       onChange={(e) => toggleSingleLogin(e.target.checked)} />
                One login at a time per {noun}
              </label>
              <p className="muted small" style={{ marginTop: 6 }}>
                When on, a {noun} signed in on one device is refused on a second device until they log
                out there, or that session lapses on its own after a few hours.
              </p>
            </>
          )}
        </div>
      )}
    </>
  );
}
