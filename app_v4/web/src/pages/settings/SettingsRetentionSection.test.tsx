import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsRetentionSection } from './SettingsRetentionSection';

const mutate = vi.fn();
const runRetentionMutate = vi.fn();

vi.mock('../../api/hooks', () => ({
  useRetention: () => ({
    data: {
      backup_min_keep: 1,
      backup_retention_days: 365,
      audit_retention_days: 90,
      retention_hour: 3,
      retention_minute: 0,
    },
    isLoading: false,
  }),
  usePatchRetention: () => ({ mutate, isPending: false }),
  useRunRetentionNow: () => ({ mutate: runRetentionMutate, isPending: false }),
}));

describe('SettingsRetentionSection', () => {
  it('disables Save until a field changes, then submits only the dirty field', async () => {
    const user = userEvent.setup();
    render(<SettingsRetentionSection />);
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled();

    const days = screen.getByLabelText(/Backup retention/i);
    fireEvent.change(days, { target: { value: '180' } });

    const save = screen.getByRole('button', { name: /save/i });
    expect(save).not.toBeDisabled();
    await user.click(save);

    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toEqual({ backup_retention_days: 180 });
  });
});
