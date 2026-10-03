import { useMemo } from "react";
import { telemetryApi } from "../../api/telemetry";
import { useAsync } from "../../hooks/useAsync";
import TrendChart from "../charts/TrendChart";
import { LoadingState } from "../common/States";

/**
 * Visualizes real measurements spanning from before the anomaly through
 * the post-intervention window (docs Milestone 7, requirement #15) — no
 * decorative fake data; if telemetry for the range isn't available yet,
 * the chart says so rather than drawing something invented.
 */
export default function VerificationChart({ resourceId, anomalyWindowStart, anomalyWindowEnd, interventionCompletedAt }) {
  const rangeStart = useMemo(() => new Date(new Date(anomalyWindowStart).getTime() - 12 * 3600 * 1000).toISOString(), [anomalyWindowStart]);
  const rangeEnd = useMemo(
    () => new Date(new Date(interventionCompletedAt || anomalyWindowEnd).getTime() + 24 * 3600 * 1000).toISOString(),
    [anomalyWindowEnd, interventionCompletedAt]
  );

  const measurementsState = useAsync(
    () => telemetryApi.getMeasurements({ resourceId, start: rangeStart, end: rangeEnd, limit: 500 }),
    [resourceId, rangeStart, rangeEnd]
  );

  if (measurementsState.loading) return <LoadingState label="Loading telemetry around this anomaly…" />;
  if (measurementsState.error || !measurementsState.data?.items?.length) {
    return <p>Telemetry for this window isn't available.</p>;
  }

  const points = measurementsState.data.items.map((m) => ({ x: new Date(m.timestamp), y: m.consumption }));

  const markers = [{ x: new Date(anomalyWindowStart), label: "Anomaly", color: "#a33a2f" }];
  if (interventionCompletedAt) {
    markers.push({ x: new Date(interventionCompletedAt), label: "Intervention", color: "#2f6b4f" });
  }

  return (
    <TrendChart
      series={[{ label: "Consumption", color: "#3d5a80", points }]}
      markers={markers}
      formatX={(x) => new Date(x).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit" })}
    />
  );
}
