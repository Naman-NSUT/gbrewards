import { useEffect } from 'react';

/** Global keydown hotkey. `combo` like "mod+k" (mod = ⌘ on mac, Ctrl elsewhere). */
export function useHotkey(combo: string, handler: () => void) {
  useEffect(() => {
    const parts = combo.toLowerCase().split('+');
    const key = parts[parts.length - 1];
    const needMod = parts.includes('mod');

    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (e.key.toLowerCase() === key && (!needMod || mod)) {
        e.preventDefault();
        handler();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [combo, handler]);
}
