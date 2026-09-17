import { describe, expect, it } from 'vitest';

import { productOptionLabel } from './format';

/**
 * A QR batch is printed against whichever product was picked, and a printed
 * batch cannot be un-printed. These pin the thing that makes the choice
 * unambiguous.
 */
describe('productOptionLabel', () => {
  it('tells two sizes of the same model apart', () => {
    const base = { name: 'GoodBed Ortho Bonnell 8 inch', points_value: 50 };

    const small = productOptionLabel({ ...base, size: '72 x 36 x 8 inch' });
    const large = productOptionLabel({ ...base, size: '75 x 60 x 8 inch' });

    // Without the size these two were the same string, which is how a batch
    // gets printed against the wrong product.
    expect(small).not.toBe(large);
    expect(small).toContain('72 x 36 x 8 inch');
    expect(large).toContain('75 x 60 x 8 inch');
  });

  it('puts the size straight after the name, before the points', () => {
    const label = productOptionLabel({
      name: 'HR Foam 6 inch',
      size: '72 x 36 x 6 inch',
      points_value: 30,
    });

    expect(label).toBe('HR Foam 6 inch · 72 x 36 x 6 inch · 30 pts');
  });

  it('omits the segment entirely when no size is recorded', () => {
    // Products predate the size field; they must not render a stray separator.
    expect(productOptionLabel({ name: 'HR Foam 6 inch', size: null, points_value: 30 })).toBe(
      'HR Foam 6 inch · 30 pts',
    );
    expect(productOptionLabel({ name: 'HR Foam 6 inch', points_value: 30 })).toBe(
      'HR Foam 6 inch · 30 pts',
    );
  });

  it('does not treat an empty size as a size', () => {
    expect(productOptionLabel({ name: 'HR Foam', size: '', points_value: 10 })).toBe(
      'HR Foam · 10 pts',
    );
  });
});
