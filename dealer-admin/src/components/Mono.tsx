import { CheckOutlined, CopyOutlined } from '@ant-design/icons';
import { App, Tooltip } from 'antd';
import { useState } from 'react';

import { brand } from '../theme';

/**
 * Serials are UUIDs read off a QR sticker and quoted down the phone. They are
 * shown in the mono face so a 0 is never an O, truncated so they don't eat a
 * table, and copied on click because nobody should retype one.
 */
export function Mono({
  value,
  chars = 12,
  size = 12.5,
  onClick,
}: {
  value: string;
  chars?: number;
  size?: number;
  /** Overrides copy — used where the serial should open a record instead. */
  onClick?: () => void;
}) {
  const { message } = App.useApp();
  const [copied, setCopied] = useState(false);
  const short = value.length > chars ? `${value.slice(0, chars)}…` : value;

  const copy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onClick) {
      onClick();
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      message.success('Copied', 1);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      message.error('Copy failed');
    }
  };

  return (
    <Tooltip title={onClick ? value : `${value} · click to copy`}>
      <button
        type="button"
        onClick={copy}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          padding: 0,
          color: brand.textDim,
        }}
      >
        <span className="mono" style={{ fontSize: size, color: brand.text }}>
          {short}
        </span>
        {onClick ? null : copied ? (
          <CheckOutlined style={{ fontSize: 11, color: brand.success }} />
        ) : (
          <CopyOutlined style={{ fontSize: 11 }} />
        )}
      </button>
    </Tooltip>
  );
}
