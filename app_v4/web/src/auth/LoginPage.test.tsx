import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginPage } from './LoginPage';
import { AuthProvider } from './AuthProvider';

const loginMock = vi.fn();
let currentToken: string | null = null;

vi.mock('./AuthProvider', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./AuthProvider')>();
  return {
    ...actual,
    useAuth: () => ({
      login: loginMock,
      logout: vi.fn(),
      user: null,
      accessToken: currentToken,
      refreshToken: null,
    }),
  };
});

vi.mock('wouter', async (importOriginal) => {
  const actual = await importOriginal<typeof import('wouter')>();
  return {
    ...actual,
    Redirect: ({ to }: { to: string }) => <div data-testid="redirect-to">{to}</div>,
  };
});


describe('LoginPage', () => {
  it('renders inside a centered login card with form fields and submit', async () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );

    const card = document.querySelector('.login-card');
    expect(card).toBeTruthy();

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /enter terminal/i })).toBeInTheDocument();
  });

  it('submits username and password', async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );
    await user.type(screen.getByLabelText(/username/i), 'admin');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /enter terminal/i }));
    expect(loginMock).toHaveBeenCalledWith('admin', 'password123');
  });

  it('redirects to / when already authenticated', () => {
    currentToken = 'existing-token';
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );
    expect(screen.getByTestId('redirect-to')).toHaveTextContent('/');
    currentToken = null;
  });
});
