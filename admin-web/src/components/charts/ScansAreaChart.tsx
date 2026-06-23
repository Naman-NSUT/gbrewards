import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { ScanDayPoint } from '../../api/types';
import { brand } from '../../theme';
import { axisTick, gridStroke, shortDate } from './chartTheme';
import { GlassTooltip } from './GlassTooltip';

export function ScansAreaChart({
  data,
  height = 300,
  highlight = 'scans',
}: {
  data: ScanDayPoint[];
  height?: number;
  highlight?: 'scans' | 'points';
}) {
  const scansActive = highlight === 'scans';
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="scanFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={brand.accent} stopOpacity={0.42} />
            <stop offset="100%" stopColor={brand.accent} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="pointFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={brand.textDim} stopOpacity={0.18} />
            <stop offset="100%" stopColor={brand.textDim} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={axisTick} axisLine={false} tickLine={false} minTickGap={24} />
        <YAxis tick={axisTick} axisLine={false} tickLine={false} width={36} allowDecimals={false} />
        <Tooltip content={<GlassTooltip />} cursor={{ stroke: brand.border }} />
        <Area
          type="monotone"
          dataKey="points"
          name="points"
          stroke={brand.textDim}
          strokeWidth={scansActive ? 1.5 : 2.75}
          strokeOpacity={scansActive ? 0.45 : 1}
          fill="url(#pointFill)"
          fillOpacity={scansActive ? 0.4 : 1}
          animationDuration={900}
        />
        <Area
          type="monotone"
          dataKey="scans"
          name="scans"
          stroke={brand.accent}
          strokeWidth={scansActive ? 2.75 : 1.5}
          strokeOpacity={scansActive ? 1 : 0.45}
          fill="url(#scanFill)"
          fillOpacity={scansActive ? 1 : 0.4}
          animationDuration={900}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
