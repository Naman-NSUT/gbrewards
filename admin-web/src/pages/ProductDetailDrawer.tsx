import { useQuery, useQueryClient } from '@tanstack/react-query';
import { App, Col, Drawer, Popconfirm, Row, Statistic } from 'antd';

import { apiErrorMessage } from '../api/client';
import { listUnits, voidUnit } from '../api/units';
import type { Unit } from '../api/types';
import { DataTable } from '../components/DataTable';
import { Mono } from '../components/Mono';
import { StatusDot } from '../components/StatusDot';
import { useProduct } from '../hooks/useProducts';

export function ProductDetailDrawer({
  productId,
  open,
  onClose,
}: {
  productId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  const qc = useQueryClient();
  const product = useProduct(open ? productId : null);

  const units = useQuery({
    queryKey: ['units', productId],
    queryFn: () => listUnits({ product_id: productId as string }),
    enabled: open && productId !== null,
  });

  const onVoid = async (unit: Unit) => {
    try {
      await voidUnit(unit.id);
      message.success('Unit voided');
      void units.refetch();
      void qc.invalidateQueries({ queryKey: ['product', productId] });
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not void unit'));
    }
  };

  return (
    <Drawer
      title={product.data ? `Product — ${product.data.name}` : 'Product'}
      width={720}
      open={open}
      onClose={onClose}
    >
      {product.data && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Statistic title="Generated" value={product.data.units_generated} />
          </Col>
          <Col span={6}>
            <Statistic title="Claimed" value={product.data.units_claimed} />
          </Col>
          <Col span={6}>
            <Statistic title="Available" value={product.data.units_available} />
          </Col>
          <Col span={6}>
            <Statistic title="Void" value={product.data.units_void} />
          </Col>
        </Row>
      )}

      <DataTable<Unit>
        rowKey="id"
        loading={units.isLoading}
        dataSource={units.data ?? []}
        pagination={{ pageSize: 10 }}
        emptyText="No units in this product"
        columns={[
          { title: 'Token', dataIndex: 'token', render: (t: string) => <Mono value={t} chars={14} /> },
          {
            title: 'Status',
            dataIndex: 'status',
            render: (s: string) => <StatusDot status={s} />,
          },
          {
            title: '',
            align: 'right',
            render: (_v, unit) =>
              unit.status === 'active' ? (
                <Popconfirm title="Void this unit?" onConfirm={() => onVoid(unit)}>
                  <a>Void</a>
                </Popconfirm>
              ) : null,
          },
        ]}
      />
    </Drawer>
  );
}
