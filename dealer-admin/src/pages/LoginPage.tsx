import { LockOutlined, MailOutlined } from '@ant-design/icons';
import { Alert, Button, Form, Input } from 'antd';
import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { login } from '../api/auth';
import { apiErrorMessage } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Logo } from '../components/Logo';
import { brand } from '../theme';

interface LocationState {
  from?: string;
}

export function LoginPage() {
  const { signIn, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const from = (location.state as LocationState | null)?.from ?? '/';
  // Redirect declaratively — navigating during render logs a warning and races
  // the first paint.
  if (isAuthenticated) return <Navigate to={from} replace />;

  const onFinish = async (values: { email: string; password: string }) => {
    setError(null);
    setLoading(true);
    try {
      const pair = await login(values.email.trim(), values.password);
      signIn(pair, values.email.trim());
      navigate(from, { replace: true });
    } catch (e) {
      setError(apiErrorMessage(e, 'Sign-in failed'));
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

        <div className="dr-gborder">
          <div className="dr-gborder__inner" style={{ padding: 28 }}>
            <h2 style={{ margin: '0 0 4px', fontSize: 19, fontWeight: 650, letterSpacing: -0.3 }}>
              Welcome back
            </h2>
            <p style={{ margin: '0 0 22px', color: brand.textDim, fontSize: 13.5 }}>
              Sign in to the GoodBed dealer warranty panel.
            </p>

            {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}

            <Form layout="vertical" onFinish={onFinish} requiredMark={false} size="large">
              <Form.Item
                name="email"
                label="Email"
                rules={[{ required: true, message: 'Enter your email' }]}
              >
                <Input
                  prefix={<MailOutlined style={{ color: brand.textFaint }} />}
                  placeholder="you@goodbed.in"
                  autoComplete="username"
                  inputMode="email"
                />
              </Form.Item>
              <Form.Item
                name="password"
                label="Password"
                rules={[{ required: true, message: 'Enter your password' }]}
              >
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
          Dealer Rewards · GoodBed warranty registration
        </p>
      </div>
    </div>
  );
}
