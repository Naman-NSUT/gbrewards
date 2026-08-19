import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { RegistrationDayPoint } from '../../api/types';
import { axisTick, gridStroke, SERIES, shortDate } from './chartTheme';
import { GlassTooltip } from './GlassTooltip';

/**
 * Dealer registrations against customer self-registrations, stacked.
 *
 * Stacked rather than side by side because the total is the real number of
 * mattresses sold, and the pink band on top is the share of them the shop
 * failed to record — which is the whole argument for this system existing.
 *
 * The series keys are the server's: `dealer` and `customer_self`.
 */
export function RegistrationsAreaChart({
  data,
  height = 300,
}: {
  data: RegistrationDayPoint[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="dealerFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={SERIES.dealer} stopOpacity={0.42} />
            <stop offset="100%" stopColor={SERIES.dealer} stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="selfFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={SERIES.self} stopOpacity={0.4} />
            <stop offset="100%" stopColor={SERIES.self} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={shortDate}
          tick={axisTick}
          axisLine={false}
          tickLine={false}
          minTickGap={24}
        />
        <YAxis tick={axisTick} axisLine={false} tickLine={false} width={36} allowDecimals={false} />
        <Tooltip content={<GlassTooltip />} cursor={{ stroke: gridStroke }} />
        <Legend
          verticalAlign="top"
          align="right"
          height={28}
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 12 }}
        />
        <Area
          type="monotone"
          stackId="reg"
          dataKey="dealer"
          name="Dealer registered"
          stroke={SERIES.dealer}
          strokeWidth={2}
          fill="url(#dealerFill)"
          animationDuration={800}
        />
        <Area
          type="monotone"
          stackId="reg"
          dataKey="customer_self"
          name="Customer self-registered"
          stroke={SERIES.self}
          strokeWidth={2}
          fill="url(#selfFill)"
          animationDuration={800}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
