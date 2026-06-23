import { describe, expect, it } from 'vitest';

import { formatDateTime } from './format';

describe('formatDateTime', () => {
  it('returns a dash for null/undefined', () => {
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime(undefined)).toBe('—');
  });

  it('formats a valid ISO string', () => {
    const out = formatDateTime('2026-06-22T00:00:00Z');
    expect(out).not.toBe('—');
    expect(out.length).toBeGreaterThan(0);
  });

  it('returns the raw value when unparseable', () => {
    expect(formatDateTime('not-a-date')).toBe('not-a-date');
  });
});
