import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SwitchesPage } from './SwitchesPage';

const createMutate = vi.fn();
const deactivateMutate = vi.fn();

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({ data: [
    { id: 1, name: 'SW-CORE-01', ip: '10.0.0.1', host: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
    { id: 2, name: 'SW-OLD-01', ip: '10.0.0.99', host: '10.0.0.99', protocol: 'telnet', port: 23, credential_id: 1, is_active: false },
  ], isLoading: false }),
  useCredentials: () => ({ data: [{ id: 1, name: 'Lab admin' }], isLoading: false }),
  useTriggerBackup: () => ({ mutate: vi.fn() }),
  useCreateSwitch: () => ({ mutate: createMutate, isPending: false }),
  useUpdateSwitch: () => ({ mutate: vi.fn(), isPending: false }),
  useDeactivateSwitch: () => ({ mutate: deactivateMutate, isPending: false }),
  useActivateSwitch: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteSwitch: () => ({ mutate: vi.fn(), isPending: false }),
  useCreateCredential: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

describe('SwitchesPage', () => {
  it('opens an inline add row when clicking + Add switch', async () => {
    const user = userEvent.setup();
    render(<SwitchesPage />);
    await user.click(screen.getByRole('button', { name: /add switch/i }));
    expect(screen.getByPlaceholderText(/name/i)).toBeInTheDocument();
  });

  it('hides inactive switches by default and reveals via filter', async () => {
    const user = userEvent.setup();
    render(<SwitchesPage />);
    expect(screen.queryByText('SW-OLD-01')).toBeNull();
    await user.click(screen.getByLabelText(/show inactive/i));
    expect(screen.getByText('SW-OLD-01')).toBeInTheDocument();
  });
});
