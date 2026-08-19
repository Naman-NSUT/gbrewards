import { DollarOutlined, LockOutlined, ToolOutlined } from '@ant-design/icons';
import { Alert, App, Button, Col, Form, Input, InputNumber, Modal, Radio, Row, Select } from 'antd';
import type { TableColumnsType } from 'antd';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { apiErrorMessage } from '../api/client';
import type { LedgerEntry, PointRateRow } from '../api/types';
import type { ProductRateRow } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';
import { SpotlightCard } from '../components/SpotlightCard';
import { useAdjustDealerPoints, useDealerLedger, useDealers } from '../hooks/useDealers';
import { useProductRates, usePointRates, useSetPointRate } from '../hooks/usePoints';
import { formatDateTime, formatNumber, formatSigned, humanise } from '../lib/format';
import { brand } from '../theme';

const PAGE_SIZE = 25;

/** Ledger rows carry ids, not names; the readable bits live in `metadata`. */
function metaString(meta: Record<string, unknown> | null | undefined, key: string): string | null {
  const value = meta?.[key];
  return typeof value === 'string' ? value : null;
}

export function PointsPage() {
  const { message } = App.useApp();
  const { isOwner } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [rateOpen, setRateOpen] = useState(false);
  const [page, setPage] = useState(1);

  // The ledger is per dealer on the server — there is no programme-wide feed —
  // so the dealer picker is the ledger's subject, not a filter over it.
  const dealerId = searchParams.get('dealer');
  const setDealerId = (id: string | undefined) => {
    const next = new URLSearchParams(searchParams);
    if (id) next.set('dealer', id);
    else next.delete('dealer');
    setSearchParams(next, { replace: true });
    setPage(1);
  };

  const adjustOpen = searchParams.get('adjust') === '1';
  const setAdjustOpen = (open: boolean) => {
    const next = new URLSearchParams(searchParams);
    if (open) next.set('adjust', '1');
    else next.delete('adjust');
    setSearchParams(next, { replace: true });
  };

  const productRates = useProductRates();
  const [rateProduct, setRateProduct] = useState<ProductRateRow | null>(null);
  const rates = usePointRates({ limit: 50, offset: 0 });
  const setRate = useSetPointRate();
  const ledger = useDealerLedger(dealerId, {
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  const [rateForm] = Form.useForm<{
    product_id: string;
    points_per_registration: number;
    note: string;
  }>();
  const rows = productRates.data ?? [];
  const priced = rows.filter((r) => r.points_per_registration !== null);
  const unpriced = rows.filter((r) => r.points_per_registration === null && r.is_active);

  const submitRate = async () => {
    const values = await rateForm.validateFields();
    try {
      const next = await setRate.mutateAsync(values);
      const name = rows.find((r) => r.product_id === values.product_id)?.product_name ?? 'product';
      message.success(
        `Registering a ${name} is now worth ${next.points_per_registration} points. ` +
          'Nothing already earned changed.',
      );
      setRateOpen(false);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not change the rate'));
    }
  };

  const current = rateProduct;
  const history = rates.data?.items ?? [];
  const points = ledger.data?.points;

  const historyColumns: TableColumnsType<PointRateRow> = [
    {
      title: 'Points per registration',
      dataIndex: 'points_per_registration',
      width: 190,
      render: (v: number, r) => (
        <span
          className="tnum"
          style={{
            fontSize: 15,
            fontWeight: 650,
            color: r.effective_to === null ? brand.accent : brand.text,
          }}
        >
          {v}
        </span>
      ),
    },
    {
      title: 'In force',
      dataIndex: 'effective_from',
      render: (from: string, r) => (
        <span style={{ fontSize: 12.5, color: brand.textDim }}>
          {formatDateTime(from)} →{' '}
          {r.effective_to ? (
            formatDateTime(r.effective_to)
          ) : (
            <span style={{ color: brand.success }}>now</span>
          )}
        </span>
      ),
    },
    {
      // The server returns the admin's id, not a name.
      title: 'Set by',
      dataIndex: 'created_by_admin_id',
      width: 160,
      render: (v: string | null) => (
        <span className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
          {v ? `${v.slice(0, 8)}…` : 'system'}
        </span>
      ),
    },
    {
      title: 'Note',
      dataIndex: 'note',
      render: (v: string | null) => (
        <span style={{ fontSize: 12.5, color: brand.textDim }}>{v ?? '—'}</span>
      ),
    },
  ];

  const ledgerColumns: TableColumnsType<LedgerEntry> = [
    {
      title: 'Type',
      dataIndex: 'type',
      width: 190,
      render: (t: string) => (
        <span style={{ fontSize: 12.5, color: brand.textDim }}>{humanise(t)}</span>
      ),
    },
    {
      title: 'Amount',
      dataIndex: 'amount',
      align: 'right',
      width: 110,
      render: (v: number) => (
        <span
          className="tnum"
          style={{ fontWeight: 650, color: v > 0 ? brand.success : brand.danger }}
        >
          {formatSigned(v)}
        </span>
      ),
    },
    {
      title: 'Balance after',
      dataIndex: 'balance_after',
      align: 'right',
      width: 130,
      render: (v: number | null | undefined) => (
        <span className="tnum" style={{ fontSize: 12.5, color: brand.textFaint }}>
          {v === null || v === undefined ? '—' : formatNumber(v)}
        </span>
      ),
    },
    {
      title: 'Cause',
      dataIndex: 'warranty_id',
      width: 210,
      render: (warrantyId: string | null, e) => {
        const serial = metaString(e.metadata, 'serial');
        if (warrantyId) {
          return (
            <span className="mono" style={{ fontSize: 12, color: brand.textDim }}>
              {serial ? `${serial.slice(0, 16)}…` : `${warrantyId.slice(0, 8)}…`}
            </span>
          );
        }
        if (e.redemption_id) {
          return <span style={{ fontSize: 12.5, color: brand.textDim }}>Redemption</span>;
        }
        return <span style={{ fontSize: 12.5, color: brand.warning }}>Manual adjustment</span>;
      },
    },
    {
      title: 'Reason',
      dataIndex: 'reason',
      render: (v: string | null) => (
        <div style={{ fontSize: 12.5, color: brand.textDim, maxWidth: 300 }}>{v ?? '—'}</div>
      ),
    },
    {
      title: 'When',
      dataIndex: 'created_at',
      width: 165,
      render: (v: string) => (
        <span style={{ fontSize: 12, color: brand.textFaint }}>{formatDateTime(v)}</span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Points"
        subtitle="Balances are derived by summing a dealer's ledger. Nothing is ever edited — corrections are new rows."
        extra={
          <div style={{ display: 'flex', gap: 10 }}>
            <Button icon={<ToolOutlined />} onClick={() => setAdjustOpen(true)}>
              Manual adjustment
            </Button>
            <Button
              type="primary"
              icon={isOwner ? <DollarOutlined /> : <LockOutlined />}
              disabled={!isOwner}
              title={isOwner ? undefined : 'Only an owner can change the rate'}
              onClick={() => {
                setRateProduct(null);
                rateForm.resetFields();
                setRateOpen(true);
              }}
            >
              Set product rate
            </Button>
          </div>
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} lg={8}>
          <SpotlightCard style={{ padding: 20, height: '100%' }}>
            <div
              style={{
                fontSize: 11.5,
                color: brand.textDim,
                textTransform: 'uppercase',
                letterSpacing: 0.7,
              }}
            >
              Products priced
            </div>
            <div
              className="tnum"
              style={{
                fontSize: 44,
                fontWeight: 700,
                letterSpacing: -1.4,
                color: brand.accent,
                marginTop: 6,
                lineHeight: 1.1,
              }}
            >
              {productRates.isLoading ? '—' : `${priced.length}/${rows.length}`}
            </div>
            <div style={{ fontSize: 13, color: brand.textDim }}>
              products with a registration rate
            </div>
            {priced.length > 0 && (
              <div style={{ fontSize: 12, color: brand.textFaint, marginTop: 8 }}>
                {priced.length === 1
                  ? '1 product pays points on registration'
                  : `${priced.length} products pay points on registration`}
              </div>
            )}
            {unpriced.length > 0 && !productRates.isLoading && (
              <Alert
                style={{ marginTop: 12 }}
                type="warning"
                showIcon
                message={`${unpriced.length} active product${unpriced.length === 1 ? '' : 's'} unpriced`}
                description="Sales on these are recorded correctly, but the dealer earns nothing for them."
              />
            )}
          </SpotlightCard>
        </Col>

        <Col xs={24} lg={16}>
          <SpotlightCard style={{ padding: 20, height: '100%' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 12,
                flexWrap: 'wrap',
                marginBottom: 14,
              }}
            >
              <span style={{ fontSize: 13, color: brand.textDim }}>
                Balances are per dealer — pick one to read its ledger
              </span>
              <DealerSelect
                value={dealerId ?? undefined}
                onChange={setDealerId}
                placeholder="Search by name or code"
                width={260}
              />
            </div>
            {points ? (
              <Row gutter={[12, 12]}>
                <Col xs={12} md={6}>
                  <Metric label="Balance" value={formatNumber(points.balance)} tone={brand.accent} />
                </Col>
                <Col xs={12} md={6}>
                  <Metric label="Pending holds" value={formatNumber(points.pending)} />
                </Col>
                <Col xs={12} md={6}>
                  <Metric
                    label="Available"
                    value={formatNumber(points.available)}
                    tone={brand.success}
                  />
                </Col>
                <Col xs={12} md={6}>
                  <Metric label="Earned ever" value={formatNumber(points.total_earned)} />
                </Col>
              </Row>
            ) : (
              <EmptyState
                title="No dealer selected"
                hint="The server keeps one ledger per dealer, so there is no programme-wide total to show here honestly."
                height={130}
              />
            )}
          </SpotlightCard>
        </Col>
      </Row>

      <SectionTitle>Rate history</SectionTitle>
      <div style={{ marginBottom: 24 }}>
        <DataTable<PointRateRow>
          rowKey="id"
          loading={rates.isLoading}
          dataSource={history}
          columns={historyColumns}
          emptyText="No rate has ever been set"
        />
      </div>

      <SectionTitle>
        {ledger.data ? `Ledger — ${ledger.data.dealer.name}` : 'Ledger'}
      </SectionTitle>
      {dealerId === null ? (
        <SpotlightCard style={{ padding: 24 }}>
          <EmptyState
            title="Pick a dealer to see their point movements"
            hint="Every credit, reversal, redemption debit and manual adjustment for that shop, newest first."
            height={180}
          />
        </SpotlightCard>
      ) : (
        <DataTable<LedgerEntry>
          rowKey="id"
          loading={ledger.isLoading}
          dataSource={ledger.data?.items ?? []}
          columns={ledgerColumns}
          total={ledger.data?.total}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
          emptyText="No point movements for this dealer"
        />
      )}

      <Modal
        open={rateOpen}
        title="Set a product\u2019s registration rate"
        okText="Open the new rate"
        confirmLoading={setRate.isPending}
        onOk={submitRate}
        onCancel={() => setRateOpen(false)}
        destroyOnHidden
        width={520}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="Nothing already earned changes"
          description="This closes the current rate and opens a new one. Every ledger row keeps pointing at the version that priced it, so a dealer who earned 50 per registration last month still shows 50 — the answer to “why is this row 50?” stays available forever."
        />
        <Form form={rateForm} layout="vertical">
          <Form.Item
            name="product_id"
            label="Product"
            rules={[{ required: true, message: 'Pick the product to price' }]}
            extra="Registration points are set per product, like worker scan points."
          >
            <Select
              size="large"
              showSearch
              optionFilterProp="label"
              placeholder="Choose a product"
              loading={productRates.isLoading}
              onChange={(id: string) => {
                const row = rows.find((r) => r.product_id === id) ?? null;
                setRateProduct(row);
                rateForm.setFieldValue(
                  'points_per_registration',
                  row?.points_per_registration ?? 50,
                );
              }}
              options={rows.map((r) => ({
                value: r.product_id,
                label: r.product_name,
                // Unpriced active products are the ones needing attention.
                title:
                  r.points_per_registration === null
                    ? 'No rate set'
                    : `Currently ${r.points_per_registration}`,
              }))}
            />
          </Form.Item>
          {current && (
            <Alert
              type={current.points_per_registration === null ? 'warning' : 'info'}
              showIcon
              style={{ marginBottom: 16 }}
              message={
                current.points_per_registration === null
                  ? `${current.product_name} has no rate — registrations earn nothing today`
                  : `${current.product_name} currently pays ${current.points_per_registration}`
              }
              description={`Warranty runs ${current.warranty_months ?? '—'} months.`}
            />
          )}
          <Form.Item
            name="points_per_registration"
            label="Points per registration"
            rules={[{ required: true, message: 'Set the new value' }]}
          >
            <InputNumber min={0} style={{ width: '100%' }} size="large" />
          </Form.Item>
          <Form.Item
            name="note"
            label="Why"
            extra="Recorded against the rate version, not just the audit log."
          >
            <Input.TextArea rows={2} maxLength={300} showCount />
          </Form.Item>
        </Form>
      </Modal>

      <AdjustModal
        open={adjustOpen}
        onClose={() => setAdjustOpen(false)}
        defaultDealerId={dealerId ?? undefined}
      />
    </>
  );
}

function AdjustModal({
  open,
  onClose,
  defaultDealerId,
}: {
  open: boolean;
  onClose: () => void;
  defaultDealerId?: string;
}) {
  const { message } = App.useApp();
  const adjust = useAdjustDealerPoints();
  const [form] = Form.useForm<{
    dealer_id: string;
    direction: 'credit' | 'debit';
    amount: number;
    reason: string;
  }>();

  const submit = async () => {
    const values = await form.validateFields();
    const signed = values.direction === 'debit' ? -Math.abs(values.amount) : Math.abs(values.amount);
    try {
      // The adjustment endpoint hangs off the dealer: the id is in the path,
      // and the body is only {amount, reason}.
      const result = await adjust.mutateAsync({
        dealerId: values.dealer_id,
        amount: signed,
        reason: values.reason,
      });
      message.success(`Adjusted. New balance: ${formatNumber(result.points.balance)} points.`);
      form.resetFields();
      onClose();
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not record that adjustment'));
    }
  };

  return (
    <Modal
      open={open}
      title="Manual point adjustment"
      okText="Record adjustment"
      confirmLoading={adjust.isPending}
      onOk={submit}
      onCancel={onClose}
      destroyOnHidden
      afterOpenChange={(o) => {
        if (o) {
          form.resetFields();
          if (defaultDealerId) form.setFieldValue('dealer_id', defaultDealerId);
        }
      }}
      width={520}
    >
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="This writes a new ledger row, it does not edit anything"
        description="Use it for goodwill credits and corrections you cannot express as a void. The reason is mandatory and shows on the dealer's own statement."
      />
      <Form form={form} layout="vertical">
        <Form.Item name="dealer_id" label="Dealer" rules={[{ required: true, message: 'Pick the dealer' }]}>
          <DealerSelect placeholder="Search by name or code" />
        </Form.Item>
        <Form.Item name="direction" label="Direction" initialValue="credit">
          <Radio.Group>
            <Radio.Button value="credit">Credit (add points)</Radio.Button>
            <Radio.Button value="debit">Debit (take points away)</Radio.Button>
          </Radio.Group>
        </Form.Item>
        <Form.Item name="amount" label="Points" rules={[{ required: true, message: 'How many points?' }]}>
          <InputNumber min={1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item
          name="reason"
          label="Reason"
          rules={[
            { required: true, message: 'A reason is required' },
            { min: 5, message: 'Write enough that this makes sense in a year' },
          ]}
        >
          <Input.TextArea rows={3} maxLength={400} showCount />
        </Form.Item>
      </Form>
    </Modal>
  );
}

/** Type-ahead dealer picker, shared by the ledger subject and the adjustment form. */
function DealerSelect({
  value,
  onChange,
  placeholder,
  width,
}: {
  value?: string;
  onChange?: (value: string | undefined) => void;
  placeholder?: string;
  width?: number;
}) {
  const [search, setSearch] = useState('');
  const dealers = useDealers({ q: search || undefined, limit: 20, offset: 0 });

  return (
    <Select
      showSearch
      allowClear
      value={value}
      onChange={onChange}
      onSearch={setSearch}
      filterOption={false}
      loading={dealers.isLoading}
      placeholder={placeholder}
      style={{ width: width ?? '100%' }}
      options={(dealers.data?.items ?? []).map((d) => ({
        label: `${d.name} · ${d.code}`,
        value: d.id,
      }))}
      notFoundContent={dealers.isLoading ? 'Searching…' : 'No dealers match'}
    />
  );
}

function SectionTitle({ children, extra }: { children: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12,
        gap: 12,
        flexWrap: 'wrap',
      }}
    >
      <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: -0.2, color: brand.text }}>
        {children}
      </span>
      {extra}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div style={{ border: `1px solid ${brand.border}`, borderRadius: 10, padding: '14px 16px' }}>
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
        style={{ fontSize: 22, fontWeight: 650, marginTop: 4, color: tone ?? brand.text }}
      >
        {value}
      </div>
    </div>
  );
}
