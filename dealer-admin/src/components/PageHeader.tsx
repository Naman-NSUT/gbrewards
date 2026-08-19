import type { ReactNode } from 'react';

import { brand } from '../theme';

export function PageHeader({
  title,
  subtitle,
  extra,
}: {
  title: string;
  subtitle?: ReactNode;
  extra?: ReactNode;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 24,
        gap: 16,
        flexWrap: 'wrap',
      }}
    >
      <div>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, letterSpacing: -0.4 }}>{title}</h1>
        {subtitle && (
          <div style={{ margin: '4px 0 0', color: brand.textDim, fontSize: 14 }}>{subtitle}</div>
        )}
      </div>
      {extra}
    </div>
  );
}
