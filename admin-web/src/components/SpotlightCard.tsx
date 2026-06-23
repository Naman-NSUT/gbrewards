import type { CSSProperties, ReactNode } from 'react';
import { useRef } from 'react';

/** Aceternity-style card: a soft accent glow follows the cursor, hairline border. */
export function SpotlightCard({
  children,
  style,
  className = '',
}: {
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
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
    <div ref={ref} onMouseMove={onMove} className={`sr-spotlight ${className}`} style={style}>
      <div className="sr-spotlight__glow" aria-hidden />
      <div style={{ position: 'relative', zIndex: 1, height: '100%' }}>{children}</div>
    </div>
  );
}
