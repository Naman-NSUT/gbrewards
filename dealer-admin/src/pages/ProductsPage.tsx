import { PlusOutlined, PrinterOutlined, QrcodeOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Switch,
  Table,
  Tag,
  message,
} from 'antd';
import type { TableColumnsType } from 'antd';
import { useState } from 'react';

import {
  createProduct,
  downloadLabels,
  generateBatch,
  listProducts,
  updateProduct,
  type DealerProduct,
  type DealerProductInput,
} from '../api/products';
import { apiErrorMessage } from '../api/client';
import { Mono } from '../components/Mono';
import { PageHeader } from '../components/PageHeader';
import { brand } from '../theme';

const PAGE_SIZE = 20;

export function ProductsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<DealerProduct | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [batchFor, setBatchFor] = useState<DealerProduct | null>(null);
  const [form] = Form.useForm<DealerProductInput>();
  const [batchForm] = Form.useForm<{ quantity: number; label?: string }>();

  const products = useQuery({
    queryKey: ['dealer-products', page],
    queryFn: () => listProducts({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
  });

  const save = useMutation({
    mutationFn: (body: DealerProductInput) =>
      editing ? updateProduct(editing.id, body) : createProduct(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['dealer-products'] });
      setFormOpen(false);
      message.success(editing ? 'Product updated' : 'Product added');
    },
  });

  const mint = useMutation({
    mutationFn: (body: { quantity: number; label?: string }) =>
      generateBatch(batchFor!.id, body),
    onSuccess: async (batch) => {
      void qc.invalidateQueries({ queryKey: ['dealer-products'] });
      setBatchFor(null);
      message.success(`${batch.quantity} labels generated — downloading the sheet`);
      // Straight to the printable sheet: the only reason to mint labels is to
      // print them, and a second click to find the download helps nobody.
      const blob = await downloadLabels(batch.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dealer-labels-${batch.id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    },
    onError: (e) => message.error(apiErrorMessage(e, 'Could not generate labels')),
  });

  const columns: TableColumnsType<DealerProduct> = [
    {
      title: 'Product',
      dataIndex: 'name',
      render: (name: string, r) => (
        <div>
          <div style={{ fontWeight: 600 }}>{name}</div>
          {r.model_code && <Mono value={r.model_code} />}
        </div>
      ),
    },
    {
      title: 'Warranty',
      dataIndex: 'warranty_months',
      width: 130,
      render: (m: number) => <span className="tnum">{m} months</span>,
    },
    {
      title: 'Labels minted',
      dataIndex: 'units_generated',
      width: 140,
      render: (n: number) => (
        <span className="tnum" style={{ color: n === 0 ? brand.textFaint : brand.text }}>
          {n === 0 ? 'none yet' : n.toLocaleString()}
        </span>
      ),
    },
    {
      title: '',
      width: 90,
      render: (_: unknown, r) => (r.is_active ? null : <Tag>inactive</Tag>),
    },
    {
      title: '',
      width: 230,
      render: (_: unknown, r) => (
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button
            size="small"
            icon={<QrcodeOutlined />}
            onClick={() => {
              setBatchFor(r);
              batchForm.resetFields();
            }}
          >
            Generate labels
          </Button>
          <Button
            size="small"
            onClick={() => {
              setEditing(r);
              form.setFieldsValue(r);
              setFormOpen(true);
            }}
          >
            Edit
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Products & QR"
        subtitle="The dealer programme's own catalogue and serials"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditing(null);
              form.resetFields();
              form.setFieldsValue({ warranty_months: 60, is_active: true });
              setFormOpen(true);
            }}
          >
            Add product
          </Button>
        }
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="These labels are separate from the factory's"
        description="The dealer app scans a dealer label, so each mattress carries two QR codes: the factory's, scanned by a worker during assembly, and this one, scanned at point of sale. The two serials are unrelated."
      />

      <Table
        rowKey="id"
        columns={columns}
        dataSource={products.data?.items ?? []}
        loading={products.isLoading}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: products.data?.total ?? 0,
          onChange: setPage,
          showSizeChanger: false,
        }}
      />

      <Modal
        open={formOpen}
        title={editing ? 'Edit product' : 'Add product'}
        okText="Save"
        confirmLoading={save.isPending}
        onOk={async () => save.mutate(await form.validateFields())}
        onCancel={() => setFormOpen(false)}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input placeholder="GoodBed HR Foam 6 inch" />
          </Form.Item>
          <Form.Item name="model_code" label="Model code">
            <Input placeholder="HR-72" />
          </Form.Item>
          <Form.Item
            name="warranty_months"
            label="Warranty length (months)"
            rules={[{ required: true }]}
            extra="Frozen onto each warranty at the moment of sale — changing it later never rewrites warranties already sold."
          >
            <InputNumber min={1} max={600} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} maxLength={500} showCount />
          </Form.Item>
          <Form.Item
            name="terms"
            label="Label terms"
            extra="Printed in small type under the QR. One line each."
          >
            <Input.TextArea rows={3} maxLength={600} showCount />
          </Form.Item>
          <Form.Item name="is_active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={batchFor !== null}
        title={`Generate labels — ${batchFor?.name ?? ''}`}
        okText="Generate & download"
        confirmLoading={mint.isPending}
        onOk={async () => mint.mutate(await batchForm.validateFields())}
        onCancel={() => setBatchFor(null)}
        destroyOnHidden
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="There is no undo"
          description="Serials are permanent once minted. If a print run is scrapped, void those labels rather than regenerating — a voided label cannot be registered, which is what stops a lost sheet turning into payable registrations."
        />
        <Form form={batchForm} layout="vertical">
          <Form.Item
            name="quantity"
            label="How many labels"
            rules={[{ required: true, message: 'How many?' }]}
          >
            <InputNumber min={1} max={10000} style={{ width: '100%' }} size="large" />
          </Form.Item>
          <Form.Item name="label" label="Batch note" extra="e.g. 'March despatch, Nagpur'">
            <Input maxLength={200} />
          </Form.Item>
        </Form>
        <div style={{ color: brand.textDim, fontSize: 12.5 }}>
          <PrinterOutlined /> The printable sheet downloads automatically — one label per page.
        </div>
      </Modal>
    </>
  );
}
