import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { analyticsApi } from "../api/analytics";
import { investigationApi } from "../api/workflow";
import AIInvestigationPanel from "../components/investigations/AIInvestigationPanel";
import EvidenceList from "../components/investigations/EvidenceList";
import InterventionFlow from "../components/investigations/InterventionFlow";
import InvestigationTimeline from "../components/investigations/InvestigationTimeline";
import MethodologySplit from "../components/investigations/MethodologySplit";
import RecommendationPanel from "../components/investigations/RecommendationPanel";
import VerificationChart from "../components/investigations/VerificationChart";
import { Button, Card, SectionHeading } from "../components/common/Primitives";
import StatusBadge from "../components/common/StatusBadge";
import { ErrorState, LoadingState } from "../components/common/States";
import { useAsync } from "../hooks/useAsync";
import { formatDuration, formatPercent, formatTimestamp, RESOURCE_UNIT, titleCase } from "../utils/format";
import "./InvestigationDetail.css";

export default function InvestigationDetail() {
  const { anomalyId } = useParams();
  const navigate = useNavigate();
  const anomalyState = useAsync(() => analyticsApi.getAnomaly(anomalyId), [anomalyId]);
  const [investigating, setInvestigating] = useState(false);
  const [investigateError, setInvestigateError] = useState(null);
  const [localIntervention, setLocalIntervention] = useState(undefined); // overrides the fetched value after a local action (create/complete/verify)

  if (anomalyState.loading) return <LoadingState label="Loading investigation…" />;
  if (anomalyState.error) {
    return <ErrorState title="Could not load this investigation" message={anomalyState.error.message} onRetry={anomalyState.reload} />;
  }

  const anomaly = anomalyState.data;
  const investigation = anomaly.investigation;
  const unit = RESOURCE_UNIT[anomaly.resource_type] || "";
  const intervention = localIntervention !== undefined ? localIntervention : investigation?.recommendation?.intervention || null;

  const handleInvestigate = async () => {
    setInvestigating(true);
    setInvestigateError(null);
    try {
      await investigationApi.investigate(anomaly.id);
      await anomalyState.reload();
    } catch (err) {
      setInvestigateError(err);
    } finally {
      setInvestigating(false);
    }
  };

  return (
    <div className="investigation-detail">
      <SectionHeading eyebrow={`${titleCase(anomaly.resource_type)} anomaly`} title={investigation?.top_cause ? titleCase(investigation.top_cause) : "Awaiting investigation"}>
        <StatusBadge value={anomaly.severity} />
      </SectionHeading>

      <div className="investigation-detail__meta-row">
        <span>{anomaly.deviation_pct != null ? formatPercent(anomaly.deviation_pct, { signed: true }) + " above baseline" : `z-score ${anomaly.z_score.toFixed(1)}`}</span>
        <span>{formatDuration(anomaly.signals?.persistence_hours)}</span>
        <span>Detected {formatTimestamp(anomaly.detected_at)}</span>
        <StatusBadge value={anomaly.classification} />
      </div>

      <div className="investigation-detail__layout">
        <div className="investigation-detail__stack">
          <Card>
            <SectionHeading eyebrow="Why is this suspicious" title="Evidence" />
            <EvidenceList evidence={anomaly.evidence} />
          </Card>

          <Card>
            <MethodologySplit anomaly={anomaly} investigation={investigation} />
          </Card>

          <Card>
            <SectionHeading eyebrow="What does EcoTwin think" title="Investigation" />
            {investigation?.explanation ? (
              <AIInvestigationPanel investigation={investigation} />
            ) : (
              <div className="investigation-detail__prompt">
                <p>This anomaly hasn't been investigated yet.</p>
                <Button onClick={handleInvestigate} disabled={investigating}>
                  {investigating ? "Investigating…" : "Investigate"}
                </Button>
                {investigateError && <p className="investigation-detail__error">{investigateError.message}</p>}
              </div>
            )}
          </Card>

          {investigation?.explanation && (
            <Card>
              <SectionHeading eyebrow="What should we do" title="Recommended action" />
              <RecommendationPanel recommendation={investigation.recommendation} unit={unit} />
            </Card>
          )}

          {investigation?.explanation && (
            <Card>
              <SectionHeading eyebrow="Did it work" title="Intervention &amp; verification" />
              <InterventionFlow
                investigationId={investigation.id}
                intervention={intervention}
                unit={unit}
                onInterventionChange={setLocalIntervention}
              />
            </Card>
          )}

          {intervention && (
            <Card>
              <SectionHeading eyebrow="Before / after" title="Consumption around this anomaly" />
              <VerificationChart
                resourceId={anomaly.resource_id}
                anomalyWindowStart={anomaly.window_start}
                anomalyWindowEnd={anomaly.window_end}
                interventionCompletedAt={intervention.marked_complete_at}
              />
            </Card>
          )}
        </div>

        <Card className="investigation-detail__timeline-card">
          <SectionHeading eyebrow="Workflow" title="Investigation timeline" />
          <InvestigationTimeline anomaly={anomaly} investigation={investigation} intervention={intervention} />
        </Card>
      </div>

      <button type="button" className="btn btn--ghost investigation-detail__back" onClick={() => navigate("/investigations")}>
        ← Back to Investigations
      </button>
    </div>
  );
}
