import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { it, expect, vi } from 'vitest';
import { SchedulesPage } from './SchedulesPage';

vi.mock('../api/hooks', () => ({
  useJobs: () => ({ data: [{ id: 1, switch_id: 1, name: 'nightly', interval_minutes: 60, schedule_hour: 2, schedule_minute: 0, enabled: true }], isLoading: false }),
}));

it('renders schedules with interval and state', () => {
  render(<QueryClientProvider client={new QueryClient()}><SchedulesPage /></QueryClientProvider>);
  expect(screen.getByText('nightly')).toBeInTheDocument();
  expect(screen.getByText('60m')).toBeInTheDocument();
  expect(screen.getByText('enabled')).toBeInTheDocument();
});
