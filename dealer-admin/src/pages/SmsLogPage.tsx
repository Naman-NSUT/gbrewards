import { MessageOutlined, RedoOutlined } from '@ant-design/icons';
import { App, Button, Input, Segmented, Select, Tooltip } from 'antd';
import type { TableColumnsType } from 'antd';
import { useMemo, useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { SmsRow, SmsStatus } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusDot';
import { useRetrySms, useSmsLog, useSmsTemplates } from '../hooks/useSms';
import { formatDateTime, humanise } from '../lib/format';
import { brand } from '../theme';

const PAGE_SIZE = 25;

const STATUSES: { label: string; value: SmsStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Queued', value: 'queued' },
  { label: 'Sent', value: 'sent' },
  { label: 'Delivered', value: 'delivered' },
  { label: 'Failed', value: 'failed' },
  { label: 'Undelivered', value: 'undelivered' },
];

export function SmsLogPage() {
  const { message } = App.useApp();
  const [status, setStatus] = useState<SmsStatus | 'all'>('all');
  const [template, setTemplate] = useState<string | undefined>();
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);

  const params = useMemo(
    () => ({
      status: status === 'all' ? undefined : status,
      template_key: template,
      q: q || undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [status, template, q, page],
  );

  const sms = useSmsLog(params);
  // The template options come from the sender's own registry, so the filter can
  // never offer a template that does not exist.
  const templates = useSmsTemplates();
  const retry = useRetrySms();

  const templateOptions = Object.keys(templates.data ?? {}).map((key) => ({
    label: humanise(key),
    value: key,
  }));

  const doRetry = async (row: SmsRow) => {
    try {
      await retry.mutateAsync(row.id);
      message.success('Queued for another attempt');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not retry that message'));
    }
  };

  const columns: TableColumnsType<SmsRow> = [
    {
      title: 'To',
      dataIndex: 'to_phone',
      width: 150,
      render: (p: string) => (
        <span className="mono" style={{ fontSize: 12.5, color: brand.text }}>
          {p}
        </span>
      ),
    },
    {
      title: 'Template',
      dataIndex: 'template_key',
      width: 190,
      render: (t: string, r) => (
        <div>
          <div style={{ fontSize: 13, color: brand.text }}>{humanise(t)}</div>
          {r.warranty_id && (
            <div className="mono" style={{ fontSize: 11, color: brand.textFaint }}>
              warranty {r.warranty_id.slice(0, 8)}…
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Message',
      dataIndex: 'preview',
      render: (preview: string | null | undefined) =>
        preview ? (
          <Tooltip title={preview}>
            <span
              style={{
                fontSize: 12,
                color: brand.textDim,
                display: 'block',
                maxWidth: 320,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {preview}
            </span>
          </Tooltip>
        ) : (
          <span style={{ color: brand.textFaint }}>—</span>
        ),
    },
    {
      title: 'Provider',
      dataIndex: 'provider',
      width: 150,
      render: (p: string, r) => (
        <div>
          <div style={{ fontSize: 12.5, color: brand.textDim }}>{p}</div>
          {r.provider_message_id && (
            <Tooltip title={r.provider_message_id}>
              <div
                className="mono"
                style={{
                  fontSize: 11,
                  color: brand.textFaint,
                  maxWidth: 130,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {r.provider_message_id}
              </div>
            </Tooltip>
          )}
        </div>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 130,
      render: (s: SmsStatus, r) => (
        <div>
          <StatusTag status={s} />
          {r.attempts > 1 && (
            <div style={{ fontSize: 11, color: brand.textFaint, marginTop: 2 }}>
              {r.attempts} attempts
            </div>
          )}
          {r.error && (
            <Tooltip title={r.error}>
              <div
                style={{
                  fontSize: 11,
                  color: brand.danger,
                  maxWidth: 120,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {r.error}
              </div>
            </Tooltip>
          )}
        </div>
      ),
    },
    {
      title: 'When',
      dataIndex: 'created_at',
      width: 165,
      render: (v: string, r) => (
        <div style={{ fontSize: 12, color: brand.textFaint }}>
          <div>{formatDateTime(v)}</div>
          {r.delivered_at && (
            <div style={{ color: brand.success }}>delivered {formatDateTime(r.delivered_at)}</div>
          )}
        </div>
      ),
    },
    {
      title: '',
      key: 'actions',
      width: 90,
      render: (_v, r) =>
        r.status === 'failed' || r.status === 'undelivered' || r.status === 'queued' ? (
          <Button
            size="small"
            type="text"
            icon={<RedoOutlined />}
            loading={retry.isPending}
            onClick={() => doRetry(r)}
          >
            Retry
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="SMS Log"
        subtitle="Every message is a row before it is an HTTP call, so “did the customer get it?” always has an answer."
        extra={
          <div style={{ display: 'flex', gap: 10 }}>
            <Input.Search
              allowClear
              placeholder="Mobile number or text"
              style={{ width: 240 }}
              onSearch={(v) => {
                setPage(1);
                setQ(v);
              }}
            />
            <Select
              allowClear
              placeholder="Any template"
              style={{ width: 190 }}
              value={template}
              loading={templates.isLoading}
              options={templateOptions}
              onChange={(v) => {
                setPage(1);
                setTemplate(v);
              }}
            />
          </div>
        }
      />

      <div style={{ marginBottom: 12 }}>
        {/* No per-status counts on this endpoint — these filter, they do not tally. */}
        <Segmented
          options={STATUSES}
          value={status}
          onChange={(v) => {
            setPage(1);
            setStatus(v as SmsStatus | 'all');
          }}
        />
      </div>

      <DataTable<SmsRow>
        rowKey="id"
        loading={sms.isLoading}
        dataSource={sms.data?.items ?? []}
        columns={columns}
        total={sms.data?.total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyText="No messages"
        emptyHint="Warranty confirmations and login codes appear here as soon as they are queued."
        emptyIcon={<MessageOutlined />}
      />
    </>
  );
}
