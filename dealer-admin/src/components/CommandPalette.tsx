import {
  AuditOutlined,
  BarcodeOutlined,
  CheckSquareOutlined,
  DashboardOutlined,
  DollarOutlined,
  FileProtectOutlined,
  GiftOutlined,
  LogoutOutlined,
  MessageOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  ShopOutlined,
  ToolOutlined,
  TrophyOutlined,
  UploadOutlined,
  WarningOutlined,
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
  keywords?: string;
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
      { id: 'compliance', label: 'Dealer Compliance', group: 'Navigate', icon: <WarningOutlined />, keywords: 'rate laggards', run: go('/compliance') },
      { id: 'approvals', label: 'Approvals', group: 'Navigate', icon: <CheckSquareOutlined />, keywords: 'backdate self registration', run: go('/approvals') },
      { id: 'warranties', label: 'Warranties', group: 'Navigate', icon: <SafetyCertificateOutlined />, run: go('/warranties') },
      { id: 'lookup', label: 'Serial Lookup', group: 'Navigate', icon: <BarcodeOutlined />, keywords: 'qr serial support', run: go('/lookup') },
      { id: 'claims', label: 'Claims', group: 'Navigate', icon: <FileProtectOutlined />, run: go('/claims') },
      { id: 'allocations', label: 'Allocations', group: 'Navigate', icon: <UploadOutlined />, run: go('/allocations') },
      { id: 'dealers', label: 'Dealers', group: 'Navigate', icon: <ShopOutlined />, run: go('/dealers') },
      { id: 'rewards', label: 'Rewards', group: 'Navigate', icon: <GiftOutlined />, run: go('/rewards') },
      { id: 'redemptions', label: 'Redemptions', group: 'Navigate', icon: <TrophyOutlined />, run: go('/redemptions') },
      { id: 'sms', label: 'SMS Log', group: 'Navigate', icon: <MessageOutlined />, run: go('/sms') },
      { id: 'points', label: 'Points', group: 'Navigate', icon: <DollarOutlined />, keywords: 'rate adjust', run: go('/points') },
      { id: 'audit', label: 'Audit', group: 'Navigate', icon: <AuditOutlined />, run: go('/audit') },
      {
        id: 'new-dealer',
        label: 'New dealer',
        group: 'Actions',
        icon: <PlusOutlined />,
        run: go('/dealers?new=1'),
      },
      {
        id: 'upload-alloc',
        label: 'Upload allocation CSV',
        group: 'Actions',
        icon: <UploadOutlined />,
        run: go('/allocations?upload=1'),
      },
      {
        id: 'adjust',
        label: 'Adjust a dealer’s points',
        group: 'Actions',
        icon: <ToolOutlined />,
        run: go('/points?adjust=1'),
      },
      {
        id: 'logout',
        label: 'Log out',
        group: 'Actions',
        icon: <LogoutOutlined />,
        run: () => {
          onClose();
          signOut();
        },
      },
    ];
  }, [navigate, onClose, signOut]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    const matches = commands.filter(
      (c) => c.label.toLowerCase().includes(q) || c.keywords?.includes(q),
    );
    // Anything that looks like a scanned serial gets a lookup as the top hit:
    // support staff paste one in here constantly and should not have to
    // navigate first and paste second.
    if (q.length >= 6) {
      matches.unshift({
        id: 'lookup-direct',
        label: `Look up serial “${query.trim()}”`,
        group: 'Search',
        icon: <SearchOutlined />,
        run: () => {
          navigate(`/lookup?serial=${encodeURIComponent(query.trim())}`);
          onClose();
        },
      });
    }
    return matches;
  }, [commands, query, navigate, onClose]);

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
      destroyOnHidden
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
        placeholder="Jump to a screen, or paste a serial…"
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
      <div style={{ maxHeight: 380, overflowY: 'auto', padding: 8 }}>
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
