import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Router } from 'wouter';
import { memoryLocation } from 'wouter/memory-location';
import { DashboardPage } from './DashboardPage';

vi.mock('../api/hooks', () => ({
  useSystemMetrics: () => ({ data: { switches: 7, backups: 42, jobs: 3, failures_24h: 0 }, isLoading: false }),
  useSwitches: () => ({ data: [], isLoading: false }),
  useBackups: () => ({ data: [], isLoading: false }),
  useLatestBackupPerSwitch: () => ({ data: [], isLoading: false }),
}));

vi.mock('../auth/AuthProvider', () => ({
  useOptionalAuth: () => null,
}));

vi.mock('../lib/ws', () => ({ useLiveSocket: () => undefined }));

function renderPage() {
  const { hook } = memoryLocation({ path: '/' });
  return render(
    <Router hook={hook}>
      <DashboardPage />
    </Router>,
  );
}

describe('DashboardPage', () => {
  it('renders the hero headline using metrics from the API', () => {
    renderPage();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('7');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('42');
  });

  it('time-range tabs change the active range', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole('button', { name: '7D' }));
    expect(screen.getByRole('button', { name: '7D' })).toHaveAttribute('data-active', 'true');
  });

  it('EXPORT triggers a CSV download', () => {
    const click = vi.fn();
    const original = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = click;
    try {
      renderPage();
      fireEvent.click(screen.getByRole('button', { name: /export/i }));
      expect(click).toHaveBeenCalled();
    } finally {
      HTMLAnchorElement.prototype.click = original;
    }
  });
});
