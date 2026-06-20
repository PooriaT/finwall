type ErrorStateProps = {
  title?: string;
  message?: string;
};

export function ErrorState({
  title = "Dashboard data could not load",
  message = "Refresh the page or try again later.",
}: ErrorStateProps) {
  return (
    <div className="state-card error-state" role="alert">
      <h2>{title}</h2>
      <p>{message}</p>
    </div>
  );
}
