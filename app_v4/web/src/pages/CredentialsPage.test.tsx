import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { it, expect, vi } from 'vitest';
import { CredentialsPage } from './CredentialsPage';

vi.mock('../api/hooks', () => ({
  useCredentials: () => ({ data: [{ id: 1, name: 'lab-creds' }], isLoading: false }),
}));

it('renders credentials with masked secret', () => {
  render(<QueryClientProvider client={new QueryClient()}><CredentialsPage /></QueryClientProvider>);
  expect(screen.getByText('lab-creds')).toBeInTheDocument();
  expect(screen.getByText('••••••••')).toBeInTheDocument();
});
