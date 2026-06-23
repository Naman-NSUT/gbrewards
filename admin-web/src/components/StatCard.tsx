import type { ReactNode } from 'react';
import { Area, AreaChart, ResponsiveContainer } from 'recharts';

import { useCountUp } from '../lib/useCountUp';
import { brand } from '../theme';
import { SpotlightCard } from './SpotlightCard';

export function StatCard({
  label,
  value,
  icon,
  spark,
}: {
  label: string;
  value: number | string;
  icon: ReactNode;
  accent?: string;
  spark?: number[];
}) {
  const numeric = typeof value === 'number';
  const animated = useCountUp(numeric ? value : 0);
  const display = numeric ? animated.toLocaleString() : value;
  const sparkData = (spark ?? []).map((v, i) => ({ i, v }));
  const gradId = `spark-${label.replace(/\s+/g, '')}`;

  return (
    <SpotlightCard style={{ padding: '18px 20px', minHeight: 128 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span
          style={{
            color: brand.textDim,
            fontSize: 12,
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: 0.7,
          }}
        >
          {label}
        </span>
        <span style={{ color: brand.textFaint, fontSize: 15 }}>{icon}</span>
      </div>

      <div
        className="tnum"
        style={{ marginTop: 12, fontSize: 30, fontWeight: 650, letterSpacing: -0.8, color: brand.text }}
      >
        {display}
      </div>

      {sparkData.length > 1 && (
        <div style={{ height: 32, marginTop: 10, marginInline: -2 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparkData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={brand.accent} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={brand.accent} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="v"
                stroke={brand.accent}
                strokeWidth={1.75}
                fill={`url(#${gradId})`}
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </SpotlightCard>
  );
}
