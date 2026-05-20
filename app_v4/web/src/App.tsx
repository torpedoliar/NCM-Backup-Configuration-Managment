import { Suspense, lazy } from 'react';
import { Route, Switch } from 'wouter';
import { AuthProvider } from './auth/AuthProvider';
import { LoginPage } from './auth/LoginPage';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { Shell } from './layout/Shell';

const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })));
const SwitchesPage = lazy(() => import('./pages/SwitchesPage').then((m) => ({ default: m.SwitchesPage })));
const CredentialsPage = lazy(() => import('./pages/CredentialsPage').then((m) => ({ default: m.CredentialsPage })));
const HistoryPage = lazy(() => import('./pages/HistoryPage').then((m) => ({ default: m.HistoryPage })));
const DiffPage = lazy(() => import('./pages/DiffPage').then((m) => ({ default: m.DiffPage })));
const SchedulesPage = lazy(() => import('./pages/SchedulesPage').then((m) => ({ default: m.SchedulesPage })));
const UsersPage = lazy(() => import('./pages/UsersPage').then((m) => ({ default: m.UsersPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })));

function PageFallback() {
  return <div className="marker" style={{ padding: 24 }}>/LOADING</div>;
}

export function App() {
  return (
    <AuthProvider>
      <Switch>
        <Route path="/login" component={LoginPage} />
        <ProtectedRoute>
          <Shell>
            <Suspense fallback={<PageFallback />}>
              <Route path="/" component={DashboardPage} />
              <Route path="/switches" component={SwitchesPage} />
              <Route path="/credentials" component={CredentialsPage} />
              <Route path="/history" component={HistoryPage} />
              <Route path="/diff" component={DiffPage} />
              <Route path="/schedules" component={SchedulesPage} />
              <Route path="/users" component={UsersPage} />
              <Route path="/settings" component={SettingsPage} />
            </Suspense>
          </Shell>
        </ProtectedRoute>
      </Switch>
    </AuthProvider>
  );
}
