import { Link } from "react-router-dom";
import { formatDuration, formatPercent, formatTimestamp, titleCase } from "../../utils/format";
import StatusBadge from "../common/StatusBadge";
import "./AnomalyTable.css";

export default function AnomalyTable({ anomalies, resourceLabelById = {} }) {
  if (anomalies.length === 0) {
    return <p className="anomaly-table__empty">No anomalies to show.</p>;
  }

  return (
    <table className="anomaly-table">
      <thead>
        <tr>
          <th>Resource</th>
          <th>Severity</th>
          <th>Classification</th>
          <th>Deviation</th>
          <th>Detected</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {anomalies.map((anomaly) => (
          <tr key={anomaly.id}>
            <td>
              <Link to={`/investigations/${anomaly.id}`} className="anomaly-table__link">
                {resourceLabelById[anomaly.resource_id] || titleCase(anomaly.resource_id?.slice(0, 8))}
              </Link>
            </td>
            <td>
              <StatusBadge value={anomaly.severity} />
            </td>
            <td>{titleCase(anomaly.classification)}</td>
            <td className="mono">{anomaly.deviation_pct != null ? formatPercent(anomaly.deviation_pct, { signed: true }) : `z=${anomaly.z_score.toFixed(1)}`}</td>
            <td>{formatTimestamp(anomaly.detected_at)}</td>
            <td>
              <StatusBadge value={anomaly.status} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
