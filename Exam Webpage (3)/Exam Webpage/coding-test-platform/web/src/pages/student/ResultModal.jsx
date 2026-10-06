import { Badge, Markdown, Modal, Progress, useToast } from "../../components/ui.jsx";
import { download } from "../../lib/api.js";

const REASONS = {
  time_up: "Submitted automatically when time ran out.",
  max_violations: "Submitted automatically because of repeated anti-cheat violations.",
  admin_force_submit: "Submitted by the exam administrator.",
};

function McqReview({ x }) {
  return (
    <div className="card pad-sm" style={{ marginBottom: 8 }}>
      <div className="row between">
        <strong className="small">{x.section}</strong>
        <span>
          {!x.selected.length ? <Badge>Not answered</Badge>
            : x.marks_awarded > 0 ? <Badge color="green">Correct</Badge>
            : <Badge color="red">Wrong</Badge>}{" "}
          {x.marks_awarded}/{x.marks}
        </span>
      </div>
      <Markdown>{x.question_text}</Markdown>
      <ol className="option-list">
        {x.options.map((o, oi) => (
          <li key={oi}
              className={x.correct_options.includes(oi) ? "correct" : x.selected.includes(oi) ? "wrong" : ""}>
            {o}{x.selected.includes(oi) && " ← your answer"}
          </li>
        ))}
      </ol>
      {x.explanation && (
        <div className="small muted"><strong>Explanation:</strong> {x.explanation}</div>
      )}
    </div>
  );
}

function CodeReview({ x }) {
  return (
    <div className="card pad-sm" style={{ marginBottom: 8 }}>
      <div className="row between">
        <strong>{x.title}</strong>
        <span>{x.passed_tests}/{x.total_tests} hidden tests · {x.marks_awarded}/{x.marks}</span>
      </div>
      {x.code ? <pre>{x.code}</pre> : <p className="muted small">No code submitted</p>}
    </div>
  );
}

export default function ResultModal({ result: r, onClose }) {
  const reason = REASONS[r.submit_reason] || "";
  return (
    <Modal title={r.exam.title} wide onClose={onClose}>
      {r.certificate_available && <CertificateBanner r={r} />}
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <div className="stat">
          <div className="label">Score</div>
          <div className="value">{r.total_score}
            <span className="muted" style={{ fontSize: 15 }}> / {r.max_score}</span></div>
        </div>
        <div className="stat">
          <div className="label">Percentage</div>
          <div className="value">{r.percentage}%</div>
        </div>
        <div className={"stat " + (r.passed ? "green" : "red")}>
          <div className="label">Result</div>
          <div className="value" style={{ color: r.passed ? "var(--success)" : "var(--danger)" }}>
            {r.passed ? "Pass" : "Fail"}
          </div>
        </div>
        <div className="stat plain">
          <div className="label">Rank</div>
          <div className="value">{r.rank}
            <span className="muted" style={{ fontSize: 15 }}> / {r.participants}</span></div>
        </div>
      </div>

      {reason && <p className="small" style={{ color: "var(--warning)" }}>{reason}</p>}

      <h3>Section-wise performance</h3>
      {r.sections.map((s) => (
        <div key={s.section}>
          <div className="section-bar">
            <strong className="small">{s.section}</strong>
            <Progress value={s.score} max={s.max} />
            <span className="small num nums">{s.score} / {s.max}</span>
          </div>
          <div className="muted small" style={{ margin: "-4px 0 8px" }}>
            {s.correct} correct · {s.wrong} wrong · {s.unanswered} unanswered
          </div>
        </div>
      ))}

      {r.review?.length > 0 && (
        <>
          <h3 style={{ marginTop: 16 }}>
            {r.answers_visible ? "Answer review" : "Your coding answers"}
          </h3>
          {r.review.map((x, i) =>
            x.type === "mcq" ? <McqReview key={i} x={x} /> : <CodeReview key={i} x={x} />
          )}
        </>
      )}
    </Modal>
  );
}

function CertificateBanner({ r }) {
  const toast = useToast();
  return (
    <div className="banner" style={{ marginBottom: 16, alignItems: "center" }}>
      <span className="grow">🎉 You passed. Your certificate is ready.</span>
      <button className="btn primary sm" onClick={() =>
        download(`/api/reios/student/attempts/${r.attempt_id}/certificate`,
                 `${r.exam.title.replace(/\W+/g, "_")}_certificate.pdf`).catch((e) => toast(e.message, "error"))
      }>Download certificate</button>
    </div>
  );
}
