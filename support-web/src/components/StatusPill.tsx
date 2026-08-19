import type { Tone } from '../lib/format';

interface StatusPillProps {
  label: string;
  tone: Tone;
}

export function StatusPill({ label, tone }: StatusPillProps) {
  return (
    <span className={`pill pill--${tone}`}>
      {/* Colour is never the only signal — the word is always there too. */}
      <span className="pill__dot" aria-hidden="true" />
      {label}
    </span>
  );
}
