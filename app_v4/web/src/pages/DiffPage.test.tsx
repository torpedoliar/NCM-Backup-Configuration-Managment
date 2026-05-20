import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
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
  api: { get: vi.fn(async () => ({ data: '--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n' })) },
}));

describe('DiffPage', () => {
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

  it('clicking Compare fetches /backups/diff with both ids', async () => {
    const { api } = await import('../api/client');
    const user = userEvent.setup();
    render(<DiffPage />);
    await user.click(screen.getByRole('button', { name: /compare/i }));
    expect(api.get).toHaveBeenCalledWith('/backups/diff', expect.objectContaining({
      params: expect.objectContaining({ a: expect.any(Number), b: expect.any(Number) }),
      responseType: 'text',
    }));
  });
});
