import {
  AppstoreOutlined,
  AuditOutlined,
  DashboardOutlined,
  FileTextOutlined,
  GiftOutlined,
  LogoutOutlined,
  QrcodeOutlined,
  QuestionCircleOutlined,
  SearchOutlined,
  SettingOutlined,
  TeamOutlined,
  UndoOutlined,
} from '@ant-design/icons';
import { Avatar, Dropdown, Layout, Menu } from 'antd';
import { AnimatePresence, motion } from 'framer-motion';
import { useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

import { CommandPalette } from '../components/CommandPalette';
import { Logo } from '../components/Logo';
import { useAuth } from '../auth/AuthContext';
import { useHotkey } from '../lib/useHotkey';
import { brand } from '../theme';

const { Sider, Header, Content } = Layout;

const NAV = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard', group: 'Overview' },
  { key: '/products', icon: <AppstoreOutlined />, label: 'Products & QR', group: 'Catalog' },
  { key: '/rewards', icon: <GiftOutlined />, label: 'Rewards', group: 'Catalog' },
  { key: '/faqs', icon: <QuestionCircleOutlined />, label: 'FAQs', group: 'Content' },
  { key: '/content', icon: <FileTextOutlined />, label: 'Content', group: 'Content' },
  { key: '/users', icon: <TeamOutlined />, label: 'Users', group: 'Operations' },
  { key: '/redemptions', icon: <GiftOutlined />, label: 'Redemptions', group: 'Operations' },
  { key: '/returns', icon: <UndoOutlined />, label: 'Returns', group: 'Operations' },
  { key: '/units', icon: <SearchOutlined />, label: 'QR Lookup', group: 'Operations' },
  { key: '/scans', icon: <QrcodeOutlined />, label: 'Scans', group: 'Insights' },
  { key: '/audit', icon: <AuditOutlined />, label: 'Audit', group: 'Insights' },
];

const GROUPS = ['Overview', 'Catalog', 'Content', 'Operations', 'Insights'];

const isMac =
  typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform ?? '');

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { admin, signOut } = useAuth();
  const [cmdOpen, setCmdOpen] = useState(false);
  useHotkey('mod+k', () => setCmdOpen(true));

  const selected =
    NAV.map((i) => i.key)
      .filter((k) => (k === '/' ? location.pathname === '/' : location.pathname.startsWith(k)))
      .sort((a, b) => b.length - a.length)[0] ?? '/';
  const current = NAV.find((i) => i.key === selected);
  const initial = (admin?.name ?? admin?.email ?? '?').charAt(0).toUpperCase();

  const menuItems = GROUPS.map((g) => ({
    type: 'group' as const,
    label: g,
    children: NAV.filter((n) => n.group === g).map((n) => ({
      key: n.key,
      icon: n.icon,
      label: n.label,
    })),
  }));

  return (
    <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
      <Sider
        width={236}
        breakpoint="lg"
        collapsedWidth="0"
        style={{ background: brand.canvas, borderRight: `1px solid ${brand.border}` }}
      >
        <div style={{ padding: '18px 18px 8px' }}>
          <Logo size={30} />
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ background: 'transparent', border: 'none' }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            width: '100%',
            padding: '14px 20px',
            borderTop: `1px solid ${brand.border}`,
            fontSize: 11,
            color: brand.textFaint,
            display: 'flex',
            justifyContent: 'space-between',
          }}
        >
          <span>v0.1.0</span>
          <span style={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>dev</span>
        </div>
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
            paddingInline: 24,
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: brand.textFaint, fontSize: 13 }}>{current?.group}</span>
            <span style={{ color: brand.textFaint }}>/</span>
            <span style={{ fontSize: 14, fontWeight: 600, color: brand.text }}>
              {current?.label}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
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
                  { key: 'role', label: `Role: ${admin?.role ?? '—'}`, disabled: true },
                  { type: 'divider' },
                  {
                    key: 'account',
                    icon: <SettingOutlined />,
                    label: 'Account',
                    onClick: () => navigate('/account'),
                  },
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
                  style={{ background: brand.accentSoft, color: brand.accent, fontWeight: 600, fontSize: 13 }}
                >
                  {initial}
                </Avatar>
                <span style={{ fontSize: 13.5 }}>{admin?.name ?? admin?.email}</span>
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
