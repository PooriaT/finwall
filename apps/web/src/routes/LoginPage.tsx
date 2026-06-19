export default function LoginPage() {
  return (
    <section className="panel auth-panel" aria-labelledby="login-title">
      <p className="eyebrow">Login</p>
      <h1 id="login-title">Session login placeholder</h1>
      <p>
        Browser session auth is planned for a later issue. This form is presentational and
        does not submit credentials or store tokens.
      </p>
      <form className="login-form" aria-label="Login placeholder form">
        <label>
          Email
          <input type="email" placeholder="you@example.com" disabled />
        </label>
        <label>
          Password
          <input type="password" placeholder="Not implemented" disabled />
        </label>
        <button type="button" disabled>
          Sign in unavailable
        </button>
      </form>
    </section>
  );
}
