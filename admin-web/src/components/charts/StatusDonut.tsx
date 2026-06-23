import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { brand } from '../../theme';
import { GlassTooltip } from './GlassTooltip';

const STATUS_COLOR: Record<string, string> = {
  pending: brand.warning,
  approved: brand.accent,
  fulfilled: brand.success,
  rejected: brand.danger,
  cancelled: brand.textDim,
};

export function StatusDonut({
  data,
  height = 240,
}: {
  data: Record<string, number>;
  height?: number;
}) {
  const slices = Object.entries(data)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));
  const total = slices.reduce((s, x) => s + x.value, 0);

  if (total === 0) {
    return (
      <div style={{ height, display: 'grid', placeItems: 'center', color: brand.textDim }}>
        No redemptions yet
      </div>
    );
  }

  return (
    <div style={{ position: 'relative' }}>
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Tooltip content={<GlassTooltip />} />
          <Pie
            data={slices}
            dataKey="value"
            nameKey="name"
            innerRadius="62%"
            outerRadius="92%"
            paddingAngle={3}
            stroke="none"
            animationDuration={900}
          >
            {slices.map((s) => (
              <Cell key={s.name} fill={STATUS_COLOR[s.name] ?? brand.accent} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'grid',
          placeItems: 'center',
          pointerEvents: 'none',
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 30, fontWeight: 700, lineHeight: 1 }}>{total}</div>
          <div style={{ fontSize: 11, color: brand.textDim, textTransform: 'uppercase', letterSpacing: 0.6 }}>
            requests
          </div>
        </div>
      </div>
    </div>
  );
}
