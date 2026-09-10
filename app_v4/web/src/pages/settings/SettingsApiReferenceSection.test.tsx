import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { API_REF, CURL_EXAMPLES, ENDPOINT_DESCRIPTIONS, KNOWN_SCOPES, LEGACY_KEY_NOTE } from '../../api/apiReference';
import { SettingsApiReferenceSection } from './SettingsApiReferenceSection';

describe('SettingsApiReferenceSection', () => {
  it('documents at least 75 endpoints with auth per entry', () => {
    expect(API_REF.length).toBeGreaterThanOrEqual(75);
    for (const e of API_REF) {
      expect(e.auth).toBeTruthy();
    }
  });

  it('every entry has a description', () => {
    for (const e of API_REF) {
      expect(ENDPOINT_DESCRIPTIONS[`${e.method} ${e.path}`]).toBeTruthy();
    }
  });

  it('documents all scopes plus the legacy-key note', () => {
    expect(Object.keys(KNOWN_SCOPES)).toContain('read');
    expect(Object.keys(KNOWN_SCOPES).length).toBeGreaterThanOrEqual(8);
    expect(LEGACY_KEY_NOTE).toMatch(/403/);
    render(<SettingsApiReferenceSection />);
    expect(screen.getByText(/Referensi lengkap REST API NCM/)).toBeTruthy();
  });

  it('mentions network-doc scope migration and renders the scope table', () => {
    render(<SettingsApiReferenceSection />);
    expect(screen.getByText(/tiket 16/i)).toBeTruthy();
    const scopeKeys = screen.getAllByText('read');
    expect(scopeKeys.length).toBeGreaterThan(0);
  });

  it('limits curl examples to at most 2 per module', () => {
    const counts = new Map<string, number>();
    for (const c of CURL_EXAMPLES) counts.set(c.tag, (counts.get(c.tag) ?? 0) + 1);
    expect([...counts.values()].every((n) => n <= 2)).toBe(true);
  });

  it('renders one table per module with method/path/auth columns', () => {
    render(<SettingsApiReferenceSection />);
    const tables = screen.getAllByRole('table');
    expect(tables.length).toBeGreaterThanOrEqual(10);
    const first = within(tables[0]);
    expect(first.getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Method',
      'Path',
      'Auth',
      'Deskripsi',
    ]);
  });
});
