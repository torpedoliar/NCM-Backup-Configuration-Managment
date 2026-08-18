import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsAuthSection } from './SettingsAuthSection';

const mutate = vi.fn();

vi.mock('../../api/hooks', () => ({
  useAuthSettings: () => ({
    data: {
      access_token_minutes: 15,
      refresh_token_days: 7,
      lockout_threshold: 5,
      lockout_window_minutes: 10,
      lockout_duration_minutes: 30,
      password_min_length: 8,
      password_require_upper: true,
      password_require_lower: true,
      password_require_digit: true,
      password_require_symbol: false,
    },
    isLoading: false,
  }),
  usePatchAuthSettings: () => ({ mutate, isPending: false }),
}));

describe('SettingsAuthSection', () => {
  it('renders three save buttons (one per card)', () => {
    render(<SettingsAuthSection />);
    expect(screen.getAllByRole('button', { name: /save/i })).toHaveLength(3);
  });

  it('Token card Save sends only the changed token field', async () => {
    const user = userEvent.setup();
    render(<SettingsAuthSection />);
    const access = screen.getByLabelText(/Access token/i);
    fireEvent.change(access, { target: { value: '30' } });
    const tokenCard = access.closest('article')!;
    const save = tokenCard.querySelector('button')! as HTMLButtonElement;
    await user.click(save);
    expect(mutate).toHaveBeenCalledWith(
      { access_token_minutes: 30 },
      expect.anything(),
    );
  });

  it('Password card Save sends only the changed password field', async () => {
    const user = userEvent.setup();
    render(<SettingsAuthSection />);
    const symbol = screen.getByLabelText(/Require symbol/i);
    await user.click(symbol);
    const card = symbol.closest('article')!;
    const save = card.querySelector('button')! as HTMLButtonElement;
    await user.click(save);
    expect(mutate).toHaveBeenLastCalledWith(
      { password_require_symbol: true },
      expect.anything(),
    );
  });
});
