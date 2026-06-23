import { App, Input, Switch } from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { AdminUser } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { useSetUserActive, useUsers } from '../hooks/useUsers';
import { formatDateTime } from '../lib/format';
import { UserDetailDrawer } from './UserDetailDrawer';

export function UsersPage() {
  const { message } = App.useApp();
  const [q, setQ] = useState('');
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const users = useUsers(q, cursor);
  const setActive = useSetUserActive();
  const [detailId, setDetailId] = useState<string | null>(null);

  const toggleActive = async (u: AdminUser, isActive: boolean) => {
    try {
      await setActive.mutateAsync({ id: u.id, isActive });
      message.success(isActive ? 'User enabled' : 'User disabled');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not update user'));
    }
  };

  return (
    <>
      <PageHeader
        title="Users"
        subtitle="Brokers, balances and point adjustments."
        extra={
          <Input.Search
            allowClear
            placeholder="Search name or phone"
            style={{ width: 280 }}
            onSearch={(v) => {
              setCursor(undefined);
              setQ(v);
            }}
          />
        }
      />

      <DataTable<AdminUser>
        rowKey="id"
        loading={users.isLoading}
        dataSource={users.data?.items ?? []}
        emptyText="No users yet"
        emptyHint="Brokers appear here after their first OTP sign-in."
        columns={[
          {
            title: 'Name',
            dataIndex: 'name',
            render: (n, u) => (
              <a onClick={() => setDetailId(u.id)} style={{ fontWeight: 550 }}>
                {n}
              </a>
            ),
          },
          { title: 'Phone', dataIndex: 'phone', render: (p: string) => <span className="mono">{p}</span> },
          { title: 'Balance', dataIndex: 'balance', render: (v: number) => <span className="tnum">{v}</span> },
          { title: 'Earned', dataIndex: 'total_earned', render: (v: number) => <span className="tnum">{v}</span> },
          { title: 'Last active', dataIndex: 'last_active_at', render: formatDateTime },
          {
            title: 'Active',
            dataIndex: 'is_active',
            render: (v: boolean, u) => (
              <Switch
                checked={v}
                loading={setActive.isPending}
                onChange={(checked) => toggleActive(u, checked)}
              />
            ),
          },
        ]}
      />
      {users.data?.next_cursor && (
        <a style={{ display: 'inline-block', marginTop: 12 }} onClick={() => setCursor(users.data.next_cursor ?? undefined)}>
          Next page →
        </a>
      )}

      <UserDetailDrawer userId={detailId} open={detailId !== null} onClose={() => setDetailId(null)} />
    </>
  );
}
