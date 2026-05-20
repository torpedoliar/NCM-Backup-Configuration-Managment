import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { it, expect } from 'vitest';
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
