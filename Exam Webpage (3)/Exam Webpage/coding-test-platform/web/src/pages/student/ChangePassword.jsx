import { useState } from "react";
import { api } from "../../lib/api.js";
import { useAuth } from "../../lib/auth.jsx";
import { Field, Modal, ModalButton, useToast } from "../../components/ui.jsx";
import { PasswordInput } from "../Login.jsx";

/** `forced` is used at first login, when a temporary password must be replaced. */
export default function ChangePassword({ forced = false, onClose, onDone }) {
  const { refresh } = useAuth();
  const toast = useToast();
  const [cur, setCur] = useState("");
  const [n1, setN1] = useState("");
  const [n2, setN2] = useState("");

  async function save() {
    if (n1 !== n2) return toast("Passwords don't match", "error");
    if (n1.length < 8) return toast("New password must be at least 8 characters", "error");
    try {
      const r = await api("POST", "/api/reios/auth/change-password", {
        current_password: cur, new_password: n1,
      });
      refresh(r.access_token, r.user);
      toast("Password updated", "success");
      onDone?.();
      onClose?.();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  return (
    <Modal
      title={forced ? "Set your password" : "Change password"}
      narrow
      closable={!forced}
      onClose={onClose}
      actions={
        <>
          {!forced && <button className="btn" onClick={onClose}>Cancel</button>}
          <ModalButton cls="primary" onClick={save}>Update password</ModalButton>
        </>
      }
    >
      {forced && (
        <p>
          You're using a temporary password from your college. Set your own password before
          taking exams.
        </p>
      )}
      <Field label="Current password">
        <PasswordInput autoComplete="current-password" value={cur}
               onChange={(e) => setCur(e.target.value)} />
      </Field>
      <Field label="New password (min 8 characters)">
        <PasswordInput autoComplete="new-password" value={n1}
               onChange={(e) => setN1(e.target.value)} />
      </Field>
      <Field label="Confirm new password">
        <PasswordInput autoComplete="new-password" value={n2}
               onChange={(e) => setN2(e.target.value)} />
      </Field>
    </Modal>
  );
}
