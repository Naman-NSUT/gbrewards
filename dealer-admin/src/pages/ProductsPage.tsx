import { PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Form, Input, InputNumber, Modal, Switch, Table, Tag, message } from 'antd';
import type { TableColumnsType } from 'antd';
import { useState } from 'react';

import {
  createProduct,
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
  const [form] = Form.useForm<ProductFormValues>();

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
      title: '',
      width: 90,
      render: (_: unknown, r) => (r.is_active ? null : <Tag>inactive</Tag>),
    },
    {
      title: '',
      width: 110,
      render: (_: unknown, r) => (
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
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
        title="Products"
        subtitle="What a shop picks from the dropdown when it registers a sale"
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
            label="Warranty terms"
            extra="The small print for this model. It used to be printed under the QR; nothing prints it now, so it is back-office copy — and saving writes exactly what is in this box, so emptying it erases the wording."
          >
            <Input.TextArea rows={3} maxLength={600} showCount />
          </Form.Item>
          <Form.Item name="is_active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
