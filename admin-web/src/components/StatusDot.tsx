import { brand } from '../theme';

const COLORS: Record<string, string> = {
  // unit
  active: brand.success,
  claimed: brand.accent,
  void: brand.textFaint,
  // redemption
  pending: brand.warning,
  approved: brand.accent,
  fulfilled: brand.success,
  rejected: brand.danger,
  cancelled: brand.textFaint,
  // generic
  inactive: brand.textFaint,
};

export function StatusDot({ status }: { status: string }) {
  const color = COLORS[status] ?? brand.textDim;
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
      <span style={{ textTransform: 'capitalize', color: brand.text, fontSize: 13.5 }}>
        {status}
      </span>
    </span>
  );
}
