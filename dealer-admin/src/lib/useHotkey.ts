import { useEffect, useRef } from 'react';

/** Global keydown hotkey. `combo` like "mod+k" (mod = ⌘ on mac, Ctrl elsewhere). */
export function useHotkey(combo: string, handler: () => void): void {
  // The handler lives in a ref so an inline arrow doesn't re-bind the window
  // listener on every render of the component that uses it.
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  }, [handler]);

  useEffect(() => {
    const parts = combo.toLowerCase().split('+');
    const key = parts[parts.length - 1];
    const needMod = parts.includes('mod');

    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (e.key.toLowerCase() === key && (!needMod || mod)) {
        e.preventDefault();
        ref.current();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [combo]);
}
