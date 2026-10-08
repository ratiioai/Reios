import { createContext, useContext } from "react";
import { qs } from "../../lib/api.js";

export const AdminCtx = createContext(null);
export const useAdmin = () => useContext(AdminCtx);

/**
 * College admins are pinned to their own college by the backend; super admins
 * must name one with ?college_id=, so every college-scoped call goes through this.
 */
export function makeCq(isSuper, collegeId) {
  return (params = {}) => qs(isSuper ? { college_id: collegeId, ...params } : params);
}

/** "event" or "college": what to call an account on screen. */
export const orgNoun = (org) => (org?.org_type === "event" ? "event" : "college");
export const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

export const ICONS = {
  overview: '<path d="M3 9.5 10 4l7 5.5V16a1 1 0 0 1-1 1h-3v-5H7v5H4a1 1 0 0 1-1-1V9.5Z"/>',
  colleges: '<path d="M10 3 3 6.5 10 10l7-3.5L10 3Z"/><path d="M4.5 9v4.5c0 1 2.5 2.5 5.5 2.5s5.5-1.5 5.5-2.5V9"/>',
  students: '<circle cx="7.5" cy="7" r="2.6"/><path d="M3 16c0-2.5 2-4.2 4.5-4.2S12 13.5 12 16"/><circle cx="14.5" cy="8" r="2"/><path d="M13 16c0-1.9 1-3.1 2.6-3.1 1.1 0 1.9.5 2.4 1.3"/>',
  exams: '<path d="M5 3h7l3.5 3.5V17H5V3Z"/><path d="M12 3v3.5h3.5"/><path d="m7.8 11.4 1.4 1.4 3-3.2"/>',
  leaderboard: '<path d="M7 17V9h6v8"/><path d="M3 17v-5h4"/><path d="M13 17v-7h4v7"/><path d="M2 17h16"/><path d="m10 3 .9 1.8 2 .3-1.45 1.4.35 2-1.8-.95-1.8.95.35-2L7.1 5.1l2-.3L10 3Z"/>',
  usage: '<path d="M3 17h14"/><path d="M5 14V9"/><path d="M9 14V5"/><path d="M13 14v-3"/><path d="M17 14V7"/>',
  announcements: '<path d="M4 8v4h2.5L11 15.5v-11L6.5 8H4Z"/><path d="M14 8.2a3 3 0 0 1 0 3.6"/>',
  mcqs: '<circle cx="5.5" cy="6" r="2"/><circle cx="5.5" cy="14" r="2"/><path d="M10 6h7M10 14h7"/>',
  problems: '<path d="m7 7-3.5 3L7 13"/><path d="m13 7 3.5 3L13 13"/>',
  account: '<circle cx="10" cy="7" r="3"/><path d="M4 17c0-3.1 2.7-5 6-5s6 1.9 6 5"/>',
};

export function NavIcon({ id }) {
  return (
    <svg className="ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
         dangerouslySetInnerHTML={{ __html: ICONS[id] || "" }} />
  );
}

export function Stat({ label, value, sub, tone = "" }) {
  return (
    <div className={"stat " + tone}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

export function windowBadgeProps(exam) {
  if (!exam.is_published) return { color: "", text: "Draft" };
  return {
    live: { color: "green", text: "Live" },
    upcoming: { color: "blue", text: "Scheduled" },
    paused: { color: "amber", text: "Paused" },
    ended: { color: "", text: "Ended" },
  }[exam.window] || { color: "", text: exam.window };
}

export const nullIfBlank = (v) =>
  v === undefined || v === null || String(v).trim() === "" ? null : String(v).trim();
