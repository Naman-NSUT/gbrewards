import { InboxOutlined, UploadOutlined, WarningOutlined } from '@ant-design/icons';
import { Alert, App, Button, Input, Modal, Select, Steps, Tabs, Tag, Upload } from 'antd';
import type { TableColumnsType } from 'antd';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { apiErrorMessage } from '../api/client';
import type {
  Allocation,
  AllocationBatch,
  AllocationStatus,
  AllocationUploadResult,
  BatchRowError,
} from '../api/types';
import { ConfirmWithReason } from '../components/ConfirmWithReason';
import { DataTable } from '../components/DataTable';
import { Mono } from '../components/Mono';
import { PageHeader } from '../components/PageHeader';
import { StatusTag } from '../components/StatusDot';
import {
  useAllocationBatches,
  useAllocations,
  usePreviewAllocationCsv,
  useRevokeAllocation,
  useUploadAllocationCsv,
} from '../hooks/useAllocations';
import { formatDateTime, formatNumber } from '../lib/format';
import { brand } from '../theme';

const PAGE_SIZE = 50;

export function AllocationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState('list');
  // The endpoint takes an exact `serial` and a `dealer_code` — there is no
  // free-text search here, so the box says what it actually matches.
  const [serial, setSerial] = useState('');
  const [dealerCode, setDealerCode] = useState('');
  const [status, setStatus] = useState<AllocationStatus | undefined>();
  const [page, setPage] = useState(1);
  const [batchPage, setBatchPage] = useState(1);
  const [revoking, setRevoking] = useState<Allocation | null>(null);

  const uploadOpen = searchParams.get('upload') === '1';
  const setUploadOpen = (open: boolean) => {
    const next = new URLSearchParams(searchParams);
    if (open) next.set('upload', '1');
    else next.delete('upload');
    setSearchParams(next, { replace: true });
  };

  const { message } = App.useApp();
  const revoke = useRevokeAllocation();

  const params = useMemo(
    () => ({
      serial: serial || undefined,
      dealer_code: dealerCode || undefined,
      status,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [serial, dealerCode, status, page],
  );
  const allocations = useAllocations(params);
  const batches = useAllocationBatches({ limit: 20, offset: (batchPage - 1) * 20 });

  const doRevoke = async (reason: string) => {
    if (!revoking) return;
    try {
      await revoke.mutateAsync({ id: revoking.id, reason });
      message.success('Allocation revoked. The dealer can no longer register this serial.');
      setRevoking(null);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not revoke that allocation'));
    }
  };

  const columns: TableColumnsType<Allocation> = [
    {
      title: 'Serial',
      dataIndex: 'serial',
      width: 220,
      render: (s: string, a) => (
        <div>
          <Mono value={s} chars={20} />
          {a.model_name && (
            <div style={{ fontSize: 11.5, color: brand.textFaint }}>{a.model_name}</div>
          )}
        </div>
      ),
    },
    {
      title: 'Dealer',
      dataIndex: 'dealer_name',
      width: 220,
      render: (name: string | null, a) => (
        <div>
          <div style={{ color: brand.text, fontSize: 13 }}>{name ?? '—'}</div>
          <div className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
            {a.dealer_code ?? a.dealer_id.slice(0, 8)}
          </div>
        </div>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 120,
      render: (s: AllocationStatus) => <StatusTag status={s} />,
    },
    {
      title: 'Dispatch ref',
      dataIndex: 'dispatch_ref',
      width: 140,
      render: (v: string | null) => (
        <span style={{ fontSize: 12.5, color: brand.textDim }}>{v ?? '—'}</span>
      ),
    },
    {
      title: 'Allocated',
      dataIndex: 'allocated_at',
      width: 170,
      render: (v: string) => (
        <span style={{ fontSize: 12.5, color: brand.textFaint }}>{formatDateTime(v)}</span>
      ),
    },
    {
      title: 'Revoked',
      dataIndex: 'revoked_at',
      width: 200,
      render: (v: string | null, a) =>
        v ? (
          <div style={{ fontSize: 12, color: brand.textFaint }}>
            <div>{formatDateTime(v)}</div>
            {a.revoke_reason && <div style={{ color: brand.textDim }}>{a.revoke_reason}</div>}
          </div>
        ) : (
          <span style={{ color: brand.textFaint }}>—</span>
        ),
    },
    {
      title: '',
      key: 'actions',
      width: 90,
      render: (_v, a) =>
        a.status === 'allocated' ? (
          <Button size="small" danger type="text" onClick={() => setRevoking(a)}>
            Revoke
          </Button>
        ) : null,
    },
  ];

  const batchColumns: TableColumnsType<AllocationBatch> = [
    {
      title: 'File',
      dataIndex: 'filename',
      render: (f: string | null) => (
        <span style={{ color: brand.text, fontSize: 13 }}>{f ?? 'upload.csv'}</span>
      ),
    },
    {
      // The API returns the admin's id, not their name — showing the id is
      // honest and still enough to match against the audit row.
      title: 'Uploaded by',
      dataIndex: 'uploaded_by_admin_id',
      width: 180,
      render: (v: string) => (
        <span className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
          {v.slice(0, 8)}…
        </span>
      ),
    },
    {
      title: 'Rows',
      dataIndex: 'row_count',
      align: 'right',
      width: 90,
      render: (v: number) => <span className="tnum">{formatNumber(v)}</span>,
    },
    {
      title: 'Allocated',
      dataIndex: 'ok_count',
      align: 'right',
      width: 100,
      render: (v: number) => (
        <span className="tnum" style={{ color: brand.success }}>
          {formatNumber(v)}
        </span>
      ),
    },
    {
      title: 'Rejected',
      dataIndex: 'error_count',
      align: 'right',
      width: 100,
      render: (v: number) => (
        <span className="tnum" style={{ color: v > 0 ? brand.danger : brand.textFaint }}>
          {formatNumber(v)}
        </span>
      ),
    },
    {
      title: 'When',
      dataIndex: 'created_at',
      width: 170,
      render: (v: string) => (
        <span style={{ fontSize: 12.5, color: brand.textFaint }}>{formatDateTime(v)}</span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Allocations"
        subtitle="Which serials each dealer may register. This is the denominator of every compliance number."
        extra={
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Input.Search
              allowClear
              placeholder="Serial"
              style={{ width: 220 }}
              onSearch={(v) => {
                setPage(1);
                setSerial(v);
              }}
            />
            <Input.Search
              allowClear
              placeholder="Dealer code"
              style={{ width: 160 }}
              onSearch={(v) => {
                setPage(1);
                setDealerCode(v);
              }}
            />
            <Select
              allowClear
              placeholder="Any status"
              style={{ width: 150 }}
              value={status}
              options={[
                { label: 'Allocated', value: 'allocated' },
                { label: 'Registered', value: 'registered' },
                { label: 'Revoked', value: 'revoked' },
                { label: 'Returned', value: 'returned' },
              ]}
              onChange={(v) => {
                setPage(1);
                setStatus(v);
              }}
            />
            <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadOpen(true)}>
              Upload CSV
            </Button>
          </div>
        }
      />

      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: 'list', label: 'Allocations' },
          { key: 'batches', label: 'Upload history' },
        ]}
      />

      {tab === 'list' ? (
        <DataTable<Allocation>
          rowKey="id"
          loading={allocations.isLoading}
          dataSource={allocations.data?.items ?? []}
          columns={columns}
          total={allocations.data?.total}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
          emptyText="No allocations"
          emptyHint="Upload a CSV of serial,dealer_code to give dealers stock they can register."
          emptyIcon={<InboxOutlined />}
          emptyAction={
            <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadOpen(true)}>
              Upload CSV
            </Button>
          }
        />
      ) : (
        <DataTable<AllocationBatch>
          rowKey="id"
          loading={batches.isLoading}
          dataSource={batches.data?.items ?? []}
          columns={batchColumns}
          total={batches.data?.total}
          page={batchPage}
          pageSize={20}
          onPageChange={setBatchPage}
          emptyText="No uploads yet"
          expandable={{
            rowExpandable: (b) => (b.errors ?? []).length > 0,
            expandedRowRender: (b) => <ErrorList errors={b.errors ?? []} />,
          }}
        />
      )}

      <UploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} />

      <ConfirmWithReason
        open={revoking !== null}
        title="Revoke this allocation"
        confirmText="Revoke"
        danger
        loading={revoke.isPending}
        description={
          revoking ? (
            <>
              <strong>{revoking.dealer_name ?? revoking.dealer_code ?? 'This dealer'}</strong> will
              no longer be able to register{' '}
              <span className="mono">{revoking.serial.slice(0, 16)}…</span>. Use this when stock was
              sent to the wrong shop or came back to the warehouse.
            </>
          ) : undefined
        }
        onCancel={() => setRevoking(null)}
        onConfirm={doRevoke}
      />
    </>
  );
}

/** Row errors read the same in the review step, the result step and history. */
function ErrorList({ errors }: { errors: BatchRowError[] }) {
  return (
    <div style={{ display: 'grid', gap: 6, padding: '4px 0' }}>
      {errors.map((e, i) => (
        <div
          key={`${e.line}-${i}`}
          style={{
            padding: '8px 12px',
            border: `1px solid ${brand.danger}33`,
            borderRadius: 8,
            background: `${brand.danger}0d`,
            fontSize: 12.5,
          }}
        >
          <span className="mono" style={{ color: brand.textFaint }}>
            line {e.line}
          </span>
          {e.serial && (
            <span className="mono" style={{ marginLeft: 10, color: brand.text }}>
              {e.serial}
            </span>
          )}
          {e.dealer_code && (
            <span className="mono" style={{ marginLeft: 10, color: brand.textDim }}>
              {e.dealer_code}
            </span>
          )}
          <span style={{ marginLeft: 10, color: brand.danger }}>{e.reason}</span>
        </div>
      ))}
    </div>
  );
}

function UploadModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp();
  const [file, setFile] = useState<File | null>(null);
  // Preview and upload return the SAME shape, so the review and result steps
  // are the same numbers — the dry run cannot promise something the commit
  // then reports differently.
  const [preview, setPreview] = useState<AllocationUploadResult | null>(null);
  const [result, setResult] = useState<AllocationUploadResult | null>(null);

  const previewCsv = usePreviewAllocationCsv();
  const upload = useUploadAllocationCsv();

  const step = result ? 2 : preview ? 1 : 0;

  const reset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
  };

  const runPreview = async (f: File) => {
    setFile(f);
    try {
      setPreview(await previewCsv.mutateAsync(f));
    } catch (e) {
      message.error(apiErrorMessage(e, 'Could not read that file'));
      setFile(null);
    }
  };

  const commit = async () => {
    if (!file) return;
    try {
      const outcome = await upload.mutateAsync(file);
      setResult(outcome);
      message.success(`${outcome.created_count} serials allocated`);
    } catch (e) {
      message.error(apiErrorMessage(e, 'Upload failed'));
    }
  };

  return (
    <Modal
      open={open}
      onCancel={() => {
        reset();
        onClose();
      }}
      title="Upload allocation CSV"
      width={860}
      destroyOnHidden
      afterOpenChange={(o) => {
        if (o) reset();
      }}
      footer={
        step === 2 ? (
          <Button
            type="primary"
            onClick={() => {
              reset();
              onClose();
            }}
          >
            Done
          </Button>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button onClick={reset} disabled={!preview}>
              Choose a different file
            </Button>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button onClick={onClose}>Cancel</Button>
              <Button
                type="primary"
                disabled={!preview || preview.created_count === 0}
                loading={upload.isPending}
                onClick={commit}
              >
                Allocate {preview ? preview.created_count : 0} serials
              </Button>
            </div>
          </div>
        )
      }
    >
      <Steps
        size="small"
        current={step}
        items={[{ title: 'Choose file' }, { title: 'Review' }, { title: 'Result' }]}
        style={{ marginBottom: 20 }}
      />

      {step === 0 && (
        <>
          <Upload.Dragger
            accept=".csv,text/csv"
            maxCount={1}
            showUploadList={false}
            // Returning false keeps antd from POSTing on its own — the preview
            // request below is the only thing that should touch the server here.
            beforeUpload={(f) => {
              void runPreview(f as unknown as File);
              return false;
            }}
            disabled={previewCsv.isPending}
          >
            <p style={{ fontSize: 32, color: brand.accent, margin: '8px 0' }}>
              <InboxOutlined />
            </p>
            <p style={{ color: brand.text, fontSize: 14 }}>
              {previewCsv.isPending ? 'Reading…' : 'Drop a CSV here, or click to choose one'}
            </p>
            <p style={{ color: brand.textDim, fontSize: 12.5 }}>
              Columns: <span className="mono">serial</span>,{' '}
              <span className="mono">dealer_code</span>, optional{' '}
              <span className="mono">dispatch_ref</span>
            </p>
          </Upload.Dragger>
          <Alert
            style={{ marginTop: 16 }}
            type="info"
            showIcon
            message="Nothing is written until you confirm"
            description="The file is checked first and you see exactly which rows would be created, which are already there, and which are rejected."
          />
        </>
      )}

      {step === 1 && preview && <Outcome outcome={preview} dryRun />}
      {step === 2 && result && <Outcome outcome={result} />}
    </Modal>
  );
}

function Outcome({ outcome, dryRun = false }: { outcome: AllocationUploadResult; dryRun?: boolean }) {
  const { batch, created_count, unchanged_count, units_stubbed, errors } = outcome;

  return (
    <>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <Tag color="default">{batch.filename ?? 'upload.csv'}</Tag>
        <Tag>{batch.row_count} rows</Tag>
        <Tag
          style={{
            color: brand.success,
            background: `${brand.success}1f`,
            borderColor: `${brand.success}3d`,
          }}
        >
          {created_count} {dryRun ? 'would be new' : 'new'}
        </Tag>
        <Tag>{unchanged_count} already allocated</Tag>
        <Tag
          style={{
            color: brand.danger,
            background: `${brand.danger}1f`,
            borderColor: `${brand.danger}3d`,
          }}
        >
          {errors.length} rejected
        </Tag>
      </div>

      {units_stubbed > 0 && (
        <Alert
          style={{ marginBottom: 14 }}
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          message={`${units_stubbed} serials are not in the unit mirror`}
          description="A stub is written for each so the dealer can still register the sale, but the model and warranty terms stay unknown until GB Rewards confirms the unit."
        />
      )}

      {!dryRun && (
        <Alert
          style={{ marginBottom: 14 }}
          type={errors.length > 0 ? 'warning' : 'success'}
          showIcon
          message={`${batch.ok_count} of ${batch.row_count} rows allocated`}
          description={
            errors.length > 0
              ? 'The rejected rows are listed below. Fix them and upload just those rows again.'
              : 'Every row in the file was accepted.'
          }
        />
      )}

      {errors.length > 0 && (
        <div style={{ maxHeight: 320, overflowY: 'auto' }}>
          <ErrorList errors={errors} />
        </div>
      )}
    </>
  );
}
