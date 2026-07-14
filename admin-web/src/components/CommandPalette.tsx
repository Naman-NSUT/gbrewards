import {
  AppstoreOutlined,
  AuditOutlined,
  DashboardOutlined,
  FileTextOutlined,
  GiftOutlined,
  LogoutOutlined,
  PlusOutlined,
  QrcodeOutlined,
  QuestionCircleOutlined,
  SearchOutlined,
  TeamOutlined,
  UndoOutlined,
} from '@ant-design/icons';
import { Modal } from 'antd';
import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { brand } from '../theme';

interface Command {
  id: string;
  label: string;
  group: string;
  icon: ReactNode;
  run: () => void;
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);

  const commands = useMemo<Command[]>(() => {
    const go = (path: string) => () => {
      navigate(path);
      onClose();
    };
    return [
      { id: 'dash', label: 'Dashboard', group: 'Navigate', icon: <DashboardOutlined />, run: go('/') },
      { id: 'products', label: 'Products & QR', group: 'Navigate', icon: <AppstoreOutlined />, run: go('/products') },
      { id: 'rewards', label: 'Rewards', group: 'Navigate', icon: <GiftOutlined />, run: go('/rewards') },
      { id: 'faqs', label: 'FAQs', group: 'Navigate', icon: <QuestionCircleOutlined />, run: go('/faqs') },
      { id: 'content', label: 'Content', group: 'Navigate', icon: <FileTextOutlined />, run: go('/content') },
      { id: 'users', label: 'Users', group: 'Navigate', icon: <TeamOutlined />, run: go('/users') },
      { id: 'redemptions', label: 'Redemptions', group: 'Navigate', icon: <GiftOutlined />, run: go('/redemptions') },
      { id: 'returns', label: 'Returns', group: 'Navigate', icon: <UndoOutlined />, run: go('/returns') },
      { id: 'units', label: 'QR Lookup', group: 'Navigate', icon: <SearchOutlined />, run: go('/units') },
      { id: 'scans', label: 'Scans', group: 'Navigate', icon: <QrcodeOutlined />, run: go('/scans') },
      { id: 'audit', label: 'Audit trail', group: 'Navigate', icon: <AuditOutlined />, run: go('/audit') },
      {
        id: 'new-product',
        label: 'New product',
        group: 'Actions',
        icon: <PlusOutlined />,
        run: () => {
          navigate('/products?new=1');
          onClose();
        },
      },
      { id: 'logout', label: 'Log out', group: 'Actions', icon: <LogoutOutlined />, run: () => { onClose(); signOut(); } },
    ];
  }, [navigate, onClose, signOut]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? commands.filter((c) => c.label.toLowerCase().includes(q)) : commands;
  }, [commands, query]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      filtered[active]?.run();
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      closable={false}
      width={560}
      styles={{ body: { padding: 0 } }}
      style={{ top: '14vh' }}
      destroyOnClose
      afterOpenChange={(o) => {
        if (o) {
          setQuery('');
          setActive(0);
        }
      }}
    >
      <input
        autoFocus
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
        }}
        onKeyDown={onKeyDown}
        placeholder="Type a command or search…"
        style={{
          width: '100%',
          boxSizing: 'border-box',
          border: 'none',
          borderBottom: `1px solid ${brand.border}`,
          background: 'transparent',
          color: brand.text,
          fontSize: 15,
          padding: '16px 18px',
          outline: 'none',
        }}
      />
      <div style={{ maxHeight: 360, overflowY: 'auto', padding: 8 }}>
        {filtered.length === 0 && (
          <div style={{ padding: 24, textAlign: 'center', color: brand.textDim }}>No results</div>
        )}
        {filtered.map((c, i) => (
          <button
            key={c.id}
            type="button"
            onMouseEnter={() => setActive(i)}
            onClick={c.run}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              width: '100%',
              textAlign: 'left',
              border: 'none',
              cursor: 'pointer',
              padding: '10px 12px',
              borderRadius: 8,
              background: i === active ? brand.accentSoft : 'transparent',
              color: i === active ? brand.text : brand.textDim,
            }}
          >
            <span style={{ fontSize: 15, color: i === active ? brand.accent : brand.textFaint }}>
              {c.icon}
            </span>
            <span style={{ flex: 1, fontSize: 14, color: brand.text }}>{c.label}</span>
            <span style={{ fontSize: 11, color: brand.textFaint }}>{c.group}</span>
          </button>
        ))}
      </div>
    </Modal>
  );
}
