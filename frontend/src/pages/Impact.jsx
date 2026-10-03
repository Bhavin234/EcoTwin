import { impactApi } from "../api/workflow";
import { Card, SectionHeading } from "../components/common/Primitives";
import { ErrorState, LoadingState } from "../components/common/States";
import ImpactSummary from "../components/impact/ImpactSummary";
import { useLocationContext } from "../context/LocationContext";
import { useAsync } from "../hooks/useAsync";
import { formatCo2e, formatCurrency, formatTimestamp, titleCase } from "../utils/format";
import "./Impact.css";

export default function Impact() {
  const { selectedLocation, loading: locationLoading } = useLocationContext();
  const locationId = selectedLocation?.id;

  const impactState = useAsync(() => (locationId ? impactApi.getImpact({ locationId }) : Promise.resolve(null)), [locationId]);

  if (locationLoading) return <LoadingState label="Loading location…" />;
  if (!selectedLocation) return <ErrorState title="No location data yet" message="Seed a demo dataset from the Data page first." />;
  if (impactState.loading) return <LoadingState label="Loading impact…" />;
  if (impactState.error) return <ErrorState message={impactState.error.message} onRetry={impactState.reload} />;

  const { summary, records } = impactState.data;

  return (
    <div>
      <SectionHeading eyebrow="Impact" title="Environmental &amp; financial impact" />

      <div className="page-grid">
        <Card>
          <SectionHeading eyebrow="Summary" title="By category" />
          <ImpactSummary summary={summary} />
        </Card>

        <Card>
          <SectionHeading eyebrow="Detail" title="Impact records" />
          {records.length === 0 ? (
            <p className="impact-page__empty">No impact records yet.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Kind</th>
                  <th>Money saved</th>
                  <th>CO₂e</th>
                  <th>Window</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.id}>
                    <td>{titleCase(r.kind)}</td>
                    <td className="mono">{formatCurrency(r.money_saved)}</td>
                    <td className="mono">{formatCo2e(r.co2e_avoided_kg)}</td>
                    <td>
                      {formatTimestamp(r.window_start)} → {formatTimestamp(r.window_end)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
