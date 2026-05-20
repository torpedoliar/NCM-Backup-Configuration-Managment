# NCM v4 Phase 4 Web Foundation and Ops Terminal Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first usable React web client: login, authenticated shell, Ops Terminal design tokens, dashboard, and live activity feed.

**Architecture:** Create `app_v4/web/` as a Vite React TypeScript app served later by the FastAPI static bundle support from Phase 3. Keep API access in one typed client, server state in TanStack Query, UI state in Zustand, and visuals in bespoke CSS using `tokens.css`.

**Tech Stack:** React 18, TypeScript, Vite, TanStack Query v5, Wouter, Zustand, Recharts, Vitest, Testing Library, MSW.

---

## File Structure

- Create: `app_v4/web/package.json`
- Create: `app_v4/web/package-lock.json` after install
- Create: `app_v4/web/index.html`
- Create: `app_v4/web/vite.config.ts`
- Create: `app_v4/web/tsconfig.json`
- Create: `app_v4/web/tsconfig.node.json`
- Create: `app_v4/web/src/main.tsx`
- Create: `app_v4/web/src/App.tsx`
- Create: `app_v4/web/src/api/client.ts`
- Create: `app_v4/web/src/api/types.ts`
- Create: `app_v4/web/src/api/hooks.ts`
- Create: `app_v4/web/src/auth/AuthProvider.tsx`
- Create: `app_v4/web/src/auth/LoginPage.tsx`
- Create: `app_v4/web/src/auth/ProtectedRoute.tsx`
- Create: `app_v4/web/src/layout/Shell.tsx`
- Create: `app_v4/web/src/layout/Sidebar.tsx`
- Create: `app_v4/web/src/layout/Topbar.tsx`
- Create: `app_v4/web/src/pages/DashboardPage.tsx`
- Create: `app_v4/web/src/components/KpiCell.tsx`
- Create: `app_v4/web/src/components/FleetGrid.tsx`
- Create: `app_v4/web/src/components/LiveFeed.tsx`
- Create: `app_v4/web/src/components/BackupChart.tsx`
- Create: `app_v4/web/src/lib/ws.ts`
- Create: `app_v4/web/src/lib/fmt.ts`
- Create: `app_v4/web/src/store/liveActivity.ts`
- Create: `app_v4/web/src/styles/tokens.css`
- Create: `app_v4/web/src/styles/global.css`
- Create: `app_v4/web/src/test/setup.ts`
- Create: `app_v4/web/src/test/server.ts`
- Create: `app_v4/web/src/auth/LoginPage.test.tsx`
- Create: `app_v4/web/src/pages/DashboardPage.test.tsx`
- Create: `app_v4/web/src/layout/Shell.test.tsx`

### Task 1: Vite React Project Skeleton

**Files:**
- Create: `app_v4/web/package.json`
- Create: `app_v4/web/index.html`
- Create: `app_v4/web/vite.config.ts`
- Create: `app_v4/web/tsconfig.json`
- Create: `app_v4/web/tsconfig.node.json`
- Create: `app_v4/web/src/main.tsx`
- Create: `app_v4/web/src/App.tsx`

- [ ] **Step 1: Create package manifest**

Create `app_v4/web/package.json`:

```json
{
  "name": "ncm-v4-web",
  "version": "4.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc -b && vite build --outDir ../service/static --emptyOutDir",
    "preview": "vite preview --host 127.0.0.1",
    "test": "vitest --environment jsdom",
    "lint": "eslint src --ext ts,tsx"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.66.0",
    "axios": "^1.7.9",
    "recharts": "^2.15.1",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "wouter": "^3.3.5",
    "zustand": "^5.0.3"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.2.0",
    "@testing-library/user-event": "^14.6.1",
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "jsdom": "^26.0.0",
    "msw": "^2.7.0",
    "typescript": "^5.7.3",
    "vite": "^6.1.0",
    "vitest": "^3.0.5"
  }
}
```

- [ ] **Step 2: Install dependencies**

Run:

```powershell
rtk npm --prefix app_v4/web install
```

Expected: `package-lock.json` created under `app_v4/web/`.

- [ ] **Step 3: Create Vite config**

Create `app_v4/web/vite.config.ts`:

```ts
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8443',
      '/ws': { target: 'ws://127.0.0.1:8443', ws: true },
    },
  },
  test: {
    setupFiles: ['./src/test/setup.ts'],
  },
});
```

Create `app_v4/web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `app_v4/web/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Create entry files**

Create `app_v4/web/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NCM v4 Ops Terminal</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `app_v4/web/src/main.tsx`:

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from './App';
import './styles/tokens.css';
import './styles/global.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
```

Create `app_v4/web/src/App.tsx`:

```tsx
import { Route, Switch } from 'wouter';
import { AuthProvider } from './auth/AuthProvider';
import { LoginPage } from './auth/LoginPage';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { Shell } from './layout/Shell';
import { DashboardPage } from './pages/DashboardPage';

export function App() {
  return (
    <AuthProvider>
      <Switch>
        <Route path="/login" component={LoginPage} />
        <ProtectedRoute>
          <Shell>
            <Route path="/" component={DashboardPage} />
          </Shell>
        </ProtectedRoute>
      </Switch>
    </AuthProvider>
  );
}
```

- [ ] **Step 5: Run skeleton build**

```powershell
rtk npm --prefix app_v4/web run build
```

Expected: fails because imported files are not created yet. Continue to Task 2.

### Task 2: Ops Terminal Design Tokens and Shell

**Files:**
- Create: `app_v4/web/src/styles/tokens.css`
- Create: `app_v4/web/src/styles/global.css`
- Create: `app_v4/web/src/layout/Shell.tsx`
- Create: `app_v4/web/src/layout/Sidebar.tsx`
- Create: `app_v4/web/src/layout/Topbar.tsx`
- Create: `app_v4/web/src/layout/Shell.test.tsx`

- [ ] **Step 1: Write shell test**

Create `app_v4/web/src/layout/Shell.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Shell } from './Shell';

it('renders Ops Terminal chrome', () => {
  render(<Shell><main>Dashboard body</main></Shell>);
  expect(screen.getByText('NCM OPS')).toBeInTheDocument();
  expect(screen.getByText('monitoring / Dashboard')).toBeInTheDocument();
  expect(screen.getByText('Dashboard body')).toBeInTheDocument();
});
```

- [ ] **Step 2: Create test setup**

Create `app_v4/web/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 3: Create tokens**

Create `app_v4/web/src/styles/tokens.css` exactly from spec tokens:

```css
:root {
  --ink: #0a0a0a;
  --ink-2: #111111;
  --surface: #141414;
  --surface-2: #1a1a1a;
  --line: #262626;
  --line-2: #333333;
  --bone: #fafaf7;
  --bone-2: #e5e5e2;
  --muted: #737373;
  --muted-2: #525252;
  --amber: #ffb800;
  --amber-2: #ffd166;
  --red: #ff3838;
  --green: #4ade80;
  --cyan: #22d3ee;
  --violet: #a78bfa;
  --font-mono: 'JetBrains Mono', monospace;
  --font-body: 'Geist', system-ui, sans-serif;
  --font-display: 'Instrument Serif', serif;
}
```

Create `app_v4/web/src/styles/global.css`:

```css
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--bone);
  background:
    linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px),
    var(--ink);
  background-size: 64px 64px;
  font-family: var(--font-body);
}
button, input { font: inherit; border-radius: 0; }
.number { font-feature-settings: 'tnum' 1, 'zero' 1; }
.marker { color: var(--muted); font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.18em; text-transform: uppercase; }
.shell { display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; }
.sidebar { border-right: 1px solid var(--line); background: var(--ink-2); padding: 18px; display: flex; flex-direction: column; gap: 24px; }
.brand { font-family: var(--font-mono); color: var(--amber); letter-spacing: 0.12em; }
.brand::after { content: '_'; animation: blink 1s steps(2, start) infinite; }
.nav-group { display: grid; gap: 8px; }
.nav-label { color: var(--muted); font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.18em; }
.nav-link { color: var(--bone-2); text-decoration: none; padding: 10px 0; border-bottom: 1px dashed var(--line-2); }
.nav-link.active { color: var(--amber); }
.topbar { height: 56px; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; padding: 0 24px; position: relative; }
.topbar::after { content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 4px; background: repeating-linear-gradient(135deg, rgba(255,184,0,.3) 0 6px, transparent 6px 12px); }
.content { padding: 24px; }
.headline { font-family: var(--font-display); font-style: italic; font-size: 44px; font-weight: 300; letter-spacing: -0.04em; margin: 0 0 24px; }
@keyframes blink { 50% { opacity: 0; } }
```

- [ ] **Step 4: Create shell components**

Create `app_v4/web/src/layout/Sidebar.tsx`:

```tsx
import { Link, useLocation } from 'wouter';

const groups = [
  { label: 'Monitoring', links: [{ href: '/', text: 'Dashboard' }, { href: '/history', text: 'History' }, { href: '/diff', text: 'Diff' }] },
  { label: 'Management', links: [{ href: '/switches', text: 'Switches' }, { href: '/credentials', text: 'Credentials' }, { href: '/schedules', text: 'Schedules' }] },
  { label: 'Administration', links: [{ href: '/users', text: 'Users' }, { href: '/settings', text: 'Settings' }] },
];

export function Sidebar() {
  const [location] = useLocation();
  return (
    <aside className="sidebar">
      <div className="brand">NCM OPS</div>
      {groups.map((group) => (
        <nav className="nav-group" key={group.label}>
          <div className="nav-label">{group.label}</div>
          {group.links.map((link) => (
            <Link key={link.href} href={link.href} className={`nav-link ${location === link.href ? 'active' : ''}`}>
              {link.text}
            </Link>
          ))}
        </nav>
      ))}
      <div className="marker" style={{ marginTop: 'auto' }}>/REF V4-OPS</div>
    </aside>
  );
}
```

Create `app_v4/web/src/layout/Topbar.tsx`:

```tsx
export function Topbar() {
  return (
    <header className="topbar">
      <div className="marker">monitoring / Dashboard</div>
      <div className="marker">UTC · {new Date().toISOString().slice(11, 19)}</div>
    </header>
  );
}
```

Create `app_v4/web/src/layout/Shell.tsx`:

```tsx
import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <Sidebar />
      <div>
        <Topbar />
        <div className="content">{children}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run shell tests**

```powershell
rtk npm --prefix app_v4/web test -- --run src/layout/Shell.test.tsx
```

Expected: pass after auth imports are handled in Task 3.

### Task 3: Auth Flow

**Files:**
- Create: `app_v4/web/src/api/client.ts`
- Create: `app_v4/web/src/api/types.ts`
- Create: `app_v4/web/src/auth/AuthProvider.tsx`
- Create: `app_v4/web/src/auth/LoginPage.tsx`
- Create: `app_v4/web/src/auth/ProtectedRoute.tsx`
- Create: `app_v4/web/src/auth/LoginPage.test.tsx`

- [ ] **Step 1: Write login page test**

Create `app_v4/web/src/auth/LoginPage.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AuthContext } from './AuthProvider';
import { LoginPage } from './LoginPage';

it('submits username and password', async () => {
  const login = vi.fn().mockResolvedValue(undefined);
  render(
    <AuthContext.Provider value={{ accessToken: null, user: null, login, logout: vi.fn() }}>
      <LoginPage />
    </AuthContext.Provider>,
  );

  await userEvent.type(screen.getByLabelText(/username/i), 'admin');
  await userEvent.type(screen.getByLabelText(/password/i), 'secret');
  await userEvent.click(screen.getByRole('button', { name: /enter terminal/i }));

  expect(login).toHaveBeenCalledWith('admin', 'secret');
});
```

- [ ] **Step 2: Create API types/client**

Create `app_v4/web/src/api/types.ts`:

```ts
export type Role = 'admin' | 'operator' | 'viewer';

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
}

export interface CurrentUser {
  id: number;
  username: string;
  role: Role;
  is_active: boolean;
}

export interface SystemMetrics {
  switches: number;
  backups: number;
  jobs: number;
  failures_24h: number;
}

export interface LiveEvent {
  type: string;
  payload: Record<string, unknown>;
  ts: string;
}
```

Create `app_v4/web/src/api/client.ts`:

```ts
import axios from 'axios';
import type { CurrentUser, TokenPair } from './types';

export const api = axios.create({ baseURL: '/api/v1' });

export function setAccessToken(token: string | null) {
  if (token) api.defaults.headers.common.Authorization = `Bearer ${token}`;
  else delete api.defaults.headers.common.Authorization;
}

export async function loginRequest(username: string, password: string): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>('/auth/login', { username, password });
  return data;
}

export async function meRequest(): Promise<CurrentUser> {
  const { data } = await api.get<CurrentUser>('/auth/me');
  return data;
}
```

- [ ] **Step 3: Create auth provider**

Create `app_v4/web/src/auth/AuthProvider.tsx`:

```tsx
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import { useLocation } from 'wouter';
import { loginRequest, setAccessToken } from '../api/client';
import type { CurrentUser } from '../api/types';

type AuthValue = {
  accessToken: string | null;
  user: CurrentUser | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

export const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [, navigate] = useLocation();
  const [accessToken, setToken] = useState<string | null>(() => localStorage.getItem('access_token'));
  const [user, setUser] = useState<CurrentUser | null>(null);
  setAccessToken(accessToken);

  const value = useMemo<AuthValue>(() => ({
    accessToken,
    user,
    async login(username, password) {
      const tokenPair = await loginRequest(username, password);
      localStorage.setItem('access_token', tokenPair.access_token);
      localStorage.setItem('refresh_token', tokenPair.refresh_token);
      setToken(tokenPair.access_token);
      setAccessToken(tokenPair.access_token);
      navigate('/');
    },
    logout() {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setToken(null);
      setUser(null);
      setAccessToken(null);
      navigate('/login');
    },
  }), [accessToken, user, navigate]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('AuthContext missing');
  return context;
}
```

- [ ] **Step 4: Create login/protected route**

Create `app_v4/web/src/auth/LoginPage.tsx`:

```tsx
import { FormEvent, useState } from 'react';
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
```

Create `app_v4/web/src/auth/ProtectedRoute.tsx`:

```tsx
import type { ReactNode } from 'react';
import { Redirect } from 'wouter';
import { useAuth } from './AuthProvider';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { accessToken } = useAuth();
  if (!accessToken) return <Redirect to="/login" />;
  return <>{children}</>;
}
```

- [ ] **Step 5: Run auth tests**

```powershell
rtk npm --prefix app_v4/web test -- --run src/auth/LoginPage.test.tsx src/layout/Shell.test.tsx
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
rtk git add app_v4/web
rtk git commit -m "feat: add v4 web foundation and auth shell"
```

### Task 4: Dashboard and Live Activity

**Files:**
- Create: `app_v4/web/src/api/hooks.ts`
- Create: `app_v4/web/src/pages/DashboardPage.tsx`
- Create: `app_v4/web/src/components/KpiCell.tsx`
- Create: `app_v4/web/src/components/FleetGrid.tsx`
- Create: `app_v4/web/src/components/LiveFeed.tsx`
- Create: `app_v4/web/src/components/BackupChart.tsx`
- Create: `app_v4/web/src/lib/ws.ts`
- Create: `app_v4/web/src/lib/fmt.ts`
- Create: `app_v4/web/src/store/liveActivity.ts`
- Create: `app_v4/web/src/pages/DashboardPage.test.tsx`

- [ ] **Step 1: Write dashboard test**

Create `app_v4/web/src/pages/DashboardPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DashboardPage } from './DashboardPage';

it('renders KPI dashboard copy', () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>,
  );
  expect(screen.getByText(/Twelve switches/i)).toBeInTheDocument();
  expect(screen.getByText('/01 · INV')).toBeInTheDocument();
});
```

- [ ] **Step 2: Add API hooks**

Create `app_v4/web/src/api/hooks.ts`:

```ts
import { useQuery } from '@tanstack/react-query';
import { api } from './client';
import type { SystemMetrics } from './types';

export function useSystemMetrics() {
  return useQuery({
    queryKey: ['system', 'metrics'],
    queryFn: async () => (await api.get<SystemMetrics>('/system/metrics')).data,
  });
}
```

- [ ] **Step 3: Add live activity store**

Create `app_v4/web/src/store/liveActivity.ts`:

```ts
import { create } from 'zustand';
import type { LiveEvent } from '../api/types';

type LiveActivityState = {
  events: LiveEvent[];
  push: (event: LiveEvent) => void;
};

export const useLiveActivity = create<LiveActivityState>((set) => ({
  events: [],
  push: (event) => set((state) => ({ events: [event, ...state.events].slice(0, 50) })),
}));
```

Create `app_v4/web/src/lib/ws.ts`:

```ts
import type { LiveEvent } from '../api/types';

export function openLiveSocket(token: string, onEvent: (event: LiveEvent) => void): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${proto}//${window.location.host}/ws?token=${encodeURIComponent(token)}`);
  socket.onmessage = (message) => onEvent(JSON.parse(message.data) as LiveEvent);
  return socket;
}
```

Create `app_v4/web/src/lib/fmt.ts`:

```ts
export function number(value: number | undefined): string {
  return (value ?? 0).toLocaleString();
}
```

- [ ] **Step 4: Add dashboard components**

Create `app_v4/web/src/components/KpiCell.tsx`:

```tsx
export function KpiCell({ marker, label, value }: { marker: string; label: string; value: string }) {
  return <section style={{ border: '1px solid var(--line)', padding: 16 }}><div className="marker">{marker}</div><strong className="number">{value}</strong><p>{label}</p></section>;
}
```

Create `app_v4/web/src/components/FleetGrid.tsx`:

```tsx
export function FleetGrid() {
  return <section style={{ border: '1px solid var(--line)', padding: 16 }}><div className="marker">/REF DSH-001</div><p>Fleet grid online.</p></section>;
}
```

Create `app_v4/web/src/components/LiveFeed.tsx`:

```tsx
import { useLiveActivity } from '../store/liveActivity';

export function LiveFeed() {
  const events = useLiveActivity((state) => state.events);
  return <section><div className="marker">/LIVE FEED</div>{events.length === 0 ? <p>No events yet.</p> : events.map((event, index) => <p key={`${event.ts}-${index}`}>{event.type}</p>)}</section>;
}
```

Create `app_v4/web/src/components/BackupChart.tsx`:

```tsx
import { Line, LineChart, ResponsiveContainer, XAxis, YAxis } from 'recharts';

const data = Array.from({ length: 14 }, (_, index) => ({ day: index + 1, backups: index + 3 }));

export function BackupChart() {
  return <ResponsiveContainer width="100%" height={180}><LineChart data={data}><XAxis dataKey="day" stroke="var(--muted)" /><YAxis stroke="var(--muted)" /><Line type="monotone" dataKey="backups" stroke="var(--amber)" dot={false} /></LineChart></ResponsiveContainer>;
}
```

- [ ] **Step 5: Add dashboard page**

Create `app_v4/web/src/pages/DashboardPage.tsx`:

```tsx
import { BackupChart } from '../components/BackupChart';
import { FleetGrid } from '../components/FleetGrid';
import { KpiCell } from '../components/KpiCell';
import { LiveFeed } from '../components/LiveFeed';
import { useSystemMetrics } from '../api/hooks';
import { number } from '../lib/fmt';

export function DashboardPage() {
  const { data } = useSystemMetrics();
  return (
    <main>
      <h1 className="headline">Twelve switches, <span>three-forty-eight</span> backups, one anomaly.</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <KpiCell marker="/01 · INV" label="Switches" value={number(data?.switches ?? 12)} />
        <KpiCell marker="/02 · BAK" label="Backups" value={number(data?.backups ?? 348)} />
        <KpiCell marker="/03 · SCH" label="Jobs" value={number(data?.jobs ?? 9)} />
        <KpiCell marker="/04 · ERR" label="24h failures" value={number(data?.failures_24h ?? 1)} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, marginTop: 16 }}>
        <section style={{ border: '1px solid var(--line)', padding: 16 }}><BackupChart /></section>
        <LiveFeed />
      </div>
      <div style={{ marginTop: 16 }}><FleetGrid /></div>
    </main>
  );
}
```

- [ ] **Step 6: Run dashboard tests and build**

```powershell
rtk npm --prefix app_v4/web test -- --run
rtk npm --prefix app_v4/web run build
```

Expected: tests pass and bundle builds into `app_v4/service/static/`.

- [ ] **Step 7: Commit**

```powershell
rtk git add app_v4/web app_v4/service/static
rtk git commit -m "feat: add v4 Ops Terminal dashboard"
```
