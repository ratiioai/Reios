import { useEffect, useState } from "react";
import { api, downloadCSV } from "../../lib/api.js";
import { Badge, Loading, useToast } from "../../components/ui.jsx";
import { Stat } from "./context.jsx";

const thisMonth = () => new Date().toISOString().slice(0, 7);

/** Super admin: what each organization used in a month, for billing. */
export default function Usage() {
  const toast = useToast();
  const [month, setMonth] = useState(thisMonth());
  const [data, setData] = useState(null);

  useEffect(() => {
    setData(null);
    api("GET", `/api/reios/super/usage?month=${month}`).then(setData).catch((e) => toast(e.message, "error"));
  }, [month, toast]);

  function exportCsv() {
    downloadCSV(`reios_usage_${data.month}.csv`,
      ["Organization", "Code", "Type", "Add-ons", "Students", "Exams created this month", "Exams total", "Exam limit", "Attempts this month", "Status"],
      data.organizations.map((o) => [o.name, o.code, o.org_type, o.features.join(" "), o.students, o.exams_created,
        o.exams_total, o.max_exams ?? "", o.attempts, !o.is_active ? "disabled" : o.expired ? "expired" : "active"]));
  }

  return (
    <>
      <div className="row between" style={{ marginBottom: 6 }}>
        <div className="page-head" style={{ margin: 0 }}>
          <h1>Usage</h1>
          <p className="lede">What each organization used in a month. Use it for invoices and renewals.</p>
        </div>
        <div className="row tight">
          <input type="month" value={month} max={thisMonth()} onChange={(e) => e.target.value && setMonth(e.target.value)} />
          <button className="btn" onClick={exportCsv} disabled={!data}>Export CSV</button>
        </div>
      </div>

      {!data ? <Loading /> : (
        <>
          <div className="grid cols-3" style={{ margin: "14px 0 18px" }}>
            <Stat label="Students (all organizations)" value={data.totals.students} tone="plain" />
            <Stat label="Exams created this month" value={data.totals.exams_created} />
            <Stat label="Attempts this month" value={data.totals.attempts} tone="green" />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Organization</th><th>Add-ons</th><th className="num">Students</th>
                  <th className="num">Exams this month</th><th className="num">Exams used</th>
                  <th className="num">Attempts this month</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.organizations.length === 0 ? (
                  <tr><td colSpan={7} className="empty">No organizations yet</td></tr>
                ) : data.organizations.map((o) => (
                  <tr key={o.id}>
                    <td><strong>{o.name}</strong> <code className="small">{o.code}</code>{" "}
                      {o.org_type === "event" && <Badge color="violet">Event</Badge>}</td>
                    <td className="small">{o.features.map((k) => k.replace("_", " ")).join(", ") || "—"}</td>
                    <td className="num">{o.students}</td>
                    <td className="num">{o.exams_created}</td>
                    <td className="num">{o.exams_total}{o.max_exams ? ` / ${o.max_exams}` : ""}</td>
                    <td className="num"><strong>{o.attempts}</strong></td>
                    <td>{!o.is_active ? <Badge color="red">Disabled</Badge>
                      : o.expired ? <Badge color="red">Expired</Badge> : <Badge color="green">Active</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
