import { BarcodeOutlined, SearchOutlined } from '@ant-design/icons';
import { Alert, Col, Descriptions, Divider, Empty, Input, Row, Timeline, Tooltip } from 'antd';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import type { SerialLookup } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { Mono } from '../components/Mono';
import { PageHeader } from '../components/PageHeader';
import { DetailSkeleton } from '../components/skeletons';
import { SpotlightCard } from '../components/SpotlightCard';
import { StatusTag } from '../components/StatusDot';
import { statusColor } from '../lib/statusColors';
import { useSerialLookup } from '../hooks/useLookup';
import { formatDate, formatDateTime, humanise, relativeTime } from '../lib/format';
import { descStyles } from '../lib/uiStyles';
import { brand } from '../theme';

/**
 * One input, one complete answer.
 *
 * Support works this screen with a customer on the line. Everything they could
 * be asked — is it covered, who sold it, when does it end, did the SMS arrive,
 * has anyone claimed on it — is on this page, in the order those questions
 * actually get asked, with no second click to find any of it.
 */
export function SerialLookupPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initial = searchParams.get('serial') ?? '';
  const [input, setInput] = useState(initial);
  const [serial, setSerial] = useState(initial);

  const lookup = useSerialLookup(serial);

  const search = (value: string) => {
    const trimmed = value.trim();
    setSerial(trimmed);
    const next = new URLSearchParams(searchParams);
    if (trimmed) next.set('serial', trimmed);
    else next.delete('serial');
    setSearchParams(next, { replace: true });
  };

  // There is no `found` flag on the response: a serial nobody has ever touched
  // comes back with unit.known=false and every collection empty.
  const data = lookup.data;
  const nothingKnown =
    data !== undefined &&
    !data.unit.known &&
    data.warranties.length === 0;

  return (
    <>
      <PageHeader
        title="Serial Lookup"
        subtitle="Paste a serial from the QR sticker, the invoice or the customer's SMS."
      />

      <SpotlightCard style={{ padding: 20, marginBottom: 16 }}>
        <Input
          size="large"
          allowClear
          autoFocus
          value={input}
          prefix={<BarcodeOutlined style={{ color: brand.textFaint }} />}
          placeholder="e.g. 3f6a2b18-9c04-4e21-b0a7-4c1e9b7d2f55"
          className="mono"
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={() => search(input)}
          onClear={() => search('')}
          suffix={
            <a onClick={() => search(input)} style={{ color: brand.accent }}>
              <SearchOutlined /> Look up
            </a>
          }
        />
      </SpotlightCard>

      {!serial ? (
        <SpotlightCard style={{ padding: 24 }}>
          <EmptyState
            title="Nothing looked up yet"
            hint="Serials are case-insensitive and a pasted QR link works too — the server takes the last segment."
            icon={<BarcodeOutlined />}
            height={220}
          />
        </SpotlightCard>
      ) : lookup.isLoading ? (
        <SpotlightCard style={{ padding: 20 }}>
          <DetailSkeleton rows={10} />
        </SpotlightCard>
      ) : lookup.isError ? (
        <Alert
          type="error"
          showIcon
          message="Lookup failed"
          description={(lookup.error as Error)?.message}
        />
      ) : nothingKnown ? (
        <SpotlightCard style={{ padding: 24 }}>
          <EmptyState
            title="No record of this serial"
            hint="No warranty exists on it and no such label was ever printed. Check for a typo, then check the label was generated in Products & QR."
            height={220}
          />
        </SpotlightCard>
      ) : data ? (
        <LookupResult data={data} />
      ) : null}
    </>
  );
}

function LookupResult({ data }: { data: SerialLookup }) {
  const detail = data.current_warranty;
  const w = detail?.warranty;
  const customer = detail?.customer ?? null;
  // Everything but the live warranty; the headline card already covers that one.
  const earlier = data.warranties.filter((item) => item.id !== w?.id);

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={14}>
        {/* The headline answer: is this mattress covered, and until when. */}
        <SpotlightCard style={{ padding: 20, marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <Mono value={data.serial} chars={40} size={14} />
            {w ? (
              <StatusTag status={w.status} />
            ) : (
              <StatusTag status="voided" label="No warranty" />
            )}
          </div>

          {w ? (
            <div style={{ marginTop: 16 }}>
              <div
                className="tnum"
                style={{ fontSize: 26, fontWeight: 650, letterSpacing: -0.6, color: brand.text }}
              >
                Covered until {formatDate(w.warranty_end_date)}
              </div>
              <div style={{ color: brand.textDim, fontSize: 13, marginTop: 4 }}>
                {w.warranty_months} months from {formatDate(w.warranty_start_date)}
                {w.backdate_days > 0 && (
                  <span style={{ color: brand.warning }}> · backdated {w.backdate_days} days</span>
                )}
                {detail?.is_expired && <span style={{ color: brand.textFaint }}> · expired</span>}
              </div>
            </div>
          ) : (
            <div style={{ marginTop: 14, color: brand.textDim, fontSize: 13.5 }}>
              This unit has no live warranty — nobody has registered a sale on it yet.
            </div>
          )}
        </SpotlightCard>

        <SpotlightCard style={{ padding: 20, marginBottom: 16 }}>
          <SectionTitle>Unit</SectionTitle>
          {data.unit.known ? (
            <Descriptions
              column={2}
              size="small"
              colon={false}
              styles={descStyles}
              items={[
                { key: 'model', label: 'Model', children: data.unit.model_name ?? '—' },
                { key: 'code', label: 'Model code', children: data.unit.model_code ?? '—' },
                {
                  key: 'months',
                  label: 'Warranty terms',
                  children: data.unit.warranty_months ? `${data.unit.warranty_months} months` : '—',
                },
                { key: 'src', label: 'Known from', children: humanise(data.unit.source) },
                {
                  key: 'upstream',
                  label: 'GB Rewards status',
                  children: data.unit.source_status ?? '—',
                },
                {
                  key: 'synced',
                  label: 'Last synced',
                  children: (
                    <span style={{ color: data.unit.stale ? brand.warning : undefined }}>
                      {data.unit.source_synced_at
                        ? relativeTime(data.unit.source_synced_at)
                        : 'never'}
                      {data.unit.stale && ' · stale'}
                    </span>
                  ),
                },
                {
                  key: 'verified',
                  label: 'Confirmed upstream',
                  span: 2,
                  children: data.unit.unverified ? (
                    <span style={{ color: brand.warning }}>
                      No — no product record
                    </span>
                  ) : (
                    'Yes'
                  ),
                },
              ]}
            />
          ) : (
            <Alert
              type="warning"
              showIcon
              message="Not in the unit mirror"
              description="We have no product record for this serial."
            />
          )}
        </SpotlightCard>

        <SpotlightCard style={{ padding: 20 }}>
          <SectionTitle>Customer</SectionTitle>
          {customer ? (
            <Descriptions
              column={2}
              size="small"
              colon={false}
              styles={descStyles}
              items={[
                { key: 'name', label: 'Name', children: customer.name },
                {
                  key: 'phone',
                  label: 'Mobile',
                  children: (
                    <span>
                      <span className="mono">{customer.phone}</span>
                      {customer.is_phone_verified && (
                        <Tooltip title="This customer acted on an SMS link themselves">
                          <span style={{ color: brand.success, fontSize: 11.5, marginLeft: 8 }}>
                            verified
                          </span>
                        </Tooltip>
                      )}
                    </span>
                  ),
                },
                { key: 'email', label: 'Email', children: customer.email ?? '—' },
                { key: 'city', label: 'City', children: customer.city ?? '—' },
                {
                  key: 'address',
                  label: 'Address',
                  span: 2,
                  children: customer.address ?? '—',
                },
              ]}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No customer on record" />
          )}
        </SpotlightCard>
      </Col>

      <Col xs={24} xl={10}>
        <SpotlightCard style={{ padding: 20, marginBottom: 16 }}>
          <SectionTitle>Everything that happened</SectionTitle>
          {/* The server merges warranty events across every warranty this serial
              has ever carried — that IS the timeline. */}
          {data.events.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No history" />
          ) : (
            <Timeline
              items={data.events.map((e) => ({
                key: e.id,
                color: statusColor(e.to_status ?? 'active'),
                children: (
                  <div>
                    <div style={{ fontSize: 13.5, color: brand.text }}>
                      {humanise(e.event)}
                      {e.from_status && e.to_status && (
                        <span style={{ color: brand.textFaint, fontSize: 12, marginLeft: 8 }}>
                          {humanise(e.from_status)} → {humanise(e.to_status)}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 11.5, color: brand.textFaint }}>
                      {formatDateTime(e.created_at)} · {e.actor_name ?? humanise(e.actor_type)}
                    </div>
                    {e.reason && (
                      <div style={{ fontSize: 12.5, color: brand.textDim, marginTop: 2 }}>
                        “{e.reason}”
                      </div>
                    )}
                  </div>
                ),
              }))}
            />
          )}
        </SpotlightCard>

        <SpotlightCard style={{ padding: 20, marginBottom: 16 }}>
          <SectionTitle>Claims</SectionTitle>
          {data.claims.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No claims raised" />
          ) : (
            <div style={{ display: 'grid', gap: 8 }}>
              {data.claims.map((c) => (
                <div
                  key={c.id}
                  style={{
                    padding: '10px 12px',
                    border: `1px solid ${brand.border}`,
                    borderRadius: 8,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span className="mono" style={{ fontSize: 12.5, color: brand.text }}>
                      {c.reference}
                    </span>
                    <StatusTag status={c.status} />
                  </div>
                  <div style={{ fontSize: 12.5, color: brand.textDim, marginTop: 6 }}>
                    {c.description}
                  </div>
                  <div style={{ fontSize: 11.5, color: brand.textFaint, marginTop: 4 }}>
                    {formatDateTime(c.created_at)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </SpotlightCard>

        <SpotlightCard style={{ padding: 20, marginBottom: 16 }}>
          <SectionTitle>SMS sent</SectionTitle>
          {data.sms.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No messages" />
          ) : (
            <div style={{ display: 'grid', gap: 6 }}>
              {data.sms.map((m) => (
                <div
                  key={m.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 10,
                    padding: '8px 12px',
                    border: `1px solid ${brand.border}`,
                    borderRadius: 8,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, color: brand.text }}>
                      {humanise(m.template_key)}
                    </div>
                    <div className="mono" style={{ fontSize: 11.5, color: brand.textFaint }}>
                      {m.to_phone} · {formatDateTime(m.created_at)}
                    </div>
                    {m.error && (
                      <div style={{ fontSize: 11.5, color: brand.danger, marginTop: 2 }}>
                        {m.error}
                      </div>
                    )}
                  </div>
                  <StatusTag status={m.status} />
                </div>
              ))}
            </div>
          )}
        </SpotlightCard>

        {earlier.length > 0 && (
          <SpotlightCard style={{ padding: 20 }}>
            <SectionTitle>Earlier warranties on this serial</SectionTitle>
            <div style={{ display: 'grid', gap: 8 }}>
              {earlier.map((p) => (
                <div
                  key={p.id}
                  style={{
                    padding: '10px 12px',
                    border: `1px solid ${brand.border}`,
                    borderRadius: 8,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontSize: 13, color: brand.text }}>
                      {p.customer?.name ?? 'Unknown customer'}
                    </span>
                    <StatusTag status={p.status} />
                  </div>
                  <div style={{ fontSize: 11.5, color: brand.textFaint, marginTop: 4 }}>
                    {formatDate(p.warranty_start_date)} → {formatDate(p.warranty_end_date)}
                    {p.dealer && ` · ${p.dealer.name}`}
                  </div>
                </div>
              ))}
            </div>
          </SpotlightCard>
        )}
      </Col>

      <Col span={24}>
        <Divider style={{ margin: '4px 0 0' }} />
      </Col>
    </Row>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 12,
        textTransform: 'uppercase',
        letterSpacing: 0.7,
        color: brand.textDim,
        fontWeight: 550,
        marginBottom: 12,
      }}
    >
      {children}
    </div>
  );
}
