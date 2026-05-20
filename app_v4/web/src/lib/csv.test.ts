import { describe, expect, it } from 'vitest';
import { toCsv } from './csv';

describe('toCsv', () => {
  it('serialises rows with header and quoted strings', () => {
    const csv = toCsv(
      ['name', 'note'],
      [{ name: 'A', note: 'hello, world' }, { name: 'B', note: 'plain' }],
    );
    expect(csv).toBe('name,note\nA,"hello, world"\nB,plain\n');
  });

  it('escapes embedded quotes', () => {
    const csv = toCsv(['x'], [{ x: 'a "b" c' }]);
    expect(csv).toContain('"a ""b"" c"');
  });
});
