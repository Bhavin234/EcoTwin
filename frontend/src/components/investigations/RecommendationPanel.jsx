import { formatConsumption, titleCase } from "../../utils/format";
import StatusBadge from "../common/StatusBadge";
import "./RecommendationPanel.css";

/**
 * Displays the backend-generated recommendation verbatim (docs Milestone
 * 6, requirement #16) — action_text may come from AI/fallback reasoning,
 * but priority and estimated_saving are always the deterministic values
 * the backend computed; this component never generates its own text.
 */
export default function RecommendationPanel({ recommendation, unit }) {
  if (!recommendation) {
    return <p className="recommendation-panel__empty">No recommendation yet.</p>;
  }

  return (
    <div className="recommendation-panel">
      <p className="recommendation-panel__text">{recommendation.action_text}</p>
      <div className="recommendation-panel__meta">
        <span>
          Priority: <StatusBadge value={recommendation.priority === "high" ? "critical" : recommendation.priority === "medium" ? "medium" : "low"} label={titleCase(recommendation.priority)} />
        </span>
        {recommendation.estimated_saving != null && (
          <span>
            Estimated wastage (this window): <span className="mono">{formatConsumption(recommendation.estimated_saving, unit)}</span>
          </span>
        )}
      </div>
    </div>
  );
}
