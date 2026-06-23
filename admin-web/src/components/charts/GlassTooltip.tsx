import { brand } from '../../theme';
import { shortDate } from './chartTheme';

interface TooltipEntry {
  dataKey?: string | number;
  name?: string | number;
  value?: number | string;
  color?: string;
}

interface GlassTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
}

// Glassy dark tooltip shared across charts.
export function GlassTooltip({ active, payload, label }: GlassTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      style={{
        background: 'rgba(17,24,39,0.92)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 10,
        padding: '8px 12px',
        backdropFilter: 'blur(8px)',
        boxShadow: '0 10px 30px -10px rgba(0,0,0,0.7)',
      }}
    >
      {label !== undefined && (
        <div style={{ color: brand.textDim, fontSize: 11, marginBottom: 4 }}>
          {typeof label === 'string' ? shortDate(label) : label}
        </div>
      )}
      {payload.map((p: TooltipEntry) => (
        <div
          key={String(p.dataKey)}
          style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 2,
              background: (p.color as string) ?? brand.accent,
            }}
          />
          <span style={{ color: brand.text, fontWeight: 600 }}>{p.value}</span>
          <span style={{ color: brand.textDim, textTransform: 'capitalize' }}>{p.name}</span>
        </div>
      ))}
    </div>
  );
}
