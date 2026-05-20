import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { it, expect, vi } from 'vitest';
import { SwitchesPage } from './SwitchesPage';

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({ data: [{ id: 1, name: 'sw01', host: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true }], isLoading: false }),
  useTriggerBackup: () => ({ mutate: vi.fn(), isPending: false }),
}));

it('renders switches and backup action', () => {
  render(<QueryClientProvider client={new QueryClient()}><SwitchesPage /></QueryClientProvider>);
  expect(screen.getByText('sw01')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /backup now/i })).toBeInTheDocument();
});
