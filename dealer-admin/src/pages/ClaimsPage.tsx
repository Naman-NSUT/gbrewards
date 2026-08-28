import { FileProtectOutlined } from '@ant-design/icons';
import { App, Button, Drawer, Form, Input, Segmented, Select, Tooltip } from 'antd';
import type { TableColumnsType } from 'antd';
import { useMemo, useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { ClaimListItem, ClaimStatus } from '../api/types';
import { DataTable } from '../components/DataTable';
import { Mono } from '../components/Mono';
import { PageHeader } from '../components/PageHeader';
import { DetailSkeleton } from '../components/skeletons';
import { StatusTag } from '../components/StatusDot';
import { useClaim, useClaims, useUpdateClaim } from '../hooks/useClaims';
import { formatDate, formatDateTime } from '../lib/format';
import { brand } from '../theme';

const PAGE_SIZE = 25;

const STATUSES: { label: string; value: ClaimStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Open', value: 'open' },
  { label: 'In review', value: 'in_review' },
  { label: 'Approved', value: 'approved' },
  { label: 'Rejected', value: 'rejected' },
  { label: 'Closed', value: 'closed' },
];

/** The workflow, as the support desk actually walks it. */
const NEXT_STATUSES: Record<ClaimStatus, ClaimStatus[]> = {
  open: ['in_review', 'rejected'],
  in_review: ['approved', 'rejected'],
  approved: ['closed'],
  rejected: ['closed'],
  closed: [],
};

export function ClaimsPage() {
  const { message } = App.useApp();
  const [status, setStatus] = useState<ClaimStatus | 'all'>('open');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form] = Form.useForm<{ status: ClaimStatus; resolution_note: string }>();

  const params = useMemo(
    () => ({
      status: status === 'all' ? undefined : status,
      q: q || undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [status, q, page],
  );

  const claims = useClaims(params);
  // The list row has no resolution note — only the detail endpoint returns one.
  const detail = useClaim(selectedId);
  const update = useUpdateClaim();

  const selected = detail.data?.claim ?? null;

  const save = async () => {
    if (!selectedId) return;
    const values = await form.validateFields();
    try {
      await update.mutateAsync({
        id: selectedId,
        status: values.status,
        resolutionNote: values.resolution_note || null,
      });
      message.success('Claim updated');
      setSelectedId(null);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not update the claim'));
    }
  };

  const columns: TableColumnsType<ClaimListItem> = [
    {
      title: 'Reference',
      dataIndex: 'reference',
      width: 130,
      render: (r: string) => (
        <span className="mono" style={{ color: brand.text, fontSize: 12.5 }}>
          {r}
        </span>
      ),
    },
    {
      title: 'Customer',
      dataIndex: ['customer', 'name'],
      width: 190,
      render: (_v, c) => (
        <div>
          <div style={{ color: brand.text }}>{c.customer.name}</div>
          <div className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
            {c.customer.phone}
          </div>
        </div>
      ),
    },
    {
      // Serial, model and cover end are flattened onto the claim row.
      title: 'Unit',
      dataIndex: 'serial',
      width: 200,
      render: (serial: string | null, c) => (
        <div>
          <Mono value={serial} chars={14} />
          <div style={{ fontSize: 11.5, color: brand.textFaint }}>
            {c.model_name ?? '—'} · cover to {formatDate(c.warranty_end_date)}
            {!c.in_warranty && (
              <Tooltip title="The warranty had already ended when this claim was raised">
                <span style={{ color: brand.danger }}> · out of warranty</span>
              </Tooltip>
            )}
          </div>
        </div>
      ),
    },
    {
      title: 'Issue',
      dataIndex: 'description',
      render: (d: string, c) => (
        <div style={{ maxWidth: 320 }}>
          {c.issue_type && (
            <div style={{ fontSize: 11.5, color: brand.textFaint }}>{c.issue_type}</div>
          )}
          <div
            style={{
              fontSize: 12.5,
              color: brand.textDim,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {d}
          </div>
        </div>
      ),
    },
    {
      title: 'Dealer',
      dataIndex: ['dealer', 'name'],
      width: 160,
      render: (_v, c) => (
        <span style={{ fontSize: 12.5, color: brand.textDim }}>{c.dealer?.name ?? '—'}</span>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 120,
      render: (s: ClaimStatus) => <StatusTag status={s} />,
    },
    {
      title: 'Raised',
      dataIndex: 'created_at',
      width: 160,
      render: (v: string) => (
        <span style={{ fontSize: 12.5, color: brand.textFaint }}>{formatDateTime(v)}</span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Claims"
        subtitle="Warranty claims raised by customers from the public support site."
        extra={
          <div style={{ display: 'flex', gap: 10 }}>
            <Input.Search
              allowClear
              placeholder="Reference, serial or mobile"
              style={{ width: 260 }}
              onSearch={(v) => {
                setPage(1);
                setQ(v);
              }}
            />
          </div>
        }
      />

      <div style={{ marginBottom: 12 }}>
        {/* No per-status counts come back from the list endpoint, so these are
            filters rather than a scoreboard. */}
        <Segmented
          options={STATUSES}
          value={status}
          onChange={(v) => {
            setPage(1);
            setStatus(v as ClaimStatus | 'all');
          }}
        />
      </div>

      <DataTable<ClaimListItem>
        rowKey="id"
        loading={claims.isLoading}
        dataSource={claims.data?.items ?? []}
        columns={columns}
        total={claims.data?.total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyText="No claims here"
        emptyHint="Claims arrive from the customer-facing warranty page."
        emptyIcon={<FileProtectOutlined />}
        rowClassName={() => 'dr-row-clickable'}
        onRow={(c) => ({
          onClick: () => {
            setSelectedId(c.id);
            form.setFieldsValue({
              status: NEXT_STATUSES[c.status][0] ?? c.status,
              resolution_note: '',
            });
          },
        })}
      />

      <Drawer
        open={selectedId !== null}
        onClose={() => setSelectedId(null)}
        width={560}
        destroyOnHidden
        title={
          selected ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="mono">{selected.reference}</span>
              <StatusTag status={selected.status} />
            </span>
          ) : (
            'Claim'
          )
        }
        footer={
          selected && NEXT_STATUSES[selected.status].length > 0 ? (
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Button onClick={() => setSelectedId(null)}>Cancel</Button>
              <Button type="primary" loading={update.isPending} onClick={save}>
                Save
              </Button>
            </div>
          ) : null
        }
      >
        {detail.isLoading || !detail.data || !selected ? (
          <DetailSkeleton rows={7} />
        ) : (
          <>
            <Field label="Customer">
              {detail.data.customer.name}
              <span className="mono" style={{ color: brand.textFaint, marginLeft: 8 }}>
                {detail.data.customer.phone}
              </span>
            </Field>
            <Field label="Unit">
              <Mono value={detail.data.warranty.serial} chars={40} />
              <div style={{ fontSize: 12, color: brand.textFaint, marginTop: 2 }}>
                {detail.data.warranty.model_name ?? '—'} · cover to{' '}
                {formatDate(detail.data.warranty.warranty_end_date)} ·{' '}
                {detail.data.warranty.status}
              </div>
            </Field>
            <Field label="Dealer">{selected.dealer?.name ?? 'Unknown'}</Field>
            <Field label="Issue">
              {selected.issue_type && (
                <div style={{ fontSize: 12, color: brand.textFaint }}>{selected.issue_type}</div>
              )}
              <div style={{ whiteSpace: 'pre-wrap' }}>{selected.description}</div>
            </Field>
            <Field label="Raised">{formatDateTime(selected.created_at)}</Field>
            {selected.resolved_at && (
              <Field label="Resolved">{formatDateTime(selected.resolved_at)}</Field>
            )}

            {NEXT_STATUSES[selected.status].length > 0 ? (
              <Form form={form} layout="vertical" style={{ marginTop: 20 }}>
                <Form.Item
                  name="status"
                  label="Move to"
                  rules={[{ required: true, message: 'Pick the next state' }]}
                >
                  <Select
                    options={NEXT_STATUSES[selected.status].map((s) => ({
                      label: s.replace(/_/g, ' '),
                      value: s,
                    }))}
                  />
                </Form.Item>
                <Form.Item
                  name="resolution_note"
                  label="Resolution note"
                  extra="The customer may be read this back on the phone."
                >
                  <Input.TextArea rows={4} maxLength={1000} showCount />
                </Form.Item>
              </Form>
            ) : (
              <div style={{ marginTop: 20 }}>
                <Field label="Resolution">{detail.data.resolution_note ?? '—'}</Field>
              </div>
            )}
          </>
        )}
      </Drawer>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 14 }}>
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
      <div style={{ fontSize: 13.5, color: brand.text, marginTop: 3 }}>{children}</div>
    </div>
  );
}
