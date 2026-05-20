# Phase 1 — Login Layout Fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broken login form layout with a centered card 380px wide that follows the dark ops-terminal theme.

**Architecture:** Pure frontend change in the React SPA. Wrap the existing form in a flex-centered container; move styles into a dedicated CSS module so the existing theme tokens (`--bg-0`, `--accent-amber`, `--text-1`, `--border-1`) drive the look.

**Tech Stack:** React 18, TypeScript, Vite, vitest, Testing Library, plain CSS using existing `visual-tokens.css` variables.

**Spec reference:** `docs/superpowers/specs/2026-05-20-ncm-v4-production-completion-design.md` Section 1.

---

## Task 1: Centered login card layout

**Files:**
- Create: `app_v4/web/src/auth/login.css`
- Modify: `app_v4/web/src/auth/LoginPage.tsx`
- Modify: `app_v4/web/src/auth/LoginPage.test.tsx`

- [ ] **Step 1: Inspect existing tokens to know which CSS variables to use**

Run: `cat app_v4/web/src/styles/visual-tokens.css`
Note the names of background, surface, border, text and accent tokens — they are referenced below as `--bg-0`, `--bg-1`, `--text-1`, `--text-2`, `--border-1`, `--accent-amber`. If your tokens use different names, substitute them in `login.css` accordingly while keeping the visual mapping (background-1 = page bg, surface-1 = card bg, etc.).

- [ ] **Step 2: Write the failing test**

Replace the contents of `app_v4/web/src/auth/LoginPage.test.tsx`:

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginPage } from './LoginPage';
import { AuthProvider } from './AuthProvider';

const loginMock = vi.fn();
vi.mock('./AuthProvider', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./AuthProvider')>();
  return {
    ...actual,
    useAuth: () => ({ login: loginMock, logout: vi.fn(), user: null, accessToken: null, refreshToken: null }),
  };
});

describe('LoginPage', () => {
  it('renders inside a centered login card with form fields and submit', async () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );

    const card = document.querySelector('.login-card');
    expect(card).toBeTruthy();

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /enter terminal/i })).toBeInTheDocument();
  });

  it('submits username and password', async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );
    await user.type(screen.getByLabelText(/username/i), 'admin');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /enter terminal/i }));
    expect(loginMock).toHaveBeenCalledWith('admin', 'password123');
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm --prefix app_v4/web test -- --run src/auth/LoginPage.test.tsx`
Expected: FAIL — `card` is null because `.login-card` does not exist yet, and the second test may also fail if labels do not bind to inputs.

- [ ] **Step 4: Create the login CSS module**

Create `app_v4/web/src/auth/login.css`:

```css
.login-screen {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-0);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 380px;
  background: var(--bg-1, #141414);
  border: 1px solid var(--border-1, #262626);
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.login-marker {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--text-2, #737373);
  margin: 0;
}

.login-headline {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-1, #fafaf7);
  margin: 0;
  line-height: 1.3;
}

.login-headline em {
  color: var(--accent-amber, #ffb800);
  font-style: normal;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.login-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-2, #a3a3a3);
  letter-spacing: 1px;
}

.login-field input {
  background: var(--bg-0, #0a0a0a);
  border: 1px solid var(--border-1, #262626);
  color: var(--text-1, #fafaf7);
  padding: 10px 14px;
  font-size: 14px;
  border-radius: 0;
  outline: none;
}

.login-field input:focus {
  border-color: var(--accent-amber, #ffb800);
}

.login-error {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.4);
  padding: 8px 12px;
  font-size: 13px;
}

.login-submit {
  background: var(--bg-0, #0a0a0a);
  color: var(--text-1, #fafaf7);
  border: 1px solid var(--border-1, #262626);
  padding: 10px 14px;
  font-size: 13px;
  letter-spacing: 1px;
  cursor: pointer;
  text-align: center;
}

.login-submit:hover {
  border-color: var(--accent-amber, #ffb800);
  color: var(--accent-amber, #ffb800);
}

.login-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

- [ ] **Step 5: Replace `LoginPage.tsx` with the new structure**

Overwrite `app_v4/web/src/auth/LoginPage.tsx`:

```tsx
import { type FormEvent, useState } from 'react';
import { useAuth } from './AuthProvider';
import './login.css';

export function LoginPage() {
  const auth = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await auth.login(username, password);
    } catch {
      setError('Login failed. Check credentials and try again.');
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `npm --prefix app_v4/web test -- --run src/auth/LoginPage.test.tsx`
Expected: PASS — `.login-card` exists, fields and submit button visible, submit invokes `login`.

- [ ] **Step 7: Run the full SPA test suite to confirm no regression**

Run: `npm --prefix app_v4/web test -- --run`
Expected: all suites pass.

- [ ] **Step 8: Type-check**

Run: `npm --prefix app_v4/web run build`
Expected: build OK; new CSS file picked up by Vite, no TS errors.

- [ ] **Step 9: Commit**

```bash
git add app_v4/web/src/auth/LoginPage.tsx app_v4/web/src/auth/LoginPage.test.tsx app_v4/web/src/auth/login.css
git commit -m "feat(login): centered login card with dark theme"
```

---

## Task 2: Rebuild PyInstaller bundle so the desktop app picks up the new SPA

**Files:**
- Modify: `app_v4/service/static/` (regenerated by vite)
- Modify: `dist/ncm-v4-desktop/` (regenerated by PyInstaller)

- [ ] **Step 1: Rebuild the SPA into the static folder**

Run: `npm --prefix app_v4/web run build`
Expected: `app_v4/service/static/index.html` and `assets/` regenerated.

- [ ] **Step 2: Confirm no live exe holds the dist files**

Run: `tasklist | rg ncm-v4-desktop || echo none`
Expected: `none`. If the exe is running, ask the user before killing.

- [ ] **Step 3: Rebuild PyInstaller bundle**

Run: `powershell -ExecutionPolicy Bypass -File installer/v4/build_app.ps1 -SkipWebBuild`
Expected: `==> Build OK` line, exe size ~15-16 MB.

- [ ] **Step 4: No commit**

The dist folder is build output — no commit. Phase 1 is complete.
