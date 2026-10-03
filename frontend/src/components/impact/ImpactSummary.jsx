import { formatCo2e, formatCurrency, titleCase } from "../../utils/format";
import { MetricTile } from "../common/Primitives";
import "./ImpactSummary.css";

const KIND_ORDER = ["verified", "estimated", "potential"];
const KIND_TONE = { verified: "positive", estimated: "warning", potential: "neutral" };

/**
 * Renders one metric-tile group per impact kind, always labeled — never
 * lets an estimated figure look visually equivalent to a verified one
 * (docs Milestone 6, requirements #9/#20).
 */
export default function ImpactSummary({ summary }) {
  const byKind = Object.fromEntries(summary.map((s) => [s.kind, s]));
  const kindsPresent = KIND_ORDER.filter((k) => byKind[k]);

  if (kindsPresent.length === 0) {
    return <p className="impact-summary__empty">No impact recorded yet.</p>;
  }

  return (
    <div className="impact-summary">
      {kindsPresent.map((kind) => {
        const s = byKind[kind];
        return (
          <div key={kind} className={`impact-summary__group impact-summary__group--${KIND_TONE[kind]}`}>
            <p className="impact-summary__kind-label">{titleCase(kind)} impact</p>
            <div className="impact-summary__tiles">
              <MetricTile label="Money saved" value={formatCurrency(s.total_money_saved)} tone={KIND_TONE[kind]} />
              <MetricTile label="CO₂e avoided" value={formatCo2e(s.total_co2e_avoided_kg)} tone={KIND_TONE[kind]} />
              {s.total_water_saved > 0 && <MetricTile label="Water avoided" value={`${s.total_water_saved.toFixed(1)} L`} tone={KIND_TONE[kind]} />}
              {s.total_energy_saved > 0 && <MetricTile label="Electricity avoided" value={`${s.total_energy_saved.toFixed(1)} kWh`} tone={KIND_TONE[kind]} />}
            </div>
            <p className="impact-summary__count">{s.record_count} record{s.record_count === 1 ? "" : "s"}</p>
          </div>
        );
      })}
    </div>
  );
}
