import { describe, expect, it, vi } from 'vitest';
import { render, act } from '@testing-library/react';
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
    mock.onGet('/auth/me').reply(401, { detail: 'unused' });

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

    mock.restore();
  });
});

describe('AuthProvider.user populate', () => {
  it('fetches /auth/me and populates user when access token present', async () => {
    const mock = new MockAdapter(api as unknown as AxiosInstance);
    mock.onGet('/auth/me').reply(200, {
      id: 1,
      username: 'admin',
      role: 'admin',
      is_active: true,
    });

    let captured: ReturnType<typeof useAuth> | null = null;
    const { hook } = memoryLocation({ path: '/' });

    render(
      <Router hook={hook}>
        <AuthProvider initialAccessToken="seeded-access" initialRefreshToken="seeded-refresh">
          <Probe onReady={(a) => { captured = a; }} />
        </AuthProvider>
      </Router>,
    );

    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });

    expect(captured!.user).not.toBeNull();
    expect(captured!.user!.username).toBe('admin');
    expect(captured!.user!.role).toBe('admin');

    mock.restore();
  });

  it('clears user on /auth/me 401', async () => {
    const mock = new MockAdapter(api as unknown as AxiosInstance);
    mock.onGet('/auth/me').reply(401, { detail: 'expired' });
    mock.onPost('/auth/logout').reply(204);

    let captured: ReturnType<typeof useAuth> | null = null;
    const { hook } = memoryLocation({ path: '/' });

    render(
      <Router hook={hook}>
        <AuthProvider initialAccessToken="bad-token" initialRefreshToken="bad-refresh">
          <Probe onReady={(a) => { captured = a; }} />
        </AuthProvider>
      </Router>,
    );

    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });

    expect(captured!.user).toBeNull();

    mock.restore();
  });
});
