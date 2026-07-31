import { formatDobFromApi, formatDobInput, parseDob } from './profile';

// Fixed "today" so age-boundary cases don't drift as the calendar moves.
const TODAY = new Date(2026, 6, 31); // 31 Jul 2026

describe('formatDobInput', () => {
  it('auto-slashes digits as they are typed', () => {
    expect(formatDobInput('1')).toBe('1');
    expect(formatDobInput('1704')).toBe('17/04');
    expect(formatDobInput('17041990')).toBe('17/04/1990');
  });

  it('strips non-digits and caps at 8 digits', () => {
    expect(formatDobInput('17/04/1990')).toBe('17/04/1990');
    expect(formatDobInput('abc17x04y1990999')).toBe('17/04/1990');
  });
});

describe('parseDob', () => {
  it('converts a valid date to the ISO form the API wants', () => {
    expect(parseDob('17/04/1990', TODAY)).toBe('1990-04-17');
  });

  it('rejects malformed input', () => {
    expect(parseDob('', TODAY)).toBeNull();
    expect(parseDob('17/04/90', TODAY)).toBeNull();
    expect(parseDob('1990-04-17', TODAY)).toBeNull();
  });

  it('rejects dates that do not exist', () => {
    expect(parseDob('31/02/1990', TODAY)).toBeNull();
    expect(parseDob('31/04/1990', TODAY)).toBeNull();
    expect(parseDob('29/02/1991', TODAY)).toBeNull(); // 1991 is not a leap year
  });

  it('accepts a real leap day', () => {
    expect(parseDob('29/02/1992', TODAY)).toBe('1992-02-29');
  });

  it('rejects future dates', () => {
    expect(parseDob('01/01/2027', TODAY)).toBeNull();
  });

  it('enforces the 18-year floor on the exact boundary', () => {
    // Turns 18 on 31 Jul 2026 — allowed on the birthday itself.
    expect(parseDob('31/07/2008', TODAY)).toBe('2008-07-31');
    // Turns 18 tomorrow — still 17 today.
    expect(parseDob('01/08/2008', TODAY)).toBeNull();
  });

  it('rejects implausibly old dates', () => {
    expect(parseDob('01/01/1800', TODAY)).toBeNull();
  });
});

describe('formatDobFromApi', () => {
  it('turns the API form back into the display form', () => {
    expect(formatDobFromApi('1990-04-17')).toBe('17/04/1990');
  });

  it('handles missing values', () => {
    expect(formatDobFromApi(null)).toBe('');
    expect(formatDobFromApi(undefined)).toBe('');
  });
});
