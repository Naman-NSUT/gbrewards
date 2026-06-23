import { STRINGS } from './strings';

describe('i18n strings', () => {
  it('English and Hindi define exactly the same keys', () => {
    const en = Object.keys(STRINGS.en).sort();
    const hi = Object.keys(STRINGS.hi).sort();
    expect(hi).toEqual(en);
  });

  it('has no empty translations', () => {
    const empties: string[] = [];
    for (const lang of ['en', 'hi'] as const) {
      for (const [key, value] of Object.entries(STRINGS[lang])) {
        if (value.trim().length === 0) empties.push(`${lang}.${key}`);
      }
    }
    expect(empties).toEqual([]);
  });
});
