import * as SecureStore from 'expo-secure-store';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { STRINGS, type Lang } from './strings';

const LANG_KEY = 'sr_lang';

interface I18nState {
  ready: boolean;
  chosen: boolean; // a language has been explicitly stored
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nState | undefined>(undefined);

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_m, k) => String(vars[k] ?? `{${k}}`));
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [chosen, setChosen] = useState(false);
  const [lang, setLangState] = useState<Lang>('en');

  useEffect(() => {
    void (async () => {
      const stored = await SecureStore.getItemAsync(LANG_KEY);
      if (stored === 'en' || stored === 'hi') {
        setLangState(stored);
        setChosen(true);
      }
      setReady(true);
    })();
  }, []);

  const value = useMemo<I18nState>(
    () => ({
      ready,
      chosen,
      lang,
      setLang: (l: Lang) => {
        setLangState(l);
        setChosen(true);
        void SecureStore.setItemAsync(LANG_KEY, l);
      },
      t: (key, vars) => interpolate(STRINGS[lang][key] ?? STRINGS.en[key] ?? key, vars),
    }),
    [ready, chosen, lang],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
}
