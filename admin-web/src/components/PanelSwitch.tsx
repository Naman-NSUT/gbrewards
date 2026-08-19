import { SafetyCertificateOutlined, SwapOutlined } from '@ant-design/icons';
import { Button, Tooltip } from 'antd';

import { brand } from '../theme';

/**
 * Jump to the dealer programme's back office.
 *
 * A full page navigation, not a router link: the two panels are separate builds
 * served from one origin — this one at `/`, the dealer panel at `/dealer`.
 * The programmes share no accounts, so this does NOT carry a session — the
 * dealer panel has its own login against its own `dealer_admins` table. Both
 * being on one origin with different storage keys means the two sessions coexist
 * in the browser: after signing into each once, switching is instant.
 */
export function PanelSwitch() {
  return (
    <Tooltip title="Dealer programme — warranties, allocations, dealer compliance">
      <Button
        icon={<SwapOutlined />}
        onClick={() => {
          window.location.href = '/dealer/';
        }}
        style={{
          background: brand.elevated,
          borderColor: brand.border,
          color: brand.textDim,
        }}
      >
        <SafetyCertificateOutlined style={{ marginInlineEnd: 4 }} />
        Dealer panel
      </Button>
    </Tooltip>
  );
}
