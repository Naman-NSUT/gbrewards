import { brand } from '../theme';

function Bar({ w = '100%', h = 14, r = 6 }: { w?: number | string; h?: number; r?: number }) {
  return <div className="sr-skeleton" style={{ width: w, height: h, borderRadius: r }} />;
}

export function StatSkeleton() {
  return (
    <div style={{ border: `1px solid ${brand.border}`, borderRadius: 12, padding: 20, minHeight: 132 }}>
      <Bar w={90} h={11} />
      <div style={{ height: 16 }} />
      <Bar w={70} h={28} />
      <div style={{ height: 14 }} />
      <Bar w="100%" h={26} />
    </div>
  );
}

export function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <div style={{ border: `1px solid ${brand.border}`, borderRadius: 12, padding: 20 }}>
      <Bar w={140} h={13} />
      <div style={{ height: 18 }} />
      <Bar w="100%" h={height - 60} r={10} />
    </div>
  );
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            gap: 16,
            alignItems: 'center',
            padding: '12px 4px',
            borderBottom: `1px solid ${brand.border}`,
          }}
        >
          <Bar w="24%" />
          <Bar w="18%" />
          <Bar w="16%" />
          <Bar w="22%" />
          <div style={{ flex: 1 }} />
          <Bar w={60} />
        </div>
      ))}
    </div>
  );
}
