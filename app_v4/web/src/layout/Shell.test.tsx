import { render, screen } from '@testing-library/react';
import { it, expect } from 'vitest';
import { Shell } from './Shell';

it('renders mockup shell chrome', () => {
  render(<Shell><main>Dashboard body</main></Shell>);

  expect(screen.getByText('NCM')).toBeInTheDocument();
  expect(screen.getByText('NETWORK CONFIG MGR')).toBeInTheDocument();
  expect(screen.getByText('V3.5.7 / PROD')).toBeInTheDocument();
  expect(screen.getAllByText('MONITORING').length).toBeGreaterThan(0);
  expect(screen.getByText('/ Dashboard')).toBeInTheDocument();
  expect(screen.getByText('SERVICE / RUNNING')).toBeInTheDocument();
  expect(screen.getByText('Dashboard body')).toBeInTheDocument();
});
