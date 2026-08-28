import {
  AppstoreOutlined,
  AuditOutlined,
  BarcodeOutlined,
  CheckSquareOutlined,
  DashboardOutlined,
  DollarOutlined,
  FileProtectOutlined,
  GiftOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MessageOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  ShopOutlined,
  TrophyOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { Avatar, Badge, Dropdown, Layout, Menu, Tooltip } from 'antd';
import { AnimatePresence, motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { CommandPalette } from '../components/CommandPalette';
import { PanelSwitch } from '../components/PanelSwitch';
import { Logo } from '../components/Logo';
import { APP_VERSION } from '../config';
import { useAdminProfile } from '../hooks/useAccount';
import { useDashboardStats } from '../hooks/useDashboard';
import { useHotkey } from '../lib/useHotkey';
import { brand } from '../theme';

const { Sider, Header, Content } = Layout;

interface NavItem {
  key: string;
  icon: ReactNode;
  label: string;
  group: string;
}

const NAV: NavItem[] = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard', group: 'Overview' },
  { key: '/compliance', icon: <WarningOutlined />, label: 'Dealer Compliance', group: 'Compliance' },
  { key: '/approvals', icon: <CheckSquareOutlined />, label: 'Approvals', group: 'Compliance' },
  { key: '/warranties', icon: <SafetyCertificateOutlined />, label: 'Warranties', group: 'Operations' },
  { key: '/lookup', icon: <BarcodeOutlined />, label: 'Serial Lookup', group: 'Operations' },
  { key: '/claims', icon: <FileProtectOutlined />, label: 'Claims', group: 'Operations' },
  { key: '/products', icon: <AppstoreOutlined />, label: 'Products', group: 'Operations' },
  { key: '/dealers', icon: <ShopOutlined />, label: 'Dealers', group: 'Operations' },
  { key: '/rewards', icon: <GiftOutlined />, label: 'Rewards', group: 'Rewards' },
  { key: '/redemptions', icon: <TrophyOutlined />, label: 'Redemptions', group: 'Rewards' },
  { key: '/sms', icon: <MessageOutlined />, label: 'SMS Log', group: 'System' },
  { key: '/points', icon: <DollarOutlined />, label: 'Points', group: 'System' },
  { key: '/audit', icon: <AuditOutlined />, label: 'Audit', group: 'System' },
];

const GROUPS = ['Overview', 'Compliance', 'Operations', 'Rewards', 'System'];

const COLLAPSE_KEY = 'dr_admin_sider_collapsed';

const isMac =
  typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.userAgent ?? '');

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { admin, signOut } = useAuth();
  const profile = useAdminProfile();
  const stats = useDashboardStats();
  const [cmdOpen, setCmdOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(COLLAPSE_KEY) === '1',
  );
  useHotkey('mod+k', () => setCmdOpen(true));

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      localStorage.setItem(COLLAPSE_KEY, c ? '0' : '1');
      return !c;
    });
  };

  // Longest matching prefix wins, so /dealers/x still highlights Dealers.
  const selected =
    NAV.map((i) => i.key)
      .filter((k) => (k === '/' ? location.pathname === '/' : location.pathname.startsWith(k)))
      .sort((a, b) => b.length - a.length)[0] ?? '/';
  const current = NAV.find((i) => i.key === selected);

  const displayName = profile.data?.name ?? admin?.name ?? admin?.email ?? '';
  const displayEmail = profile.data?.email ?? admin?.email ?? '';
  const role = profile.data?.role ?? admin?.role ?? '—';
  const initial = (displayName || displayEmail || '?').charAt(0).toUpperCase();
  const pendingApprovals = stats.data?.pending_approvals ?? 0;

  const renderLabel = (item: NavItem) => {
    if (item.key !== '/approvals' || pendingApprovals === 0) return item.label;
    // The queue count lives in the nav because an unworked approval is a
    // warranty sitting unpaid and unstarted — it should nag from every screen.
    return (
      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {item.label}
        <Badge
          count={pendingApprovals}
          overflowCount={99}
          style={{ background: brand.accentSoft, color: brand.accent, boxShadow: 'none' }}
        />
      </span>
    );
  };

  const menuItems = collapsed
    ? NAV.map((n) => ({ key: n.key, icon: n.icon, label: n.label }))
    : GROUPS.map((g) => ({
        type: 'group' as const,
        label: g,
        children: NAV.filter((n) => n.group === g).map((n) => ({
          key: n.key,
          icon: n.icon,
          label: renderLabel(n),
        })),
      }));

  return (
    <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
      <Sider
        width={236}
        collapsedWidth={64}
        collapsed={collapsed}
        breakpoint="lg"
        onBreakpoint={(broken) => setCollapsed(broken)}
        style={{
          background: brand.canvas,
          borderRight: `1px solid ${brand.border}`,
          position: 'sticky',
          top: 0,
          height: '100vh',
          overflow: 'auto',
        }}
      >
        <div style={{ padding: collapsed ? '18px 17px 8px' : '18px 18px 8px' }}>
          <Logo size={30} showWord={!collapsed} />
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ background: 'transparent', border: 'none' }}
        />
        {!collapsed && (
          <div
            style={{
              position: 'sticky',
              top: '100%',
              padding: '14px 20px',
              borderTop: `1px solid ${brand.border}`,
              fontSize: 11,
              color: brand.textFaint,
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>v{APP_VERSION}</span>
            <span style={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>GoodBed</span>
          </div>
        )}
      </Sider>

      <Layout style={{ background: 'transparent' }}>
        <Header
          style={{
            background: 'rgba(10,10,11,0.8)',
            backdropFilter: 'blur(12px)',
            borderBottom: `1px solid ${brand.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingInline: 20,
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
              style={{
                border: 'none',
                background: 'transparent',
                color: brand.textDim,
                cursor: 'pointer',
                fontSize: 15,
                display: 'grid',
                placeItems: 'center',
                width: 28,
                height: 28,
              }}
            >
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </button>
            <nav aria-label="Breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ color: brand.textFaint, fontSize: 13 }}>{current?.group}</span>
              <span style={{ color: brand.textFaint }}>/</span>
              <span style={{ fontSize: 14, fontWeight: 600, color: brand.text }}>
                {current?.label}
              </span>
            </nav>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <PanelSwitch />
            <button
              type="button"
              onClick={() => setCmdOpen(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                height: 32,
                paddingInline: 10,
                borderRadius: 8,
                border: `1px solid ${brand.border}`,
                background: brand.elevated,
                color: brand.textDim,
                cursor: 'pointer',
                fontSize: 13,
              }}
            >
              <SearchOutlined />
              <span>Search</span>
              <kbd
                className="mono"
                style={{
                  fontSize: 11,
                  padding: '1px 6px',
                  borderRadius: 5,
                  border: `1px solid ${brand.border}`,
                  color: brand.textFaint,
                }}
              >
                {isMac ? '⌘K' : 'Ctrl K'}
              </kbd>
            </button>

            <Dropdown
              menu={{
                items: [
                  { key: 'who', label: displayEmail || 'Signed in', disabled: true },
                  { key: 'role', label: `Role: ${role}`, disabled: true },
                  { type: 'divider' },
                  { key: 'logout', icon: <LogoutOutlined />, label: 'Log out', onClick: signOut },
                ],
              }}
              placement="bottomRight"
            >
              <button
                type="button"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 9,
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: brand.text,
                }}
              >
                <Avatar
                  size={28}
                  style={{
                    background: brand.accentSoft,
                    color: brand.accent,
                    fontWeight: 600,
                    fontSize: 13,
                  }}
                >
                  {initial}
                </Avatar>
                <Tooltip title={displayEmail}>
                  <span style={{ fontSize: 13.5 }}>{displayName}</span>
                </Tooltip>
              </button>
            </Dropdown>
          </div>
        </Header>

        <Content style={{ margin: 24 }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </Content>
      </Layout>

      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
    </Layout>
  );
}
