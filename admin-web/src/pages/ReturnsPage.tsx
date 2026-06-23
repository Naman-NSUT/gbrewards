import { App, Button, Card, Descriptions, Input, Modal, Popconfirm, Space, Typography } from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import { getUnit, reactivateUnit } from '../api/units';
import type { LedgerEntry, UnitDetail } from '../api/types';
import { DataTable } from '../components/DataTable';
import { Mono } from '../components/Mono';
import { PageHeader } from '../components/PageHeader';
import { StatusDot } from '../components/StatusDot';
import { formatDateTime } from '../lib/format';
import { WebcamScanner } from './WebcamScanner';

export function ReturnsPage() {
  const { message } = App.useApp();
  const [token, setToken] = useState('');
  const [unit, setUnit] = useState<UnitDetail | null>(null);
  const [looking, setLooking] = useState(false);
  const [reactivating, setReactivating] = useState(false);
  const [scanOpen, setScanOpen] = useState(false);

  const lookup = async (value: string) => {
    const t = value.trim();
    if (!t) return;
    setLooking(true);
    setUnit(null);
    try {
      setUnit(await getUnit(t));
    } catch (e) {
      message.error(apiErrorMessage(e, 'Unit not found'));
    } finally {
      setLooking(false);
    }
  };

  const onScan = (text: string) => {
    setScanOpen(false);
    setToken(text);
    void lookup(text);
  };

  const reactivate = async () => {
    if (!unit) return;
    setReactivating(true);
    try {
      const res = await reactivateUnit(unit.id);
      message.success(`Reactivated — reversed ${res.reversed_points} points`);
      await lookup(unit.token);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not reactivate'));
    } finally {
      setReactivating(false);
    }
  };

  return (
    <>
      <PageHeader title="Returns" subtitle="Reactivate returned units and reverse their points." />
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          style={{ width: 420 }}
          placeholder="Enter / paste a QR token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          onSearch={lookup}
          loading={looking}
          enterButton="Look up"
        />
        <Button onClick={() => setScanOpen(true)}>Scan with webcam</Button>
      </Space>

      {unit && (
        <Card title="Unit" className="sr-card" style={{ marginBottom: 16 }}>
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="Token" span={2}>
              <Mono value={unit.token} chars={40} />
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              <StatusDot status={unit.status} />
            </Descriptions.Item>
            <Descriptions.Item label="Claimed at">{formatDateTime(unit.claimed_at)}</Descriptions.Item>
          </Descriptions>

          <div style={{ marginTop: 16 }}>
            {unit.status === 'claimed' ? (
              <Popconfirm
                title="Reactivate this unit and reverse its points?"
                onConfirm={reactivate}
              >
                <Button type="primary" danger loading={reactivating}>
                  Reactivate (reverse points)
                </Button>
              </Popconfirm>
            ) : (
              <Typography.Text type="secondary">
                Only claimed units can be reactivated.
              </Typography.Text>
            )}
          </div>

          <div style={{ marginTop: 16 }}>
            <DataTable<LedgerEntry>
              rowKey="id"
              dataSource={unit.history}
              emptyText="No history"
              columns={[
                { title: 'Type', dataIndex: 'type', render: (t: string) => t.replace(/_/g, ' ') },
                { title: 'Amount', dataIndex: 'amount', render: (v: number) => <span className="tnum">{v}</span> },
                { title: 'When', dataIndex: 'created_at', render: formatDateTime },
              ]}
            />
          </div>
        </Card>
      )}

      <Modal title="Scan QR" open={scanOpen} onCancel={() => setScanOpen(false)} footer={null} destroyOnClose>
        {scanOpen && <WebcamScanner onDecode={onScan} />}
      </Modal>
    </>
  );
}
