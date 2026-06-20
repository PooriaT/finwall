type LoadingStateProps = {
  title?: string;
  message?: string;
};

export function LoadingState({
  title = "Loading dashboard",
  message = "Loading portfolio data.",
}: LoadingStateProps) {
  return (
    <div className="state-card" aria-live="polite">
      <h2>{title}</h2>
      <p>{message}</p>
    </div>
  );
}
