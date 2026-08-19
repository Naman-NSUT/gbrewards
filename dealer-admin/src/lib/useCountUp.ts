import { useEffect, useRef, useState } from 'react';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/** Animates from the previous value → `value`. Instant under reduced-motion. */
export function useCountUp(value: number, durationMs = 900): number {
  const reduce = prefersReducedMotion();
  const [display, setDisplay] = useState(0);
  const current = useRef(0);

  useEffect(() => {
    // Under reduced motion the returned value is `value` already, so there is
    // nothing to schedule and no state to push.
    if (reduce) return;

    const from = current.current;
    let raf = 0;
    let start: number | null = null;
    const tick = (ts: number) => {
      if (start === null) start = ts;
      const progress = Math.min(1, (ts - start) / durationMs);
      const next = from + (value - from) * easeOut(progress);
      current.current = next;
      setDisplay(next); // inside the rAF callback, never the effect body
      if (progress < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, durationMs, reduce]);

  return reduce ? value : Math.round(display);
}
