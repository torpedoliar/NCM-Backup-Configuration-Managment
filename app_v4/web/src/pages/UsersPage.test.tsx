import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UsersPage } from './UsersPage';

const createMutate = vi.fn();
const updateMutate = vi.fn();
const deleteMutate = vi.fn();
const resetMutateAsync = vi.fn().mockResolvedValue(undefined);

vi.mock('../api/hooks', () => ({
  useUsers: () => ({ data: [
    { id: 1, username: 'admin', role: 'admin', is_active: true, created_at: '2026-05-01T00:00:00Z' },
    { id: 2, username: 'op1',   role: 'operator', is_active: true, created_at: '2026-05-01T00:00:00Z' },
  ], isLoading: false }),
  useCreateUser: () => ({ mutate: createMutate, isPending: false }),
  useUpdateUser: () => ({ mutate: updateMutate, isPending: false }),
  useDeleteUser: () => ({ mutate: deleteMutate, isPending: false }),
  useResetUserPassword: () => ({ mutateAsync: resetMutateAsync, isPending: false }),
}));

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({ user: { id: 1, username: 'admin', role: 'admin', is_active: true } }),
}));

describe('UsersPage', () => {
  it('opens an inline draft row on + Add user', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);
    await user.click(screen.getByRole('button', { name: /add user/i }));
    expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
  });

  it('disables Delete on the current user row', () => {
    render(<UsersPage />);
    const row = screen.getAllByText('admin')[0].closest('tr')!;
    const deleteBtn = row.querySelector('button[data-action="delete"]') as HTMLButtonElement;
    expect(deleteBtn).toBeDisabled();
  });

  it('toggling Active calls useUpdateUser with {is_active: false}', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);
    const row = screen.getByText('op1').closest('tr')!;
    await user.click(row.querySelector('input[type=checkbox]') as HTMLElement);
    expect(updateMutate).toHaveBeenCalledWith({ id: 2, input: { is_active: false } });
  });

  it('Reset password expansion submits new password', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);
    const row = screen.getByText('op1').closest('tr')!;
    await user.click(row.querySelector('button[data-action="reset"]') as HTMLElement);
    await user.type(screen.getByPlaceholderText(/new password/i), 'NewPass123');
    await user.click(screen.getByRole('button', { name: /save new password/i }));
    expect(resetMutateAsync).toHaveBeenCalledWith({ id: 2, password: 'NewPass123' });
  });
});
