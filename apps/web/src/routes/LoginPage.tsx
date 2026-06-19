import { FormEvent, useState } from "react";
import { login } from "../api/client";

type LoginPageProps = {
  onAuthenticated?: () => void | Promise<void>;
};

export default function LoginPage({ onAuthenticated }: LoginPageProps) {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submittedToken = token;
    setSubmitting(true);
    setError(null);
    setToken("");

    try {
      const session = await login(submittedToken);
      if (session.authenticated) {
        await onAuthenticated?.();
        return;
      }
      setError("Login failed. Check the token and try again.");
    } catch {
      setError("Login failed. Check the token and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel auth-panel" aria-labelledby="login-title">
      <p className="eyebrow">Login</p>
      <h1 id="login-title">Sign in to Finwall</h1>
      <p>Enter the local app token to start a browser session.</p>
      <form className="login-form" aria-label="Login form" onSubmit={handleSubmit}>
        <label>
          App token
          <input
            autoComplete="current-password"
            name="token"
            onChange={(event) => setToken(event.target.value)}
            placeholder="Enter token"
            type="password"
            value={token}
          />
        </label>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <button type="submit" disabled={submitting || token.trim().length === 0}>
          {submitting ? "Signing in" : "Sign in"}
        </button>
      </form>
    </section>
  );
}
