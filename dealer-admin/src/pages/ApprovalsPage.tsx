import { CheckOutlined, CloseOutlined, FileImageOutlined, WarningOutlined } from '@ant-design/icons';
import { App, Badge, Button, Pagination, Radio, Tabs, Tooltip } from 'antd';
import { useMemo, useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { ApprovalItem, ApprovalStatus } from '../api/types';
import { ConfirmWithReason } from '../components/ConfirmWithReason';
import { EmptyState } from '../components/EmptyState';
import { Mono } from '../components/Mono';
import { PageHeader } from '../components/PageHeader';
import { DetailSkeleton } from '../components/skeletons';
import { SpotlightCard } from '../components/SpotlightCard';
import { StatusTag } from '../components/StatusDot';
import {
  useApprovalCounts,
  useApprovals,
  useApproveWarranty,
  useRejectWarranty,
} from '../hooks/useApprovals';
import { formatDate, formatDateTime } from '../lib/format';
import { brand } from '../theme';

const PAGE_SIZE = 20;

type Decision =
  | { type: 'approve'; item: ApprovalItem }
  | { type: 'reject'; item: ApprovalItem }
  | null;

export function ApprovalsPage() {
  const { message } = App.useApp();
  // The server splits this queue by warranty status: a backdate request is
  // `pending_backdate`, a customer self-registration is `pending_review`.
  const [status, setStatus] = useState<ApprovalStatus>('pending_backdate');
  const [page, setPage] = useState(1);
  const [decision, setDecision] = useState<Decision>(null);
  const [honourDate, setHonourDate] = useState(true);

  const params = useMemo(
    () => ({ status, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
    [status, page],
  );
  const approvals = useApprovals(params);
  const counts = useApprovalCounts();
  const approve = useApproveWarranty();
  const reject = useRejectWarranty();

  const items = approvals.data?.items ?? [];

  const runDecision = async (reason: string) => {
    if (!decision) return;
    try {
      if (decision.type === 'approve') {
        const result = await approve.mutateAsync({
          id: decision.item.id,
          reason,
          honourRequestedDate: honourDate,
        });
        const credited = result.ledger_entries.reduce(
          (sum, e) => (e.type === 'registration_credit' ? sum + e.amount : sum),
          0,
        );
        message.success(
          credited > 0
            ? `Approved — ${credited} points credited to ${decision.item.dealer?.name ?? 'the dealer'}`
            : 'Approved. No points were due on this one.',
        );
      } else {
        await reject.mutateAsync({ id: decision.item.id, reason });
        message.success('Rejected. The warranty has been voided and any points reversed.');
      }
      setDecision(null);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not record that decision'));
    }
  };

  const tabs = [
    {
      key: 'pending_backdate',
      label: (
        <span>
          Backdate requests{' '}
          <Badge
            count={counts.data?.pending_backdate ?? 0}
            showZero
            style={{ background: brand.accentSoft, color: brand.accent, boxShadow: 'none' }}
          />
        </span>
      ),
    },
    {
      key: 'pending_review',
      label: (
        <span>
          Customer self-registrations{' '}
          <Badge
            count={counts.data?.pending_review ?? 0}
            showZero
            style={{ background: brand.accentSoft, color: brand.accent, boxShadow: 'none' }}
          />
        </span>
      ),
    },
  ];

  const isBackdate = status === 'pending_backdate';

  return (
    <>
      <PageHeader
        title="Approvals"
        subtitle="Every decision here starts or refuses a five-year warranty clock."
      />

      <Tabs
        items={tabs}
        activeKey={status}
        onChange={(k) => {
          setStatus(k as ApprovalStatus);
          setPage(1);
        }}
      />

      {approvals.isLoading ? (
        <SpotlightCard style={{ padding: 20 }}>
          <DetailSkeleton rows={6} />
        </SpotlightCard>
      ) : items.length === 0 ? (
        <SpotlightCard style={{ padding: 24 }}>
          <EmptyState
            title={isBackdate ? 'No backdate requests' : 'No self-registrations waiting'}
            hint={
              isBackdate
                ? 'A dealer whose invoice date falls outside the grace window lands here.'
                : 'When a customer registers a warranty their dealer never recorded, it waits here.'
            }
            icon={<CheckOutlined />}
            height={220}
          />
        </SpotlightCard>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {items.map((item) => (
            <ApprovalCard
              key={item.id}
              item={item}
              onApprove={() => {
                setHonourDate(true);
                setDecision({ type: 'approve', item });
              }}
              onReject={() => setDecision({ type: 'reject', item })}
            />
          ))}
        </div>
      )}

      {(approvals.data?.total ?? 0) > PAGE_SIZE && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <Pagination
            current={page}
            pageSize={PAGE_SIZE}
            total={approvals.data?.total ?? 0}
            onChange={setPage}
            size="small"
            showSizeChanger={false}
          />
        </div>
      )}

      <ConfirmWithReason
        open={decision?.type === 'approve'}
        title="Approve this registration"
        confirmText="Approve"
        loading={approve.isPending}
        description={
          decision?.item ? (
            <>
              This activates the warranty on <strong>{decision.item.serial.slice(0, 12)}…</strong>
              {decision.item.dealer && (
                <>
                  {' '}
                  and credits <strong>{decision.item.dealer.name}</strong>
                </>
              )}
              .
            </>
          ) : undefined
        }
        extra={
          decision?.item.status === 'pending_backdate' ? (
            <div>
              <div style={{ fontSize: 12.5, color: brand.textDim, marginBottom: 8 }}>
                The dealer asked for a start date {decision.item.days_back} days back.
              </div>
              <Radio.Group
                value={honourDate}
                onChange={(e) => setHonourDate(e.target.value)}
                style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
              >
                <Radio value={true}>
                  Honour {formatDate(decision.item.requested_invoice_date)} — ends{' '}
                  {formatDate(decision.item.warranty_end_date)}
                </Radio>
                <Radio value={false}>
                  Start the clock today instead (accepts the sale, refuses the date)
                </Radio>
              </Radio.Group>
            </div>
          ) : undefined
        }
        onCancel={() => setDecision(null)}
        onConfirm={runDecision}
      />

      <ConfirmWithReason
        open={decision?.type === 'reject'}
        title="Reject this registration"
        confirmText="Reject and void"
        danger
        loading={reject.isPending}
        description="The warranty is voided and any points already credited are reversed. The customer keeps no cover from this record."
        onCancel={() => setDecision(null)}
        onConfirm={runDecision}
      />
    </>
  );
}

function ApprovalCard({
  item,
  onApprove,
  onReject,
}: {
  item: ApprovalItem;
  onApprove: () => void;
  onReject: () => void;
}) {
  const severe = item.days_back > 180;
  const isBackdate = item.status === 'pending_backdate';

  return (
    <SpotlightCard style={{ padding: 18 }}>
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 420px', minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Mono value={item.serial} chars={18} size={13} />
            <StatusTag status={item.status} />
            {item.unit_unverified && (
              <Tooltip title="This unit could not be verified against GB Rewards when it was registered.">
                <span>
                  <StatusTag status="pending" label="Unverified unit" />
                </span>
              </Tooltip>
            )}
            {item.waiting_days > 0 && (
              <span style={{ fontSize: 11.5, color: brand.textFaint }}>
                waiting {item.waiting_days}d
              </span>
            )}
          </div>

          <div style={{ marginTop: 4, fontSize: 13, color: brand.textDim }}>
            {item.model_name ?? 'Unknown model'} · {item.warranty_months} month cover
          </div>

          <div
            style={{
              marginTop: 14,
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: 12,
            }}
          >
            <Field label="Dealer">
              {item.dealer ? (
                <>
                  {item.dealer.name}
                  <span
                    className="mono"
                    style={{ color: brand.textFaint, marginLeft: 6, fontSize: 11.5 }}
                  >
                    {item.dealer.code}
                  </span>
                  {item.dealer_source && (
                    <div style={{ fontSize: 11.5, color: brand.textFaint }}>
                      via {item.dealer_source}
                    </div>
                  )}
                </>
              ) : (
                <span style={{ color: brand.danger }}>No dealer — customer registered it</span>
              )}
            </Field>
            <Field label="Customer">
              {item.customer.name}
              <span
                className="mono"
                style={{ color: brand.textFaint, marginLeft: 6, fontSize: 11.5 }}
              >
                {item.customer.phone}
              </span>
            </Field>
            <Field label="Invoice">
              {item.invoice_ref ?? '—'}
              {item.requested_invoice_date && (
                <span style={{ color: brand.textFaint, marginLeft: 6 }}>
                  {formatDate(item.requested_invoice_date)}
                </span>
              )}
            </Field>
            <Field label="Submitted">
              {formatDateTime(item.registered_at)}
              {item.staff && (
                <div style={{ fontSize: 11.5, color: brand.textFaint }}>by {item.staff.name}</div>
              )}
            </Field>
          </div>
        </div>

        <div
          style={{
            flex: '0 0 260px',
            borderLeft: `1px solid ${brand.border}`,
            paddingLeft: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          {isBackdate ? (
            <div>
              <div
                style={{
                  fontSize: 11.5,
                  color: brand.textFaint,
                  textTransform: 'uppercase',
                  letterSpacing: 0.6,
                }}
              >
                Requested start
              </div>
              <div
                className="tnum"
                style={{ fontSize: 20, fontWeight: 650, color: brand.text, marginTop: 2 }}
              >
                {formatDate(item.requested_invoice_date)}
              </div>
              <div
                style={{
                  marginTop: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  color: severe ? brand.danger : brand.warning,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <WarningOutlined />
                {item.days_back} days back
              </div>
              <div style={{ fontSize: 12, color: brand.textDim, marginTop: 6 }}>
                Would end {formatDate(item.warranty_end_date)}
              </div>
            </div>
          ) : (
            <div>
              <div
                style={{
                  fontSize: 11.5,
                  color: brand.textFaint,
                  textTransform: 'uppercase',
                  letterSpacing: 0.6,
                }}
              >
                Proof of purchase
              </div>
              {/* The API returns the object-store KEY, not a fetchable URL, so
                  there is nothing honest to render as an image here. */}
              <div
                style={{
                  marginTop: 6,
                  minHeight: 88,
                  display: 'grid',
                  placeItems: 'center',
                  border: `1px dashed ${brand.border}`,
                  borderRadius: 8,
                  color: item.proof_file_key ? brand.textDim : brand.textFaint,
                  fontSize: 12,
                  gap: 4,
                  padding: 10,
                  textAlign: 'center',
                  overflowWrap: 'anywhere',
                }}
              >
                <FileImageOutlined />
                {item.proof_file_key ? (
                  <span className="mono" style={{ fontSize: 11 }}>
                    {item.proof_file_key}
                  </span>
                ) : (
                  'No proof attached'
                )}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
            <Button type="primary" icon={<CheckOutlined />} onClick={onApprove} style={{ flex: 1 }}>
              Approve
            </Button>
            <Button danger icon={<CloseOutlined />} onClick={onReject}>
              Reject
            </Button>
          </div>
        </div>
      </div>
    </SpotlightCard>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ minWidth: 0 }}>
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
      <div style={{ fontSize: 13, color: brand.text, marginTop: 2, overflowWrap: 'anywhere' }}>
        {children}
      </div>
    </div>
  );
}
