import { brand } from '../theme';

export function Logo({ size = 30, showWord = true }: { size?: number; showWord?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
      <div
        style={{
          width: size,
          height: size,
          borderRadius: size * 0.28,
          background: brand.elevated,
          border: `1px solid ${brand.borderStrong}`,
          display: 'grid',
          placeItems: 'center',
          flexShrink: 0,
        }}
      >
        <svg width={size * 0.56} height={size * 0.56} viewBox="0 0 24 24" fill="none">
          <path
            d="M4 4h6v6H4V4zm10 0h6v6h-6V4zM4 14h6v6H4v-6zm12 1.5h3.5M14 14h.01M20 14v.01M14 20h6"
            stroke={brand.accent}
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      {showWord && (
        <span style={{ fontWeight: 700, fontSize: 15.5, letterSpacing: -0.2, color: brand.text }}>
          GB Rewards
        </span>
      )}
    </div>
  );
}
