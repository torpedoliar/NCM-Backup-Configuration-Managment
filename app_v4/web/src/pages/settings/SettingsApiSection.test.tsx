import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsApiSection } from './SettingsApiSection';

const KEY = { id: 1, name: 'lab-automation', prefix: 'ncr_Ab1', key: 'ncr_secret_token_123' };

const createMutate = vi.fn((_name: string, options?: { onSuccess?: (key: typeof KEY) => void }) => {
  options?.onSuccess?.(KEY);
});
const revokeMutate = vi.fn();
const deleteMutate = vi.fn();

vi.mock('../../api/hooks', () => ({
  useApiKeys: () => ({
    data: [
      { id: 1, name: 'lab-automation', prefix: 'ncr_Ab1', created_at: '2026-08-01T10:00:00Z', last_used_at: null, revoked: false },
      { id: 2, name: 'old-key', prefix: 'ncr_Xy2', created_at: '2026-07-01T10:00:00Z', last_used_at: '2026-07-20T08:00:00Z', archived: false, revoked: true },
    ],
    isLoading: false,
  }),
  useCreateApiKey: () => ({ mutate: createMutate, isPending: false }),
  useRevokeApiKey: () => ({ mutate: revokeMutate, isPending: false }),
  useDeleteApiKey: () => ({ mutate: deleteMutate, isPending: false }),
}));

describe('SettingsApiSection', () => {
  it('renders API documentation with curl examples', () => {
    render(<SettingsApiSection />);
    expect(screen.getByText('Using the API')).toBeTruthy();
    expect(screen.getAllByText(/network-doc/).length).toBeGreaterThan(0);
  });

  it('creates a key and reveals the plaintext once', async () => {
    const user = userEvent.setup();
    render(<SettingsApiSection />);
    await user.type(screen.getByLabelText(/key name/i), 'automation');
    await user.click(screen.getByRole('button', { name: /create key/i }));
    expect(createMutate).toHaveBeenCalledWith('automation', expect.anything());
    expect(screen.getByText('ncr_secret_token_123')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Done' })).toBeTruthy();
  });

  it('copy button writes the plaintext key to the clipboard', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    // Must override AFTER setup: user-event stubs navigator.clipboard on setup.
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    render(<SettingsApiSection />);
    await user.type(screen.getByLabelText(/key name/i), 'automation');
    await user.click(screen.getByRole('button', { name: /create key/i }));
    await user.click(screen.getByRole('button', { name: 'Copy' }));
    expect(writeText).toHaveBeenCalledWith('ncr_secret_token_123');
    expect(screen.getByRole('button', { name: 'Copied' })).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it('marks revoked keys and only offers revoke for active ones', () => {
    render(<SettingsApiSection />);
    expect(screen.getByText('REVOKED')).toBeTruthy();
    expect(screen.getByText('lab-automation')).toBeTruthy();
    expect(screen.getAllByRole('button', { name: 'Revoke' })).toHaveLength(1);
  });

  it('revokes an active key after confirmation', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = userEvent.setup();
    render(<SettingsApiSection />);
    await user.click(screen.getAllByRole('button', { name: 'Revoke' })[0]);
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('lab-automation'));
    expect(revokeMutate).toHaveBeenCalledWith(1);
    confirmSpy.mockRestore();
  });
});