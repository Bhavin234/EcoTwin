import { titleCase } from "../../utils/format";
import "./InvestigationTimeline.css";

/**
 * A vertical timeline visualizing the existing backend workflow state
 * (docs Milestone 7, requirement #8). Every stage's "done"/"pending" state
 * is derived directly from data already present on the anomaly/
 * investigation/intervention objects — this component makes no decisions
 * of its own about what happened.
 */
export default function InvestigationTimeline({ anomaly, investigation, intervention }) {
  const hasEvidence = anomaly.evidence?.length > 0;
  const hasInvestigation = Boolean(investigation?.explanation);
  const hasRecommendation = Boolean(investigation?.recommendation);
  const hasIntervention = Boolean(intervention);
  const isCompleted = intervention?.status === "completed";
  const isVerified = intervention?.verification_status === "verified" || intervention?.verification_status === "improvement_detected";
  const isNoImprovement = intervention?.verification_status === "no_measurable_improvement";

  const steps = [
    {
      title: "Anomaly detected",
      done: true,
      detail: `${titleCase(anomaly.resource_type)} consumption deviated from the expected baseline.`,
    },
    {
      title: "Evidence collected",
      done: hasEvidence,
      detail: hasEvidence ? anomaly.evidence.map((e) => e.description).join(" ") : "Awaiting evidence.",
    },
    {
      title: "Cause investigated",
      done: hasInvestigation,
      detail: hasInvestigation ? `${titleCase(investigation.top_cause)} ranked as the likely cause.` : "Not yet investigated.",
    },
    {
      title: "Action recommended",
      done: hasRecommendation,
      detail: hasRecommendation ? investigation.recommendation.action_text : "No recommendation yet.",
    },
    {
      title: "Intervention completed",
      done: isCompleted,
      detail: hasIntervention ? (isCompleted ? "Reported as done." : "Recommended, not yet completed.") : "Not yet created.",
    },
    {
      title: isNoImprovement ? "Improvement not yet observed" : "Improvement verified",
      done: isVerified,
      pending: isCompleted && !isVerified && !isNoImprovement,
      warning: isNoImprovement,
      detail: intervention?.verification_status ? titleCase(intervention.verification_status) : "Verification pending.",
    },
  ];

  return (
    <ol className="investigation-timeline">
      {steps.map((step, idx) => (
        <li key={step.title} className="investigation-timeline__item">
          <div className="investigation-timeline__rail">
            <span
              className={`investigation-timeline__dot${step.done ? " investigation-timeline__dot--done" : step.warning ? " investigation-timeline__dot--warning" : ""}`}
              aria-hidden="true"
            />
            {idx < steps.length - 1 && <span className="investigation-timeline__line" />}
          </div>
          <div className="investigation-timeline__body">
            <p className="investigation-timeline__title">{step.title}</p>
            <p className="investigation-timeline__detail">{step.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
