import { DownloadOutlined, WarningOutlined } from '@ant-design/icons';
import { App, Col, DatePicker, Input, Row, Segmented, Select, Tooltip } from 'antd';
import type { TableColumnsType } from 'antd';
import dayjs from 'dayjs';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import type { ComplianceQuery, ComplianceSort } from '../api/compliance';
import type { ComplianceRow, DealerStatus } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { SpotlightCard } from '../components/SpotlightCard';
import { StatusTag } from '../components/StatusDot';
import { useCompliance } from '../hooks/useCompliance';
import { isoDate, lastDays, type DateRange } from '../lib/dates';
import { downloadBlob, formatNumber, toCsv } from '../lib/format';
import { brand } from '../theme';
import { ComplianceDrawer } from './ComplianceDrawer';

/** The keys services/compliance._SORTS accepts — anything else is a 400. */
const SORTS: { label: string; value: ComplianceSort }[] = [
  { label: 'Worst overall', value: 'worst' },
  { label: 'Longest silent', value: 'quietest' },
  { label: 'Most self-registered', value: 'self_registrations' },
];

const PAGE_SIZE = 50;

export function CompliancePage() {
  const { message } = App.useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [range, setRange] = useState<DateRange>(() => lastDays(30));
  const [q, setQ] = useState('');
  const [sort, setSort] = useState<ComplianceSort>('worst');
  const [status, setStatus] = useState<DealerStatus | undefined>(undefined);
  const [page, setPage] = useState(1);

  const openDealer = searchParams.get('dealer');
  const setOpenDealer = (id: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (id) next.set('dealer', id);
    else next.delete('dealer');
    // Replace, not push: the drawer is a peek at a row, not a place in history
    // the client wants to walk back through one dealer at a time.
    setSearchParams(next, { replace: true });
  };

  const params = useMemo<ComplianceQuery>(
    () => ({
      date_from: isoDate(range[0]),
      date_to: isoDate(range[1]),
      q: q || undefined,
      status,
      sort,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [range, q, status, sort, page],
  );

  const compliance = useCompliance(params);
  const rows = compliance.data?.items ?? [];
  // A shop that has stopped registering is the clearest signal left now that
  // stock is not scoped and there is no allocated-versus-registered ratio.
  const quietCount = rows.filter((r) => (r.days_since_last_registration ?? 999) >= 30).length;
  const totals = compliance.data?.totals;

  const exportCsv = () => {
    if (rows.length === 0) {
      message.info('Nothing to export');
      return;
    }
    const csv = toCsv(
      rows.map((r) => ({
        code: r.dealer_code,
        dealer: r.dealer_name,
        city: r.city ?? '',
        status: r.dealer_status,
        warranties_registered: r.warranties_registered,
        self_registrations: r.self_registrations,
        backdated_registrations: r.backdated_registrations,
        days_since_last: r.days_since_last_registration ?? '',
      })),
      [
        'code',
        'dealer',
        'city',
        'status',
        'warranties_registered',
        'self_registrations',
        'backdated_registrations',
        'days_since_last',
      ],
    );
    downloadBlob(
      new Blob([csv], { type: 'text/csv;charset=utf-8' }),
      `compliance-${isoDate(range[0])}-to-${isoDate(range[1])}.csv`,
    );
  };

  const columns: TableColumnsType<ComplianceRow> = [
    {
      title: 'Dealer',
      dataIndex: 'dealer_name',
      width: 260,
      render: (name: string, r) => (
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 550, color: brand.text }}>{name}</div>
          <div style={{ fontSize: 11.5, color: brand.textFaint }}>
            <span className="mono">{r.dealer_code}</span>
            {r.dealer_status !== 'active' && (
              <span style={{ marginLeft: 8 }}>
                <StatusTag status={r.dealer_status} />
              </span>
            )}
          </div>
        </div>
      ),
    },
    {
      title: 'City',
      dataIndex: 'city',
      width: 130,
      render: (city: string | null) => (
        <span style={{ color: brand.textDim }}>{city ?? '—'}</span>
      ),
    },
    {
      title: 'Registered',
      dataIndex: 'warranties_registered',
      align: 'right',
      width: 105,
      render: (v: number) => <span className="tnum">{formatNumber(v)}</span>,
    },
    {
      title: (
        <Tooltip title="Warranties on this dealer's stock that the customer registered instead. Every one is a sale this shop failed to record.">
          <span style={{ borderBottom: `1px dotted ${brand.textFaint}` }}>Self-reg</span>
        </Tooltip>
      ),
      dataIndex: 'self_registrations',
      align: 'right',
      width: 100,
      render: (v: number) => (
        <span className="tnum" style={{ color: v > 0 ? brand.danger : brand.textFaint }}>
          {v}
        </span>
      ),
    },
    {
      title: 'Last registration',
      dataIndex: 'days_since_last_registration',
      align: 'right',
      width: 140,
      render: (days: number | null) => {
        if (days === null) {
          return <span style={{ color: brand.danger, fontSize: 12.5 }}>never</span>;
        }
        const colour = days > 30 ? brand.danger : days > 14 ? brand.warning : brand.textDim;
        return (
          <span className="tnum" style={{ color: colour, fontSize: 12.5 }}>
            {days === 0 ? 'today' : `${days}d ago`}
          </span>
        );
      },
    },
  ];

  return (
    <>
      <PageHeader
        title="Dealer Compliance"
        subtitle="Whose customers are registering their own warranties — worst first."
        extra={
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Input.Search
              allowClear
              placeholder="Dealer name, code or city"
              style={{ width: 240 }}
              onSearch={(v) => {
                setPage(1);
                setQ(v);
              }}
            />
            <Select
              allowClear
              placeholder="All statuses"
              style={{ width: 150 }}
              value={status}
              onChange={(v) => {
                setPage(1);
                setStatus(v);
              }}
              options={[
                { label: 'Pending', value: 'pending' },
                { label: 'Active', value: 'active' },
                { label: 'Suspended', value: 'suspended' },
                { label: 'Closed', value: 'closed' },
              ]}
            />
            <DatePicker.RangePicker
              value={range}
              allowClear={false}
              onChange={(v) => {
                if (v && v[0] && v[1]) {
                  setPage(1);
                  setRange([v[0], v[1]]);
                }
              }}
              presets={[
                { label: 'Last 7 days', value: lastDays(7) },
                { label: 'Last 30 days', value: lastDays(30) },
                { label: 'Last 90 days', value: lastDays(90) },
                { label: 'This year', value: [dayjs().startOf('year'), dayjs()] },
              ]}
            />
            <Tooltip title="Export this view as CSV">
              <a
                onClick={exportCsv}
                style={{
                  display: 'grid',
                  placeItems: 'center',
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  border: `1px solid ${brand.border}`,
                  background: brand.elevated,
                  color: brand.textDim,
                }}
              >
                <DownloadOutlined />
              </a>
            </Tooltip>
          </div>
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} lg={6}>
          <Headline
            label="Registered"
            value={formatNumber(totals?.warranties_registered ?? 0)}
            hint="Sales the shops recorded in this window"
            tone="ok"
          />
        </Col>
        <Col xs={12} lg={6}>
          <Headline
            label="Shops gone quiet"
            value={formatNumber(quietCount)}
            hint="No registration in 30 days or more"
            tone={quietCount > 0 ? 'critical' : 'good'}
          />
        </Col>
        <Col xs={12} lg={6}>
          <Headline
            label="Dealers in view"
            value={formatNumber(totals?.dealers ?? 0)}
            hint="Every dealer on the programme"
            tone="ok"
          />
        </Col>
        <Col xs={12} lg={6}>
          <Headline
            label="Self-registered"
            value={formatNumber(totals?.self_registrations ?? 0)}
            hint="Customers who had to do it themselves"
            tone={(totals?.self_registrations ?? 0) > 0 ? 'warn' : 'good'}
          />
        </Col>
      </Row>

      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          gap: 12,
          marginBottom: 12,
          flexWrap: 'wrap',
        }}
      >
        <Segmented
          options={SORTS}
          value={sort}
          onChange={(v) => {
            setPage(1);
            setSort(v as ComplianceSort);
          }}
          size="small"
        />
      </div>

      <DataTable<ComplianceRow>
        rowKey="dealer_id"
        loading={compliance.isLoading}
        dataSource={rows}
        columns={columns}
        total={compliance.data?.total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyText="No dealers in this window"
        emptyHint="Every dealer on the programme appears here."
        emptyIcon={<WarningOutlined />}
        rowClassName={(r) => {
          const base = 'dr-row-clickable';
          // Tint on the two things that still mean something: a customer having
          // to register their own warranty, and a shop that has gone silent.
          if (r.self_registrations > 0) return `${base} dr-row-critical`;
          if ((r.days_since_last_registration ?? 0) >= 30) return `${base} dr-row-warn`;
          return base;
        }}
        onRow={(r) => ({ onClick: () => setOpenDealer(r.dealer_id) })}
      />

      <ComplianceDrawer
        dealerId={openDealer}
        dateFrom={isoDate(range[0])}
        dateTo={isoDate(range[1])}
        onClose={() => setOpenDealer(null)}
      />
    </>
  );
}

const TONE_COLOR = {
  critical: brand.danger,
  warn: brand.warning,
  ok: brand.accent,
  good: brand.success,
};

function Headline({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone: keyof typeof TONE_COLOR;
}) {
  return (
    <SpotlightCard style={{ padding: '16px 18px' }}>
      <div
        style={{
          color: brand.textDim,
          fontSize: 11.5,
          textTransform: 'uppercase',
          letterSpacing: 0.7,
          fontWeight: 500,
        }}
      >
        {label}
      </div>
      <div
        className="tnum"
        style={{
          fontSize: 26,
          fontWeight: 650,
          letterSpacing: -0.6,
          marginTop: 8,
          color: TONE_COLOR[tone],
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: 12, color: brand.textFaint, marginTop: 2 }}>{hint}</div>
    </SpotlightCard>
  );
}
