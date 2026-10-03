import { useMemo, useState } from "react";
import { analyticsApi } from "../api/analytics";
import { telemetryApi } from "../api/telemetry";
import TrendChart from "../components/charts/TrendChart";
import { Card, MetricTile, SectionHeading } from "../components/common/Primitives";
import { ErrorState, LoadingState } from "../components/common/States";
import { useLocationContext } from "../context/LocationContext";
import { useAsync } from "../hooks/useAsync";
import { formatConsumption, RESOURCE_UNIT, titleCase } from "../utils/format";

const RESOURCE_TABS = [
  { key: "electricity", label: "Electricity" },
  { key: "water", label: "Water" },
];

export default function Resources() {
  const { selectedLocation, loading: locationLoading } = useLocationContext();
  const [activeTab, setActiveTab] = useState("electricity");
  const locationId = selectedLocation?.id;

  const resourcesState = useAsync(() => (locationId ? telemetryApi.listResources({ locationId }) : Promise.resolve([])), [locationId]);
  const resource = resourcesState.data?.find((r) => r.resource_type === activeTab);

  const measurementsState = useAsync(
    () => (resource ? telemetryApi.getRecentMeasurements({ resourceId: resource.id, count: 168 }) : Promise.resolve([])),
    [resource?.id]
  );
  const baselinesState = useAsync(() => (resource ? analyticsApi.getResourceBaselines(resource.id) : Promise.resolve([])), [resource?.id]);
  const anomaliesState = useAsync(() => (resource ? analyticsApi.listAnomalies({ resourceId: resource.id }) : Promise.resolve([])), [resource?.id]);

  const latest = measurementsState.data?.[measurementsState.data.length - 1];

  const matchingBaseline = useMemo(() => {
    if (!latest || !baselinesState.data) return null;
    const ts = new Date(latest.timestamp);
    const hour = ts.getUTCHours();
    // JS getUTCDay(): 0=Sunday..6=Saturday; backend uses 0=Monday..6=Sunday — convert.
    const weekday = (ts.getUTCDay() + 6) % 7;
    return baselinesState.data.find((b) => b.hour_of_day === hour && b.day_of_week === weekday) || null;
  }, [latest, baselinesState.data]);

  if (locationLoading) return <LoadingState label="Loading location…" />;
  if (!selectedLocation) return <ErrorState title="No location data yet" message="Seed a demo dataset from the Data page first." />;

  const unit = RESOURCE_UNIT[activeTab];
  const anomalyMarkers = (anomaliesState.data || []).map((a) => ({
    x: new Date(a.window_start),
    label: titleCase(a.severity),
    color: a.severity === "critical" || a.severity === "high" ? "#a33a2f" : "#9a6b12",
  }));

  return (
    <div>
      <SectionHeading eyebrow="Resources" title="Consumption &amp; operating context" />

      <div className="tab-row" role="tablist" aria-label="Resource type">
        {RESOURCE_TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            className={`tab-button${activeTab === tab.key ? " tab-button--active" : ""}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {!resource ? (
        <LoadingState label="Loading resource…" />
      ) : (
        <div className="page-stack">
          <div className="kpi-row">
            <MetricTile label="Latest reading" value={latest ? formatConsumption(latest.consumption, unit) : "—"} sublabel={latest ? titleCase(latest.operating_status) : ""} />
            <MetricTile
              label="Expected (baseline) for this slot"
              value={matchingBaseline ? formatConsumption(matchingBaseline.mean, unit) : "—"}
              sublabel={matchingBaseline ? `${matchingBaseline.sample_count} comparable samples` : "Not yet computed — run analysis"}
            />
            <MetricTile label="Occupancy" value={latest?.occupancy ?? "—"} sublabel="people (reported)" />
            <MetricTile label="Open anomalies" value={(anomaliesState.data || []).filter((a) => a.status === "open").length} />
          </div>

          <Card>
            <SectionHeading eyebrow={titleCase(activeTab)} title="Consumption trend" />
            {measurementsState.loading ? (
              <LoadingState label="Loading telemetry…" />
            ) : measurementsState.error ? (
              <ErrorState message={measurementsState.error.message} onRetry={measurementsState.reload} />
            ) : (
              <TrendChart
                series={[
                  {
                    label: titleCase(activeTab),
                    color: activeTab === "electricity" ? "#2f6b4f" : "#3d5a80",
                    points: (measurementsState.data || []).map((m) => ({ x: new Date(m.timestamp), y: m.consumption })),
                  },
                ]}
                markers={anomalyMarkers}
                formatX={(x) => new Date(x).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}
              />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
