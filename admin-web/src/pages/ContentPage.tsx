import { App, Button, Card, Form, Input, Segmented, Space } from 'antd';
import { useEffect, useMemo, useState } from 'react';

import { apiErrorMessage } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { useContentDocs, useUpsertContentDoc } from '../hooks/useContent';

interface DocForm {
  title: string;
  body: string;
}

const STANDARD_KEYS = ['terms', 'privacy', 'about'];

export function ContentPage() {
  const { message } = App.useApp();
  const docs = useContentDocs();
  const upsert = useUpsertContentDoc();
  const [form] = Form.useForm<DocForm>();

  // Explicit user selection (or a freshly-added, not-yet-persisted key). When
  // null we fall back to the first available key — derived, not stored.
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [newKey, setNewKey] = useState('');

  const keys = useMemo(() => (docs.data ?? []).map((d) => d.key), [docs.data]);
  const activeKey = selectedKey ?? keys[0] ?? null;

  // Sync the form to the currently active doc (form is an external system, so
  // updating it from an effect is the intended pattern).
  useEffect(() => {
    if (activeKey === null) return;
    const doc = (docs.data ?? []).find((d) => d.key === activeKey);
    form.setFieldsValue({ title: doc?.title ?? '', body: doc?.body ?? '' });
  }, [activeKey, docs.data, form]);

  const addKey = (key: string) => {
    const k = key.trim().toLowerCase();
    if (!k) return;
    setNewKey('');
    setSelectedKey(k);
  };

  const save = async () => {
    if (activeKey === null) return;
    const values = await form.validateFields();
    try {
      await upsert.mutateAsync({ key: activeKey, input: values });
      setSelectedKey(activeKey);
      message.success('Content saved');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not save content'));
    }
  };

  // Include the active key in the options even if it is not yet persisted so a
  // freshly-added key is visible/selected in the switcher.
  const optionKeys =
    activeKey !== null && !keys.includes(activeKey) ? [...keys, activeKey] : keys;
  const segmentOptions = optionKeys.map((k) => ({ label: k, value: k }));
  const missingStandard = STANDARD_KEYS.filter((k) => !optionKeys.includes(k));

  return (
    <>
      <PageHeader
        title="Content"
        subtitle="Edit the Terms, Privacy and About documents brokers read in the app."
      />

      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <Card style={{ minWidth: 240 }} styles={{ body: { padding: 16 } }}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {segmentOptions.length > 0 ? (
              <Segmented
                vertical
                block
                options={segmentOptions}
                value={activeKey ?? undefined}
                onChange={(v) => setSelectedKey(v as string)}
              />
            ) : (
              <span style={{ opacity: 0.6 }}>No documents yet.</span>
            )}

            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="New key (e.g. terms)"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                onPressEnter={() => addKey(newKey)}
              />
              <Button onClick={() => addKey(newKey)}>Add</Button>
            </Space.Compact>

            {missingStandard.length > 0 && (
              <Space wrap>
                {missingStandard.map((k) => (
                  <Button key={k} size="small" onClick={() => addKey(k)}>
                    + {k}
                  </Button>
                ))}
              </Space>
            )}
          </Space>
        </Card>

        <Card style={{ flex: 1, minWidth: 320 }} styles={{ body: { padding: 20 } }}>
          {activeKey === null ? (
            <span style={{ opacity: 0.6 }}>Select or add a key to edit its content.</span>
          ) : (
            <Form form={form} layout="vertical">
              <div style={{ marginBottom: 12, fontSize: 13, opacity: 0.6 }}>
                Key: <span className="mono">{activeKey}</span>
              </div>
              <Form.Item name="title" label="Title" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="body" label="Body (markdown)" rules={[{ required: true }]}>
                <Input.TextArea autoSize={{ minRows: 16 }} />
              </Form.Item>
              <Button type="primary" onClick={save} loading={upsert.isPending}>
                Save
              </Button>
            </Form>
          )}
        </Card>
      </div>
    </>
  );
}
