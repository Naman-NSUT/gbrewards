import { App, Button, Drawer, Form, Input, InputNumber, Popconfirm, Space, Switch } from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { Reward } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { StatusDot } from '../components/StatusDot';
import {
  useCreateReward,
  useDeleteReward,
  useRewards,
  useUpdateReward,
} from '../hooks/useRewards';
import { formatDateTime } from '../lib/format';

interface RewardForm {
  title: string;
  description?: string;
  points_cost: number;
  image_url?: string;
  sort_order: number;
  is_active: boolean;
}

export function RewardsPage() {
  const { message } = App.useApp();
  const rewards = useRewards();
  const createReward = useCreateReward();
  const updateReward = useUpdateReward();
  const deleteRewardMut = useDeleteReward();

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<Reward | null>(null);
  const [form] = Form.useForm<RewardForm>();

  const onDelete = async (r: Reward) => {
    try {
      await deleteRewardMut.mutateAsync(r.id);
      message.success('Reward deleted');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not delete reward — deactivate it instead.'));
    }
  };

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ is_active: true, points_cost: 0, sort_order: 0 });
    setEditorOpen(true);
  };

  const openEdit = (r: Reward) => {
    setEditing(r);
    form.setFieldsValue({
      title: r.title,
      description: r.description ?? undefined,
      points_cost: r.points_cost,
      image_url: r.image_url ?? undefined,
      sort_order: r.sort_order,
      is_active: r.is_active,
    });
    setEditorOpen(true);
  };

  const submitEditor = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await updateReward.mutateAsync({ id: editing.id, input: values });
        message.success('Reward updated');
      } else {
        await createReward.mutateAsync(values);
        message.success('Reward created');
      }
      setEditorOpen(false);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not save reward'));
    }
  };

  return (
    <>
      <PageHeader
        title="Rewards"
        subtitle="Manage the catalog brokers can redeem their points for."
        extra={
          <Button type="primary" onClick={openCreate}>
            New reward
          </Button>
        }
      />

      <DataTable<Reward>
        rowKey="id"
        loading={rewards.isLoading}
        dataSource={rewards.data ?? []}
        emptyText="No rewards yet"
        emptyHint="Create a reward to let brokers redeem their points."
        columns={[
          {
            title: 'Title',
            dataIndex: 'title',
            render: (t: string) => <span style={{ fontWeight: 550 }}>{t}</span>,
          },
          {
            title: 'Points cost',
            dataIndex: 'points_cost',
            render: (v: number) => <span className="tnum">{v}</span>,
          },
          {
            title: 'Status',
            dataIndex: 'is_active',
            render: (v: boolean) => <StatusDot status={v ? 'active' : 'inactive'} />,
          },
          {
            title: 'Sort order',
            dataIndex: 'sort_order',
            render: (v: number) => <span className="tnum">{v}</span>,
          },
          { title: 'Created', dataIndex: 'created_at', render: formatDateTime },
          {
            title: '',
            align: 'right',
            render: (_v, r) => (
              <Space size="large">
                <a onClick={() => openEdit(r)}>Edit</a>
                <Popconfirm
                  title="Delete this reward?"
                  description="Only rewards with no redemptions can be deleted. Otherwise deactivate it."
                  okText="Delete"
                  okButtonProps={{ danger: true }}
                  onConfirm={() => onDelete(r)}
                >
                  <a style={{ color: '#e5648b' }}>Delete</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title={editing ? 'Edit reward' : 'New reward'}
        width={420}
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        extra={
          <Button
            type="primary"
            onClick={submitEditor}
            loading={createReward.isPending || updateReward.isPending}
          >
            Save
          </Button>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="Title" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="points_cost" label="Points cost" rules={[{ required: true }]}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="image_url" label="Image URL">
            <Input placeholder="https://…" />
          </Form.Item>
          <Form.Item name="sort_order" label="Sort order">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Drawer>
    </>
  );
}
