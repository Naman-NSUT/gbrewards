import { AppstoreOutlined, SwapOutlined } from '@ant-design/icons';
import { Button, Tooltip } from 'antd';

import { brand } from '../theme';

/**
 * Jump to the worker programme's back office.
 *
 * A full page navigation, not a router link: the two panels are separate builds.
 *
 * The programmes share no accounts, so this does NOT carry a session — the
 * worker panel needs its own login. Because both are served from one origin with
 * different storage keys, the two sessions coexist: once signed into both, the
 * switch is instant thereafter. See src/auth/tokenStore.ts.
 */
export function PanelSwitch() {
  return (
    <Tooltip title="Factory worker programme — QR batches, scans, worker points">
      <Button
        icon={<SwapOutlined />}
        onClick={() => {
          window.location.href = '/';
        }}
        style={{
          background: brand.elevated,
          borderColor: brand.border,
          color: brand.textDim,
        }}
      >
        <AppstoreOutlined style={{ marginInlineEnd: 4 }} />
        Worker panel
      </Button>
    </Tooltip>
  );
}
