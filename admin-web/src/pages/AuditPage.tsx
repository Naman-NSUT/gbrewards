import { DatePicker, Select, Space, Tag } from 'antd';
import { useState } from 'react';

import type { AuditItem } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { useAudit } from '../hooks/useReporting';
import { formatDateTime } from '../lib/format';

const ENTITIES = ['user', 'product', 'product_unit', 'qr_batch', 'redemption'];

export function AuditPage() {
  const [entity, setEntity] = useState<string | undefined>();
  const [range, setRange] = useState<{ from?: string; to?: string }>({});
  const [cursor, setCursor] = useState<string | undefined>();

  const audit = useAudit({ entity, from: range.from, to: range.to, cursor });

  return (
    <>
      <PageHeader title="Audit trail" subtitle="Immutable log of every administrative action." />
      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          allowClear
          placeholder="Filter by entity"
          style={{ width: 200 }}
          value={entity}
          onChange={(v) => {
            setCursor(undefined);
            setEntity(v);
          }}
          options={ENTITIES.map((e) => ({ label: e, value: e }))}
        />
        <DatePicker.RangePicker
          showTime
          onChange={(vals) => {
            setCursor(undefined);
            setRange({ from: vals?.[0]?.toISOString(), to: vals?.[1]?.toISOString() });
          }}
        />
      </Space>

      <DataTable<AuditItem>
        rowKey="id"
        loading={audit.isLoading}
        dataSource={audit.data?.items ?? []}
        emptyText="No audit entries"
        columns={[
          { title: 'When', dataIndex: 'created_at', render: formatDateTime },
          {
            title: 'Action',
            dataIndex: 'action',
            render: (a: string) => <Tag>{a.replace(/_/g, ' ')}</Tag>,
          },
          { title: 'Entity', dataIndex: 'entity_type', render: (e: string | null) => e ?? '—' },
          {
            title: 'Details',
            dataIndex: 'metadata',
            render: (m: Record<string, unknown> | null) => (
              <span className="mono" style={{ fontSize: 12, opacity: 0.7 }}>
                {m ? JSON.stringify(m) : '—'}
              </span>
            ),
          },
        ]}
      />
      {audit.data?.next_cursor && (
        <a style={{ display: 'inline-block', marginTop: 12 }} onClick={() => setCursor(audit.data.next_cursor ?? undefined)}>
          Next page →
        </a>
      )}
    </>
  );
}
