import { type FormEvent, useState } from 'react';
import { Redirect } from 'wouter';
import { useAuth } from './AuthProvider';
import { humanizeError } from '../lib/errors';
import './login.css';

export function LoginPage() {
  const auth = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (auth.accessToken) return <Redirect to="/" />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await auth.login(username, password);
    } catch (err) {
      setError(humanizeError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <p className="login-marker">/AUTH · NCM V4</p>
        <h1 className="login-headline">
          Enter the <em>operations terminal.</em>
        </h1>
        <form onSubmit={submit} className="login-form">
          <label className="login-field">
            Username
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label className="login-field">
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error ? (
            <div role="alert" className="login-error">
              {error}
            </div>
          ) : null}
          <button type="submit" className="login-submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Enter terminal'}
          </button>
        </form>
      </div>
    </div>
  );
}
