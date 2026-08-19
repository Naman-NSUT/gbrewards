import { AppstoreOutlined, SwapOutlined } from '@ant-design/icons';
import { Button, Tooltip } from 'antd';

import { brand } from '../theme';

/**
 * Jump to the worker programme's back office.
 *
 * A full page navigation, not a router link: the two panels are separate builds.
 * They are served from ONE origin precisely so the session survives the hop —
 * both authenticate the same `admins` row with the same aud='admin' token, and
 * both read it from the same localStorage keys, so nobody is asked to log in
 * twice. See src/auth/tokenStore.ts.
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
