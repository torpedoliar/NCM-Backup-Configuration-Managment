import { render, screen } from '@testing-library/react';
import { it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Shell } from './Shell';

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'admin', role: 'admin', is_active: true },
    accessToken: 'token',
    refreshToken: 'refresh',
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

it('renders mockup shell chrome', () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Shell><main>Dashboard body</main></Shell>
    </QueryClientProvider>,
  );

  expect(screen.getByText('NCM')).toBeInTheDocument();
  expect(screen.getByText('NETWORK CONFIG MGR')).toBeInTheDocument();
  expect(screen.getByText('V3.5.7 / PROD')).toBeInTheDocument();
  expect(screen.getAllByText('MONITORING').length).toBeGreaterThan(0);
  expect(screen.getByText('/ Dashboard')).toBeInTheDocument();
  expect(screen.getByText('SERVICE / RUNNING')).toBeInTheDocument();
  expect(screen.getByText('Dashboard body')).toBeInTheDocument();
});
