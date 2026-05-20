import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HistoryPage } from './HistoryPage';

const filteredFactory = vi.fn(() => ({
  data: [
    { id: 100, switch_id: 1, backup_type: 'manual', success: true,
      created_at: '2026-05-20T01:00:00Z', size_bytes: 2048, message: 'ok' },
  ],
  isLoading: false,
}));
const deleteMutate = vi.fn();

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({ data: [{ id: 1, name: 'SW-A', ip: '10.0.0.1', host: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true }] }),
  useFilteredBackups: (filters: unknown) => filteredFactory(filters as never),
  useDeleteBackup: () => ({ mutate: deleteMutate, isPending: false }),
  fetchBackupContent: vi.fn(async () => 'config text'),
  downloadBackupUrl: (id: number) => `/api/v1/backups/${id}/content?download=true`,
}));

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({ user: { id: 1, username: 'admin', role: 'admin', is_active: true } }),
}));

describe('HistoryPage', () => {
  it('passes selected filters to useFilteredBackups', async () => {
    const user = userEvent.setup();
    filteredFactory.mockClear();
    render(<HistoryPage />);
    await user.selectOptions(screen.getByLabelText(/state/i), 'success');
    const lastCall = filteredFactory.mock.calls.at(-1)![0] as { success?: boolean };
    expect(lastCall.success).toBe(true);
  });

  it('opens the view modal when clicking View', async () => {
    const user = userEvent.setup();
    render(<HistoryPage />);
    await user.click(screen.getByRole('button', { name: /view/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('Delete (admin) calls useDeleteBackup after confirm', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<HistoryPage />);
    await user.click(screen.getByRole('button', { name: /delete/i }));
    expect(deleteMutate).toHaveBeenCalledWith(100);
    confirm.mockRestore();
  });
});
