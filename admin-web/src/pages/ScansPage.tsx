import { DatePicker, Select, Space, Typography } from 'antd';
import { useState } from 'react';

import type { ScanFeedItem } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { useProducts } from '../hooks/useProducts';
import { useScans } from '../hooks/useReporting';
import { formatDateTime } from '../lib/format';

export function ScansPage() {
  const products = useProducts();
  const [productId, setProductId] = useState<string | undefined>();
  const [range, setRange] = useState<{ from?: string; to?: string }>({});
  const [cursor, setCursor] = useState<string | undefined>();

  const scans = useScans({ product_id: productId, from: range.from, to: range.to, cursor });

  return (
    <>
      <PageHeader title="Scans" subtitle="Every scan-to-earn event across the program." />
      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          allowClear
          placeholder="Filter by product"
          style={{ width: 240 }}
          loading={products.isLoading}
          value={productId}
          onChange={(v) => {
            setCursor(undefined);
            setProductId(v);
          }}
          options={(products.data ?? []).map((p) => ({ label: p.name, value: p.id }))}
        />
        <DatePicker.RangePicker
          showTime
          onChange={(vals) => {
            setCursor(undefined);
            setRange({
              from: vals?.[0]?.toISOString(),
              to: vals?.[1]?.toISOString(),
            });
          }}
        />
      </Space>

      <DataTable<ScanFeedItem>
        rowKey="id"
        loading={scans.isLoading}
        dataSource={scans.data?.items ?? []}
        emptyText="No scans match these filters"
        columns={[
          { title: 'When', dataIndex: 'scanned_at', render: formatDateTime },
          {
            title: 'User',
            render: (_v, s) => (
              <span>
                <span style={{ fontWeight: 550 }}>{s.user.name}</span>{' '}
                <span className="mono" style={{ opacity: 0.6 }}>{s.user.phone}</span>
              </span>
            ),
          },
          { title: 'Product', render: (_v, s) => s.product.name },
          {
            title: 'QR code',
            render: (_v, s) =>
              s.token ? (
                <Typography.Text
                  className="mono"
                  style={{ fontSize: 12 }}
                  copyable={{ text: s.token }}
                >
                  {s.token}
                </Typography.Text>
              ) : (
                <span className="tnum">—</span>
              ),
          },
          { title: 'Points', dataIndex: 'points', render: (v: number) => <span className="tnum">+{v}</span> },
        ]}
      />
      {scans.data?.next_cursor && (
        <a style={{ display: 'inline-block', marginTop: 12 }} onClick={() => setCursor(scans.data.next_cursor ?? undefined)}>
          Next page →
        </a>
      )}
    </>
  );
}
