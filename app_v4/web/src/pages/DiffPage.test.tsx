import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DiffPage } from './DiffPage';

vi.mock('../api/hooks', () => {
  const SWITCH1 = {
    data: [
      { id: 30, switch_id: 1, backup_type: 'manual', success: true, created_at: '2026-05-20T09:00:00Z' },
      { id: 29, switch_id: 1, backup_type: 'manual', success: true, created_at: '2026-05-19T09:00:00Z' },
      { id: 28, switch_id: 1, backup_type: 'manual', success: true, created_at: '2026-05-18T09:00:00Z' },
    ],
    isLoading: false,
  };
  const EMPTY = { data: [], isLoading: false };
  return {
    useSwitches: () => ({ data: [
      { id: 1, name: 'SW-A', ip: '10.0.0.1', host: '10.0.0.1', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
      { id: 2, name: 'SW-B', ip: '10.0.0.2', host: '10.0.0.2', protocol: 'ssh', port: 22, credential_id: 1, is_active: true },
    ], isLoading: false }),
    useFilteredBackups: ({ switch_id }: { switch_id: number }) => (switch_id === 1 ? SWITCH1 : EMPTY),
  };
});

vi.mock('../api/client', () => ({
  api: { get: vi.fn(async () => ({ data: { rows: [], stats: { added_lines: 0, removed_lines: 0, changed_lines: 0, total_changes: 0 } } })) },
}));

const SIDE_OK = {
  data: {
    rows: [
      { line_a: 1, line_b: 1, text_a: 'hostname sw', text_b: 'hostname sw', op: 'equal' },
      { line_a: 2, line_b: 0, text_a: 'vlan 20', text_b: '', op: 'delete' },
      { line_a: 0, line_b: 2, text_a: '', text_b: 'vlan 30', op: 'insert' },
    ],
    stats: { added_lines: 1, removed_lines: 1, changed_lines: 0, total_changes: 2 },
  },
};

describe('DiffPage', () => {
  beforeEach(async () => {
    const { api } = await import('../api/client');
    vi.mocked(api.get).mockReset();
    vi.mocked(api.get).mockResolvedValue(SIDE_OK);
  });

  it('populates A and B pickers from selected switch backups and disables Compare when A === B', async () => {
    render(<DiffPage />);
    const aSelect = screen.getByLabelText(/backup a/i) as HTMLSelectElement;
    const bSelect = screen.getByLabelText(/backup b/i) as HTMLSelectElement;
    expect(aSelect.options.length).toBe(3);
    expect(bSelect.options.length).toBe(3);
    expect(aSelect.value).not.toBe(bSelect.value);

    const user = userEvent.setup();
    await user.selectOptions(aSelect, bSelect.value);
    expect(screen.getByRole('button', { name: /compare/i })).toBeDisabled();
  });

  it('clicking Compare fetches /backups/diff/side-by-side by default', async () => {
    const { api } = await import('../api/client');
    const user = userEvent.setup();
    render(<DiffPage />);
    await user.click(screen.getByRole('button', { name: /compare/i }));
    expect(api.get).toHaveBeenCalledWith('/backups/diff/side-by-side', expect.objectContaining({
      params: expect.objectContaining({ a: expect.any(Number), b: expect.any(Number) }),
    }));
  });

  it('renders added/removed rows with op-specific classes', async () => {
    const user = userEvent.setup();
    render(<DiffPage />);
    await user.click(screen.getByRole('button', { name: /compare/i }));
    expect(await screen.findByText('vlan 20')).toBeInTheDocument();
    expect(screen.getByText('vlan 30')).toBeInTheDocument();
    expect(document.querySelectorAll('.diff-row-delete').length).toBe(1);
    expect(document.querySelectorAll('.diff-row-insert').length).toBe(1);
  });

  it('switching to Unified view fetches /backups/diff', async () => {
    const { api } = await import('../api/client');
    vi.mocked(api.get).mockResolvedValueOnce({ data: '--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n' });
    const user = userEvent.setup();
    render(<DiffPage />);
    await user.selectOptions(screen.getByLabelText(/view/i), 'unified');
    await user.click(screen.getByRole('button', { name: /compare/i }));
    expect(api.get).toHaveBeenCalledWith('/backups/diff', expect.objectContaining({
      params: expect.objectContaining({ a: expect.any(Number), b: expect.any(Number) }),
      responseType: 'text',
    }));
  });

  it('shows problem detail from failed compare and clears previous diff', async () => {
    const { api } = await import('../api/client');
    vi.mocked(api.get)
      .mockResolvedValueOnce(SIDE_OK)
      .mockRejectedValueOnce({ response: { data: { detail: 'One or both backup files were not found' } } });
    const user = userEvent.setup();
    render(<DiffPage />);

    await user.click(screen.getByRole('button', { name: /compare/i }));
    expect(await screen.findByText('vlan 20')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /compare/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Backup file is missing on disk. It may have been deleted manually or by retention.',
    );
    await waitFor(() => expect(screen.queryByText('vlan 20')).not.toBeInTheDocument());
  });
});
