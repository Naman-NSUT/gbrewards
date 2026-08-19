import { PlusOutlined, ShopOutlined } from '@ant-design/icons';
import { App, Button, Form, Input, Modal, Select } from 'antd';
import type { TableColumnsType } from 'antd';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { apiErrorMessage } from '../api/client';
import type { Dealer, DealerInput, DealerListItem, DealerStatus } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusDot';
import { useCreateDealer, useDealers, useUpdateDealer } from '../hooks/useDealers';
import { formatDate, formatNumber } from '../lib/format';
import { brand } from '../theme';
import { DealerDrawer } from './DealerDrawer';

const PAGE_SIZE = 25;

export function DealersPage() {
  const { message } = App.useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<DealerStatus | undefined>();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Dealer | null>(null);
  const [form] = Form.useForm<DealerInput>();

  const creating = searchParams.get('new') === '1';
  const openId = searchParams.get('dealer');

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  };

  const params = useMemo(
    () => ({ q: q || undefined, status, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
    [q, status, page],
  );
  const dealers = useDealers(params);
  const create = useCreateDealer();
  const update = useUpdateDealer();

  const formOpen = creating || editing !== null;

  const closeForm = () => {
    setEditing(null);
    setParam('new', null);
  };

  const submit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await update.mutateAsync({ id: editing.id, body: values });
        message.success('Dealer updated');
      } else {
        await create.mutateAsync(values);
        message.success('Dealer created. Add a staff login so they can register sales.');
      }
      closeForm();
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not save the dealer'));
    }
  };

  const columns: TableColumnsType<DealerListItem> = [
    {
      title: 'Dealer',
      dataIndex: 'name',
      width: 250,
      render: (name: string, d) => (
        <div>
          <div style={{ fontWeight: 550, color: brand.text }}>{name}</div>
          <div className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
            {d.code}
          </div>
        </div>
      ),
    },
    {
      title: 'Location',
      dataIndex: 'city',
      width: 160,
      render: (city: string | null, d) => (
        <span style={{ fontSize: 12.5, color: brand.textDim }}>
          {city ?? '—'}
          {d.state && <span style={{ color: brand.textFaint }}> · {d.state}</span>}
        </span>
      ),
    },
    {
      title: 'Contact',
      dataIndex: 'phone',
      width: 170,
      render: (phone: string | null, d) => (
        <div>
          <div className="mono" style={{ fontSize: 12, color: brand.textDim }}>
            {phone ?? '—'}
          </div>
          <div
            style={{
              fontSize: 11.5,
              color: brand.textFaint,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {d.email ?? ''}
          </div>
        </div>
      ),
    },
    {
      title: 'Staff',
      dataIndex: 'staff_count',
      align: 'right',
      width: 90,
      render: (n: number) => (
        <span className="tnum" style={{ color: n === 0 ? brand.danger : brand.textDim }}>
          {n}
        </span>
      ),
    },
    {
      // The list row carries the balance and nothing else derived — the
      // registration rate lives on the compliance screen, which computes it
      // over a date window this table has no concept of.
      title: 'Points balance',
      dataIndex: 'points_balance',
      align: 'right',
      width: 130,
      render: (v: number) => (
        <span className="tnum" style={{ color: v < 0 ? brand.danger : brand.text }}>
          {formatNumber(v)}
        </span>
      ),
    },
    {
      title: 'On programme',
      dataIndex: 'created_at',
      width: 140,
      render: (v: string) => (
        <span style={{ fontSize: 12.5, color: brand.textFaint }}>{formatDate(v)}</span>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 110,
      render: (s: DealerStatus) => <StatusTag status={s} />,
    },
  ];

  return (
    <>
      <PageHeader
        title="Dealers"
        subtitle="The shops on the programme, their logins and their balances."
        extra={
          <div style={{ display: 'flex', gap: 10 }}>
            <Input.Search
              allowClear
              placeholder="Name, code, city or phone"
              style={{ width: 260 }}
              onSearch={(v) => {
                setPage(1);
                setQ(v);
              }}
            />
            <Select
              allowClear
              placeholder="Any status"
              style={{ width: 140 }}
              value={status}
              options={[
                { label: 'Active', value: 'active' },
                { label: 'Suspended', value: 'suspended' },
                { label: 'Closed', value: 'closed' },
              ]}
              onChange={(v) => {
                setPage(1);
                setStatus(v);
              }}
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                form.resetFields();
                setParam('new', '1');
              }}
            >
              New dealer
            </Button>
          </div>
        }
      />

      <DataTable<DealerListItem>
        rowKey="id"
        loading={dealers.isLoading}
        dataSource={dealers.data?.items ?? []}
        columns={columns}
        total={dealers.data?.total}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        emptyText="No dealers yet"
        emptyHint="Dealers are provisioned here, never self-registered — each one is a contract the brand already has."
        emptyIcon={<ShopOutlined />}
        rowClassName={() => 'dr-row-clickable'}
        onRow={(d) => ({ onClick: () => setParam('dealer', d.id) })}
      />

      <DealerDrawer
        dealerId={openId}
        onClose={() => setParam('dealer', null)}
        onEdit={(d) => {
          form.setFieldsValue(d);
          setEditing(d);
        }}
      />

      <Modal
        open={formOpen}
        title={editing ? `Edit ${editing.name}` : 'New dealer'}
        okText={editing ? 'Save' : 'Create dealer'}
        confirmLoading={create.isPending || update.isPending}
        onOk={submit}
        onCancel={closeForm}
        destroyOnHidden
        width={560}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item
              name="code"
              label="Dealer code"
              style={{ width: 180 }}
              rules={[{ required: true, message: 'The code is what CSV uploads key on' }]}
              extra="Used by allocation uploads"
            >
              <Input className="mono" placeholder="GB-DLR-014" disabled={editing !== null} />
            </Form.Item>
            <Form.Item
              name="name"
              label="Shop name"
              style={{ flex: 1 }}
              rules={[{ required: true, message: 'Enter the shop name' }]}
            >
              <Input placeholder="Sleepwell Furnishings" />
            </Form.Item>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="phone" label="Phone" style={{ flex: 1 }}>
              <Input className="mono" placeholder="+91…" />
            </Form.Item>
            <Form.Item name="email" label="Email" style={{ flex: 1 }}>
              <Input placeholder="owner@shop.in" />
            </Form.Item>
          </div>
          <Form.Item name="address" label="Address">
            <Input />
          </Form.Item>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="city" label="City" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="state" label="State" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="pincode" label="PIN" style={{ width: 110 }}>
              <Input className="mono" />
            </Form.Item>
          </div>
          <Form.Item name="gst_number" label="GST number">
            <Input className="mono" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
