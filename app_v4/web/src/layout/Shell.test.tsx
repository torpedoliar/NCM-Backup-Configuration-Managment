import { render, screen } from '@testing-library/react';
import { it, expect } from 'vitest';
import { Shell } from './Shell';

it('renders Ops Terminal chrome', () => {
  render(<Shell><main>Dashboard body</main></Shell>);
  expect(screen.getByText('NCM OPS')).toBeInTheDocument();
  expect(screen.getByText('monitoring / Dashboard')).toBeInTheDocument();
  expect(screen.getByText('Dashboard body')).toBeInTheDocument();
});
