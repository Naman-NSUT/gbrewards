// Profile field helpers shared by sign-in (PhoneScreen) and edit (ProfileScreen),
// so both screens validate identically and match the backend rules in
// backend/app/schemas/profile.py.

export type Gender = 'male' | 'female';

export const GENDERS: Gender[] = ['male', 'female'];

// Keep in step with MIN_AGE_YEARS in backend/app/schemas/profile.py — the app is
// declared 18+ on Google Play.
export const MIN_AGE_YEARS = 18;
export const MAX_AGE_YEARS = 120;

export const PINCODE_RE = /^\d{6}$/;

/** Digits-only, auto-slashed as the user types: "17041990" -> "17/04/1990". */
export function formatDobInput(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 8);
  const parts = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4, 8)];
  return parts.filter((p) => p.length > 0).join('/');
}

function ageOn(dob: Date, today: Date): number {
  let age = today.getFullYear() - dob.getFullYear();
  const beforeBirthday =
    today.getMonth() < dob.getMonth() ||
    (today.getMonth() === dob.getMonth() && today.getDate() < dob.getDate());
  if (beforeBirthday) age -= 1;
  return age;
}

/**
 * "17/04/1990" -> "1990-04-17" (what the API wants), or null if the text is not
 * a real date, is in the future, or falls outside the allowed age range.
 */
export function parseDob(input: string, today: Date = new Date()): string | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(input.trim());
  if (!m) return null;

  const [, dd, mm, yyyy] = m;
  const day = Number(dd);
  const month = Number(mm);
  const year = Number(yyyy);

  const date = new Date(year, month - 1, day);
  // Rejects impossible dates like 31/02 — JS rolls those over to March.
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null;
  }
  if (date > today) return null;

  const age = ageOn(date, today);
  if (age < MIN_AGE_YEARS || age > MAX_AGE_YEARS) return null;

  return `${yyyy}-${mm}-${dd}`;
}

/** "1990-04-17" (from the API) -> "17/04/1990" for display in the input. */
export function formatDobFromApi(iso: string | null | undefined): string {
  if (!iso) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : '';
}
