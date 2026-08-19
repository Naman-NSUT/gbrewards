import { DeleteOutlined, EditOutlined, GiftOutlined, PlusOutlined } from '@ant-design/icons';
import { App, Button, Form, Input, InputNumber, Modal, Switch } from 'antd';
import type { TableColumnsType } from 'antd';
import { useMemo, useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { RewardInput, RewardRow } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusDot';
import { useCreateReward, useDeleteReward, useRewards, useUpdateReward } from '../hooks/useRewards';
import { formatNumber } from '../lib/format';
import { brand } from '../theme';

const PAGE_SIZE = 50;

export function RewardsPage() {
  const { message, modal } = App.useApp();
  const [page, setPage] = useState(1);
  const params = useMemo(
    () => ({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
    [page],
  );
  // The catalogue is paginated on the server like every other list.
  const rewards = useRewards(params);
  const create = useCreateReward();
  const update = useUpdateReward();
  const remove = useDeleteReward();

  const [editing, setEditing] = useState<RewardRow | null>(null);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm<RewardInput>();

  const open = creating || editing !== null;

  const submit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await update.mutateAsync({ id: editing.id, body: values });
        message.success('Reward updated');
      } else {
        await create.mutateAsync(values);
        message.success('Reward added to the catalogue');
      }
      setEditing(null);
      setCreating(false);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not save the reward'));
    }
  };

  const confirmDelete = (r: RewardRow) => {
    modal.confirm({
      title: `Remove “${r.name}”?`,
      content:
        'Redemption requests already in the queue keep the points they were priced at — removing this only takes it out of the dealer app.',
      okText: 'Remove',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await remove.mutateAsync(r.id);
          message.success('Reward removed');
        } catch (e) {
          message.error(apiErrorMessage(e, 'Could not remove that reward'));
        }
      },
    });
  };

  const columns: TableColumnsType<RewardRow> = [
    {
      title: 'Reward',
      dataIndex: 'name',
      render: (name: string, r) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {r.image_url ? (
            <img
              src={r.image_url}
              alt=""
              style={{ width: 40, height: 40, borderRadius: 8, objectFit: 'cover' }}
            />
          ) : (
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 8,
                display: 'grid',
                placeItems: 'center',
                border: `1px solid ${brand.border}`,
                color: brand.textFaint,
              }}
            >
              <GiftOutlined />
            </div>
          )}
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 550, color: brand.text }}>{name}</div>
            <div
              style={{
                fontSize: 12,
                color: brand.textFaint,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                maxWidth: 380,
              }}
            >
              {r.description ?? ''}
            </div>
          </div>
        </div>
      ),
    },
    {
      title: 'Cost',
      dataIndex: 'points_cost',
      align: 'right',
      width: 120,
      render: (v: number) => (
        <span className="tnum" style={{ color: brand.text }}>
          {formatNumber(v)} pts
        </span>
      ),
    },
    {
      title: 'Stock',
      dataIndex: 'stock',
      align: 'right',
      width: 110,
      render: (v: number | null) => (
        <span className="tnum" style={{ color: v === 0 ? brand.danger : brand.textDim }}>
          {v === null ? 'unlimited' : formatNumber(v)}
        </span>
      ),
    },
    {
      title: 'Order',
      dataIndex: 'sort_order',
      align: 'right',
      width: 80,
      render: (v: number) => (
        <span className="tnum" style={{ color: brand.textFaint }}>
          {v}
        </span>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      width: 110,
      render: (active: boolean) => <StatusTag status={active ? 'active' : 'inactive'} />,
    },
    {
      title: '',
      key: 'actions',
      width: 100,
      render: (_v, r) => (
        <div style={{ display: 'flex', gap: 4 }}>
          <Button
            size="small"
            type="text"
            icon={<EditOutlined />}
            onClick={() => {
              form.setFieldsValue(r);
              setEditing(r);
            }}
          />
          <Button
            size="small"
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => confirmDelete(r)}
          />
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Rewards"
        subtitle="What dealers can spend their points on. Separate from the GB Rewards worker catalogue on purpose."
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              form.resetFields();
              setCreating(true);
            }}
          >
            New reward
          </Button>
        }
      />

      <DataTable<RewardRow>
        rowKey="id"
        loading={rewards.isLoading}
        dataSource={rewards.data?.items ?? []}
        columns={columns}
        total={rewards.data?.total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyText="The catalogue is empty"
        emptyHint="Dealers see nothing to redeem against until you add something here."
        emptyIcon={<GiftOutlined />}
      />

      <Modal
        open={open}
        title={editing ? `Edit ${editing.name}` : 'New reward'}
        okText={editing ? 'Save' : 'Add reward'}
        confirmLoading={create.isPending || update.isPending}
        onOk={submit}
        onCancel={() => {
          setEditing(null);
          setCreating(false);
        }}
        destroyOnHidden
        width={520}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Give it a name' }]}>
            <Input placeholder="₹2,000 fuel voucher" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} maxLength={500} showCount />
          </Form.Item>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item
              name="points_cost"
              label="Points cost"
              style={{ flex: 1 }}
              rules={[{ required: true, message: 'Set a cost' }]}
            >
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="stock" label="Stock" style={{ flex: 1 }} extra="Leave blank for unlimited">
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="sort_order" label="Order" style={{ width: 90 }} initialValue={0}>
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <Form.Item name="image_url" label="Image URL">
            <Input placeholder="https://…" />
          </Form.Item>
          <Form.Item name="is_active" label="Visible to dealers" valuePropName="checked" initialValue>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
