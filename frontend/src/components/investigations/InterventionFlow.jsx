import { useState } from "react";
import { interventionApi } from "../../api/workflow";
import { formatConsumption, formatCo2e, formatCurrency, formatTimestamp } from "../../utils/format";
import { Button } from "../common/Primitives";
import StatusBadge from "../common/StatusBadge";
import "./InterventionFlow.css";

/**
 * The intervention + verification workflow (docs Milestone 6, requirements
 * #17-19). All state transitions are backend-driven — this component only
 * calls the existing intervention/verification APIs and displays their
 * response; it never decides completion or verification itself.
 */
export default function InterventionFlow({ investigationId, intervention, unit, onInterventionChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [verification, setVerification] = useState(null);

  const handleCreate = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await interventionApi.create(investigationId);
      onInterventionChange(created);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const handleComplete = async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await interventionApi.complete(intervention.id);
      onInterventionChange(updated);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const handleVerify = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await interventionApi.verify(intervention.id);
      setVerification(result);
      onInterventionChange({ ...intervention, verification_status: result.verification_status });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (!intervention) {
    return (
      <div className="intervention-flow">
        <p className="intervention-flow__hint">No intervention recorded yet for this investigation.</p>
        <Button onClick={handleCreate} disabled={busy}>
          Create Intervention
        </Button>
        {error && <p className="intervention-flow__error">{error.message}</p>}
      </div>
    );
  }

  return (
    <div className="intervention-flow">
      <div className="intervention-flow__status-row">
        <span>
          Status: <StatusBadge value={intervention.status} />
        </span>
        {intervention.marked_complete_at && <span className="intervention-flow__timestamp">Completed {formatTimestamp(intervention.marked_complete_at)}</span>}
      </div>

      {intervention.status !== "completed" && (
        <Button onClick={handleComplete} disabled={busy}>
          Mark Intervention Complete
        </Button>
      )}

      {intervention.status === "completed" && (
        <div className="intervention-flow__verification">
          <div className="intervention-flow__status-row">
            <span>
              Verification: <StatusBadge value={intervention.verification_status} />
            </span>
            {intervention.verification_status === "pending" || !verification ? (
              <Button variant="secondary" onClick={handleVerify} disabled={busy}>
                Run Verification
              </Button>
            ) : (
              <Button variant="ghost" onClick={handleVerify} disabled={busy}>
                Re-check
              </Button>
            )}
          </div>

          {verification && (
            <div className="verification-result">
              <p className="verification-result__message">{verification.message}</p>
              {verification.actual_post_consumption_mean != null && (
                <div className="verification-result__grid">
                  <div>
                    <p className="verification-result__label">Expected (ordinary baseline)</p>
                    <p className="mono">{formatConsumption(verification.ordinary_baseline_mean, unit)}</p>
                  </div>
                  <div>
                    <p className="verification-result__label">Actual (post-intervention)</p>
                    <p className="mono">{formatConsumption(verification.actual_post_consumption_mean, unit)}</p>
                  </div>
                  <div>
                    <p className="verification-result__label">Avoided vs. continuing anomaly</p>
                    <p className="mono">{formatConsumption(verification.avoided_consumption, unit)}</p>
                  </div>
                  <div>
                    <p className="verification-result__label">Impact</p>
                    <p className="mono">
                      {formatCurrency(verification.money_saved)} · {formatCo2e(verification.co2e_avoided_kg)}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {error && <p className="intervention-flow__error">{error.message}</p>}
    </div>
  );
}
