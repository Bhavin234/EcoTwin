import { useMemo } from "react";
import { analyticsApi } from "../api/analytics";
import { impactApi } from "../api/workflow";
import { telemetryApi } from "../api/telemetry";
import AnomalyTable from "../components/anomalies/AnomalyTable";
import { Card, MetricTile, SectionHeading } from "../components/common/Primitives";
import { ErrorState, LoadingState } from "../components/common/States";
import TrendChart from "../components/charts/TrendChart";
import { useLocationContext } from "../context/LocationContext";
import { useAsync } from "../hooks/useAsync";
import { formatCo2e, formatCurrency, titleCase } from "../utils/format";

export default function Overview() {
  const { selectedLocation, loading: locationLoading } = useLocationContext();
  const locationId = selectedLocation?.id;

  const resourcesState = useAsync(() => (locationId ? telemetryApi.listResources({ locationId }) : Promise.resolve([])), [locationId]);
  const anomaliesState = useAsync(() => (locationId ? analyticsApi.listAnomalies({ locationId, status: "open" }) : Promise.resolve([])), [locationId]);
  const impactState = useAsync(() => (locationId ? impactApi.getImpact({ locationId }) : Promise.resolve(null)), [locationId]);

  const electricityResource = resourcesState.data?.find((r) => r.resource_type === "electricity");
  const waterResource = resourcesState.data?.find((r) => r.resource_type === "water");

  const electricityRecent = useAsync(
    () => (electricityResource ? telemetryApi.getRecentMeasurements({ resourceId: electricityResource.id, count: 72 }) : Promise.resolve([])),
    [electricityResource?.id]
  );
  const waterRecent = useAsync(
    () => (waterResource ? telemetryApi.getRecentMeasurements({ resourceId: waterResource.id, count: 72 }) : Promise.resolve([])),
    [waterResource?.id]
  );

  const trendSeries = useMemo(() => {
    const series = [];
    if (electricityRecent.data?.length) {
      series.push({
        label: "Electricity (kWh)",
        color: "#2f6b4f",
        points: electricityRecent.data.map((m) => ({ x: new Date(m.timestamp), y: m.consumption })),
      });
    }
    if (waterRecent.data?.length) {
      series.push({
        label: "Water (L)",
        color: "#3d5a80",
        points: waterRecent.data.map((m) => ({ x: new Date(m.timestamp), y: m.consumption })),
      });
    }
    return series;
  }, [electricityRecent.data, waterRecent.data]);

  if (locationLoading) return <LoadingState label="Loading location…" />;
  if (!selectedLocation) {
    return (
      <ErrorState
        title="No location data yet"
        message="Seed a demo dataset from the Data page, or click Run EcoTwin Demo, to get started."
      />
    );
  }

  const latestElectricity = electricityRecent.data?.[electricityRecent.data.length - 1];
  const latestWater = waterRecent.data?.[waterRecent.data.length - 1];

  const estimatedSummary = impactState.data?.summary.find((s) => s.kind === "estimated");
  const verifiedSummary = impactState.data?.summary.find((s) => s.kind === "verified");

  const activeAnomalies = anomaliesState.data || [];

  return (
    <div>
      <SectionHeading eyebrow="Overview" title={selectedLocation.name} />

      <div className="kpi-row">
        <MetricTile
          label="Electricity — latest reading"
          value={latestElectricity ? `${latestElectricity.consumption.toFixed(1)} kWh` : "—"}
          sublabel={latestElectricity ? titleCase(latestElectricity.operating_status) : "No data"}
        />
        <MetricTile
          label="Water — latest reading"
          value={latestWater ? `${latestWater.consumption.toFixed(1)} L` : "—"}
          sublabel={latestWater ? titleCase(latestWater.operating_status) : "No data"}
        />
        <MetricTile
          label="Active anomalies"
          value={activeAnomalies.length}
          tone={activeAnomalies.length > 0 ? "warning" : "positive"}
          sublabel={activeAnomalies.length > 0 ? "Needs review" : "None open"}
        />
        <MetricTile
          label="Verified impact (CO₂e)"
          value={verifiedSummary ? formatCo2e(verifiedSummary.total_co2e_avoided_kg) : "—"}
          tone="positive"
          sublabel={verifiedSummary ? formatCurrency(verifiedSummary.total_money_saved) : "No verified impact yet"}
        />
      </div>

      <div className="page-grid">
        <Card>
          <SectionHeading eyebrow="Telemetry" title="Resource consumption (last 72 readings)" />
          {electricityRecent.loading || waterRecent.loading ? (
            <LoadingState label="Loading telemetry…" />
          ) : (
            <>
              <TrendChart series={trendSeries} formatX={(x) => new Date(x).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })} />
              <div className="trend-chart-legend">
                {trendSeries.map((s) => (
                  <span key={s.label} className="trend-chart-legend__item">
                    <span className="trend-chart-legend__swatch" style={{ background: s.color }} />
                    {s.label}
                  </span>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card>
          <SectionHeading eyebrow="Active issues" title="Anomalies" />
          {anomaliesState.loading ? (
            <LoadingState label="Loading anomalies…" />
          ) : anomaliesState.error ? (
            <ErrorState message={anomaliesState.error.message} onRetry={anomaliesState.reload} />
          ) : (
            <AnomalyTable
              anomalies={activeAnomalies}
              resourceLabelById={{
                [electricityResource?.id]: "Electricity",
                [waterResource?.id]: "Water",
              }}
            />
          )}
        </Card>

        <Card>
          <SectionHeading eyebrow="Recent impact" title="Estimated vs. verified" />
          {impactState.loading ? (
            <LoadingState label="Loading impact…" />
          ) : (
            <div className="overview-impact-row">
              <div>
                <p className="overview-impact-row__label">Estimated</p>
                <p className="mono overview-impact-row__value">{estimatedSummary ? formatCurrency(estimatedSummary.total_money_saved) : "—"}</p>
                <p className="overview-impact-row__sub">{estimatedSummary ? formatCo2e(estimatedSummary.total_co2e_avoided_kg) : "No estimated impact yet"}</p>
              </div>
              <div>
                <p className="overview-impact-row__label">Verified</p>
                <p className="mono overview-impact-row__value overview-impact-row__value--verified">{verifiedSummary ? formatCurrency(verifiedSummary.total_money_saved) : "—"}</p>
                <p className="overview-impact-row__sub">{verifiedSummary ? formatCo2e(verifiedSummary.total_co2e_avoided_kg) : "No verified impact yet"}</p>
              </div>
            </div>
          )}
        </Card>
      </div>

      <Card className="why-ecotwin">
        <SectionHeading eyebrow="Why EcoTwin" title="A closed sustainability loop" />
        <div className="why-ecotwin__grid">
          <div>
            <p className="why-ecotwin__step">Detect</p>
            <p className="why-ecotwin__copy">Find resource anomalies using contextual baselines, not a single threshold.</p>
          </div>
          <div>
            <p className="why-ecotwin__step">Investigate</p>
            <p className="why-ecotwin__copy">Combine structured evidence with contextual AI reasoning to explain the likely cause.</p>
          </div>
          <div>
            <p className="why-ecotwin__step">Act</p>
            <p className="why-ecotwin__copy">Turn findings into a specific, prioritized operational intervention.</p>
          </div>
          <div>
            <p className="why-ecotwin__step">Verify</p>
            <p className="why-ecotwin__copy">Measure whether the intervention actually worked — not just assume it did.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
