import {
  ArrowRightOutlined,
  CheckSquareOutlined,
  DollarOutlined,
  FileProtectOutlined,
  SafetyCertificateOutlined,
  ShopOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Col, Row, Segmented, Tooltip } from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { AuditRow, ComplianceRow } from '../api/types';
import { ChartCard } from '../components/ChartCard';
import { RegistrationsAreaChart } from '../components/charts/RegistrationsAreaChart';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';
import { ChartSkeleton, StatSkeleton } from '../components/skeletons';
import { SpotlightCard } from '../components/SpotlightCard';
import { StatCard } from '../components/StatCard';
import { useAudit } from '../hooks/useAudit';
import { useCompliance } from '../hooks/useCompliance';
import { useDashboardAnalytics, useDashboardStats } from '../hooks/useDashboard';
import { formatNumber, humanise, relativeTime } from '../lib/format';
import { brand } from '../theme';

const WINDOWS = [
  { label: '7d', value: 7 },
  { label: '30d', value: 30 },
  { label: '90d', value: 90 },
];

export function DashboardPage() {
  const navigate = useNavigate();
  const [days, setDays] = useState(30);
  const stats = useDashboardStats();
  const analytics = useDashboardAnalytics(days);
  // The dashboard has no compliance or activity payload of its own; both panels
  // read the same endpoints the dedicated screens do, so they can never drift.
  const worst = useCompliance({ sort: 'worst', limit: 8, offset: 0 });
  const activity = useAudit({ limit: 12, offset: 0 });

  const s = stats.data;
  const series = analytics.data?.series ?? [];
  const dealerSpark = series.map((d) => d.dealer);
  const selfShare =
    series.length > 0
      ? series.reduce((a, d) => a + d.customer_self, 0) /
        Math.max(1, series.reduce((a, d) => a + d.customer_self + d.dealer, 0))
      : 0;

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle="Registrations are the product. Points are only what makes them happen."
        extra={
          <Segmented
            options={WINDOWS}
            value={days}
            onChange={(v) => setDays(v as number)}
            size="middle"
          />
        }
      />

      <Row gutter={[16, 16]}>
        {stats.isLoading || !s ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Col key={i} xs={24} sm={12} lg={8} xxl={4}>
              <StatSkeleton />
            </Col>
          ))
        ) : (
          <>
            <Col xs={24} sm={12} lg={8} xxl={4}>
              <StatCard
                label="Registered today"
                value={s.registered_today}
                icon={<SafetyCertificateOutlined />}
                hint={`${formatNumber(s.registered_this_month)} this month`}
                spark={dealerSpark}
                onClick={() => navigate('/warranties')}
              />
            </Col>
            <Col xs={24} sm={12} lg={8} xxl={4}>
              <StatCard
                label="Active dealers"
                value={s.active_dealers}
                icon={<ShopOutlined />}
                hint="Shops able to register a sale today"
                onClick={() => navigate('/dealers')}
              />
            </Col>
            <Col xs={24} sm={12} lg={8} xxl={4}>
              <StatCard
                label="Pending approvals"
                value={s.pending_approvals}
                icon={<CheckSquareOutlined />}
                tone="alert"
                hint="Backdates and self-registrations"
                onClick={() => navigate('/approvals')}
              />
            </Col>
            <Col xs={24} sm={12} lg={8} xxl={4}>
              <StatCard
                label="Open claims"
                value={s.open_claims}
                icon={<FileProtectOutlined />}
                tone="alert"
                onClick={() => navigate('/claims')}
              />
            </Col>
            <Col xs={24} sm={12} lg={8} xxl={4}>
              <StatCard
                label="Self-registered"
                value={s.self_registered_this_month}
                icon={<UserOutlined />}
                tone="alert"
                hint="This month — each one is a shop that didn't"
                onClick={() => navigate('/approvals')}
              />
            </Col>
            <Col xs={24} sm={12} lg={8} xxl={4}>
              <StatCard
                label="Points issued"
                value={s.points_issued}
                icon={<DollarOutlined />}
                hint={`${formatNumber(s.points_reversed)} reversed`}
                onClick={() => navigate('/points')}
              />
            </Col>
          </>
        )}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} xl={16}>
          {analytics.isLoading ? (
            <ChartSkeleton height={320} />
          ) : (
            <ChartCard
              title="Registrations over time"
              subtitle={`Last ${days} days · ${(selfShare * 100).toFixed(0)}% registered by customers themselves`}
            >
              {series.length === 0 ? (
                <EmptyState
                  title="No registrations in this window"
                  hint="Widen the window, or check that dealers are scanning at the point of sale."
                  height={280}
                />
              ) : (
                <RegistrationsAreaChart data={series} height={300} />
              )}
            </ChartCard>
          )}
        </Col>

        <Col xs={24} xl={8}>
          {worst.isLoading ? (
            <ChartSkeleton height={320} />
          ) : (
            <ChartCard
              title="Worst compliance"
              subtitle="Sales their customers registered instead of them"
              extra={
                <a onClick={() => navigate('/compliance')} style={{ fontSize: 12.5 }}>
                  All dealers <ArrowRightOutlined style={{ fontSize: 10 }} />
                </a>
              }
            >
              <WorstCompliance rows={worst.data?.items ?? []} />
            </ChartCard>
          )}
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <ChartCard
            title="Recent activity"
            subtitle="Everything that moved a record"
            extra={
              <a onClick={() => navigate('/audit')} style={{ fontSize: 12.5 }}>
                Full audit <ArrowRightOutlined style={{ fontSize: 10 }} />
              </a>
            }
          >
            <RecentActivity items={activity.data?.items ?? []} />
          </ChartCard>
        </Col>
      </Row>
    </>
  );
}

function WorstCompliance({ rows }: { rows: ComplianceRow[] }) {
  const navigate = useNavigate();
  if (rows.length === 0) {
    return (
      <EmptyState
        title="Nothing to chase"
        hint="Every dealer is registering their stock."
        height={280}
      />
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {rows.slice(0, 8).map((r) => (
        <button
          key={r.dealer_id}
          type="button"
          onClick={() => navigate(`/compliance?dealer=${r.dealer_id}`)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '9px 8px',
            border: 'none',
            borderRadius: 8,
            background: 'transparent',
            cursor: 'pointer',
            textAlign: 'left',
            width: '100%',
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                color: brand.text,
                fontSize: 13.5,
                fontWeight: 550,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {r.dealer_name}
            </div>
            <div style={{ color: brand.textFaint, fontSize: 11.5 }}>
              {r.city ?? '—'}
              {r.days_since_last_registration !== null &&
                ` · silent ${r.days_since_last_registration}d`}
            </div>
          </div>
          <div style={{ textAlign: 'right', minWidth: 116 }}>
            <div className="tnum" style={{ fontSize: 15, fontWeight: 650, color: brand.danger }}>
              {r.self_registrations}
            </div>
            <div style={{ fontSize: 11, color: brand.textFaint }}>self-registered</div>
          </div>
        </button>
      ))}
    </div>
  );
}

/** Audit rows are the activity feed: an action name plus who and when. */
const ACTOR_COLOR: Record<string, string> = {
  admin: brand.accent,
  dealer_staff: brand.success,
  customer: brand.warning,
  system: brand.textDim,
};

function RecentActivity({ items }: { items: AuditRow[] }) {
  if (items.length === 0) {
    return <EmptyState title="Nothing has happened yet" height={160} />;
  }
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {items.slice(0, 12).map((item) => (
        <SpotlightCard key={item.id} style={{ padding: '10px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: 999,
                background: ACTOR_COLOR[item.actor_type] ?? brand.textDim,
                flexShrink: 0,
              }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13.5, color: brand.text }}>{humanise(item.action)}</div>
              <div style={{ fontSize: 12, color: brand.textDim }}>
                {humanise(item.entity_type)}
                {item.reason ? ` · ${item.reason}` : ''}
              </div>
            </div>
            <span style={{ fontSize: 12, color: brand.textDim, whiteSpace: 'nowrap' }}>
              {item.actor_name ?? item.actor_label ?? humanise(item.actor_type)}
            </span>
            <Tooltip title={new Date(item.created_at).toLocaleString()}>
              <span style={{ fontSize: 11.5, color: brand.textFaint, whiteSpace: 'nowrap' }}>
                {relativeTime(item.created_at)}
              </span>
            </Tooltip>
          </div>
        </SpotlightCard>
      ))}
    </div>
  );
}
