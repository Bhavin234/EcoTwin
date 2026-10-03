import { useEffect, useRef, useState } from "react";
import { telemetryApi } from "../../api/telemetry";
import { Button } from "../common/Primitives";
import { formatTimestamp } from "../../utils/format";

export default function LiveSimulator({ locationId, onTick }) {
  const [running, setRunning] = useState(false);
  const [hoursPerTick, setHoursPerTick] = useState(6);
  const [lastTick, setLastTick] = useState(null);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);
  const busyRef = useRef(false);

  useEffect(() => () => clearInterval(timerRef.current), []);

  const tick = async () => {
    if (!locationId || busyRef.current) return false;
    busyRef.current = true;
    setError(null);
    try {
      const result = await telemetryApi.liveTick({ locationId, hours: hoursPerTick });
      setLastTick(result);
      onTick?.();
      return true;
    } catch (err) {
      setError(err.message);
      setRunning(false);
      clearInterval(timerRef.current);
      return false;
    } finally {
      busyRef.current = false;
    }
  };

  const start = async () => {
    clearInterval(timerRef.current);
    setRunning(true);
    const ok = await tick();
    if (ok) timerRef.current = setInterval(tick, 10000);
  };

  const stop = () => {
    clearInterval(timerRef.current);
    setRunning(false);
  };

  if (!locationId) return null;

  return (
    <div className="live-simulator">
      <div>
        <p className="data-page__ingestion-label">Live simulated telemetry</p>
        <p className="data-page__message">
          Advances the simulated clock while this page is open. The readings are deterministic mock telemetry, not physical sensor data.
        </p>
      </div>
      <div className="live-simulator__controls">
        <label>
          Simulated hours / tick
          <select value={hoursPerTick} onChange={(e) => setHoursPerTick(Number(e.target.value))} disabled={running}>
            <option value={1}>1 hour</option>
            <option value={6}>6 hours</option>
            <option value={24}>24 hours</option>
          </select>
        </label>
        {!running ? (
          <Button variant="secondary" onClick={start}>Start live stream</Button>
        ) : (
          <Button variant="secondary" onClick={stop}>Stop live stream</Button>
        )}
      </div>
      {lastTick && (
        <p className="live-simulator__status">
          {running ? "Streaming" : "Stopped"} · simulated through {formatTimestamp(lastTick.simulated_end)} · {lastTick.inserted} new readings
        </p>
      )}
      {error && <p className="data-page__error">{error}</p>}
    </div>
  );
}
