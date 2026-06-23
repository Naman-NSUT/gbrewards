import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import type { TopProduct } from '../../api/types';
import { brand } from '../../theme';
import { axisTick } from './chartTheme';
import { GlassTooltip } from './GlassTooltip';

// Monochrome + violet: accent fading to grays (no rainbow).
const PALETTE = ['#6e56cf', '#8b78dd', '#6b6b76', '#52525b', '#3f3f46'];

export function TopProductsBar({ data, height = 260 }: { data: TopProduct[]; height?: number }) {
  if (data.length === 0) {
    return (
      <div style={{ height, display: 'grid', placeItems: 'center', color: brand.textDim }}>
        No claimed units yet
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
        <XAxis type="number" tick={axisTick} axisLine={false} tickLine={false} allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="name"
          tick={axisTick}
          axisLine={false}
          tickLine={false}
          width={110}
        />
        <Tooltip content={<GlassTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
        <Bar dataKey="claimed" name="claimed" radius={[0, 6, 6, 0]} animationDuration={900}>
          {data.map((_d, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
