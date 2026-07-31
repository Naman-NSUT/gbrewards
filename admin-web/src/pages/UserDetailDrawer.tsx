import { App, Button, Descriptions, Divider, Drawer, Form, InputNumber, Input, Space, Table, Tag } from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { LedgerEntry, LedgerType } from '../api/types';
import { useCreditUser, useDebitUser, useUser, useUserLedger } from '../hooks/useUsers';
import { formatAddress, formatDate, formatDateTime } from '../lib/format';

const GENDER_LABEL: Record<string, string> = { male: 'Male', female: 'Female' };

const TYPE_LABEL: Record<LedgerType, string> = {
  scan_credit: 'Earned',
  return_reversal: 'Reversed',
  redemption_debit: 'Redeemed',
  admin_credit: 'Admin credit',
  admin_debit: 'Admin debit',
};

export function UserDetailDrawer({
  userId,
  open,
  onClose,
}: {
  userId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  const user = useUser(open ? userId : null);
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const ledger = useUserLedger(open ? userId : null, cursor);
  const credit = useCreditUser(userId);
  const debit = useDebitUser(userId);
  const [form] = Form.useForm<{ points: number; note?: string }>();

  const adjust = async (kind: 'credit' | 'debit') => {
    const values = await form.validateFields();
    try {
      if (kind === 'credit') await credit.mutateAsync(values);
      else await debit.mutateAsync(values);
      message.success(`${kind === 'credit' ? 'Credited' : 'Debited'} ${values.points} points`);
      form.resetFields();
    } catch (e) {
      message.error(apiErrorMessage(e, 'Adjustment failed'));
    }
  };

  return (
    <Drawer title={user.data ? user.data.name : 'User'} width={680} open={open} onClose={onClose}>
      {user.data && (
        <Descriptions column={2} size="small" bordered>
          <Descriptions.Item label="Phone">{user.data.phone}</Descriptions.Item>
          <Descriptions.Item label="Verified">{user.data.is_verified ? 'yes' : 'no'}</Descriptions.Item>
          <Descriptions.Item label="Balance">{user.data.balance}</Descriptions.Item>
          <Descriptions.Item label="Available">{user.data.available}</Descriptions.Item>
          <Descriptions.Item label="Total earned">{user.data.total_earned}</Descriptions.Item>
          <Descriptions.Item label="Active">{user.data.is_active ? 'yes' : 'no'}</Descriptions.Item>
          <Descriptions.Item label="Date of birth">{formatDate(user.data.dob)}</Descriptions.Item>
          <Descriptions.Item label="Gender">
            {user.data.gender ? (GENDER_LABEL[user.data.gender] ?? user.data.gender) : '—'}
          </Descriptions.Item>
          {/* Delivery address for fulfilling redemptions. */}
          <Descriptions.Item label="Address" span={2}>
            {formatAddress(user.data)}
          </Descriptions.Item>
        </Descriptions>
      )}

      <Divider>Adjust points</Divider>
      <Form form={form} layout="inline">
        <Form.Item name="points" rules={[{ required: true }]}>
          <InputNumber min={1} placeholder="Points" />
        </Form.Item>
        <Form.Item name="note">
          <Input placeholder="Reason / note" />
        </Form.Item>
        <Space>
          <Button onClick={() => adjust('credit')} loading={credit.isPending}>
            Credit
          </Button>
          <Button danger onClick={() => adjust('debit')} loading={debit.isPending}>
            Debit
          </Button>
        </Space>
      </Form>

      <Divider>Ledger</Divider>
      <Table<LedgerEntry>
        size="small"
        rowKey="id"
        loading={ledger.isLoading}
        dataSource={ledger.data?.items ?? []}
        pagination={false}
        columns={[
          { title: 'Type', dataIndex: 'type', render: (t: LedgerType) => TYPE_LABEL[t] ?? t },
          {
            title: 'Amount',
            dataIndex: 'amount',
            render: (a: number) => (
              <Tag color={a >= 0 ? 'green' : 'red'}>
                {a >= 0 ? '+' : ''}
                {a}
              </Tag>
            ),
          },
          { title: 'Note', dataIndex: 'note', render: (n: string | null) => n ?? '—' },
          { title: 'When', dataIndex: 'created_at', render: formatDateTime },
        ]}
      />
      {ledger.data?.next_cursor && (
        <Button block style={{ marginTop: 12 }} onClick={() => setCursor(ledger.data.next_cursor ?? undefined)}>
          Load more
        </Button>
      )}
    </Drawer>
  );
}
