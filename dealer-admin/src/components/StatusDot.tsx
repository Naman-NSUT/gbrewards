import { Tag } from 'antd';

import { humanise } from '../lib/format';
import { statusColor } from '../lib/statusColors';
import { brand } from '../theme';

export function StatusDot({ status, label }: { status: string; label?: string }) {
  const color = statusColor(status);
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: 999,
          background: color,
          boxShadow: `0 0 0 3px ${color}22`,
          flexShrink: 0,
        }}
      />
      <span style={{ color: brand.text, fontSize: 13.5 }}>{label ?? humanise(status)}</span>
    </span>
  );
}

export function StatusTag({ status, label }: { status: string; label?: string }) {
  const color = statusColor(status);
  return (
    <Tag
      style={{
        color,
        background: `${color}1f`,
        borderColor: `${color}3d`,
        fontSize: 12,
        fontWeight: 550,
        marginInlineEnd: 0,
      }}
    >
      {label ?? humanise(status)}
    </Tag>
  );
}
