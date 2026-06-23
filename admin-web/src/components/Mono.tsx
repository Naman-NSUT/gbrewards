import { CheckOutlined, CopyOutlined } from '@ant-design/icons';
import { App, Tooltip } from 'antd';
import { useState } from 'react';

import { brand } from '../theme';

/** Monospace, truncated identifier/token with copy-on-click. */
export function Mono({ value, chars = 10 }: { value: string; chars?: number }) {
  const { message } = App.useApp();
  const [copied, setCopied] = useState(false);
  const short = value.length > chars ? `${value.slice(0, chars)}…` : value;

  const copy = async () => {
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
    <Tooltip title={value}>
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
        <span className="mono" style={{ fontSize: 12.5, color: brand.text }}>
          {short}
        </span>
        {copied ? (
          <CheckOutlined style={{ fontSize: 11, color: brand.success }} />
        ) : (
          <CopyOutlined style={{ fontSize: 11 }} />
        )}
      </button>
    </Tooltip>
  );
}
