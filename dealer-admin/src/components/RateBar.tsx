import { rateTone, type RateTone } from '../lib/rate';
import { brand } from '../theme';

const TONE_COLOR: Record<RateTone, string> = {
  critical: brand.danger,
  warn: brand.warning,
  ok: brand.accent,
  good: brand.success,
};

/**
 * The compliance rate, as a bar you can scan down a column.
 *
 * Colour is the point: a shop at 12% and a shop at 91% must be distinguishable
 * without reading either number, because the client scrolls this list looking
 * for who to phone this morning.
 *
 * `rate` is nullable because the server sends null when nothing was allocated.
 * A dealer with no stock has NO rate, which is not the same as 0% — showing
 * them as a red zero would send an account manager to shout at the wrong shop.
 */
export function RateBar({
  rate,
  registered,
  allocated,
  width = 132,
}: {
  rate: number | null | undefined;
  registered?: number;
  allocated?: number;
  width?: number;
}) {
  const showFraction = registered !== undefined && allocated !== undefined;

  if (rate === null || rate === undefined || !Number.isFinite(rate)) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, width }}>
        <div
          style={{
            flex: 1,
            height: 6,
            borderRadius: 999,
            background: 'rgba(255,255,255,0.07)',
          }}
        />
        <div style={{ minWidth: 74, textAlign: 'right' }}>
          <span style={{ color: brand.textFaint, fontSize: 12.5 }}>no stock</span>
        </div>
      </div>
    );
  }

  const safe = Math.max(0, Math.min(1, rate));
  const color = TONE_COLOR[rateTone(safe)];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, width }}>
      <div
        style={{
          flex: 1,
          height: 6,
          borderRadius: 999,
          background: 'rgba(255,255,255,0.07)',
          overflow: 'hidden',
        }}
      >
        {/*
          Full width, slid left inside the clipping track, rather than a bar
          whose `width` is the rate. Compliance renders one of these per dealer
          row, so a sort or filter change would otherwise transition hundreds of
          widths at once and force a layout pass per row per frame. `transform`
          is composited and costs none of that.

          Translating rather than scaleX on purpose: this bar is 6px tall with a
          999px radius, and scaling the X axis would squash the 3px end cap into
          a flat sliver at low rates — exactly the rows the client looks at most.
          Sliding keeps the cap circular at every value.
        */}
        <div
          className="dr-ratebar__fill"
          style={{
            width: '100%',
            height: '100%',
            background: color,
            borderRadius: 999,
            transform: `translateX(${(safe - 1) * 100}%)`,
            transition: 'transform 0.4s cubic-bezier(0.16,1,0.3,1)',
          }}
        />
      </div>
      <div style={{ minWidth: 74, textAlign: 'right' }}>
        <span className="tnum" style={{ color, fontWeight: 600, fontSize: 13 }}>
          {(safe * 100).toFixed(0)}%
        </span>
        {showFraction && (
          <span className="tnum" style={{ color: brand.textFaint, fontSize: 11.5, marginLeft: 6 }}>
            {registered}/{allocated}
          </span>
        )}
      </div>
    </div>
  );
}
