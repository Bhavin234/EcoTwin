import "./Primitives.css";

export function Card({ children, className = "", ...props }) {
  return (
    <div className={`card ${className}`} {...props}>
      {children}
    </div>
  );
}

export function SectionHeading({ eyebrow, title, children }) {
  return (
    <div className="section-heading">
      <div>
        {eyebrow && <p className="section-heading__eyebrow">{eyebrow}</p>}
        <h2 className="section-heading__title">{title}</h2>
      </div>
      {children}
    </div>
  );
}

export function Button({ variant = "primary", children, ...props }) {
  return (
    <button type="button" className={`btn btn--${variant}`} {...props}>
      {children}
    </button>
  );
}

export function MetricTile({ label, value, sublabel, tone = "neutral" }) {
  return (
    <div className={`metric-tile metric-tile--${tone}`}>
      <p className="metric-tile__label">{label}</p>
      <p className="metric-tile__value mono">{value}</p>
      {sublabel && <p className="metric-tile__sublabel">{sublabel}</p>}
    </div>
  );
}
