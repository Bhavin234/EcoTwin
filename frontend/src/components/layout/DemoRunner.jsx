import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { demoApi } from "../../api/workflow";
import { useLocationContext } from "../../context/LocationContext";
import { formatCo2e, formatCurrency, formatDuration, formatPercent, titleCase } from "../../utils/format";
import { Button } from "../common/Primitives";
import StatusBadge from "../common/StatusBadge";
import "./DemoRunner.css";

/**
 * Run EcoTwin Demo (docs Milestone 6, requirements #24-25).
 *
 * The entire workflow — seed, analyze, investigate, recommend, intervene,
 * complete, verify — runs as one backend call (`POST /api/demo/run`); the
 * backend is authoritative and nothing here duplicates that logic. Because
 * it genuinely is a single request/response (not a multi-step API the
 * frontend can poll), the step list below is shown as pending during the
 * single loading phase, then presented as a completed summary once the
 * response confirms each stage actually happened — this is honest about
 * what can actually be observed, rather than faking a granular progress
 * animation the backend doesn't report.
 */
const STEPS = [
  "Loading telemetry",
  "Detecting anomaly",
  "Building evidence",
  "Investigating cause",
  "Creating recommendation",
  "Recording intervention",
  "Verifying improvement",
];

export default function DemoRunner({ onClose }) {
  const [phase, setPhase] = useState("running"); // running | done | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [resetting, setResetting] = useState(false);
  const navigate = useNavigate();
  const { refresh: refreshLocations, setSelectedId } = useLocationContext();
  const hasStartedRef = useRef(false);

  const runDemo = () => {
    setPhase("running");
    setError(null);
    demoApi
      .run({})
      .then((data) => {
        setResult(data);
        setPhase(data.status === "complete" ? "done" : "error");

        // The demo workflow creates/updates a location entirely through
        // POST /api/demo/run, a call LocationContext never sees. Without
        // this, the shared location state — which every other page reads
        // — stays stale until a full page reload re-fetches it from
        // scratch. Refresh the shared list and explicitly select the
        // location the demo just used (by ID, not by name or list order —
        // never assume it's first in the list, since a location can share
        // its display name with an older one from a prior test session).
        if (data.status === "complete" && data.location_id) {
          refreshLocations().then(() => setSelectedId(data.location_id));
        }
      })
      .catch((err) => {
        setError(err);
        setPhase("error");
      });
  };

  useEffect(() => {
    // Guards against React 18 StrictMode's deliberate double-invocation of
    // effects in development (mount -> unmount -> mount, with no cleanup
    // here to cancel the first call's in-flight request). Without this
    // guard, mounting this component once in dev fires POST /api/demo/run
    // twice in quick succession; since backend location creation
    // (get_or_create_location) has no unique constraint or lock, two
    // near-simultaneous calls against an empty database can each see "no
    // existing location" and both create one — a very plausible explanation
    // for duplicate same-named location rows observed during local dev
    // testing. This is a frontend-only fix (prevents the redundant call
    // from firing at all); it does not touch backend behavior.
    if (hasStartedRef.current) return;
    hasStartedRef.current = true;
    runDemo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleResetAndRerun = async () => {
    setResetting(true);
    try {
      await demoApi.reset({});
    } catch {
      // A reset failing (e.g. nothing to reset yet) shouldn't block re-running.
    } finally {
      setResetting(false);
      runDemo();
    }
  };

  return (
    <div className="demo-runner-overlay" role="dialog" aria-label="EcoTwin demo">
      <div className="demo-runner">
        <div className="demo-runner__header">
          <h2>Run EcoTwin Demo</h2>
          <button type="button" className="btn btn--ghost" onClick={onClose} aria-label="Close">
            Close
          </button>
        </div>

        {phase === "running" && (
          <ul className="demo-runner__steps">
            {STEPS.map((step) => (
              <li key={step} className="demo-runner__step demo-runner__step--pending">
                <span className="demo-runner__step-marker" aria-hidden="true" />
                {step}
              </li>
            ))}
          </ul>
        )}

        {phase === "error" && (
          <div className="demo-runner__result">
            <p className="demo-runner__result-title">
              {error ? "Could not reach the backend" : result?.message || "No anomaly found for this scenario"}
            </p>
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
          </div>
        )}

        {phase === "done" && result && (
          <div className="demo-runner__result">
            <ul className="demo-runner__steps">
              {STEPS.map((step) => (
                <li key={step} className="demo-runner__step demo-runner__step--done">
                  <span className="demo-runner__step-marker demo-runner__step-marker--done" aria-hidden="true">
                    ✓
                  </span>
                  {step}
                </li>
              ))}
            </ul>

            <div className="demo-runner__summary">
              <div className="demo-runner__summary-row">
                <StatusBadge value={result.severity} />
                <span className="demo-runner__summary-headline">
                  {titleCase(result.resource_type)} anomaly detected — likely cause: <strong>{titleCase(result.likely_cause)}</strong>
                </span>
              </div>

              <div className="demo-runner__evidence-grid">
                <div>
                  <p className="demo-runner__evidence-label">Deviation</p>
                  <p className="mono">
                    {result.deviation_pct != null ? formatPercent(result.deviation_pct, { signed: true }) : `z=${result.z_score?.toFixed(1)}`}
                  </p>
                </div>
                <div>
                  <p className="demo-runner__evidence-label">Duration</p>
                  <p className="mono">{formatDuration(result.persistence_hours)}</p>
                </div>
                <div>
                  <p className="demo-runner__evidence-label">Building status</p>
                  <p>{result.majority_closed ? "Closed" : "Open"}</p>
                </div>
                <div>
                  <p className="demo-runner__evidence-label">Occupancy</p>
                  <p>{result.majority_zero_occupancy ? "0" : "Present"}</p>
                </div>
              </div>

              <p>↓ Recommended inspection · ↓ Intervention completed</p>

              <p>
                Verification: <StatusBadge value={result.verification_status} />
              </p>

              {result.avoided_consumption != null && (
                <div className="demo-runner__impact-row">
                  <div>
                    <p className="demo-runner__evidence-label">Avoided consumption</p>
                    <p className="mono">{result.avoided_consumption.toFixed(1)}</p>
                  </div>
                  <div>
                    <p className="demo-runner__evidence-label">Financial impact</p>
                    <p className="mono">{formatCurrency(result.money_saved)}</p>
                  </div>
                  <div>
                    <p className="demo-runner__evidence-label">CO₂e impact</p>
                    <p className="mono">{formatCo2e(result.co2e_avoided_kg)}</p>
                  </div>
                </div>
              )}
            </div>

            <div className="demo-runner__actions">
              <Button
                onClick={() => {
                  navigate(`/investigations/${result.anomaly_id}`);
                  onClose();
                }}
              >
                View Investigation
              </Button>
              <Button variant="secondary" onClick={onClose}>
                Close
              </Button>
            </div>

            <button type="button" className="demo-runner__reset-link" onClick={handleResetAndRerun} disabled={resetting}>
              {resetting ? "Resetting…" : "Reset demo and run again from scratch"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
