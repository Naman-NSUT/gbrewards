import { Table, type TableProps } from 'antd';

import { EmptyState } from './EmptyState';
import { TableSkeleton } from './skeletons';

type Props<T> = TableProps<T> & {
  emptyText?: string;
  emptyHint?: string;
  skeletonRows?: number;
};

/** AntD Table standardized to the design system: compact, hairline, sticky
 *  header, content-shaped skeleton on first load, crafted empty state. */
export function DataTable<T extends object>({
  loading,
  emptyText = 'No records',
  emptyHint,
  skeletonRows = 6,
  ...props
}: Props<T>) {
  const isEmpty = !props.dataSource || props.dataSource.length === 0;
  if (loading && isEmpty) {
    return <TableSkeleton rows={skeletonRows} />;
  }
  return (
    <Table<T>
      size="small"
      pagination={false}
      sticky
      loading={loading}
      locale={{ emptyText: <EmptyState title={emptyText} hint={emptyHint} height={180} /> }}
      {...props}
    />
  );
}
