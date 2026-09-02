/**
 * Protects: M9 FR-9.10 «external links are built from a `set_number` template;
 * nothing is stored, nothing is fetched, nothing goes stale».
 */

import { describe, expect, it } from 'vitest';
import {
  ageRangeLabel,
  boxDimensionsLabel,
  externalLinks,
  parseAgeRange,
  parseBoxDimensions,
} from './constants';

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

describe('ageRangeLabel', () => {
  it('reads an open-ended range the way the box prints it', () => {
    expect(ageRangeLabel(18, null)).toBe('18+');
    expect(ageRangeLabel(6, 12)).toBe('6–12');
    expect(ageRangeLabel(null, null)).toBeNull();
  });
});

describe('boxDimensionsLabel', () => {
  it('joins the three sides and marks the one the provider did not know', () => {
    expect(boxDimensionsLabel('26.2', '7.1', '38.2')).toBe('26,2 × 7,1 × 38,2 cm');
    expect(boxDimensionsLabel('26.2', null, null)).toBe('26,2 × ? × ? cm');
    expect(boxDimensionsLabel(null, null, null)).toBeNull();
  });
});

describe('parseAgeRange', () => {
  it('reads the age the way it is printed on any box', () => {
    expect(parseAgeRange('18+')).toEqual({ min: 18, max: null });
    expect(parseAgeRange('+4')).toEqual({ min: 4, max: null });
    expect(parseAgeRange('6-12')).toEqual({ min: 6, max: 12 });
    expect(parseAgeRange('6–12')).toEqual({ min: 6, max: 12 });
    expect(parseAgeRange('')).toEqual({ min: null, max: null });
    expect(parseAgeRange('a partir dos 8')).toEqual({ min: null, max: null });
  });
});

describe('parseBoxDimensions', () => {
  it('splits one typed field back into three sides, comma decimals included', () => {
    expect(parseBoxDimensions('26,2 × 7,1 × 38,2')).toEqual({
      width: '26.2',
      depth: '7.1',
      height: '38.2',
    });
    expect(parseBoxDimensions('26.2x7.1x38.2')).toEqual({
      width: '26.2',
      depth: '7.1',
      height: '38.2',
    });
    expect(parseBoxDimensions('')).toEqual({ width: null, depth: null, height: null });
  });
});
