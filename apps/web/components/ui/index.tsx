'use client';

import { type ButtonHTMLAttributes, type ReactNode } from 'react';
import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react';
import { toneForStatus, type Tone } from '@/lib/status';

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <p className="page-eyebrow">{eyebrow}</p>
        <h1 className="page-title">{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </div>
  );
}

export function Card({
  children,
  className = '',
  noPad = false,
}: {
  children: ReactNode;
  className?: string;
  noPad?: boolean;
}) {
  return <section className={`card ${noPad ? 'no-pad' : ''} ${className}`.trim()}>{children}</section>;
}

export function CardHead({
  title,
  sub,
  actions,
}: {
  title: string;
  sub?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="card-head">
      <div>
        <h2 className="card-title">{title}</h2>
        {sub ? <p className="card-sub">{sub}</p> : null}
      </div>
      {actions ? <div className="row">{actions}</div> : null}
    </div>
  );
}

export function Badge({
  children,
  status,
  tone,
}: {
  children?: ReactNode;
  status?: string | null;
  tone?: Tone;
}) {
  const resolved: Tone = tone ?? toneForStatus(status);
  return <span className={`badge badge-${resolved}`}>{children ?? status ?? '—'}</span>;
}

type ButtonVariant = 'primary' | 'ghost' | 'subtle' | 'danger';

export function Button({
  children,
  variant = 'primary',
  size,
  className = '',
  ...props
}: {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: 'sm';
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const variantClass = variant === 'primary' ? 'btn' : `btn btn-${variant}`;
  return (
    <button className={`${variantClass} ${size === 'sm' ? 'btn-sm' : ''} ${className}`.trim()} {...props}>
      {children}
    </button>
  );
}

export function Metric({
  label,
  value,
  detail,
  tone = 'muted',
  icon,
}: {
  label: string;
  value: string | number;
  detail?: string;
  tone?: Tone;
  icon?: ReactNode;
}) {
  const detailColor =
    tone === 'ok' ? 'var(--cn-ok)' : tone === 'warn' ? 'var(--cn-warn)' : tone === 'danger' ? 'var(--cn-danger)' : undefined;
  return (
    <div className="metric">
      <div className="metric-head">
        <div>
          <p className="metric-label">{label}</p>
          <p className="metric-value">{value}</p>
          {detail ? (
            <p className="metric-detail" style={detailColor ? { color: detailColor } : undefined}>
              {detail}
            </p>
          ) : null}
        </div>
        {icon ? <span className="metric-icon" aria-hidden="true">{icon}</span> : null}
      </div>
    </div>
  );
}

export function TableWrap({ children }: { children: ReactNode }) {
  return <div className="table-wrap">{children}</div>;
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="stack" role="status" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton" style={{ width: `${100 - i * 8}%` }} />
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message?: string }) {
  return (
    <div className="empty-state">
      <Inbox size={24} aria-hidden="true" />
      <p style={{ margin: 0, fontWeight: 600, color: 'var(--cn-text)' }}>{title}</p>
      {message ? <p style={{ margin: 0 }}>{message}</p> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <AlertTriangle size={16} aria-hidden="true" />
      <div style={{ flex: 1 }}>
        <p style={{ margin: 0 }}>{message}</p>
        {onRetry ? (
          <button className="btn btn-ghost btn-sm" style={{ marginTop: '0.5rem' }} onClick={onRetry}>
            <RefreshCw size={13} /> Retry
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function Notice({
  children,
  tone = 'default',
  style,
}: {
  children: ReactNode;
  tone?: 'default' | 'accent' | 'warn' | 'danger';
  style?: React.CSSProperties;
}) {
  const cls = tone === 'default' ? 'notice' : `notice notice-${tone}`;
  return <div className={cls} style={style}>{children}</div>;
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          className="tab"
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="modal-scrim" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <Button variant="subtle" size="sm" aria-label="Close dialog" onClick={onClose}>
            ✕
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
}
