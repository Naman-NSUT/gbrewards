import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { App, Button, Descriptions, Divider, Drawer, Form, Input, Switch, Timeline } from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { LedgerEntry, WarrantyEvent } from '../api/types';
import { ConfirmWithReason } from '../components/ConfirmWithReason';
import { EmptyState } from '../components/EmptyState';
import { Mono } from '../components/Mono';
import { DetailSkeleton } from '../components/skeletons';
import { StatusTag } from '../components/StatusDot';
import { statusColor } from '../lib/statusColors';
import { useUpdateWarrantyCustomer, useVoidWarranty, useWarranty } from '../hooks/useWarranties';
import { formatDate, formatDateTime, formatSigned, humanise } from '../lib/format';
import { descStyles } from '../lib/uiStyles';
import { brand } from '../theme';

/** The ledger row carries ids, not names; anything readable is in `metadata`. */
function metaString(meta: Record<string, unknown> | null | undefined, key: string): string | null {
  const value = meta?.[key];
  return typeof value === 'string' ? value : null;
}

export function WarrantyDrawer({
  warrantyId,
  onClose,
}: {
  warrantyId: string | null;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  const detail = useWarranty(warrantyId);
  const voidWarranty = useVoidWarranty();
  const updateCustomer = useUpdateWarrantyCustomer();
  const [voiding, setVoiding] = useState(false);
  const [clawback, setClawback] = useState(true);
  const [editing, setEditing] = useState(false);
  const [form] = Form.useForm();

  const detailData = detail.data;
  const w = detailData?.warranty;

  const doVoid = async (reason: string) => {
    if (!warrantyId) return;
    try {
      const result = await voidWarranty.mutateAsync({ id: warrantyId, reason, clawback });
      // The response is the warranty as it now stands; the reversal, if any, is
      // a new row in its own ledger.
      const reversed = result.ledger_entries
        .filter((e) => e.type === 'registration_reversal')
        .reduce((sum, e) => sum + Math.abs(e.amount), 0);
      message.success(
        reversed > 0
          ? `Voided. ${reversed} points reversed as a compensating debit.`
          : 'Voided. No points had been credited.',
      );
      setVoiding(false);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not void this warranty'));
    }
  };

  const saveCustomer = async (reason: string) => {
    if (!warrantyId) return;
    try {
      const values = form.getFieldsValue();
      await updateCustomer.mutateAsync({ id: warrantyId, patch: { ...values, reason } });
      message.success('Customer details updated');
      setEditing(false);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not update the customer'));
    }
  };

  return (
    <Drawer
      open={warrantyId !== null}
      onClose={onClose}
      width={760}
      destroyOnHidden
      title={
        w ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {/* Nothing registered since the serial went away carries one, and
                the invoice number is what identifies that sale instead — a bare
                dash would leave support nothing to read back down the phone. */}
            {w.serial ? (
              <Mono value={w.serial} chars={20} size={13} />
            ) : (
              <span style={{ fontSize: 13, color: brand.text }}>
                {w.invoice_ref ? `Invoice ${w.invoice_ref}` : '—'}
              </span>
            )}
            <StatusTag status={w.status} />
          </div>
        ) : (
          'Warranty'
        )
      }
      extra={
        w && w.stored_status !== 'voided' ? (
          <Button danger icon={<DeleteOutlined />} onClick={() => setVoiding(true)}>
            Void
          </Button>
        ) : null
      }
    >
      {detail.isLoading || !detailData || !w ? (
        <DetailSkeleton rows={8} />
      ) : (
        <>
          <Descriptions
            column={2}
            size="small"
            colon={false}
            styles={descStyles}
            items={[
              { key: 'model', label: 'Model', children: w.model_name ?? '—' },
              { key: 'months', label: 'Cover', children: `${w.warranty_months} months` },
              { key: 'start', label: 'Starts', children: formatDate(w.warranty_start_date) },
              {
                key: 'end',
                label: 'Ends',
                children: (
                  <span style={{ color: detailData.is_expired ? brand.textFaint : undefined }}>
                    {formatDate(w.warranty_end_date)}
                    {detailData.is_expired && ' · expired'}
                  </span>
                ),
              },
              {
                key: 'backdate',
                label: 'Backdated',
                children:
                  w.backdate_days > 0 ? (
                    <span style={{ color: brand.warning }}>{w.backdate_days} days</span>
                  ) : (
                    'No'
                  ),
              },
              { key: 'source', label: 'Source', children: humanise(w.source) },
              {
                key: 'dealer',
                label: 'Dealer',
                children: detailData.dealer
                  ? `${detailData.dealer.name} (${detailData.dealer.code})`
                  : '—',
              },
              {
                key: 'staff',
                label: 'Registered by',
                children: detailData.staff?.name ?? '—',
              },
              { key: 'invoice', label: 'Invoice', children: w.invoice_ref ?? '—' },
              {
                key: 'invoice_date',
                label: 'Invoice date',
                children: formatDate(w.invoice_date),
              },
              {
                key: 'verified',
                label: 'Unit verified',
                children: w.unit_unverified ? (
                  <span style={{ color: brand.warning }}>No — allocation only</span>
                ) : (
                  'Yes'
                ),
              },
              {
                key: 'registered',
                label: 'Registered at',
                children: formatDateTime(w.registered_at),
              },
            ]}
          />

          {w.stored_status === 'voided' && detailData.void_reason && (
            <div
              style={{
                marginTop: 14,
                padding: '10px 14px',
                borderRadius: 8,
                border: `1px solid ${brand.danger}44`,
                background: `${brand.danger}12`,
                fontSize: 13,
              }}
            >
              <span style={{ color: brand.danger, fontWeight: 600 }}>Voided</span>{' '}
              <span style={{ color: brand.textDim }}>{formatDateTime(detailData.voided_at)}</span>
              <div style={{ color: brand.text, marginTop: 4 }}>{detailData.void_reason}</div>
            </div>
          )}

          <Divider style={{ margin: '20px 0 12px' }} />
          <SectionTitle
            extra={
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => {
                  form.setFieldsValue({
                    name: detailData.customer.name,
                    phone: detailData.customer.phone,
                    email: detailData.customer.email,
                    address: detailData.customer.address,
                    city: detailData.customer.city,
                    state: detailData.customer.state,
                    pincode: detailData.customer.pincode,
                  });
                  setEditing(true);
                }}
              >
                Edit
              </Button>
            }
          >
            Customer
          </SectionTitle>
          <Descriptions
            column={2}
            size="small"
            colon={false}
            styles={descStyles}
            items={[
              { key: 'name', label: 'Name', children: detailData.customer.name },
              {
                key: 'phone',
                label: 'Mobile',
                children: (
                  <span>
                    <span className="mono">{detailData.customer.phone}</span>
                    {detailData.customer.is_phone_verified && (
                      <span style={{ color: brand.success, fontSize: 11.5, marginLeft: 8 }}>
                        verified
                      </span>
                    )}
                  </span>
                ),
              },
              { key: 'email', label: 'Email', children: detailData.customer.email ?? '—' },
              { key: 'city', label: 'City', children: detailData.customer.city ?? '—' },
              {
                key: 'address',
                label: 'Address',
                span: 2,
                children: detailData.customer.address ?? '—',
              },
            ]}
          />

          <Divider style={{ margin: '20px 0 12px' }} />
          <SectionTitle>History</SectionTitle>
          <EventTimeline events={detailData.events} />

          <Divider style={{ margin: '20px 0 12px' }} />
          <SectionTitle>Points</SectionTitle>
          <LedgerList entries={detailData.ledger_entries} />
        </>
      )}

      <ConfirmWithReason
        open={voiding}
        title="Void this warranty"
        confirmText="Void warranty"
        danger
        loading={voidWarranty.isPending}
        description="The customer loses cover from this record, and the invoice number is freed so that sale can be registered again — as is the serial, on a warranty old enough to have one. Nothing is deleted; the void is recorded as its own event."
        extra={
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 12px',
              border: `1px solid ${brand.border}`,
              borderRadius: 8,
            }}
          >
            <Switch checked={clawback} onChange={setClawback} size="small" />
            <div style={{ fontSize: 12.5 }}>
              <div style={{ color: brand.text }}>Reverse the points this paid</div>
              <div style={{ color: brand.textFaint }}>
                Writes a compensating debit. The balance may go negative — that is a debt you can
                chase, where a skipped clawback is a loss you cannot.
              </div>
            </div>
          </div>
        }
        onCancel={() => setVoiding(false)}
        onConfirm={doVoid}
      />

      <ConfirmWithReason
        open={editing}
        title="Edit customer details"
        confirmText="Save changes"
        loading={updateCustomer.isPending}
        description="Editing a customer on a live warranty is audited. Correct a typo, do not repoint the record at a different buyer."
        extra={
          <Form form={form} layout="vertical" size="small">
            <Form.Item name="name" label="Name" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="phone" label="Mobile" rules={[{ required: true }]}>
              <Input className="mono" />
            </Form.Item>
            <Form.Item name="email" label="Email">
              <Input />
            </Form.Item>
            <Form.Item name="address" label="Address">
              <Input />
            </Form.Item>
            <div style={{ display: 'flex', gap: 10 }}>
              <Form.Item name="city" label="City" style={{ flex: 1 }}>
                <Input />
              </Form.Item>
              <Form.Item name="state" label="State" style={{ flex: 1 }}>
                <Input />
              </Form.Item>
              <Form.Item name="pincode" label="PIN" style={{ width: 100 }}>
                <Input />
              </Form.Item>
            </div>
          </Form>
        }
        onCancel={() => setEditing(false)}
        onConfirm={saveCustomer}
      />
    </Drawer>
  );
}

function SectionTitle({ children, extra }: { children: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 10,
      }}
    >
      <span
        style={{
          fontSize: 12,
          textTransform: 'uppercase',
          letterSpacing: 0.7,
          color: brand.textDim,
          fontWeight: 550,
        }}
      >
        {children}
      </span>
      {extra}
    </div>
  );
}

function EventTimeline({ events }: { events: WarrantyEvent[] }) {
  if (events.length === 0) return <EmptyState title="No events" height={100} />;
  return (
    <Timeline
      items={events.map((e) => ({
        color: statusColor(e.to_status ?? 'active'),
        children: (
          <div>
            <div style={{ fontSize: 13.5, color: brand.text }}>
              {humanise(e.event)}
              {e.from_status && e.to_status && (
                <span style={{ color: brand.textFaint, fontSize: 12, marginLeft: 8 }}>
                  {humanise(e.from_status)} → {humanise(e.to_status)}
                </span>
              )}
            </div>
            <div style={{ fontSize: 11.5, color: brand.textFaint }}>
              {formatDateTime(e.created_at)} · {e.actor_name ?? humanise(e.actor_type)}
            </div>
            {e.reason && (
              <div style={{ fontSize: 12.5, color: brand.textDim, marginTop: 4 }}>“{e.reason}”</div>
            )}
          </div>
        ),
      }))}
    />
  );
}

function LedgerList({ entries }: { entries: LedgerEntry[] }) {
  if (entries.length === 0) {
    return <EmptyState title="No points moved on this warranty" height={100} />;
  }
  return (
    <div style={{ display: 'grid', gap: 6 }}>
      {entries.map((e) => (
        <div
          key={e.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 12px',
            border: `1px solid ${brand.border}`,
            borderRadius: 8,
          }}
        >
          <div>
            <div style={{ fontSize: 13, color: brand.text }}>{humanise(e.type)}</div>
            <div style={{ fontSize: 11.5, color: brand.textFaint }}>
              {formatDateTime(e.created_at)}
              {e.balance_after !== null &&
                e.balance_after !== undefined &&
                ` · balance ${e.balance_after}`}
            </div>
            {e.reason && (
              <div style={{ fontSize: 12, color: brand.textDim, marginTop: 2 }}>“{e.reason}”</div>
            )}
            {metaString(e.metadata, 'serial') && (
              <div className="mono" style={{ fontSize: 11, color: brand.textFaint, marginTop: 2 }}>
                {metaString(e.metadata, 'serial')}
              </div>
            )}
          </div>
          <span
            className="tnum"
            style={{
              fontSize: 15,
              fontWeight: 650,
              color: e.amount > 0 ? brand.success : brand.danger,
            }}
          >
            {formatSigned(e.amount)}
          </span>
        </div>
      ))}
    </div>
  );
}
