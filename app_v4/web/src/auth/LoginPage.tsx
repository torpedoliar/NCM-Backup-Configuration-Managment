import { type FormEvent, useState } from 'react';
import { useAuth } from './AuthProvider';

export function LoginPage() {
  const auth = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await auth.login(username, password);
    } catch {
      setError('Login failed');
    }
  }

  return (
    <main className="content" style={{ maxWidth: 520 }}>
      <p className="marker">/AUTH · NCM V4</p>
      <h1 className="headline">Enter the <span>operations terminal.</span></h1>
      <form onSubmit={submit} className="nav-group">
        <label>Username<input value={username} onChange={(event) => setUsername(event.target.value)} /></label>
        <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {error ? <div role="alert">{error}</div> : null}
        <button type="submit">Enter terminal</button>
      </form>
    </main>
  );
}
