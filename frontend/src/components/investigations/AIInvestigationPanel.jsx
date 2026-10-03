import { titleCase } from "../../utils/format";
import { AIUnavailableNotice } from "../common/States";
import StatusBadge from "../common/StatusBadge";
import "./AIInvestigationPanel.css";

/**
 * Displays the AI (or deterministic fallback) investigation result
 * (docs Milestone 6, requirements #14-15). The observed/inference split
 * mirrors the backend's InvestigationResult schema directly — this
 * component never re-derives or rephrases either field.
 */
export default function AIInvestigationPanel({ investigation, fallbackReason }) {
  const { explanation, explanation_source: source, top_cause: topCause } = investigation;

  if (!explanation) {
    return <p className="ai-panel__empty">Not yet investigated.</p>;
  }

  return (
    <div className="ai-panel">
      <div className="ai-panel__header">
        <div>
          <p className="ai-panel__eyebrow">Contextual Investigation {source === "ai" ? "· AI-assisted" : ""}</p>
          <h3 className="ai-panel__cause">{titleCase(topCause)}</h3>
        </div>
        <div className="ai-panel__meta">
          <span className="ai-panel__engine-label">{source === "ai" ? "Investigation engine: AI reasoning" : "Investigation engine: Deterministic fallback"}</span>
          <span className="ai-panel__confidence">
            Confidence: <StatusBadge value={explanation.reasoning_confidence === "high" ? "verified" : explanation.reasoning_confidence === "medium" ? "improvement_detected" : "insufficient_data"} label={titleCase(explanation.reasoning_confidence)} />
          </span>
        </div>
      </div>

      {source !== "ai" && <AIUnavailableNotice fallbackReason={fallbackReason} />}

      <div className="ai-panel__block">
        <p className="ai-panel__label">Observed</p>
        <ul className="ai-panel__list">
          {explanation.observed.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ul>
      </div>

      <div className="ai-panel__block">
        <p className="ai-panel__label">Inference</p>
        <p className="ai-panel__inference">{explanation.inference}</p>
      </div>

      {explanation.alternative_explanations?.length > 0 && (
        <div className="ai-panel__block">
          <p className="ai-panel__label">Alternative explanations</p>
          <ol className="ai-panel__list">
            {explanation.alternative_explanations.map((alt, idx) => (
              <li key={idx}>
                <strong>{titleCase(alt.cause)}</strong> — {alt.why_less_likely}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
