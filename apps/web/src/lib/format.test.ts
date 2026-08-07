/**
 * Protects: rubric «EUR formatting is comma-decimal (€1.234,56) via a single money
 * util» and M9 «`roi_pct` is NULL for gifts and for sets with no value — the UI
 * shows — rather than a fake percentage».
 */

import { describe, expect, it } from 'vitest';
import { EM_DASH, date, eur, num, percent, relativeDays, signedEur } from './format';

describe('eur', () => {
  it('formats decimal strings as pt-PT euros without ever parsing money as a float first', () => {
    // Non-breaking space before the symbol is what Intl emits for pt-PT.
    expect(eur('1234.56').replace(/\u00a0/g, ' ')).toBe('1234,56 €');
    expect(eur('0.00').replace(/\u00a0/g, ' ')).toBe('0,00 €');
    expect(eur('689').replace(/\u00a0/g, ' ')).toBe('689,00 €');
  });

  it('renders an em dash for absent values instead of a misleading zero', () => {
    expect(eur(null)).toBe(EM_DASH);
    expect(eur(undefined)).toBe(EM_DASH);
    expect(eur('')).toBe(EM_DASH);
  });
});

describe('percent', () => {
  it('signs positive returns and leaves negatives alone', () => {
    expect(percent('14.84')).toBe('+14,8 %');
    expect(percent('-40.00')).toBe('-40 %');
  });

  it('shows an em dash for a null ROI (gift or no value set)', () => {
    expect(percent(null)).toBe(EM_DASH);
  });
});

describe('signedEur', () => {
  it('marks gains with a plus and losses with the numeric minus', () => {
    expect(signedEur('89.01').replace(/\u00a0/g, ' ')).toBe('+89,01 €');
    expect(signedEur('-40.00').replace(/\u00a0/g, ' ')).toBe('-40,00 €');
    expect(signedEur(null)).toBe(EM_DASH);
  });
});

describe('dates and counts', () => {
  it('uses the pt-PT calendar order', () => {
    expect(date('2023-03-18')).toBe('18/03/2023');
    expect(date(null)).toBe(EM_DASH);
  });

  it('groups thousands the Portuguese way', () => {
    expect(num(10001).replace(/\u00a0/g, ' ')).toBe('10 001');
    expect(num(null)).toBe(EM_DASH);
  });

  it('describes value staleness in plain Portuguese', () => {
    const tenDaysAgo = new Date(Date.now() - 10 * 86_400_000).toISOString();
    expect(relativeDays(tenDaysAgo)).toBe('há 10 dias');
    expect(relativeDays(null)).toBe('nunca');
  });
});
