import { useRef, useState } from "react";
import { telemetryApi } from "../api/telemetry";
import { Button, Card, SectionHeading } from "../components/common/Primitives";
import { ErrorState, LoadingState } from "../components/common/States";
import { useLocationContext } from "../context/LocationContext";
import { useAsync } from "../hooks/useAsync";
import { formatTimestamp, titleCase } from "../utils/format";
import LiveSimulator from "../components/data/LiveSimulator";
import "./Data.css";

const SCENARIOS = [
  "normal_operation",
  "water_leak",
  "electricity_overconsumption",
  "closed_building_consumption",
  "legitimate_spike",
  "post_intervention_recovery",
];

export default function Data() {
  const { selectedLocation, loading: locationLoading, refresh: refreshLocations } = useLocationContext();
  const [scenario, setScenario] = useState("post_intervention_recovery");
  const [seeding, setSeeding] = useState(false);
  const [seedMessage, setSeedMessage] = useState(null);
  const [uploadMessage, setUploadMessage] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);

  const locationId = selectedLocation?.id;
  const resourcesState = useAsync(() => (locationId ? telemetryApi.listResources({ locationId }) : Promise.resolve([])), [locationId]);
  const firstResource = resourcesState.data?.[0];
  const measurementsState = useAsync(
    () => (firstResource ? telemetryApi.getRecentMeasurements({ resourceId: firstResource.id, count: 25 }) : Promise.resolve([])),
    [firstResource?.id]
  );

  const handleGenerate = async () => {
    setSeeding(true);
    setSeedMessage(null);
    try {
      const result = await telemetryApi.simulate({ scenario, locationName: selectedLocation?.name || "Greenfield Public School" });
      setSeedMessage(`Inserted ${Object.values(result.inserted).reduce((a, b) => a + b, 0)} new readings.`);
      await refreshLocations();
    } catch (err) {
      setSeedMessage(err.message);
    } finally {
      setSeeding(false);
    }
  };

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadMessage(null);
    setUploadError(null);
    try {
      const result = await telemetryApi.uploadCsv(file);
      setUploadMessage(`Inserted ${result.inserted} row(s), skipped ${result.skipped_duplicates} duplicate(s).`);
      await refreshLocations();
    } catch (err) {
      setUploadError(err);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div>
      <SectionHeading eyebrow="Data" title="Telemetry &amp; ingestion" />

      <div className="page-grid">
        <Card>
          <SectionHeading eyebrow={selectedLocation?.name || "No location"} title="Recent telemetry" />
          {locationLoading || measurementsState.loading ? (
            <LoadingState label="Loading telemetry…" />
          ) : measurementsState.error ? (
            <ErrorState message={measurementsState.error.message} onRetry={measurementsState.reload} />
          ) : !measurementsState.data?.length ? (
            <p className="data-page__empty">No telemetry yet — generate demo data or upload a CSV to get started.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Resource</th>
                  <th>Consumption</th>
                  <th>Occupancy</th>
                  <th>Status</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {[...measurementsState.data].reverse().map((m) => (
                  <tr key={m.id}>
                    <td>{formatTimestamp(m.timestamp)}</td>
                    <td>{titleCase(firstResource?.resource_type)}</td>
                    <td className="mono">{m.consumption}</td>
                    <td className="mono">{m.occupancy ?? "—"}</td>
                    <td>{titleCase(m.operating_status)}</td>
                    <td>{titleCase(m.source)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <div className="page-stack">
          <Card>
            <SectionHeading eyebrow="Live demo" title="Simulated telemetry stream" />
            <LiveSimulator locationId={locationId} onTick={measurementsState.reload} />
          </Card>

          <Card>
            <SectionHeading eyebrow="Data sources" title="Ingestion" />
            <div className="data-page__ingestion-list">
              <div className="data-page__ingestion-item">
                <p className="data-page__ingestion-label">CSV upload</p>
                <input ref={fileInputRef} type="file" accept=".csv" onChange={handleUpload} />
                {uploadMessage && <p className="data-page__message">{uploadMessage}</p>}
                {uploadError && <p className="data-page__error">{uploadError.message}{uploadError.details ? `: ${uploadError.details.join("; ")}` : ""}</p>}
              </div>

              <div className="data-page__ingestion-item">
                <p className="data-page__ingestion-label">Generate demo data</p>
                <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
                  {SCENARIOS.map((s) => (
                    <option key={s} value={s}>
                      {titleCase(s)}
                    </option>
                  ))}
                </select>
                <Button variant="secondary" onClick={handleGenerate} disabled={seeding}>
                  {seeding ? "Generating…" : "Generate"}
                </Button>
                {seedMessage && <p className="data-page__message">{seedMessage}</p>}
              </div>

              <div className="data-page__ingestion-item">
                <p className="data-page__ingestion-label">Telemetry API</p>
                <p className="data-page__message">Available for future smart meters / IoT devices — see below.</p>
              </div>
            </div>
          </Card>

          <Card>
            <SectionHeading eyebrow="Architecture" title="Hardware-agnostic ingestion" />
            <p className="data-page__hw-copy">
              EcoTwin's intelligence layer consumes normalized telemetry regardless of the underlying source — it never knows or
              cares whether a reading came from a CSV, the simulator, or (in the future) a real smart meter, IoT sensor, or
              building management system. No physical hardware is connected in this environment; ingestion here is CSV and
              simulated telemetry only.
            </p>
            <p className="data-page__hw-sources">CSV · Simulated telemetry · Future smart meters · Future BMS · Future IoT sensors</p>
          </Card>
        </div>
      </div>
    </div>
  );
}
