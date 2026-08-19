import { brand } from '../../theme';
import { shortDate } from './chartTheme';

interface TooltipEntry {
  dataKey?: string | number;
  name?: string | number;
  value?: number | string;
  color?: string;
}

export interface GlassTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
}

export function GlassTooltip({ active, payload, label }: GlassTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      style={{
        background: 'rgba(20,20,22,0.94)',
        border: `1px solid ${brand.borderStrong}`,
        borderRadius: 10,
        padding: '9px 12px',
        backdropFilter: 'blur(8px)',
        boxShadow: '0 10px 30px -10px rgba(0,0,0,0.7)',
      }}
    >
      {label !== undefined && (
        <div style={{ color: brand.textDim, fontSize: 11, marginBottom: 5 }}>
          {typeof label === 'string' ? shortDate(label) : label}
        </div>
      )}
      {payload.map((p) => (
        <div
          key={String(p.dataKey)}
          style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 2,
              background: p.color ?? brand.accent,
              flexShrink: 0,
            }}
          />
          <span className="tnum" style={{ color: brand.text, fontWeight: 600 }}>
            {p.value}
          </span>
          <span style={{ color: brand.textDim }}>{p.name}</span>
        </div>
      ))}
    </div>
  );
}
