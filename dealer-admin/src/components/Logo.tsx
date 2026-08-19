import { brand } from '../theme';

/** The mark is a mattress with a tick — the sale record, not the points. */
export function Logo({ size = 30, showWord = true }: { size?: number; showWord?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
      <div
        style={{
          width: size,
          height: size,
          borderRadius: size * 0.28,
          background: brand.navyDeep,
          border: `1px solid ${brand.borderStrong}`,
          display: 'grid',
          placeItems: 'center',
          flexShrink: 0,
        }}
      >
        <svg width={size * 0.6} height={size * 0.6} viewBox="0 0 24 24" fill="none">
          <rect
            x="2.5"
            y="7"
            width="19"
            height="10"
            rx="2.6"
            stroke={brand.accent}
            strokeWidth="1.9"
          />
          <path
            d="M7.5 12.2l3 3 6.2-6.2"
            stroke={brand.accent}
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      {showWord && (
        <span
          style={{ fontWeight: 700, fontSize: 15.5, letterSpacing: -0.2, color: brand.text }}
        >
          Dealer Rewards
        </span>
      )}
    </div>
  );
}
