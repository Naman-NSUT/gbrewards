import {
  CheckOutlined,
  EditOutlined,
  PlusOutlined,
  StopOutlined,
  UndoOutlined,
} from '@ant-design/icons';
import {
  App,
  Button,
  Col,
  Descriptions,
  Divider,
  Drawer,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Switch,
} from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { Dealer, StaffInput, StaffRow } from '../api/types';
import { ConfirmWithReason } from '../components/ConfirmWithReason';
import { EmptyState } from '../components/EmptyState';
import { DetailSkeleton } from '../components/skeletons';
import { StatusTag } from '../components/StatusDot';
import {
  useCreateDealerStaff,
  useDealer,
  useDealerLedger,
  useDealerStaff,
  useReactivateDealer,
  useApproveDealer,
  useSuspendDealer,
  useUpdateDealerStaff,
} from '../hooks/useDealers';
import {
  formatAddress,
  formatDateTime,
  formatNumber,
  formatSigned,
  humanise,
  relativeTime,
} from '../lib/format';
import { descStyles } from '../lib/uiStyles';
import { brand } from '../theme';

/** Ledger rows carry ids, not names; the readable bits live in `metadata`. */
function metaString(meta: Record<string, unknown> | null | undefined, key: string): string | null {
  const value = meta?.[key];
  return typeof value === 'string' ? value : null;
}

export function DealerDrawer({
  dealerId,
  onClose,
  onEdit,
}: {
  dealerId: string | null;
  onClose: () => void;
  onEdit: (dealer: Dealer) => void;
}) {
  const { message } = App.useApp();
  const detail = useDealer(dealerId);
  const staff = useDealerStaff(dealerId);
  const ledger = useDealerLedger(dealerId, { limit: 15, offset: 0 });
  const suspend = useSuspendDealer();
  const reactivate = useReactivateDealer();
  const approve = useApproveDealer();
  const createStaff = useCreateDealerStaff();
  const updateStaff = useUpdateDealerStaff();

  const [suspending, setSuspending] = useState(false);
  const [addingStaff, setAddingStaff] = useState(false);
  const [staffForm] = Form.useForm<StaffInput>();

  const detailData = detail.data;
  const d = detailData?.dealer;
  const stats = detailData?.stats;
  const points = detailData?.points;

  const doSuspend = async (reason: string) => {
    if (!dealerId) return;
    try {
      await suspend.mutateAsync({ id: dealerId, reason });
      message.success('Dealer suspended. Their staff tokens stop working immediately.');
      setSuspending(false);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not suspend that dealer'));
    }
  };

  const doApprove = async () => {
    if (!dealerId) return;
    try {
      await approve.mutateAsync(dealerId);
      message.success('Shop verified. They can now redeem the points they have earned.');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not approve that dealer'));
    }
  };

  const doReactivate = async () => {
    if (!dealerId) return;
    try {
      await reactivate.mutateAsync(dealerId);
      message.success('Dealer reactivated');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not reactivate that dealer'));
    }
  };

  const addStaff = async () => {
    if (!dealerId) return;
    const values = await staffForm.validateFields();
    try {
      await createStaff.mutateAsync({ dealerId, body: values });
      message.success(`${values.name} can now sign in with ${values.phone}`);
      setAddingStaff(false);
      staffForm.resetFields();
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not add that staff login'));
    }
  };

  const toggleStaff = async (s: StaffRow, isActive: boolean) => {
    if (!dealerId) return;
    try {
      await updateStaff.mutateAsync({ dealerId, staffId: s.id, body: { is_active: isActive } });
      message.success(isActive ? `${s.name} re-enabled` : `${s.name} can no longer sign in`);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not update that staff login'));
    }
  };

  return (
    <Drawer
      open={dealerId !== null}
      onClose={onClose}
      width={720}
      destroyOnHidden
      title={
        d ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 650 }}>{d.name}</span>
            <span className="mono" style={{ fontSize: 12, color: brand.textFaint }}>
              {d.code}
            </span>
            <StatusTag status={d.status} />
          </div>
        ) : (
          'Dealer'
        )
      }
      extra={
        d ? (
          <div style={{ display: 'flex', gap: 8 }}>
            <Button icon={<EditOutlined />} onClick={() => onEdit(d)}>
              Edit
            </Button>
            {d.status === 'active' && (
              <Button danger icon={<StopOutlined />} onClick={() => setSuspending(true)}>
                Suspend
              </Button>
            )}
            {d.status === 'pending' && (
              <Button
                type="primary"
                icon={<CheckOutlined />}
                loading={approve.isPending}
                onClick={doApprove}
              >
                Approve shop
              </Button>
            )}
            {(d.status === 'suspended' || d.status === 'closed') && (
              <Button icon={<UndoOutlined />} loading={reactivate.isPending} onClick={doReactivate}>
                Reactivate
              </Button>
            )}
          </div>
        ) : null
      }
    >
      {detail.isLoading || !detailData || !d || !stats || !points ? (
        <DetailSkeleton rows={8} />
      ) : (
        <>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col span={24}>
              <div
                style={{
                  border: `1px solid ${brand.border}`,
                  borderRadius: 12,
                  padding: 16,
                  background: brand.surface,
                }}
              >
                <div style={{ fontSize: 12.5, color: brand.textDim }}>
                  Registered {formatNumber(stats.warranties_registered)}{' '}
                  {stats.warranties_registered === 1 ? 'sale' : 'sales'} in total
                  {stats.self_registrations > 0 && (
                    <>
                      {' · '}
                      <span style={{ color: brand.danger }}>
                        {formatNumber(stats.self_registrations)} registered by the customer
                        instead
                      </span>
                    </>
                  )}
                </div>
              </div>
            </Col>
            <Col xs={8}>
              <Metric label="Balance" value={formatNumber(points.balance)} />
            </Col>
            <Col xs={8}>
              <Metric label="Available" value={formatNumber(points.available)} />
            </Col>
            <Col xs={8}>
              <Metric
                label="Last sale"
                value={
                  stats.last_registration_at ? relativeTime(stats.last_registration_at) : 'never'
                }
              />
            </Col>
            <Col xs={8}>
              <Metric label="Self-registered" value={formatNumber(stats.self_registrations)} />
            </Col>
            <Col xs={8}>
              <Metric label="Voided" value={formatNumber(stats.warranties_voided)} />
            </Col>
          </Row>

          <Descriptions
            column={2}
            size="small"
            colon={false}
            styles={descStyles}
            items={[
              { key: 'phone', label: 'Phone', children: d.phone ?? '—' },
              { key: 'email', label: 'Email', children: d.email ?? '—' },
              { key: 'gst', label: 'GST', children: d.gst_number ?? '—' },
              { key: 'since', label: 'On programme since', children: formatDateTime(d.created_at) },
              {
                key: 'addr',
                label: 'Address',
                span: 2,
                children: formatAddress(d),
              },
            ]}
          />

          <Divider style={{ margin: '20px 0 12px' }} />
          <SectionTitle
            extra={
              <Button
                size="small"
                type="text"
                icon={<PlusOutlined />}
                onClick={() => {
                  staffForm.resetFields();
                  setAddingStaff(true);
                }}
              >
                Add login
              </Button>
            }
          >
            Staff logins
          </SectionTitle>
          {staff.isLoading ? (
            <DetailSkeleton rows={3} />
          ) : (staff.data ?? []).length === 0 ? (
            <EmptyState
              title="No logins yet"
              hint="Without a staff login this shop cannot register anything, and its compliance rate will stay at zero for reasons that are not their fault."
              height={140}
            />
          ) : (
            <div style={{ display: 'grid', gap: 6 }}>
              {(staff.data ?? []).map((s) => (
                <div
                  key={s.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    padding: '10px 12px',
                    border: `1px solid ${brand.border}`,
                    borderRadius: 8,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13.5, color: brand.text }}>
                      {s.name}
                      {s.role === 'owner' && (
                        <span
                          style={{
                            fontSize: 10.5,
                            color: brand.accent,
                            border: `1px solid ${brand.accent}44`,
                            borderRadius: 4,
                            padding: '1px 5px',
                            marginLeft: 8,
                          }}
                        >
                          OWNER
                        </span>
                      )}
                    </div>
                    <div className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
                      {s.phone} ·{' '}
                      {s.last_active_at ? relativeTime(s.last_active_at) : 'never signed in'}
                    </div>
                  </div>
                  <Switch
                    checked={s.is_active}
                    size="small"
                    loading={updateStaff.isPending}
                    onChange={(checked) => toggleStaff(s, checked)}
                  />
                </div>
              ))}
            </div>
          )}

          <Divider style={{ margin: '20px 0 12px' }} />
          <SectionTitle>Recent points</SectionTitle>
          {(ledger.data?.items ?? []).length === 0 ? (
            <EmptyState title="No point movements yet" height={120} />
          ) : (
            <div style={{ display: 'grid', gap: 6 }}>
              {(ledger.data?.items ?? []).map((e) => (
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
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, color: brand.text }}>{humanise(e.type)}</div>
                    <div style={{ fontSize: 11.5, color: brand.textFaint }}>
                      {formatDateTime(e.created_at)}
                      {metaString(e.metadata, 'serial') && (
                        <span className="mono">
                          {' '}
                          · {metaString(e.metadata, 'serial')?.slice(0, 12)}…
                        </span>
                      )}
                      {e.balance_after !== null &&
                        e.balance_after !== undefined &&
                        ` · balance ${e.balance_after}`}
                    </div>
                    {e.reason && (
                      <div style={{ fontSize: 12, color: brand.textDim, marginTop: 2 }}>
                        “{e.reason}”
                      </div>
                    )}
                  </div>
                  <span
                    className="tnum"
                    style={{
                      fontSize: 14.5,
                      fontWeight: 650,
                      color: e.amount > 0 ? brand.success : brand.danger,
                    }}
                  >
                    {formatSigned(e.amount)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <ConfirmWithReason
        open={suspending}
        title="Suspend this dealer"
        confirmText="Suspend"
        danger
        loading={suspend.isPending}
        description="Every staff login under this shop stops working at once, including tokens already issued. Existing warranties are untouched."
        onCancel={() => setSuspending(false)}
        onConfirm={doSuspend}
      />

      <Modal
        open={addingStaff}
        title="Add a staff login"
        okText="Create login"
        confirmLoading={createStaff.isPending}
        onOk={addStaff}
        onCancel={() => setAddingStaff(false)}
        destroyOnHidden
        width={440}
      >
        <Form form={staffForm} layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item
            name="name"
            label="Name"
            rules={[{ required: true, message: 'Enter their name' }]}
          >
            <Input placeholder="Ravi Kumar" />
          </Form.Item>
          <Form.Item
            name="phone"
            label="Mobile number"
            rules={[{ required: true, message: 'They sign in with this number' }]}
            extra="They receive a one-time code on this number to sign in — no password is set."
          >
            <Input className="mono" placeholder="+91 98765 43210" />
          </Form.Item>
          <Form.Item name="role" label="Role" initialValue="staff">
            <Select
              options={[
                { label: 'Staff — registers sales', value: 'staff' },
                { label: 'Owner — also requests redemptions', value: 'owner' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ border: `1px solid ${brand.border}`, borderRadius: 10, padding: '12px 14px' }}>
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
      <div
        className="tnum"
        style={{ fontSize: 19, fontWeight: 650, marginTop: 4, color: brand.text }}
      >
        {value}
      </div>
    </div>
  );
}
