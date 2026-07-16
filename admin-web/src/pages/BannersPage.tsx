import { App, Button, Drawer, Form, Input, InputNumber, Popconfirm, Space, Switch, Typography } from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { Banner } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { StatusDot } from '../components/StatusDot';
import { API_BASE_URL } from '../config';
import {
  useBanners,
  useCreateBanner,
  useDeleteBanner,
  useUpdateBanner,
} from '../hooks/useBanners';

interface BannerForm {
  image_url: string;
  caption?: string;
  link_url?: string;
  sort_order: number;
  is_active: boolean;
}

/**
 * Resolve a banner image_url for display. Absolute URLs (http/https) are used
 * as-is; relative paths (starting with '/') are prefixed with the backend
 * origin — the API base URL WITHOUT the '/api/v1' prefix.
 */
function resolveImageUrl(url: string): string {
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith('/')) return `${API_BASE_URL}${url}`;
  return url;
}

export function BannersPage() {
  const { message } = App.useApp();
  const banners = useBanners();
  const createBanner = useCreateBanner();
  const updateBanner = useUpdateBanner();
  const deleteBannerMut = useDeleteBanner();

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<Banner | null>(null);
  const [form] = Form.useForm<BannerForm>();

  const onDelete = async (b: Banner) => {
    try {
      await deleteBannerMut.mutateAsync(b.id);
      message.success('Banner deleted');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not delete banner — deactivate it instead.'));
    }
  };

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ is_active: true, sort_order: 0 });
    setEditorOpen(true);
  };

  const openEdit = (b: Banner) => {
    setEditing(b);
    form.setFieldsValue({
      image_url: b.image_url,
      caption: b.caption ?? undefined,
      link_url: b.link_url ?? undefined,
      sort_order: b.sort_order,
      is_active: b.is_active,
    });
    setEditorOpen(true);
  };

  const submitEditor = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await updateBanner.mutateAsync({ id: editing.id, input: values });
        message.success('Banner updated');
      } else {
        await createBanner.mutateAsync(values);
        message.success('Banner created');
      }
      setEditorOpen(false);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not save banner'));
    }
  };

  return (
    <>
      <PageHeader
        title="Ad Carousel"
        subtitle="Manage the banner slideshow brokers see on the Home / Scan screen."
        extra={
          <Button type="primary" onClick={openCreate}>
            New banner
          </Button>
        }
      />

      <DataTable<Banner>
        rowKey="id"
        loading={banners.isLoading}
        dataSource={banners.data ?? []}
        emptyText="No banners yet"
        emptyHint="Create a banner to show it in the mobile ad carousel."
        columns={[
          {
            title: 'Preview',
            dataIndex: 'image_url',
            render: (url: string) => (
              <img
                src={resolveImageUrl(url)}
                alt="banner preview"
                style={{
                  width: 120,
                  height: 56,
                  objectFit: 'cover',
                  borderRadius: 6,
                  background: 'rgba(255,255,255,0.04)',
                }}
              />
            ),
          },
          {
            title: 'Caption',
            dataIndex: 'caption',
            render: (t: string | null) =>
              t ? <span style={{ fontWeight: 550 }}>{t}</span> : <span className="tnum">—</span>,
          },
          {
            title: 'Sort order',
            dataIndex: 'sort_order',
            render: (v: number) => <span className="tnum">{v}</span>,
          },
          {
            title: 'Status',
            dataIndex: 'is_active',
            render: (v: boolean) => <StatusDot status={v ? 'active' : 'inactive'} />,
          },
          {
            title: '',
            align: 'right',
            render: (_v, b) => (
              <Space size="large">
                <a onClick={() => openEdit(b)}>Edit</a>
                <Popconfirm
                  title="Delete this banner?"
                  description="This removes it from the carousel permanently. To hide it temporarily, deactivate it instead."
                  okText="Delete"
                  okButtonProps={{ danger: true }}
                  onConfirm={() => onDelete(b)}
                >
                  <a style={{ color: '#e5648b' }}>Delete</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title={editing ? 'Edit banner' : 'New banner'}
        width={420}
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        extra={
          <Button
            type="primary"
            onClick={submitEditor}
            loading={createBanner.isPending || updateBanner.isPending}
          >
            Save
          </Button>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="image_url"
            label="Image URL"
            rules={[{ required: true, message: 'An image URL is required' }]}
            extra={
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                A full https URL to any hosted image (e.g. https://…/poster.jpg), or a backend
                static path starting with “/” (e.g. /static/banners/goodbed-poster.jpg), which is
                resolved against the backend origin.
              </Typography.Text>
            }
          >
            <Input placeholder="https://… or /static/banners/…" />
          </Form.Item>
          <Form.Item name="caption" label="Caption">
            <Input placeholder="GoodBed HR Foam — 25 Year Warranty" />
          </Form.Item>
          <Form.Item name="link_url" label="Link URL">
            <Input placeholder="https://… (optional, opened when tapped)" />
          </Form.Item>
          <Form.Item name="sort_order" label="Sort order">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Drawer>
    </>
  );
}
