import { describe, expect, it } from 'vitest';
import { humanizeError } from './errors';

describe('humanizeError', () => {
  it('returns clean fallback for null/undefined', () => {
    expect(humanizeError(null)).toBe('Something went wrong. Please try again.');
    expect(humanizeError(undefined)).toBe('Something went wrong. Please try again.');
  });

  it('passes structured server detail through unchanged when no rewrite matches', () => {
    const err = { response: { status: 409, data: { detail: 'Some unique conflict text' } } };
    expect(humanizeError(err)).toBe('Some unique conflict text');
  });

  it('rewrites known sentinel detail like "Switch name already exists"', () => {
    const err = { response: { status: 409, data: { detail: 'Switch name already exists' } } };
    expect(humanizeError(err)).toBe('A switch with that name already exists. Pick another name.');
  });

  it('rewrites 401 invalid credentials to plain language', () => {
    const err = {
      response: {
        status: 401,
        data: { detail: 'Invalid username or password' },
      },
    };
    expect(humanizeError(err)).toBe(
      'Username or password is wrong. Check your credentials and try again.',
    );
  });

  it('rewrites 423 lockout to friendly text', () => {
    const err = {
      response: {
        status: 423,
        data: { detail: 'Account temporarily locked' },
      },
    };
    expect(humanizeError(err)).toBe(
      'Account is temporarily locked after too many failed attempts. Wait a few minutes and try again.',
    );
  });

  it('rewrites 403 to plain language', () => {
    const err = {
      response: {
        status: 403,
        data: { detail: 'User role is not permitted for this operation' },
      },
    };
    expect(humanizeError(err)).toBe(
      "You don't have permission for this action. Ask an admin if you need access.",
    );
  });

  it('falls back to a friendly 404 message', () => {
    const err = { response: { status: 404, data: {} } };
    expect(humanizeError(err)).toBe(
      'The item you tried to open is no longer available. It may have been deleted.',
    );
  });

  it('rewrites network failures', () => {
    const err = { code: 'ERR_NETWORK', message: 'Network Error' };
    expect(humanizeError(err)).toBe(
      'Cannot reach the backend service. Check that NCM v4 is running and try again.',
    );
  });

  it('rewrites timeouts', () => {
    const err = { code: 'ECONNABORTED', message: 'timeout of 5000ms exceeded' };
    expect(humanizeError(err)).toBe(
      'The request took too long. The device may be slow or unreachable.',
    );
  });

  it('rewrites 500 to a stable apology', () => {
    const err = { response: { status: 500, data: { detail: 'kaboom' } } };
    expect(humanizeError(err)).toBe(
      'Something broke on the server. Try again; if it keeps failing, check the service logs.',
    );
  });

  it('passes structured server detail through unchanged when meaningful', () => {
    const err = {
      response: {
        status: 422,
        data: { detail: 'Backup root folder must not be empty' },
      },
    };
    expect(humanizeError(err)).toBe('Backup root folder must not be empty');
  });
});
