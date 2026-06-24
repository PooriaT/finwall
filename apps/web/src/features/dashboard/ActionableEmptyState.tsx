type ActionableEmptyStateProps = {
  title: string;
  message: string;
  nextStep?: string;
  commandHint?: string;
  docsHref?: string;
  docsLabel?: string;
};

export function ActionableEmptyState({
  title,
  message,
  nextStep,
  commandHint,
  docsHref,
  docsLabel = "Read the docs",
}: ActionableEmptyStateProps) {
  return (
    <div className="actionable-empty-state">
      <h3>{title}</h3>
      <p>{message}</p>
      {nextStep ? <p className="empty-next-step">{nextStep}</p> : null}
      {commandHint || docsHref ? (
        <div className="empty-state-actions">
          {commandHint ? <code className="command-hint">{commandHint}</code> : null}
          {docsHref ? (
            <a href={docsHref} className="button-link">
              {docsLabel}
            </a>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
