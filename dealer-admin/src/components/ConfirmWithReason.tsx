import { Alert, Input, Modal } from 'antd';
import type { ReactNode } from 'react';
import { useState } from 'react';

import { brand } from '../theme';

const MIN_REASON = 5;

/**
 * The one modal behind every action the backend refuses without a reason —
 * void, reject, revoke, suspend, adjust, edit-customer (see
 * services/audit.REASON_REQUIRED).
 *
 * The reason is typed here rather than picked from a list on purpose. A dropdown
 * would get one option clicked for everything, and the audit row exists to be
 * read by a client asking "why did we cancel this customer's warranty?" a year
 * later. A menu cannot answer that; a sentence can.
 */
export function ConfirmWithReason({
  open,
  title,
  description,
  confirmText = 'Confirm',
  danger = false,
  placeholder = 'Why are you doing this? This is recorded against your name.',
  extra,
  loading = false,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmText?: string;
  danger?: boolean;
  placeholder?: string;
  /** Extra controls that belong to the decision (e.g. "also claw back points"). */
  extra?: ReactNode;
  loading?: boolean;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const tooShort = reason.trim().length < MIN_REASON;

  const submit = () => {
    setTouched(true);
    if (tooShort) return;
    onConfirm(reason.trim());
  };

  return (
    <Modal
      open={open}
      title={title}
      okText={confirmText}
      okButtonProps={{ danger, disabled: tooShort }}
      confirmLoading={loading}
      onOk={submit}
      onCancel={onCancel}
      destroyOnHidden
      afterOpenChange={(isOpen) => {
        if (isOpen) {
          setReason('');
          setTouched(false);
        }
      }}
      width={480}
    >
      {description && (
        <div style={{ color: brand.textDim, fontSize: 13.5, marginBottom: 14 }}>{description}</div>
      )}
      {extra && <div style={{ marginBottom: 14 }}>{extra}</div>}

      <div style={{ fontSize: 12.5, color: brand.textDim, marginBottom: 6 }}>
        Reason <span style={{ color: brand.danger }}>*</span>
      </div>
      <Input.TextArea
        autoFocus
        rows={3}
        value={reason}
        maxLength={400}
        showCount
        onChange={(e) => setReason(e.target.value)}
        onBlur={() => setTouched(true)}
        onPressEnter={(e) => {
          if (e.metaKey || e.ctrlKey) submit();
        }}
        placeholder={placeholder}
        status={touched && tooShort ? 'error' : undefined}
      />
      {touched && tooShort && (
        <Alert
          type="error"
          showIcon
          style={{ marginTop: 10 }}
          message={`Write at least ${MIN_REASON} characters — this goes on the audit trail.`}
        />
      )}
    </Modal>
  );
}
