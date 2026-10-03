import { Link } from "react-router-dom";
import { analyticsApi } from "../api/analytics";
import { telemetryApi } from "../api/telemetry";
import { Card, SectionHeading } from "../components/common/Primitives";
import StatusBadge from "../components/common/StatusBadge";
import { ErrorState, LoadingState } from "../components/common/States";
import { useLocationContext } from "../context/LocationContext";
import { useAsync } from "../hooks/useAsync";
import { formatPercent, formatTimestamp, titleCase } from "../utils/format";
import "./Investigations.css";

export default function Investigations() {
  const { selectedLocation, loading: locationLoading } = useLocationContext();
  const locationId = selectedLocation?.id;

  const resourcesState = useAsync(() => (locationId ? telemetryApi.listResources({ locationId }) : Promise.resolve([])), [locationId]);
  const anomaliesState = useAsync(
    () => (locationId ? analyticsApi.listAnomalies({ locationId, classification: "operationally_suspicious" }) : Promise.resolve([])),
    [locationId]
  );

  if (locationLoading) return <LoadingState label="Loading location…" />;
  if (!selectedLocation) return <ErrorState title="No location data yet" message="Seed a demo dataset from the Data page first." />;

  const resourceById = Object.fromEntries((resourcesState.data || []).map((r) => [r.id, r]));
  const anomalies = anomaliesState.data || [];

  return (
    <div>
      <SectionHeading eyebrow="Investigations" title="Anomalies requiring investigation" />

      {anomaliesState.loading ? (
        <LoadingState label="Loading investigations…" />
      ) : anomaliesState.error ? (
        <ErrorState message={anomaliesState.error.message} onRetry={anomaliesState.reload} />
      ) : anomalies.length === 0 ? (
        <Card>
          <p className="investigations-empty">
            No operationally-suspicious anomalies right now. Anomalies appear here once the deterministic analytics engine detects
            elevated, persistent, contextually-inconsistent consumption — see Resources for statistically unusual but not (yet)
            suspicious readings.
          </p>
        </Card>
      ) : (
        <div className="investigation-card-list">
          {anomalies.map((anomaly) => {
            const resource = resourceById[anomaly.resource_id];
            return (
              <Link key={anomaly.id} to={`/investigations/${anomaly.id}`} className="investigation-card">
                <div className="investigation-card__header">
                  <span className="investigation-card__resource">{titleCase(resource?.resource_type) || "Resource"}</span>
                  <StatusBadge value={anomaly.severity} />
                </div>
                <p className="investigation-card__deviation">
                  {anomaly.deviation_pct != null ? formatPercent(anomaly.deviation_pct, { signed: true }) + " above baseline" : `z-score ${anomaly.z_score.toFixed(1)}`}
                </p>
                <p className="investigation-card__meta">Detected {formatTimestamp(anomaly.detected_at)}</p>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
