import React from "react";

export function MetricCard({ label, value, hint }) {
  return (
    <div className="metric-card">
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value ?? "—"}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}

export function StatusPill({ children, tone = "neutral" }) {
  return <span className={`status-pill status-${tone}`}>{children}</span>;
}

export function SectionTitle({ eyebrow, title, description, actions }) {
  return (
    <div className="section-title-row">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {description ? <p className="muted section-description">{description}</p> : null}
      </div>
      {actions ? <div className="section-actions">{actions}</div> : null}
    </div>
  );
}

export function EmptyState({ icon = "◇", title, children }) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">{icon}</div>
      <strong>{title}</strong>
      <p>{children}</p>
    </div>
  );
}

export function CheckRow({ check }) {
  const passed = Boolean(check?.passed);
  return (
    <div className="check-row" key={check?.check}>
      <span className={passed ? "check-pass" : "check-fail"}>{passed ? "✓" : "×"}</span>
      <div>
        <strong>{String(check?.check || "Check").replaceAll("_", " ")}</strong>
        <small>{typeof check?.details === "string" ? check.details : JSON.stringify(check?.details ?? "")}</small>
      </div>
    </div>
  );
}
