import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CredentialsPage } from './CredentialsPage';

const createMutate = vi.fn();
const deleteMutate = vi.fn();

vi.mock('../api/hooks', () => ({
  useCredentials: () => ({ data: [
    { id: 1, name: 'Lab admin', username: 'lab' },
  ], isLoading: false }),
  useCreateCredential: () => ({ mutate: createMutate, isPending: false }),
  useUpdateCredential: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteCredential: () => ({ mutate: deleteMutate, isPending: false }),
}));

describe('CredentialsPage', () => {
  it('opens an inline draft row on + Add credential', async () => {
    const user = userEvent.setup();
    render(<CredentialsPage />);
    await user.click(screen.getByRole('button', { name: /add credential/i }));
    expect(screen.getByPlaceholderText(/^name$/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/^password$/i)).toBeInTheDocument();
  });

  it('renders the secret column as masked', () => {
    render(<CredentialsPage />);
    expect(screen.getByText('••••••••')).toBeInTheDocument();
  });

  it('Delete asks for confirm and calls useDeleteCredential', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<CredentialsPage />);
    await user.click(screen.getByRole('button', { name: /delete/i }));
    expect(deleteMutate).toHaveBeenCalledWith(1);
    confirm.mockRestore();
  });
});
