import { InboxOutlined } from '@ant-design/icons';
import type { ReactNode } from 'react';

import { brand } from '../theme';

export function EmptyState({
  title = 'Nothing here yet',
  hint,
  icon,
  action,
  height = 200,
}: {
  title?: string;
  hint?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  height?: number | string;
}) {
  return (
    <div
      style={{
        height,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        color: brand.textDim,
        textAlign: 'center',
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 12,
          display: 'grid',
          placeItems: 'center',
          background: 'rgba(255,255,255,0.03)',
          border: `1px solid ${brand.border}`,
          color: brand.textFaint,
          fontSize: 20,
        }}
      >
        {icon ?? <InboxOutlined />}
      </div>
      <div style={{ color: brand.text, fontWeight: 550, fontSize: 14 }}>{title}</div>
      {hint && <div style={{ fontSize: 13, maxWidth: 320 }}>{hint}</div>}
      {action && <div style={{ marginTop: 8 }}>{action}</div>}
    </div>
  );
}
