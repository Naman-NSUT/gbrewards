import { SafetyCertificateOutlined } from '@ant-design/icons';
import { Checkbox, DatePicker, Input, Select, Tag, Tooltip } from 'antd';
import type { TableColumnsType } from 'antd';
import dayjs from 'dayjs';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import type { WarrantiesQuery } from '../api/warranties';
import type { WarrantyListItem } from '../api/types';
import { DataTable } from '../components/DataTable';
import { Mono } from '../components/Mono';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusDot';
import { useWarranties } from '../hooks/useWarranties';
import { isoDate, lastDays, type DateRange } from '../lib/dates';
import { formatDate, formatDateTime } from '../lib/format';
import { brand } from '../theme';
import { WarrantyDrawer } from './WarrantyDrawer';

const PAGE_SIZE = 25;

const STATUS_OPTIONS = [
  { label: 'Active', value: 'active' },
  { label: 'Pending backdate', value: 'pending_backdate' },
  { label: 'Pending review', value: 'pending_review' },
  { label: 'Pending confirmation', value: 'pending_confirmation' },
  { label: 'Claimed', value: 'claimed' },
  { label: 'Voided', value: 'voided' },
  { label: 'Expired', value: 'expired' },
];

export function WarrantiesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<string | undefined>();
  const [source, setSource] = useState<WarrantiesQuery['source']>();
  const [unverifiedOnly, setUnverifiedOnly] = useState(false);
  const [backdatedOnly, setBackdatedOnly] = useState(false);
  const [range, setRange] = useState<DateRange | null>(null);
  const [page, setPage] = useState(1);

  const dealerId = searchParams.get('dealer') ?? undefined;
  const openWarranty = searchParams.get('warranty');

  const clearDealerFilter = () => {
    const next = new URLSearchParams(searchParams);
    next.delete('dealer');
    setSearchParams(next, { replace: true });
    setPage(1);
  };

  const setOpenWarranty = (id: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (id) next.set('warranty', id);
    else next.delete('warranty');
    setSearchParams(next, { replace: true });
  };

  const params = useMemo<WarrantiesQuery>(
    () => ({
      q: q || undefined,
      status,
      source,
      dealer_id: dealerId,
      unverified: unverifiedOnly || undefined,
      backdated: backdatedOnly || undefined,
      date_from: range ? isoDate(range[0]) : undefined,
      date_to: range ? isoDate(range[1]) : undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [q, status, source, dealerId, unverifiedOnly, backdatedOnly, range, page],
  );

  const warranties = useWarranties(params);

  const columns: TableColumnsType<WarrantyListItem> = [
    {
      // Blank on everything registered since the serial went away, which is why
      // the row itself opens the drawer: the dash is not a click target.
      title: 'Serial',
      dataIndex: 'serial',
      width: 190,
      render: (serial: string | null, r) => (
        <div>
          <Mono value={serial} chars={16} onClick={() => setOpenWarranty(r.id)} />
          <div style={{ fontSize: 11.5, color: brand.textFaint }}>{r.model_name ?? '—'}</div>
        </div>
      ),
    },
    {
      title: 'Customer',
      dataIndex: ['customer', 'name'],
      width: 200,
      render: (_v, r) =>
        r.customer ? (
          <div>
            <div style={{ color: brand.text }}>{r.customer.name}</div>
            <div className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
              {r.customer.phone}
            </div>
          </div>
        ) : (
          <span style={{ color: brand.textFaint }}>—</span>
        ),
    },
    {
      title: 'Dealer',
      dataIndex: ['dealer', 'name'],
      width: 190,
      render: (_v, r) =>
        r.dealer ? (
          <div>
            <div style={{ color: brand.text, fontSize: 13 }}>{r.dealer.name}</div>
            <div className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
              {r.dealer.code}
            </div>
          </div>
        ) : (
          <Tooltip title="Registered by the customer, not by a shop">
            <span style={{ color: brand.danger, fontSize: 12.5 }}>Self-registered</span>
          </Tooltip>
        ),
    },
    {
      title: 'Invoice',
      dataIndex: 'invoice_ref',
      width: 150,
      render: (ref: string | null, r) => (
        <div>
          <div style={{ fontSize: 12.5, color: brand.textDim }}>{ref ?? '—'}</div>
          {r.invoice_date && (
            <div style={{ fontSize: 11.5, color: brand.textFaint }}>
              {formatDate(r.invoice_date)}
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Cover',
      dataIndex: 'warranty_start_date',
      width: 190,
      render: (start: string, r) => (
        <div style={{ fontSize: 12.5, color: brand.textDim }}>
          {formatDate(start)} → {formatDate(r.warranty_end_date)}
          {r.backdate_days > 0 && (
            <div style={{ fontSize: 11.5, color: brand.warning }}>
              backdated {r.backdate_days}d
            </div>
          )}
        </div>
      ),
    },
    {
      // `status` already has expiry folded in; `stored_status` is the raw column.
      title: 'Status',
      dataIndex: 'status',
      width: 130,
      render: (s: string, r) => (
        <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
          <StatusTag status={s} />
          {r.unit_unverified && (
            <Tooltip title="Registered without confirming the unit against GB Rewards">
              <span style={{ color: brand.warning, fontSize: 11 }}>●</span>
            </Tooltip>
          )}
        </span>
      ),
    },
    {
      title: 'Registered',
      dataIndex: 'registered_at',
      width: 160,
      render: (v: string) => (
        <span style={{ fontSize: 12.5, color: brand.textFaint }}>{formatDateTime(v)}</span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Warranties"
        subtitle={
          dealerId ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              Filtered to one dealer.
              <Tag closable onClose={clearDealerFilter} style={{ marginInlineEnd: 0 }}>
                Showing one dealer
              </Tag>
            </span>
          ) : (
            'Every sale record in the system.'
          )
        }
        extra={
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Input.Search
              allowClear
              placeholder="Serial, mobile or invoice"
              style={{ width: 280 }}
              onSearch={(v) => {
                setPage(1);
                setQ(v);
              }}
            />
            <Select
              allowClear
              placeholder="Any status"
              style={{ width: 170 }}
              value={status}
              options={STATUS_OPTIONS}
              onChange={(v) => {
                setPage(1);
                setStatus(v);
              }}
            />
            <Select
              allowClear
              placeholder="Any source"
              style={{ width: 150 }}
              value={source}
              options={[
                { label: 'Dealer', value: 'dealer' },
                { label: 'Customer', value: 'customer_self' },
                { label: 'Admin', value: 'admin' },
                { label: 'Migration', value: 'migration' },
              ]}
              onChange={(v) => {
                setPage(1);
                setSource(v);
              }}
            />
            <DatePicker.RangePicker
              value={range}
              onChange={(v) => {
                setPage(1);
                setRange(v && v[0] && v[1] ? [v[0], v[1]] : null);
              }}
              presets={[
                { label: 'Last 7 days', value: lastDays(7) },
                { label: 'Last 30 days', value: lastDays(30) },
                { label: 'This year', value: [dayjs().startOf('year'), dayjs()] },
              ]}
            />
          </div>
        }
      />

      <div style={{ marginBottom: 12, display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        <Checkbox
          checked={unverifiedOnly}
          onChange={(e) => {
            setPage(1);
            setUnverifiedOnly(e.target.checked);
          }}
        >
          <span style={{ fontSize: 13, color: brand.textDim }}>
            Only units we could not verify upstream
          </span>
        </Checkbox>
        <Checkbox
          checked={backdatedOnly}
          onChange={(e) => {
            setPage(1);
            setBackdatedOnly(e.target.checked);
          }}
        >
          <span style={{ fontSize: 13, color: brand.textDim }}>Only backdated registrations</span>
        </Checkbox>
      </div>

      <DataTable<WarrantyListItem>
        rowKey="id"
        loading={warranties.isLoading}
        dataSource={warranties.data?.items ?? []}
        columns={columns}
        total={warranties.data?.total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyText="No warranties match"
        emptyHint="Try a shorter search — the serial box also accepts a mobile number or an invoice reference."
        emptyIcon={<SafetyCertificateOutlined />}
        rowClassName={() => 'dr-row-clickable'}
        onRow={(r) => ({ onClick: () => setOpenWarranty(r.id) })}
      />

      <WarrantyDrawer warrantyId={openWarranty} onClose={() => setOpenWarranty(null)} />
    </>
  );
}
