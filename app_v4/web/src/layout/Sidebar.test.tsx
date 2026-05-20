import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../api/hooks', () => ({
  useSystemMetrics: () => ({
    data: { switches: 7, backups: 42, jobs: 3, failures_24h: 1 },
    isLoading: false,
  }),
}));

vi.mock('wouter', async () => {
  const actual = await vi.importActual<typeof import('wouter')>('wouter');
  return { ...actual, useLocation: () => ['/'] };
});

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'admin', role: 'admin', is_active: true },
    logout: vi.fn(),
  }),
}));

afterEach(() => {
  vi.resetModules();
});

describe('Sidebar', () => {
  it('renders counts from /system/metrics', async () => {
    const { Sidebar } = await import('./Sidebar');
    render(<Sidebar />);
    expect(screen.getByText(/Switches/i).parentElement?.textContent).toContain('7');
    expect(screen.getByText(/Backup History/i).parentElement?.textContent).toContain('42');
    expect(screen.getByText(/Schedules/i).parentElement?.textContent).toContain('3');
  });

  it('shows a Sign out button that triggers auth.logout', async () => {
    const logout = vi.fn();
    vi.doMock('../auth/AuthProvider', () => ({
      useAuth: () => ({
        user: { id: 1, username: 'admin', role: 'admin', is_active: true },
        logout,
      }),
    }));
    vi.doMock('../api/hooks', () => ({
      useSystemMetrics: () => ({
        data: { switches: 0, backups: 0, jobs: 0, failures_24h: 0 },
        isLoading: false,
      }),
    }));
    vi.doMock('wouter', async () => {
      const actual = await vi.importActual<typeof import('wouter')>('wouter');
      return { ...actual, useLocation: () => ['/'] };
    });

    const { Sidebar } = await import('./Sidebar');
    const user = userEvent.setup();
    render(<Sidebar />);
    await user.click(screen.getByRole('button', { name: /sign out/i }));
    expect(logout).toHaveBeenCalled();
  });

  it('hides the Activity link for non-admin users', async () => {
    vi.doMock('../auth/AuthProvider', () => ({
      useAuth: () => ({
        user: { id: 1, username: 'op', role: 'operator', is_active: true },
        logout: vi.fn(),
      }),
    }));
    vi.doMock('../api/hooks', () => ({
      useSystemMetrics: () => ({
        data: { switches: 0, backups: 0, jobs: 0, failures_24h: 0 },
        isLoading: false,
      }),
    }));
    vi.doMock('wouter', async () => {
      const actual = await vi.importActual<typeof import('wouter')>('wouter');
      return { ...actual, useLocation: () => ['/'] };
    });

    const { Sidebar } = await import('./Sidebar');
    render(<Sidebar />);
    expect(screen.queryByText(/^Activity$/)).toBeNull();
  });
});
