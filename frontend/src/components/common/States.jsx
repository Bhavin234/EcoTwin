import "./States.css";

/** Subtle, professional loading state — no giant spinners (docs Milestone 6, requirement #27). */
export function LoadingState({ label = "Loading…" }) {
  return (
    <div className="state-block state-block--loading" role="status">
      <span className="state-block__pulse" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

/** Informative, not alarming error state (docs Milestone 6, requirement #26). */
export function ErrorState({ title = "Something went wrong", message, onRetry }) {
  return (
    <div className="state-block state-block--error" role="alert">
      <p className="state-block__title">{title}</p>
      {message && <p className="state-block__message">{message}</p>}
      {onRetry && (
        <button type="button" className="btn btn--secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, message, action }) {
  return (
    <div className="state-block state-block--empty">
      <p className="state-block__title">{title}</p>
      {message && <p className="state-block__message">{message}</p>}
      {action}
    </div>
  );
}

/** Honest AI-vs-fallback disclosure (docs Milestone 6, requirement #15/#26) — never claims AI when fallback was used. */
export function AIUnavailableNotice({ fallbackReason }) {
  return (
    <div className="state-block state-block--info">
      <p className="state-block__title">Investigation engine: deterministic fallback</p>
      <p className="state-block__message">
        AI reasoning was unavailable, so EcoTwin used its deterministic fallback investigation engine instead. The
        conclusion below is still fully evidence-grounded — see the Evidence section.
        {fallbackReason ? ` (${fallbackReason})` : ""}
      </p>
    </div>
  );
}
