import { titleCase } from "../../utils/format";
import "./EvidenceList.css";

const SIGNAL_CONTEXT = {
  baseline_deviation: "Observed deviation",
  baseline_deviation_zscore: "Observed deviation",
  persistence: "Temporal evidence",
  operating_status: "Operational context",
  occupancy: "Context signal",
  cross_resource_correlation: "Cross-resource signal",
  classification: "Classification",
};

/**
 * Evidence is a major differentiator (docs Milestone 6, requirement #13) —
 * shown prominently and in full, never behind a default-collapsed
 * accordion. Every item here is exactly what the backend's evidence engine
 * produced (app/analytics/evidence.py) — nothing is invented here.
 */
export default function EvidenceList({ evidence }) {
  if (!evidence || evidence.length === 0) {
    return <p className="evidence-list__empty">No evidence recorded for this anomaly.</p>;
  }

  return (
    <ul className="evidence-list">
      {evidence.map((item, idx) => (
        <li key={idx} className="evidence-list__item">
          <div className="evidence-list__marker" aria-hidden="true" />
          <div>
            <p className="evidence-list__description">{item.description}</p>
            <p className="evidence-list__context">{SIGNAL_CONTEXT[item.signal] || titleCase(item.signal)}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
