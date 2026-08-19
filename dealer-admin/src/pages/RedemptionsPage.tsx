import { CheckOutlined, CloseOutlined, TrophyOutlined } from '@ant-design/icons';
import { App, Button, Input, Modal, Segmented } from 'antd';
import type { TableColumnsType } from 'antd';
import { useMemo, useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { RedemptionRow, RedemptionStatus } from '../api/types';
import { ConfirmWithReason } from '../components/ConfirmWithReason';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusDot';
import {
  useApproveRedemption,
  useMarkRedemptionFulfilled,
  useRedemptions,
  useRejectRedemption,
} from '../hooks/useRedemptions';
import { formatDateTime, formatNumber } from '../lib/format';
import { brand } from '../theme';

const PAGE_SIZE = 25;

const STATUSES: { label: string; value: RedemptionStatus | 'all' }[] = [
  { label: 'Pending', value: 'pending' },
  { label: 'Approved', value: 'approved' },
  { label: 'Fulfilled', value: 'fulfilled' },
  { label: 'Rejected', value: 'rejected' },
  { label: 'Cancelled', value: 'cancelled' },
  { label: 'All', value: 'all' },
];

export function RedemptionsPage() {
  const { message } = App.useApp();
  const [status, setStatus] = useState<RedemptionStatus | 'all'>('pending');
  const [page, setPage] = useState(1);
  const [rejecting, setRejecting] = useState<RedemptionRow | null>(null);
  const [noting, setNoting] = useState<{
    row: RedemptionRow;
    action: 'approve' | 'fulfil';
  } | null>(null);
  const [note, setNote] = useState('');

  const params = useMemo(
    () => ({
      status: status === 'all' ? undefined : status,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [status, page],
  );

  const redemptions = useRedemptions(params);
  const approve = useApproveRedemption();
  const reject = useRejectRedemption();
  const fulfil = useMarkRedemptionFulfilled();

  const runNoted = async () => {
    if (!noting) return;
    try {
      if (noting.action === 'approve') {
        // The decision response carries the dealer's balance AFTER the debit,
        // which is the only balance this screen can state as fact.
        const result = await approve.mutateAsync({ id: noting.row.id, note: note || null });
        message.success(
          `Approved — ${formatNumber(noting.row.points)} points debited from ${noting.row.dealer.name}. Balance now ${formatNumber(result.points.balance)}.`,
        );
      } else {
        await fulfil.mutateAsync({ id: noting.row.id, note: note || null });
        message.success('Marked as fulfilled');
      }
      setNoting(null);
      setNote('');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not update that request'));
    }
  };

  const doReject = async (reason: string) => {
    if (!rejecting) return;
    try {
      await reject.mutateAsync({ id: rejecting.id, reason });
      message.success('Rejected. The hold on their balance is released.');
      setRejecting(null);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not reject that request'));
    }
  };

  const columns: TableColumnsType<RedemptionRow> = [
    {
      title: 'Dealer',
      dataIndex: ['dealer', 'name'],
      width: 240,
      render: (_v, r) => (
        <div>
          <div style={{ color: brand.text, fontWeight: 550 }}>{r.dealer.name}</div>
          <div className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
            {r.dealer.code}
            {r.requested_by && (
              <span style={{ fontFamily: 'inherit' }}> · {r.requested_by.name}</span>
            )}
          </div>
        </div>
      ),
    },
    {
      title: 'Reward',
      dataIndex: 'reward_name',
      render: (name: string | null) => (
        <span style={{ color: brand.text, fontSize: 13 }}>{name ?? 'Custom request'}</span>
      ),
    },
    {
      title: 'Points',
      dataIndex: 'points',
      align: 'right',
      width: 110,
      render: (v: number) => (
        <span className="tnum" style={{ color: brand.text, fontWeight: 600 }}>
          {formatNumber(v)}
        </span>
      ),
    },
    {
      title: 'Note',
      dataIndex: 'note',
      width: 220,
      render: (v: string | null) => (
        <span style={{ fontSize: 12.5, color: brand.textDim }}>{v ?? '—'}</span>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 120,
      render: (s: RedemptionStatus) => <StatusTag status={s} />,
    },
    {
      title: 'Requested',
      dataIndex: 'created_at',
      width: 165,
      render: (v: string) => (
        <span style={{ fontSize: 12.5, color: brand.textFaint }}>{formatDateTime(v)}</span>
      ),
    },
    {
      title: '',
      key: 'actions',
      width: 180,
      render: (_v, r) => {
        if (r.status === 'pending') {
          return (
            <div style={{ display: 'flex', gap: 6 }}>
              <Button
                size="small"
                type="primary"
                icon={<CheckOutlined />}
                onClick={() => {
                  setNote('');
                  setNoting({ row: r, action: 'approve' });
                }}
              >
                Approve
              </Button>
              <Button size="small" danger icon={<CloseOutlined />} onClick={() => setRejecting(r)} />
            </div>
          );
        }
        if (r.status === 'approved') {
          return (
            <Button
              size="small"
              onClick={() => {
                setNote('');
                setNoting({ row: r, action: 'fulfil' });
              }}
            >
              Mark fulfilled
            </Button>
          );
        }
        return (
          <span style={{ fontSize: 12, color: brand.textFaint }}>
            {r.processed_at ? formatDateTime(r.processed_at) : ''}
          </span>
        );
      },
    },
  ];

  return (
    <>
      <PageHeader
        title="Redemptions"
        subtitle="A pending request is itself the hold on the balance — approving it writes the debit."
      />

      <div style={{ marginBottom: 12 }}>
        {/* The list endpoint returns no per-status counts, so the tabs are
            filters, not a scoreboard. */}
        <Segmented
          options={STATUSES}
          value={status}
          onChange={(v) => {
            setPage(1);
            setStatus(v as RedemptionStatus | 'all');
          }}
        />
      </div>

      <DataTable<RedemptionRow>
        rowKey="id"
        loading={redemptions.isLoading}
        dataSource={redemptions.data?.items ?? []}
        columns={columns}
        total={redemptions.data?.total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyText="Nothing in this queue"
        emptyHint="Dealers request rewards from the mobile app."
        emptyIcon={<TrophyOutlined />}
      />

      <Modal
        open={noting !== null}
        title={noting?.action === 'approve' ? 'Approve this redemption' : 'Mark as fulfilled'}
        okText={noting?.action === 'approve' ? 'Approve' : 'Mark fulfilled'}
        confirmLoading={approve.isPending || fulfil.isPending}
        onOk={runNoted}
        onCancel={() => setNoting(null)}
        destroyOnHidden
        width={460}
      >
        {noting && (
          <>
            <div style={{ fontSize: 13.5, color: brand.textDim, marginBottom: 12 }}>
              {noting.action === 'approve' ? (
                <>
                  This debits{' '}
                  <strong style={{ color: brand.text }}>{formatNumber(noting.row.points)}</strong>{' '}
                  points from <strong style={{ color: brand.text }}>{noting.row.dealer.name}</strong>
                  . Their balance may go negative — the ledger records that honestly rather than
                  refusing.
                </>
              ) : (
                'Record that the reward has actually been sent to the dealer.'
              )}
            </div>
            <Input.TextArea
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={300}
              showCount
              placeholder="Optional note — courier reference, voucher code, who arranged it."
            />
          </>
        )}
      </Modal>

      <ConfirmWithReason
        open={rejecting !== null}
        title="Reject this request"
        confirmText="Reject"
        danger
        loading={reject.isPending}
        description="No points move — the pending hold simply ends. The dealer sees the reason in their app."
        onCancel={() => setRejecting(null)}
        onConfirm={doReject}
      />
    </>
  );
}
