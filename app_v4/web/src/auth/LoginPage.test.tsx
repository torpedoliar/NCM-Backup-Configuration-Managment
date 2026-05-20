import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { it, expect, vi } from 'vitest';
import { AuthContext } from './AuthProvider';
import { LoginPage } from './LoginPage';

it('submits username and password', async () => {
  const login = vi.fn().mockResolvedValue(undefined);
  render(
    <AuthContext.Provider value={{ accessToken: null, user: null, login, logout: vi.fn() }}>
      <LoginPage />
    </AuthContext.Provider>,
  );

  await userEvent.type(screen.getByLabelText(/username/i), 'admin');
  await userEvent.type(screen.getByLabelText(/password/i), 'secret');
  await userEvent.click(screen.getByRole('button', { name: /enter terminal/i }));

  expect(login).toHaveBeenCalledWith('admin', 'secret');
});
