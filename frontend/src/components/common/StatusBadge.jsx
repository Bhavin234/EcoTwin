import "./StatusBadge.css";

/**
 * Consistent status visual language (docs Milestone 6, requirement #33):
 * green = healthy/verified/completed, amber = unusual/investigating/pending,
 * red = high/critical/no-improvement, neutral = informational/insufficient.
 * Text label is always present — color never carries meaning alone
 * (requirement #29, accessibility).
 */
const TONE_BY_VALUE = {
  // severity
  low: "neutral",
  medium: "warning",
  high: "critical",
  critical: "critical",
  // classification
  unusual: "neutral",
  operationally_suspicious: "warning",
  // anomaly status
  open: "warning",
  investigating: "warning",
  resolved: "positive",
  dismissed: "neutral",
  // intervention lifecycle
  recommended: "neutral",
  in_progress: "warning",
  completed: "positive",
  // verification status
  pending: "neutral",
  insufficient_data: "neutral",
  no_measurable_improvement: "critical",
  improvement_detected: "warning",
  verified: "positive",
  // impact kind
  potential: "neutral",
  estimated: "warning",
  // explanation source
  ai: "positive",
  fallback: "neutral",
};

export default function StatusBadge({ value, label }) {
  const tone = TONE_BY_VALUE[value] || "neutral";
  const text = label || value?.toString().replace(/_/g, " ") || "—";
  return <span className={`status-badge status-badge--${tone}`}>{text}</span>;
}
