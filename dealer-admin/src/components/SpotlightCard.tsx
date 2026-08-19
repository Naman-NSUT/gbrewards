import type { CSSProperties, ReactNode } from 'react';
import { useRef } from 'react';

/** Hairline card with a soft accent glow that follows the cursor. */
export function SpotlightCard({
  children,
  style,
  className = '',
  onClick,
}: {
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
  onClick?: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty('--mx', `${e.clientX - r.left}px`);
    el.style.setProperty('--my', `${e.clientY - r.top}px`);
  };

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onClick={onClick}
      className={`dr-spotlight ${className}`}
      style={{ cursor: onClick ? 'pointer' : undefined, ...style }}
    >
      <div className="dr-spotlight__glow" aria-hidden />
      <div style={{ position: 'relative', zIndex: 1, height: '100%' }}>{children}</div>
    </div>
  );
}
