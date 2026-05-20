import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { it, expect, vi } from 'vitest';
import { DashboardPage } from './DashboardPage';

vi.mock('../api/hooks', () => ({
  useSystemMetrics: () => ({ data: { switches: 12, backups: 348, jobs: 5, failures_24h: 1 }, isLoading: false }),
}));

it('renders mockup dashboard hero and KPI markers', () => {
  render(<QueryClientProvider client={new QueryClient()}><DashboardPage /></QueryClientProvider>);

  expect(screen.getByText('OPERATIONS OVERVIEW')).toBeInTheDocument();
  expect(screen.getByText('three-forty-eight')).toBeInTheDocument();
  expect(screen.getByText('/01 · INV')).toBeInTheDocument();
  expect(screen.getByText('/02 · EXEC')).toBeInTheDocument();
  expect(screen.getByText('/03 · QOS')).toBeInTheDocument();
  expect(screen.getByText('/04 · ALERT')).toBeInTheDocument();
});

it('renders chart, stream, and fleet sections', () => {
  render(<QueryClientProvider client={new QueryClient()}><DashboardPage /></QueryClientProvider>);

  expect(screen.getAllByText('TODAY').length).toBeGreaterThan(0);
  expect(screen.getAllByText('SW-EDGE-07 backup completed').length).toBeGreaterThan(0);
  expect(screen.getAllByText('SW-CORE-01').length).toBeGreaterThan(0);
});
