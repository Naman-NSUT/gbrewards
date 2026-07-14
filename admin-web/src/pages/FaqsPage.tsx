import { App, Button, Drawer, Form, Input, InputNumber, Popconfirm, Space, Switch } from 'antd';
import { useState } from 'react';

import { apiErrorMessage } from '../api/client';
import type { Faq } from '../api/types';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { StatusDot } from '../components/StatusDot';
import { useCreateFaq, useDeleteFaq, useFaqs, useUpdateFaq } from '../hooks/useFaqs';
import { formatDateTime } from '../lib/format';

interface FaqForm {
  question: string;
  answer: string;
  sort_order: number;
  is_published: boolean;
}

export function FaqsPage() {
  const { message } = App.useApp();
  const faqs = useFaqs();
  const createFaq = useCreateFaq();
  const updateFaq = useUpdateFaq();
  const deleteFaqMut = useDeleteFaq();

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<Faq | null>(null);
  const [form] = Form.useForm<FaqForm>();

  const onDelete = async (f: Faq) => {
    try {
      await deleteFaqMut.mutateAsync(f.id);
      message.success('FAQ deleted');
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not delete FAQ'));
    }
  };

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ is_published: true, sort_order: 0 });
    setEditorOpen(true);
  };

  const openEdit = (f: Faq) => {
    setEditing(f);
    form.setFieldsValue({
      question: f.question,
      answer: f.answer,
      sort_order: f.sort_order,
      is_published: f.is_published,
    });
    setEditorOpen(true);
  };

  const submitEditor = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await updateFaq.mutateAsync({ id: editing.id, input: values });
        message.success('FAQ updated');
      } else {
        await createFaq.mutateAsync(values);
        message.success('FAQ created');
      }
      setEditorOpen(false);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not save FAQ'));
    }
  };

  return (
    <>
      <PageHeader
        title="FAQs"
        subtitle="Manage the questions brokers see in the mobile app."
        extra={
          <Button type="primary" onClick={openCreate}>
            New FAQ
          </Button>
        }
      />

      <DataTable<Faq>
        rowKey="id"
        loading={faqs.isLoading}
        dataSource={faqs.data ?? []}
        emptyText="No FAQs yet"
        emptyHint="Add a question and answer to help your brokers."
        columns={[
          {
            title: 'Question',
            dataIndex: 'question',
            ellipsis: true,
            render: (q: string) => <span style={{ fontWeight: 550 }}>{q}</span>,
          },
          {
            title: 'Published',
            dataIndex: 'is_published',
            render: (v: boolean) => <StatusDot status={v ? 'active' : 'inactive'} />,
          },
          {
            title: 'Sort order',
            dataIndex: 'sort_order',
            render: (v: number) => <span className="tnum">{v}</span>,
          },
          { title: 'Created', dataIndex: 'created_at', render: formatDateTime },
          {
            title: '',
            align: 'right',
            render: (_v, f) => (
              <Space size="large">
                <a onClick={() => openEdit(f)}>Edit</a>
                <Popconfirm
                  title="Delete this FAQ?"
                  okText="Delete"
                  okButtonProps={{ danger: true }}
                  onConfirm={() => onDelete(f)}
                >
                  <a style={{ color: '#e5648b' }}>Delete</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title={editing ? 'Edit FAQ' : 'New FAQ'}
        width={480}
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        extra={
          <Button
            type="primary"
            onClick={submitEditor}
            loading={createFaq.isPending || updateFaq.isPending}
          >
            Save
          </Button>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="question" label="Question" rules={[{ required: true }]}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="answer" label="Answer" rules={[{ required: true }]}>
            <Input.TextArea rows={5} />
          </Form.Item>
          <Form.Item name="sort_order" label="Sort order">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_published" label="Published" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Drawer>
    </>
  );
}
