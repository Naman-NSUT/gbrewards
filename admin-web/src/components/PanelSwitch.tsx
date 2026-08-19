import { SafetyCertificateOutlined, SwapOutlined } from '@ant-design/icons';
import { Button, Tooltip } from 'antd';

import { brand } from '../theme';

/**
 * Jump to the dealer programme's back office.
 *
 * A full page navigation, not a router link: the two panels are separate builds
 * served from one origin — this one at `/`, the dealer panel at `/dealer`.
 * Sharing the origin is what lets the session come along: both panels
 * authenticate the same `admins` row with the same aud='admin' token and read it
 * from the same localStorage keys, so switching never asks for a second login.
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
