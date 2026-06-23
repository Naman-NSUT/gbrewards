import {
  AppstoreOutlined,
  GiftOutlined,
  QrcodeOutlined,
  RiseOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  WalletOutlined,
} from '@ant-design/icons';
import { Col, Row, Segmented } from 'antd';
import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { useState } from 'react';

import { ChartCard } from '../components/ChartCard';
import { PageHeader } from '../components/PageHeader';
import { StatCard } from '../components/StatCard';
import { ChartSkeleton, StatSkeleton } from '../components/skeletons';
import { ScansAreaChart } from '../components/charts/ScansAreaChart';
import { StatusDonut } from '../components/charts/StatusDonut';
import { TopProductsBar } from '../components/charts/TopProductsBar';
import { useAnalytics, useDashboard } from '../hooks/useReporting';

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05, delayChildren: 0.03 } },
};
const item = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as const } },
};

function Cell({
  span,
  children,
}: {
  span: { xs: number; sm?: number; md?: number; xl?: number };
  children: ReactNode;
}) {
  return (
    <Col {...span}>
      <motion.div variants={item} style={{ height: '100%' }}>
        {children}
      </motion.div>
    </Col>
  );
}

export function DashboardPage() {
  const dash = useDashboard();
  const analytics = useAnalytics();
  const [series, setSeries] = useState<'scans' | 'points'>('scans');

  const loading = dash.isLoading || !dash.data || analytics.isLoading || !analytics.data;

  if (loading) {
    return (
      <>
        <PageHeader title="Dashboard" subtitle="Live overview of the rewards program." />
        <Row gutter={[16, 16]}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Col xs={24} sm={12} xl={6} key={i}>
              <StatSkeleton />
            </Col>
          ))}
        </Row>
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={24} xl={16}>
            <ChartSkeleton />
          </Col>
          <Col xs={24} xl={8}>
            <ChartSkeleton height={240} />
          </Col>
        </Row>
      </>
    );
  }

  const d = dash.data!;
  const a = analytics.data!;
  const sparkScans = a.scans_by_day.map((x) => x.scans);
  const sparkPoints = a.scans_by_day.map((x) => x.points);

  const heroes = [
    { label: 'Total users', value: d.total_users, icon: <TeamOutlined /> },
    { label: 'Points outstanding', value: d.total_points_outstanding, icon: <WalletOutlined />, spark: sparkPoints },
    { label: 'Total scans', value: d.total_scans, icon: <QrcodeOutlined />, spark: sparkScans },
    { label: 'Pending redemptions', value: d.pending_redemptions, icon: <GiftOutlined /> },
  ];
  const secondary = [
    { label: 'Scans today', value: d.scans_today, icon: <ThunderboltOutlined /> },
    { label: 'Scans this week', value: d.scans_this_week, icon: <RiseOutlined /> },
    { label: 'Products in catalog', value: d.products_in_catalog, icon: <AppstoreOutlined /> },
  ];

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Live overview of the rewards program." />

      <motion.div variants={container} initial="hidden" animate="show">
        <Row gutter={[16, 16]}>
          {heroes.map((h) => (
            <Cell span={{ xs: 24, sm: 12, xl: 6 }} key={h.label}>
              <StatCard {...h} />
            </Cell>
          ))}
        </Row>

        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Cell span={{ xs: 24, xl: 16 }}>
            <ChartCard
              title="Scan activity"
              subtitle="Last 14 days"
              extra={
                <Segmented
                  size="small"
                  value={series}
                  onChange={(v) => setSeries(v as 'scans' | 'points')}
                  options={[
                    { label: 'Scans', value: 'scans' },
                    { label: 'Points', value: 'points' },
                  ]}
                />
              }
            >
              <ScansAreaChart data={a.scans_by_day} highlight={series} />
            </ChartCard>
          </Cell>
          <Cell span={{ xs: 24, xl: 8 }}>
            <ChartCard title="Redemptions" subtitle="By status">
              <StatusDonut data={a.redemptions_by_status} />
            </ChartCard>
          </Cell>
        </Row>

        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Cell span={{ xs: 24, xl: 12 }}>
            <ChartCard title="Top products" subtitle="By claimed units">
              <TopProductsBar data={a.top_products} />
            </ChartCard>
          </Cell>
          {secondary.map((s) => (
            <Cell span={{ xs: 24, sm: 8, xl: 4 }} key={s.label}>
              <StatCard {...s} />
            </Cell>
          ))}
        </Row>
      </motion.div>
    </>
  );
}
