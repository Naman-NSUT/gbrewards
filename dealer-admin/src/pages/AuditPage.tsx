import { AuditOutlined } from '@ant-design/icons';
import { DatePicker, Input, Select, Tooltip } from 'antd';
import type { TableColumnsType } from 'antd';
import dayjs from 'dayjs';
import { useMemo, useState } from 'react';

import type { ActorType, AuditRow } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { useAudit, useAuditFilters } from '../hooks/useAudit';
import { isoDate, lastDays, type DateRange } from '../lib/dates';
import { formatDateTime, humanise } from '../lib/format';
import { brand } from '../theme';

const PAGE_SIZE = 50;

/** Anything that moves points or rewrites a record — see services/audit.py. */
const HIGH_STAKES = new Set([
  'void_warranty',
  'adjust_points',
  'approve_backdate',
  'reject_backdate',
  'edit_customer',
  'suspend_dealer',
  'reject_self_registration',
]);

export function AuditPage() {
  const [q, setQ] = useState('');
  const [action, setAction] = useState<string | undefined>();
  const [entityType, setEntityType] = useState<string | undefined>();
  const [actorType, setActorType] = useState<ActorType | undefined>();
  const [range, setRange] = useState<DateRange | null>(null);
  const [page, setPage] = useState(1);

  const params = useMemo(
    () => ({
      q: q || undefined,
      action,
      entity_type: entityType,
      actor_type: actorType,
      date_from: range ? isoDate(range[0]) : undefined,
      date_to: range ? isoDate(range[1]) : undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [q, action, entityType, actorType, range, page],
  );

  const audit = useAudit(params);
  // Options come from /admin/audit/filters, not from the page in view: a filter
  // list that shrank as you paged would be worse than useless.
  const filters = useAuditFilters();

  const columns: TableColumnsType<AuditRow> = [
    {
      title: 'When',
      dataIndex: 'created_at',
      width: 170,
      render: (v: string) => (
        <span style={{ fontSize: 12.5, color: brand.textFaint }}>{formatDateTime(v)}</span>
      ),
    },
    {
      title: 'Who',
      dataIndex: 'actor_name',
      width: 190,
      render: (name: string | null, r) => (
        <div>
          <div style={{ fontSize: 13, color: brand.text }}>
            {name ?? r.actor_label ?? humanise(r.actor_type)}
          </div>
          <div style={{ fontSize: 11.5, color: brand.textFaint }}>{humanise(r.actor_type)}</div>
        </div>
      ),
    },
    {
      title: 'Action',
      dataIndex: 'action',
      width: 200,
      render: (a: string) => (
        <span
          style={{
            fontSize: 12.5,
            fontWeight: HIGH_STAKES.has(a) ? 600 : 400,
            color: HIGH_STAKES.has(a) ? brand.warning : brand.text,
          }}
        >
          {humanise(a)}
        </span>
      ),
    },
    {
      title: 'Entity',
      dataIndex: 'entity_type',
      width: 190,
      render: (t: string, r) => (
        <div>
          <div style={{ fontSize: 12.5, color: brand.textDim }}>{humanise(t)}</div>
          {r.entity_id && (
            <Tooltip title={r.entity_id}>
              <div className="mono" style={{ fontSize: 11, color: brand.textFaint }}>
                {r.entity_id.slice(0, 8)}…
              </div>
            </Tooltip>
          )}
        </div>
      ),
    },
    {
      title: 'Reason',
      dataIndex: 'reason',
      render: (reason: string | null, r) => (
        <div style={{ maxWidth: 420 }}>
          {reason ? (
            <span style={{ fontSize: 12.5, color: brand.text }}>{reason}</span>
          ) : (
            <span style={{ color: brand.textFaint }}>—</span>
          )}
          {r.metadata && Object.keys(r.metadata).length > 0 && (
            <Tooltip title={<pre style={{ margin: 0 }}>{JSON.stringify(r.metadata, null, 2)}</pre>}>
              <span
                className="mono"
                style={{
                  display: 'block',
                  fontSize: 11,
                  color: brand.textFaint,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {JSON.stringify(r.metadata)}
              </span>
            </Tooltip>
          )}
        </div>
      ),
    },
    {
      title: 'IP',
      dataIndex: 'ip',
      width: 130,
      render: (v: string | null) => (
        <span className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
          {v ?? '—'}
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Audit"
        subtitle="Who changed what, when, and why. Append-only — nothing here can be edited or removed."
        extra={
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Input.Search
              allowClear
              placeholder="Search reasons and ids"
              style={{ width: 220 }}
              onSearch={(v) => {
                setPage(1);
                setQ(v);
              }}
            />
            <Select
              allowClear
              placeholder="Any action"
              style={{ width: 190 }}
              value={action}
              loading={filters.isLoading}
              options={(filters.data?.actions ?? []).map((a) => ({ label: humanise(a), value: a }))}
              onChange={(v) => {
                setPage(1);
                setAction(v);
              }}
            />
            <Select
              allowClear
              placeholder="Any entity"
              style={{ width: 150 }}
              value={entityType}
              loading={filters.isLoading}
              options={(filters.data?.entity_types ?? []).map((t) => ({
                label: humanise(t),
                value: t,
              }))}
              onChange={(v) => {
                setPage(1);
                setEntityType(v);
              }}
            />
            <Select
              allowClear
              placeholder="Any actor"
              style={{ width: 140 }}
              value={actorType}
              options={[
                { label: 'Admin', value: 'admin' },
                { label: 'Dealer staff', value: 'dealer_staff' },
                { label: 'Customer', value: 'customer' },
                { label: 'System', value: 'system' },
              ]}
              onChange={(v) => {
                setPage(1);
                setActorType(v);
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

      <DataTable<AuditRow>
        rowKey="id"
        loading={audit.isLoading}
        dataSource={audit.data?.items ?? []}
        columns={columns}
        total={audit.data?.total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyText="No audit entries match"
        emptyHint="Voids, approvals, adjustments and dealer changes all land here."
        emptyIcon={<AuditOutlined />}
      />
    </>
  );
}
