import { formatDuration, formatPercent, titleCase } from "../../utils/format";
import "./MethodologySplit.css";

/**
 * Makes the deterministic-analysis vs. AI-reasoning separation visible
 * (docs Milestone 7, requirement #10) — every value shown here is read
 * directly from the anomaly/investigation the backend already computed;
 * this component adds no new business logic, only a side-by-side layout.
 */
export default function MethodologySplit({ anomaly, investigation }) {
  const signals = anomaly.signals || {};

  return (
    <div>
      <p className="methodology-split__eyebrow">How EcoTwin reached this conclusion</p>
      <div className="methodology-split">
        <div className="methodology-split__column">
          <p className="methodology-split__heading">Deterministic analysis</p>
          <dl className="methodology-split__list">
            <div>
              <dt>Baseline</dt>
              <dd>{titleCase(signals.baseline_state) || "—"} confidence</dd>
            </div>
            <div>
              <dt>Deviation</dt>
              <dd>{anomaly.deviation_pct != null ? formatPercent(anomaly.deviation_pct, { signed: true }) : `z=${anomaly.z_score?.toFixed(1)}`}</dd>
            </div>
            <div>
              <dt>Persistence</dt>
              <dd>{formatDuration(signals.persistence_hours)}</dd>
            </div>
            <div>
              <dt>Operational context</dt>
              <dd>
                {signals.majority_closed ? "Closed" : "Open"} · Occupancy {signals.majority_zero_occupancy ? "zero" : "present"}
              </dd>
            </div>
            <div>
              <dt>Candidate causes</dt>
              <dd>{investigation?.candidate_causes?.map((c) => titleCase(c.cause)).join(", ") || "—"}</dd>
            </div>
          </dl>
        </div>

        <div className="methodology-split__column">
          <p className="methodology-split__heading">AI contextual investigation</p>
          {investigation?.explanation ? (
            <dl className="methodology-split__list">
              <div>
                <dt>Likely cause</dt>
                <dd>{titleCase(investigation.explanation.likely_cause)}</dd>
              </div>
              <div>
                <dt>Alternative explanations</dt>
                <dd>{investigation.explanation.alternative_explanations?.map((a) => titleCase(a.cause)).join(", ") || "None"}</dd>
              </div>
              <div>
                <dt>Recommended next step</dt>
                <dd>{investigation.explanation.recommended_next_step}</dd>
              </div>
            </dl>
          ) : (
            <p className="methodology-split__empty">Not yet investigated.</p>
          )}
        </div>
      </div>
    </div>
  );
}
