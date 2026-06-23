import { App, Button, Form, Input } from 'antd';

import { apiErrorMessage } from '../api/client';
import { changePassword, updateProfile } from '../api/account';
import { useAuth } from '../auth/AuthContext';
import { PageHeader } from '../components/PageHeader';
import { SpotlightCard } from '../components/SpotlightCard';
import { brand } from '../theme';

export function AccountPage() {
  const { message } = App.useApp();
  const { admin, updateAdmin } = useAuth();
  const [profileForm] = Form.useForm();
  const [pwForm] = Form.useForm();

  const onSaveProfile = async (values: { name?: string; email?: string }) => {
    try {
      const updated = await updateProfile(values);
      updateAdmin({ email: updated.email, name: updated.name });
      message.success('Profile updated');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not update profile'));
    }
  };

  const onChangePassword = async (values: {
    current: string;
    next: string;
    confirm: string;
  }) => {
    if (values.next !== values.confirm) {
      message.error('New passwords do not match');
      return;
    }
    try {
      await changePassword(values.current, values.next);
      message.success('Password changed');
      pwForm.resetFields();
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not change password'));
    }
  };

  return (
    <>
      <PageHeader title="Account" subtitle="Manage your admin credentials." />

      <div style={{ maxWidth: 520, display: 'flex', flexDirection: 'column', gap: 18 }}>
        <SpotlightCard style={{ padding: 22 }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600 }}>Profile</h3>
          <Form
            form={profileForm}
            layout="vertical"
            initialValues={{ name: admin?.name ?? '', email: admin?.email ?? '' }}
            onFinish={onSaveProfile}
            requiredMark={false}
          >
            <Form.Item name="email" label="Username / email" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="name" label="Display name">
              <Input />
            </Form.Item>
            <Button type="primary" htmlType="submit">
              Save profile
            </Button>
          </Form>
        </SpotlightCard>

        <SpotlightCard style={{ padding: 22 }}>
          <h3 style={{ margin: '0 0 4px', fontSize: 15, fontWeight: 600 }}>Change password</h3>
          <p style={{ margin: '0 0 16px', color: brand.textDim, fontSize: 13 }}>
            Use at least 8 characters.
          </p>
          <Form form={pwForm} layout="vertical" onFinish={onChangePassword} requiredMark={false}>
            <Form.Item name="current" label="Current password" rules={[{ required: true }]}>
              <Input.Password autoComplete="current-password" />
            </Form.Item>
            <Form.Item
              name="next"
              label="New password"
              rules={[{ required: true, min: 8 }]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
            <Form.Item name="confirm" label="Confirm new password" rules={[{ required: true }]}>
              <Input.Password autoComplete="new-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit">
              Update password
            </Button>
          </Form>
        </SpotlightCard>
      </div>
    </>
  );
}
