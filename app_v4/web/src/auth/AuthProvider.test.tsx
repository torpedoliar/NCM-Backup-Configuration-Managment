import { describe, expect, it, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import MockAdapter from 'axios-mock-adapter';
import type { AxiosInstance } from 'axios';
import { Router } from 'wouter';
import { memoryLocation } from 'wouter/memory-location';
import { api } from '../api/client';
import { AuthProvider, useAuth } from './AuthProvider';

function Probe({ onReady }: { onReady: (auth: ReturnType<typeof useAuth>) => void }) {
  const auth = useAuth();
  onReady(auth);
  return <span>{auth.user ? 'in' : 'out'}</span>;
}

describe('AuthProvider.logout', () => {
  it('calls /auth/logout, clears tokens, and redirects to /login', async () => {
    const mock = new MockAdapter(api as unknown as AxiosInstance);
    mock.onPost('/auth/logout').reply(204);

    let captured: ReturnType<typeof useAuth> | null = null;
    const { hook, history } = memoryLocation({ path: '/dashboard', record: true });

    render(
      <Router hook={hook}>
        <AuthProvider initialAccessToken="seeded-access" initialRefreshToken="seeded-refresh">
          <Probe onReady={(a) => { captured = a; }} />
        </AuthProvider>
      </Router>,
    );

    await act(async () => { await captured!.logout(); });

    expect(mock.history.post.find((r) => r.url === '/auth/logout')).toBeTruthy();
    expect(captured!.accessToken).toBeNull();
    expect(captured!.refreshToken).toBeNull();
    expect(history[history.length - 1]).toBe('/login');
    expect(screen.getByText('out')).toBeInTheDocument();

    mock.restore();
  });
});
