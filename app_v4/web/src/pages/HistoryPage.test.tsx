import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { it, expect, vi } from 'vitest';
import { HistoryPage } from './HistoryPage';

vi.mock('../api/hooks', () => ({
  useBackups: () => ({ data: [{ id: 42, switch_id: 1, backup_type: 'startup', success: true, created_at: '2026-05-19T00:00:00Z' }], isLoading: false }),
}));

it('renders backup history rows', () => {
  render(<QueryClientProvider client={new QueryClient()}><HistoryPage /></QueryClientProvider>);
  expect(screen.getByText('42')).toBeInTheDocument();
  expect(screen.getByText('startup')).toBeInTheDocument();
  expect(screen.getByText('success')).toBeInTheDocument();
});
