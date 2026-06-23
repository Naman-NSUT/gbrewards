import type { ReactNode } from 'react';

import { brand } from '../theme';
import { SpotlightCard } from './SpotlightCard';

export function ChartCard({
  title,
  subtitle,
  extra,
  children,
}: {
  title: string;
  subtitle?: string;
  extra?: ReactNode;
  children: ReactNode;
}) {
  return (
    <SpotlightCard style={{ padding: 20, height: '100%' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          marginBottom: 16,
          gap: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: -0.2 }}>{title}</div>
          {subtitle && (
            <div style={{ fontSize: 12.5, color: brand.textDim, marginTop: 2 }}>{subtitle}</div>
          )}
        </div>
        {extra}
      </div>
      {children}
    </SpotlightCard>
  );
}
