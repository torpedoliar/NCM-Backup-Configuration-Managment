import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HistoryPage } from './HistoryPage';
import { downloadBackup } from '../api/hooks';

function makeRows(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: 100 + i,
    switch_id: 1,
    backup_type: 'manual' as const,
    success: true,
    created_at: `2026-05-20T01:00:0${i % 10}Z`,
    size_bytes: 2048,
    message: `row-${i}`,
  }));
}

const filteredFactory = vi.fn((_filters: unknown, opts?: { offset?: number; limit?: number }) => {
  const all = makeRows(12);
  return {
    data: {
      rows: all.slice(opts?.offset ?? 0, (opts?.offset ?? 0) + (opts?.limit ?? 10)),
      total: all.length,
    },
    isLoading: false,
  };
});
const deleteMutate = vi.fn();
const downloadBackupMock = vi.fn();

vi.mock('../api/hooks', () => ({
  useSwitches: () => ({ data: [{ id: 1, name: 'SW-A', ip: '10.0.0.1', host: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true }] }),
  usePagedBackups: (filters: unknown, opts: { offset: number; limit: number }) => filteredFactory(filters as never, opts),
  useDeleteBackup: () => ({ mutate: deleteMutate, isPending: false }),
  fetchBackupContent: vi.fn(async () => 'config text'),
  downloadBackup: (id: number) => downloadBackupMock(id),
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
    const calls = filteredFactory.mock.calls;
    const lastCall = calls[calls.length - 1]![0] as { success?: boolean };
    expect(lastCall.success).toBe(true);
  });

  it('shows the first page of history and pages through the rest', async () => {
    const user = userEvent.setup();
    render(<HistoryPage />);
    expect(screen.getByText('row-0')).toBeInTheDocument();
    expect(screen.queryByText('row-10')).toBeNull();
    await user.click(screen.getByRole('button', { name: /next/i }));
    expect(screen.getByText('row-10')).toBeInTheDocument();
    expect(screen.queryByText('row-0')).toBeNull();
    expect(screen.getByText('PAGE 2 / 2')).toBeInTheDocument();
  });

  it('renders the selected backup config in the viewer box', async () => {
    const user = userEvent.setup();
    render(<HistoryPage />);
    await user.click(screen.getAllByRole('button', { name: /view/i })[0]!);
    expect(screen.getByLabelText(/backup config viewer/i)).toBeInTheDocument();
    expect(await screen.findByText('config text')).toBeInTheDocument();
  });

  it('Delete (admin) calls useDeleteBackup after confirm', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<HistoryPage />);
    await user.click(screen.getAllByRole('button', { name: /delete/i })[0]!);
    expect(deleteMutate).toHaveBeenCalledWith(100);
    confirm.mockRestore();
  });

  it('Download calls downloadBackup with the row id', async () => {
    const user = userEvent.setup();
    downloadBackupMock.mockClear();
    render(<HistoryPage />);
    await user.click(screen.getAllByRole('button', { name: /download/i })[0]!);
    expect(downloadBackupMock).toHaveBeenCalledWith(100);
    // referenced to keep the import as a type-check sanity
    expect(typeof downloadBackup).toBe('function');
  });
});