import { App, Input, Modal, Segmented, Space } from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { Redemption, RedemptionStatus } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { StatusDot } from '../components/StatusDot';
import { useRedemptionAction, useRedemptions } from '../hooks/useRedemptions';
import { formatDateTime } from '../lib/format';

type Filter = 'pending' | 'approved' | 'all';
type Action = 'approve' | 'reject' | 'fulfill';

export function RedemptionsPage() {
  const { message } = App.useApp();
  const [filter, setFilter] = useState<Filter>('pending');
  const status = filter === 'all' ? undefined : (filter as RedemptionStatus);
  const redemptions = useRedemptions(status);
  const action = useRedemptionAction();

  const [pending, setPending] = useState<{ row: Redemption; action: Action } | null>(null);
  const [note, setNote] = useState('');

  const confirm = async () => {
    if (!pending) return;
    try {
      await action.mutateAsync({ id: pending.row.id, action: pending.action, note: note || undefined });
      message.success(`Request ${pending.action}d`);
      setPending(null);
      setNote('');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Action failed'));
    }
  };

  return (
    <>
      <PageHeader
        title="Redemptions"
        subtitle="Review and process broker redemption requests."
        extra={
          <Segmented
            options={[
              { label: 'Pending', value: 'pending' },
              { label: 'Approved', value: 'approved' },
              { label: 'All', value: 'all' },
            ]}
            value={filter}
            onChange={(v) => setFilter(v as Filter)}
          />
        }
      />

      <DataTable<Redemption>
        rowKey="id"
        loading={redemptions.isLoading}
        dataSource={redemptions.data ?? []}
        emptyText="No redemption requests"
        columns={[
          {
            title: 'User',
            render: (_v, r) => (
              <span>
                <span style={{ fontWeight: 550 }}>{r.user.name}</span>{' '}
                <span style={{ opacity: 0.6 }}>{r.user.phone}</span>
              </span>
            ),
          },
          {
            title: 'Reward',
            render: (_v, r) => r.reward?.title ?? '—',
          },
          { title: 'Points', dataIndex: 'points', render: (v: number) => <span className="tnum">{v}</span> },
          {
            title: 'Status',
            dataIndex: 'status',
            render: (s: RedemptionStatus) => <StatusDot status={s} />,
          },
          { title: 'Requested', dataIndex: 'created_at', render: formatDateTime },
          { title: 'Note', dataIndex: 'note', render: (n: string | null) => n ?? '—' },
          {
            title: '',
            align: 'right',
            render: (_v, r) => (
              <Space size="large">
                {r.status === 'pending' && (
                  <>
                    <a onClick={() => setPending({ row: r, action: 'approve' })}>Approve</a>
                    <a onClick={() => setPending({ row: r, action: 'reject' })}>Reject</a>
                  </>
                )}
                {r.status === 'approved' && (
                  <a onClick={() => setPending({ row: r, action: 'fulfill' })}>Mark fulfilled</a>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={pending ? `${pending.action} — ${pending.row.points} pts for ${pending.row.user.name}` : ''}
        open={pending !== null}
        onCancel={() => setPending(null)}
        onOk={confirm}
        confirmLoading={action.isPending}
      >
        <Input.TextArea
          rows={3}
          placeholder="Optional note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </Modal>
    </>
  );
}
