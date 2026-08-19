import dayjs, { type Dayjs } from 'dayjs';

export type DateRange = [Dayjs, Dayjs];

/** ISO yyyy-mm-dd — the plain-date form every date filter on this API takes. */
export function isoDate(d: Dayjs): string {
  return d.format('YYYY-MM-DD');
}

export const RANGE_PRESETS: { label: string; days: number }[] = [
  { label: '7 days', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: '12 months', days: 365 },
];

export function lastDays(days: number): DateRange {
  return [dayjs().subtract(days - 1, 'day').startOf('day'), dayjs().endOf('day')];
}
