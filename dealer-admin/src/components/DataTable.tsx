import { Table, type TableProps } from 'antd';
import type { ReactNode } from 'react';

import { EmptyState } from './EmptyState';
import { TableSkeleton } from './skeletons';

type Props<T> = Omit<TableProps<T>, 'pagination'> & {
  emptyText?: string;
  emptyHint?: string;
  emptyIcon?: ReactNode;
  emptyAction?: ReactNode;
  skeletonRows?: number;
  /** Supply total + onPageChange to get paging; omit them for a full list. */
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number, pageSize: number) => void;
};

/**
 * The single table in this app. It owns the three states every admin table has
 * to get right — first load, empty, and paging — so no screen reinvents them
 * and none of them can drift apart.
 */
export function DataTable<T extends object>({
  loading,
  emptyText = 'No records',
  emptyHint,
  emptyIcon,
  emptyAction,
  skeletonRows = 8,
  total,
  page = 1,
  pageSize = 25,
  onPageChange,
  ...props
}: Props<T>) {
  const isEmpty = !props.dataSource || props.dataSource.length === 0;
  // A spinner over an empty grid tells the reader nothing. The skeleton shows
  // the shape of what is coming, and only on the FIRST load — a refetch keeps
  // the old rows visible under the spinner instead of blanking the screen.
  if (loading && isEmpty) return <TableSkeleton rows={skeletonRows} />;

  return (
    <Table<T>
      size="small"
      sticky
      loading={loading}
      locale={{
        emptyText: (
          <EmptyState
            title={emptyText}
            hint={emptyHint}
            icon={emptyIcon}
            action={emptyAction}
            height={200}
          />
        ),
      }}
      pagination={
        onPageChange
          ? {
              current: page,
              pageSize,
              total: total ?? 0,
              showSizeChanger: true,
              pageSizeOptions: [25, 50, 100, 200],
              size: 'small',
              showTotal: (t, range) => `${range[0]}–${range[1]} of ${t.toLocaleString()}`,
              onChange: onPageChange,
            }
          : false
      }
      {...props}
    />
  );
}
