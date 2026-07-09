import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { App, Button, Drawer, Input, InputNumber, Select, Space } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import { createOrder, downloadOrderPdf } from '../api/products';
import type { Product } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { downloadBlob, printBlob } from '../lib/format';
import { brand } from '../theme';

interface Line {
  key: number;
  productId?: string;
  quantity: number;
}

let counter = 0;
const newLine = (): Line => ({ key: counter++, quantity: 50 });

export function OrderDrawer({
  open,
  onClose,
  products,
}: {
  open: boolean;
  onClose: () => void;
  products: Product[];
}) {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [lines, setLines] = useState<Line[]>([newLine()]);
  const [label, setLabel] = useState('');
  const [busy, setBusy] = useState(false);

  const update = (key: number, patch: Partial<Line>) =>
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  const remove = (key: number) => setLines((ls) => ls.filter((l) => l.key !== key));

  const valid = lines.filter((l) => l.productId && l.quantity > 0);
  const totalUnits = valid.reduce((s, l) => s + l.quantity, 0);
  const canGenerate = valid.length > 0 && valid.length === lines.length;

  const generate = async (mode: 'print' | 'download') => {
    setBusy(true);
    try {
      const result = await createOrder(
        valid.map((l) => ({ product_id: l.productId as string, quantity: l.quantity })),
        label || undefined,
      );
      const blob = await downloadOrderPdf(result.batches.map((b) => b.batch_id));
      if (mode === 'print') {
        printBlob(blob);
      } else {
        downloadBlob(blob, `qr-order-${Date.now()}.pdf`);
      }
      message.success(`Generated ${result.total_units} QR codes`);
      void qc.invalidateQueries({ queryKey: ['products'] });
      setLines([newLine()]);
      setLabel('');
      onClose();
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not generate order'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      title="Generate QR order"
      width={520}
      open={open}
      onClose={onClose}
      extra={
        <Space>
          <Button onClick={() => void generate('download')} loading={busy} disabled={!canGenerate}>
            Download
          </Button>
          <Button
            type="primary"
            onClick={() => void generate('print')}
            loading={busy}
            disabled={!canGenerate}
          >
            Generate & print
          </Button>
        </Space>
      }
    >
      <p style={{ color: brand.textDim, marginTop: 0, fontSize: 13.5 }}>
        Add products and quantities — one batch of unique QR codes is generated per line, exported as
        a single printable sheet.
      </p>

      <Input
        placeholder="Order label (optional) — e.g. Jun 2026 dispatch"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        style={{ marginBottom: 16 }}
      />

      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        {lines.map((l) => (
          <div key={l.key} style={{ display: 'flex', gap: 8 }}>
            <Select
              showSearch
              optionFilterProp="label"
              placeholder="Product"
              style={{ flex: 1 }}
              value={l.productId}
              onChange={(v) => update(l.key, { productId: v })}
              options={products.map((p) => ({ label: `${p.name} · ${p.points_value} pts`, value: p.id }))}
            />
            <InputNumber
              min={1}
              max={10000}
              value={l.quantity}
              onChange={(v) => update(l.key, { quantity: v ?? 1 })}
              style={{ width: 110 }}
            />
            <Button
              icon={<DeleteOutlined />}
              onClick={() => remove(l.key)}
              disabled={lines.length === 1}
            />
          </div>
        ))}
      </Space>

      <Button
        icon={<PlusOutlined />}
        onClick={() => setLines((ls) => [...ls, newLine()])}
        style={{ marginTop: 12 }}
        block
      >
        Add product
      </Button>

      {products.length === 0 && (
        <EmptyState title="No products" hint="Create a product first." height={120} />
      )}

      <div
        style={{
          marginTop: 20,
          paddingTop: 16,
          borderTop: `1px solid ${brand.border}`,
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ color: brand.textDim }}>Total QR codes</span>
        <span className="tnum" style={{ fontWeight: 650, fontSize: 18 }}>
          {totalUnits}
        </span>
      </div>
    </Drawer>
  );
}
