import { App, Button, Card, Descriptions, Input, Modal, Popconfirm, Space, Typography } from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import { getUnit, reactivateUnit, voidUnit } from '../api/units';
import type { LedgerEntry, UnitDetail } from '../api/types';
import { DataTable } from '../components/DataTable';
import { Mono } from '../components/Mono';
import { PageHeader } from '../components/PageHeader';
import { StatusDot } from '../components/StatusDot';
import { formatDateTime } from '../lib/format';
import { WebcamScanner } from './WebcamScanner';

export function UnitLookupPage() {
  const { message } = App.useApp();
  const [token, setToken] = useState('');
  const [unit, setUnit] = useState<UnitDetail | null>(null);
  const [looking, setLooking] = useState(false);
  const [acting, setActing] = useState(false);
  const [scanOpen, setScanOpen] = useState(false);

  const lookup = async (value: string) => {
    const t = value.trim();
    if (!t) return;
    setLooking(true);
    setUnit(null);
    try {
      setUnit(await getUnit(t));
    } catch (e) {
      message.error(apiErrorMessage(e, 'QR not found'));
    } finally {
      setLooking(false);
    }
  };

  const onScan = (text: string) => {
    setScanOpen(false);
    setToken(text);
    void lookup(text);
  };

  const doVoid = async () => {
    if (!unit) return;
    setActing(true);
    try {
      await voidUnit(unit.id);
      message.success('QR voided — it can no longer be scanned');
      await lookup(unit.token);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not void'));
    } finally {
      setActing(false);
    }
  };

  const doReactivate = async () => {
    if (!unit) return;
    setActing(true);
    try {
      const res = await reactivateUnit(unit.id);
      message.success(`Reactivated — reversed ${res.reversed_points} points`);
      await lookup(unit.token);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not reactivate'));
    } finally {
      setActing(false);
    }
  };

  return (
    <>
      <PageHeader
        title="QR Lookup"
        subtitle="Look up any QR by its token — see its status, who scanned it, and void or reactivate it."
      />
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          style={{ width: 460 }}
          placeholder="Enter / paste a QR token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          onSearch={lookup}
          loading={looking}
          enterButton="Look up"
          allowClear
        />
        <Button onClick={() => setScanOpen(true)}>Scan with webcam</Button>
      </Space>

      {unit && (
        <Card title="QR unit" className="sr-card" style={{ marginBottom: 16 }}>
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="Token" span={2}>
              <Mono value={unit.token} chars={40} />
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              <StatusDot status={unit.status} />
            </Descriptions.Item>
            <Descriptions.Item label="Product">{unit.product_name ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="Scanned by">
              {unit.claimed_by_user_id ? (
                <Space direction="vertical" size={0}>
                  <span>
                    {unit.claimed_by_name ?? '—'}
                    {unit.claimed_by_phone ? ` · ${unit.claimed_by_phone}` : ''}
                  </span>
                  <Mono value={unit.claimed_by_user_id} chars={40} />
                </Space>
              ) : (
                <Typography.Text type="secondary">Not yet scanned</Typography.Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Scanned at">
              {formatDateTime(unit.claimed_at)}
            </Descriptions.Item>
            <Descriptions.Item label="Batch">
              {unit.batch_id ? <Mono value={unit.batch_id} chars={40} /> : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="Created">{formatDateTime(unit.created_at)}</Descriptions.Item>
          </Descriptions>

          <Space style={{ marginTop: 16 }} wrap>
            {unit.status === 'active' && (
              <Popconfirm title="Void this QR so it can never be scanned?" onConfirm={doVoid}>
                <Button danger loading={acting}>
                  Void QR
                </Button>
              </Popconfirm>
            )}
            {unit.status === 'claimed' && (
              <Popconfirm
                title="Reactivate this QR and reverse its points?"
                onConfirm={doReactivate}
              >
                <Button type="primary" danger loading={acting}>
                  Reactivate (reverse points)
                </Button>
              </Popconfirm>
            )}
            {unit.status === 'void' && (
              <Typography.Text type="secondary">
                This QR is voided. Generate a new batch to replace it.
              </Typography.Text>
            )}
          </Space>

          <div style={{ marginTop: 16 }}>
            <Typography.Text type="secondary">Ledger history for this QR</Typography.Text>
            <DataTable<LedgerEntry>
              rowKey="id"
              dataSource={unit.history}
              emptyText="No history"
              columns={[
                { title: 'Type', dataIndex: 'type', render: (t: string) => t.replace(/_/g, ' ') },
                {
                  title: 'Amount',
                  dataIndex: 'amount',
                  render: (v: number) => <span className="tnum">{v}</span>,
                },
                { title: 'When', dataIndex: 'created_at', render: formatDateTime },
              ]}
            />
          </div>
        </Card>
      )}

      <Modal
        title="Scan QR"
        open={scanOpen}
        onCancel={() => setScanOpen(false)}
        footer={null}
        destroyOnClose
      >
        {scanOpen && <WebcamScanner onDecode={onScan} />}
      </Modal>
    </>
  );
}
