import { App, Button, Drawer, Form, Input, InputNumber, Modal, Popconfirm, Space, Switch } from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import { downloadBatchPdf } from '../api/products';
import type { Product } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { StatusDot } from '../components/StatusDot';
import {
  useCreateBatch,
  useCreateProduct,
  useDeleteProduct,
  useProducts,
  useUpdateProduct,
} from '../hooks/useProducts';
import { downloadBlob, formatDateTime } from '../lib/format';
import { OrderDrawer } from './OrderDrawer';
import { ProductDetailDrawer } from './ProductDetailDrawer';

interface ProductForm {
  name: string;
  description?: string;
  points_value: number;
  is_active: boolean;
}

export function ProductsPage() {
  const { message } = App.useApp();
  const products = useProducts();
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();
  const createBatch = useCreateBatch();
  const deleteProductMut = useDeleteProduct();

  const onDelete = async (p: Product) => {
    try {
      await deleteProductMut.mutateAsync(p.id);
      message.success('Product deleted');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not delete product'));
    }
  };

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [form] = Form.useForm<ProductForm>();

  const [batchFor, setBatchFor] = useState<Product | null>(null);
  const [batchForm] = Form.useForm<{ quantity: number; label?: string }>();

  const [orderOpen, setOrderOpen] = useState(false);

  const [detailId, setDetailId] = useState<string | null>(null);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ is_active: true, points_value: 0 });
    setEditorOpen(true);
  };

  const openEdit = (p: Product) => {
    setEditing(p);
    form.setFieldsValue({
      name: p.name,
      description: p.description ?? undefined,
      points_value: p.points_value,
      is_active: p.is_active,
    });
    setEditorOpen(true);
  };

  const submitEditor = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await updateProduct.mutateAsync({ id: editing.id, input: values });
        message.success('Product updated');
      } else {
        await createProduct.mutateAsync(values);
        message.success('Product created');
      }
      setEditorOpen(false);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not save product'));
    }
  };

  const submitBatch = async () => {
    if (!batchFor) return;
    const values = await batchForm.validateFields();
    try {
      const batch = await createBatch.mutateAsync({
        productId: batchFor.id,
        quantity: values.quantity,
        label: values.label,
      });
      message.success(`Generated ${values.quantity} codes — downloading sheet…`);
      const blob = await downloadBatchPdf(batch.id);
      downloadBlob(blob, `batch-${batch.id}.pdf`);
      setBatchFor(null);
      batchForm.resetFields();
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not generate batch'));
    }
  };

  return (
    <>
      <PageHeader
        title="Products & QR"
        subtitle="Manage products and generate printable QR batches."
        extra={
          <Space>
            <Button onClick={() => setOrderOpen(true)}>Generate QR order</Button>
            <Button type="primary" onClick={openCreate}>
              New product
            </Button>
          </Space>
        }
      />

      <DataTable<Product>
        rowKey="id"
        loading={products.isLoading}
        dataSource={products.data ?? []}
        emptyText="No products yet"
        emptyHint="Create a product to start generating QR batches."
        columns={[
          { title: 'Name', dataIndex: 'name', render: (n: string) => <span style={{ fontWeight: 550 }}>{n}</span> },
          { title: 'Points', dataIndex: 'points_value', render: (v: number) => <span className="tnum">{v}</span> },
          {
            title: 'Status',
            dataIndex: 'is_active',
            render: (v: boolean) => <StatusDot status={v ? 'active' : 'inactive'} />,
          },
          { title: 'Created', dataIndex: 'created_at', render: formatDateTime },
          {
            title: '',
            align: 'right',
            render: (_v, p) => (
              <Space size="large">
                <a onClick={() => setDetailId(p.id)}>Details</a>
                <a onClick={() => openEdit(p)}>Edit</a>
                <a onClick={() => setBatchFor(p)}>Batch</a>
                <Popconfirm
                  title="Delete this product?"
                  description="Only products with no QR codes can be deleted."
                  okText="Delete"
                  okButtonProps={{ danger: true }}
                  onConfirm={() => onDelete(p)}
                >
                  <a style={{ color: '#e5648b' }}>Delete</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title={editing ? 'Edit product' : 'New product'}
        width={420}
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        extra={
          <Button type="primary" onClick={submitEditor} loading={createProduct.isPending || updateProduct.isPending}>
            Save
          </Button>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="points_value" label="Points value" rules={[{ required: true }]}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Drawer>

      <Modal
        title={`Generate batch — ${batchFor?.name ?? ''}`}
        open={batchFor !== null}
        onCancel={() => setBatchFor(null)}
        onOk={submitBatch}
        confirmLoading={createBatch.isPending}
        okText="Generate & download PDF"
      >
        <Form form={batchForm} layout="vertical">
          <Form.Item name="quantity" label="Quantity" rules={[{ required: true }]}>
            <InputNumber min={1} max={10000} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="label" label="Label">
            <Input placeholder="e.g. Jun 2026 — SKU-A" />
          </Form.Item>
        </Form>
      </Modal>

      <ProductDetailDrawer
        productId={detailId}
        open={detailId !== null}
        onClose={() => setDetailId(null)}
      />

      <OrderDrawer
        open={orderOpen}
        onClose={() => setOrderOpen(false)}
        products={products.data ?? []}
      />
    </>
  );
}
