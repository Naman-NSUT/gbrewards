import { ArrowRightOutlined } from '@ant-design/icons';
import { Col, Divider, Drawer, Empty, Row } from 'antd';
import { useNavigate } from 'react-router-dom';

import type { ComplianceDetail } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { Mono } from '../components/Mono';
import { DetailSkeleton } from '../components/skeletons';
import { StatusTag } from '../components/StatusDot';
import { useComplianceDetail } from '../hooks/useCompliance';
import { formatDate, formatDateTime, formatNumber, relativeTime } from '../lib/format';
import { brand } from '../theme';

/**
 * The answer to "why is this shop at 14%?".
 *
 * The list of unregistered units is the point of this drawer: it turns an
 * accusation into a phone call with a list of serials the shop is sitting on.
 */
export function ComplianceDrawer({
  dealerId,
  dateFrom,
  dateTo,
  onClose,
}: {
  dealerId: string | null;
  dateFrom: string;
  dateTo: string;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const detail = useComplianceDetail(dealerId, { date_from: dateFrom, date_to: dateTo });
  const d = detail.data;

  return (
    <Drawer
      open={dealerId !== null}
      onClose={onClose}
      width={720}
      destroyOnHidden
      title={
        d ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 650 }}>{d.dealer.name}</span>
            <span className="mono" style={{ fontSize: 12, color: brand.textFaint }}>
              {d.dealer.code}
            </span>
            <StatusTag status={d.dealer.status} />
          </div>
        ) : (
          'Dealer'
        )
      }
      extra={
        d ? (
          <a onClick={() => navigate(`/warranties?dealer=${d.dealer.id}`)} style={{ fontSize: 13 }}>
            Warranties <ArrowRightOutlined style={{ fontSize: 10 }} />
          </a>
        ) : null
      }
    >
      {detail.isLoading || !d ? <DetailSkeleton rows={8} /> : <Body detail={d} />}
    </Drawer>
  );
}

function Body({ detail: d }: { detail: ComplianceDetail }) {
  const s = d.summary;

  return (
    <>
      <Row gutter={[12, 12]}>
        <Col span={24}>
          <div
            style={{
              border: `1px solid ${brand.border}`,
              borderRadius: 12,
              padding: 16,
              background: brand.surface,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ fontSize: 13, color: brand.textDim }}>Registration rate</span>
              <span style={{ fontSize: 12, color: brand.textFaint }}>
                {d.date_from ? formatDate(d.date_from) : 'all time'}
                {d.date_to ? ` – ${formatDate(d.date_to)}` : ''}
              </span>
            </div>

          </div>
        </Col>
        <Col xs={12} sm={6}>
          <Metric
            label="Registered"
            value={formatNumber(s.warranties_registered)}
            tone={brand.success}
          />
        </Col>
        <Col xs={12} sm={6}>
          <Metric
            label="Days quiet"
            value={
              s.days_since_last_registration === null
                ? 'never registered'
                : formatNumber(s.days_since_last_registration)
            }
            tone={(s.days_since_last_registration ?? 999) >= 30 ? brand.danger : brand.textDim}
          />
        </Col>
        <Col xs={12} sm={6}>
          <Metric
            label="Self-registered"
            value={formatNumber(s.self_registrations)}
            tone={s.self_registrations > 0 ? brand.danger : brand.textDim}
          />
        </Col>
      </Row>

      <div style={{ marginTop: 12, fontSize: 12.5, color: brand.textDim }}>
        {s.warranties_registered === 0
          ? 'No registrations in this window.'
          : `${formatNumber(s.warranties_registered)} registered in this window.`}
        {s.backdated_registrations > 0 && (
          <>
            {' · '}
            <span style={{ color: brand.warning }}>
              {formatNumber(s.backdated_registrations)} backdated
            </span>
          </>
        )}
      </div>

      <Divider style={{ margin: '20px 0 14px' }} />
      <SectionTitle>Staff</SectionTitle>
      {d.staff_activity.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="No logins provisioned — this shop physically cannot register anything"
        />
      ) : (
        <div style={{ display: 'grid', gap: 6 }}>
          {d.staff_activity.map((a) => (
            <div
              key={a.staff.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                border: `1px solid ${brand.border}`,
                borderRadius: 8,
              }}
            >
              <div>
                <span style={{ fontSize: 13.5, color: brand.text }}>{a.staff.name}</span>
                <span
                  className="mono"
                  style={{ fontSize: 11.5, color: brand.textFaint, marginLeft: 8 }}
                >
                  {a.staff.phone}
                </span>
                {!a.is_active && (
                  <span style={{ marginLeft: 8 }}>
                    <StatusTag status="inactive" />
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <span className="tnum" style={{ fontSize: 12.5, color: brand.textDim }}>
                  {a.registrations} registered
                </span>
                <span style={{ fontSize: 11.5, color: brand.textFaint }}>
                  {a.last_active_at ? relativeTime(a.last_active_at) : 'never signed in'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      <Divider style={{ margin: '20px 0 14px' }} />
      <SectionTitle>Sales the customer registered instead</SectionTitle>
      {d.self_registrations.length === 0 ? (
        <EmptyState title="None in this window" height={110} />
      ) : (
        <div style={{ display: 'grid', gap: 6 }}>
          {d.self_registrations.map((r) => (
            <div
              key={r.warranty_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 10,
                padding: '8px 12px',
                border: `1px solid ${brand.border}`,
                borderRadius: 8,
              }}
            >
              <Mono value={r.serial} chars={14} />
              <span style={{ fontSize: 12.5, color: brand.textDim, flex: 1, marginLeft: 12 }}>
                {r.customer.name}
              </span>
              <StatusTag status={r.status} />
              <span style={{ fontSize: 11.5, color: brand.textFaint, whiteSpace: 'nowrap' }}>
                {formatDateTime(r.registered_at)}
              </span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 12,
        textTransform: 'uppercase',
        letterSpacing: 0.7,
        color: brand.textDim,
        fontWeight: 550,
        marginBottom: 10,
      }}
    >
      {children}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div style={{ border: `1px solid ${brand.border}`, borderRadius: 10, padding: '12px 14px' }}>
      <div
        style={{
          fontSize: 11,
          color: brand.textFaint,
          textTransform: 'uppercase',
          letterSpacing: 0.6,
        }}
      >
        {label}
      </div>
      <div
        className="tnum"
        style={{ fontSize: 21, fontWeight: 650, marginTop: 4, color: tone ?? brand.text }}
      >
        {value}
      </div>
    </div>
  );
}
