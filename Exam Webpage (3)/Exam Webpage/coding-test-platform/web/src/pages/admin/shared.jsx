import { downloadCSV } from "../../lib/api.js";
import { Modal } from "../../components/ui.jsx";

const DEFAULT_NOTE =
  "Share these passwords with the users. They must change them at first login. " +
  "They won't be shown again.";

/** Temporary passwords are returned once and never stored in readable form. */
export function CredentialsModal({ title, creds, note, onClose }) {
  return (
    <Modal
      title={title}
      wide
      onClose={onClose}
      actions={
        <>
          <button
            className="btn"
            onClick={() =>
              downloadCSV(
                "credentials.csv",
                ["Login", "Name", "Password"],
                creds.map((c) => [c.roll_no || c.email, c.name, c.password])
              )
            }
          >
            Download CSV
          </button>
          <button className="btn primary" onClick={onClose}>Done</button>
        </>
      }
    >
      <p className="muted">{note || DEFAULT_NOTE}</p>
      <div className="table-wrap compact">
        <table>
          <thead>
            <tr><th>Login</th><th>Name</th><th>Temporary password</th></tr>
          </thead>
          <tbody>
            {creds.map((c, i) => (
              <tr key={i}>
                <td>{c.roll_no || c.email || ""}</td>
                <td>{c.name || ""}</td>
                <td><code>{c.password}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}

export function Pager({ page, pages, total, noun = "items", onPage }) {
  return (
    <div className="row between" style={{ marginTop: 12 }}>
      <span className="muted small">{total} {noun}</span>
      <div className="row tight">
        <button className="btn sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>‹ Prev</button>
        <span className="small">Page {page} of {Math.max(1, pages)}</span>
        <button className="btn sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next ›</button>
      </div>
    </div>
  );
}

/** Reads a user-chosen file as text, for the CSV import flows. */
export function readFileText(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(new Error("Could not read that file"));
    r.readAsText(file);
  });
}
