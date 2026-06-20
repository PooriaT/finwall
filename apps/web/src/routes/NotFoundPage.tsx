export default function NotFoundPage() {
  return (
    <section className="panel" aria-labelledby="not-found-title">
      <p className="eyebrow">Not found</p>
      <h1 id="not-found-title">Page not found</h1>
      <p>The requested Finwall page does not exist in this scaffold.</p>
      <a className="button-link" href="/dashboard">
        Go to dashboard
      </a>
    </section>
  );
}
