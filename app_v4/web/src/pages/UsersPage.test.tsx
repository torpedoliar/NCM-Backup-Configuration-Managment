import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { it, expect, vi } from 'vitest';
import { UsersPage } from './UsersPage';

vi.mock('../api/hooks', () => ({
  useUsers: () => ({ data: [{ id: 1, username: 'opadmin', role: 'admin', is_active: true, created_at: '2026-05-19T00:00:00Z' }], isLoading: false }),
}));

it('renders users with role and active state', () => {
  render(<QueryClientProvider client={new QueryClient()}><UsersPage /></QueryClientProvider>);
  expect(screen.getByText('opadmin')).toBeInTheDocument();
  expect(screen.getByText('admin')).toBeInTheDocument();
  expect(screen.getByText('yes')).toBeInTheDocument();
});
