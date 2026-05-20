import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const tokensPath = path.resolve(__dirname, 'tokens.css');
const tokens = readFileSync(tokensPath, 'utf-8');

const requiredTokens = [
  '--ink: #0a0a0a',
  '--amber: #ffb800',
  '--red: #ff3838',
  '--green: #4ade80',
  '--font-mono:',
  '--font-display:',
  '--grid-size: 64px',
  '--panel-border: #262626',
];

describe('Ops Terminal tokens', () => {
  it('keeps mockup-critical visual tokens', () => {
    for (const token of requiredTokens) {
      expect(tokens).toContain(token);
    }
  });
});
