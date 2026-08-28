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
import { listProductRates, setPointRate } from '../api/points';
import { apiErrorCode, apiErrorMessage } from '../api/client';
import { Mono } from '../components/Mono';
import { PageHeader } from '../components/PageHeader';
import { brand } from '../theme';

const PAGE_SIZE = 20;

/**
 * The create form carries the rate as well as the product.
 *
 * A product with no rate registers sales perfectly and pays the dealer NOTHING,
 * silently — no error, no warning at the counter. Setting it here, at the only
 * moment anyone is thinking about this product, is what stops that. The rate is
 * still a separate versioned record on the server, so history stays intact.
 */
type ProductFormValues = DealerProductInput & { points_per_registration?: number | null };

export function ProductsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<DealerProduct | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [batchFor, setBatchFor] = useState<DealerProduct | null>(null);
  const [form] = Form.useForm<ProductFormValues>();
  const [batchForm] = Form.useForm<{ quantity: number; label?: string }>();

  const products = useQuery({
    queryKey: ['dealer-products', page],
    queryFn: () => listProducts({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
  });

  // Rates live on their own versioned endpoint, so they are fetched alongside
  // and joined by product id rather than being a field on the product.
  const rates = useQuery({ queryKey: ['dealer-product-rates'], queryFn: listProductRates });
  const rateFor = (productId: string): number | null =>
    rates.data?.find((r) => r.product_id === productId)?.points_per_registration ?? null;

  const save = useMutation({
    mutationFn: async (values: ProductFormValues) => {
      const { points_per_registration: points, ...body } = values;
      const product = editing
        ? await updateProduct(editing.id, body)
        : await createProduct(body);

      // Only when it actually changed: every call opens a NEW rate version, and
      // an unchanged save would otherwise fill the rate history with duplicates
      // that say nothing happened.
      const unchanged = points == null || points === rateFor(product.id);
      if (unchanged) return { product, rateSet: false, rateRefused: false };

      try {
        await setPointRate({
          product_id: product.id,
          points_per_registration: points,
          note: editing ? 'Changed from the product form' : 'Set when the product was added',
        });
        return { product, rateSet: true, rateRefused: false };
      } catch (e) {
        // Setting a rate is owner-only — it is the one lever that decides what
        // the programme costs. A manager saving a product must still keep the
        // product; they just cannot price it, and they need telling which half
        // of this actually happened.
        if (apiErrorCode(e) === 'forbidden') {
          return { product, rateSet: false, rateRefused: true };
        }
        throw e;
      }
    },
    onSuccess: ({ rateSet, rateRefused }) => {
      void qc.invalidateQueries({ queryKey: ['dealer-products'] });
      void qc.invalidateQueries({ queryKey: ['dealer-product-rates'] });
      setFormOpen(false);
      if (rateRefused) {
        message.warning(
          `${editing ? 'Product updated' : 'Product added'}, but only an owner can set the points. Ask an owner to price it — until then a dealer earns nothing for it.`,
        );
        return;
      }
      const what = editing ? 'Product updated' : 'Product added';
      message.success(rateSet ? `${what}, and the points are set` : what);
    },
    onError: (e) => message.error(apiErrorMessage(e, 'Could not save that product')),
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
      title: 'Points',
      width: 150,
      render: (_: unknown, r) => {
        const points = rateFor(r.id);
        if (points === null) {
          return r.is_active ? (
            <Tag color="warning">not set</Tag>
          ) : (
            <span style={{ color: brand.textFaint }}>—</span>
          );
        }
        return (
          <span className="tnum" style={{ fontWeight: 600 }}>
            {points.toLocaleString()}
            <span style={{ color: brand.textFaint, fontWeight: 400 }}> / sale</span>
          </span>
        );
      },
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
              form.setFieldsValue({ ...r, points_per_registration: rateFor(r.id) });
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
          <Form.Item
            name="points_per_registration"
            label="Points per registration"
            extra="What the dealer earns each time this product's warranty is registered. Leave empty and the sale still records — the dealer just earns nothing for it. Changing this never reprices sales already made."
          >
            <InputNumber min={0} max={100000} style={{ width: '100%' }} placeholder="e.g. 120" />
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
