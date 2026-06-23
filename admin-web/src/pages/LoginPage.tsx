import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { Alert, Button, Form, Input } from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { login } from '../api/auth';
import { apiErrorMessage } from '../api/client';
import { Logo } from '../components/Logo';
import { useAuth } from '../auth/AuthContext';
import { brand } from '../theme';

export function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { email: string; password: string }) => {
    setError(null);
    setLoading(true);
    try {
      const pair = await login(values.email, values.password);
      signIn(pair);
      navigate('/', { replace: true });
    } catch (e) {
      setError(apiErrorMessage(e, 'Login failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24 }}>
      <div style={{ width: 380, maxWidth: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 26 }}>
          <Logo size={34} />
        </div>

        <div className="sr-gborder">
          <div className="sr-gborder__inner" style={{ padding: 28 }}>
            <h2 style={{ margin: '0 0 4px', fontSize: 19, fontWeight: 650, letterSpacing: -0.3 }}>
            Welcome back
          </h2>
          <p style={{ margin: '0 0 22px', color: brand.textDim, fontSize: 13.5 }}>
            Sign in to the GB Rewards control panel.
          </p>

          {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}

          <Form layout="vertical" onFinish={onFinish} requiredMark={false} size="large">
            <Form.Item name="email" label="Username" rules={[{ required: true }]}>
              <Input prefix={<UserOutlined style={{ color: brand.textFaint }} />} placeholder="gbrewards" autoComplete="username" />
            </Form.Item>
            <Form.Item name="password" label="Password" rules={[{ required: true }]}>
              <Input.Password
                prefix={<LockOutlined style={{ color: brand.textFaint }} />}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              block
              size="large"
              loading={loading}
              style={{ marginTop: 4, height: 44, fontWeight: 600 }}
            >
              Sign in
            </Button>
          </Form>
          </div>
        </div>

        <p style={{ textAlign: 'center', color: brand.textFaint, fontSize: 12, marginTop: 18 }}>
          GB Rewards · QR rewards & loyalty platform
        </p>
      </div>
    </div>
  );
}
