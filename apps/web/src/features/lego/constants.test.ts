/**
 * Protects: M9 FR-9.10 «external links are built from a `set_number` template;
 * nothing is stored, nothing is fetched, nothing goes stale».
 */

import { describe, expect, it } from 'vitest';
import { externalLinks } from './constants';

describe('externalLinks', () => {
  it('builds all four marketplace links from the bare set number', () => {
    const links = externalLinks('10307');
    expect(links.map((link) => link.label)).toEqual([
      'Brickset',
      'BrickLink',
      'BrickEconomy',
      'Rebrickable',
    ]);
    expect(links[0].href).toBe('https://brickset.com/sets/10307-1');
    expect(links[3].href).toBe('https://rebrickable.com/sets/10307-1/');
  });

  it('does not double up a variant suffix the user already typed', () => {
    expect(externalLinks('10307-1')[0].href).toBe('https://brickset.com/sets/10307-1');
  });
});
