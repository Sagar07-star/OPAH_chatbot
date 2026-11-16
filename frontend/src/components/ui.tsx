import { X } from "lucide-react";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { initials, statusLabel, statusTone } from "../services/format";

export function StatusBadge({ status }: { status: string | null | undefined }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium ${statusTone(
        status,
      )}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" aria-hidden />
      {statusLabel(status)}
    </span>
  );
}

export function Avatar({
  name,
  size = "md",
  tone = "ink",
}: {
  name: string | null | undefined;
  size?: "sm" | "md" | "lg";
  tone?: "ink" | "accent" | "soft";
}) {
  const dimension = size === "sm" ? "h-6 w-6 text-[10px]" : size === "lg" ? "h-10 w-10 text-[13px]" : "h-8 w-8 text-[11px]";
  const palette =
    tone === "accent"
      ? "bg-accent-soft text-accent-ink border-accent/15"
      : tone === "soft"
        ? "bg-canvas text-muted border-line"
        : "bg-ink text-white border-transparent";
  return (
    <span
      className={`inline-flex ${dimension} ${palette} flex-none items-center justify-center rounded-full border font-semibold tracking-wide`}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon?: ReactNode;
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line bg-surface/60 px-6 py-10 text-center">
      {icon ? <div className="mb-3 text-faint">{icon}</div> : null}
      <p className="text-[13.5px] font-medium text-ink">{title}</p>
      {body ? <p className="mt-1 max-w-sm text-[12.5px] leading-relaxed text-muted">{body}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 pb-6">
      <div>
        {eyebrow ? <p className="eyebrow mb-2">{eyebrow}</p> : null}
        <h1 className="text-[22px] font-semibold tracking-[-0.02em]">{title}</h1>
        {description ? <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  width = "max-w-lg",
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  width?: string;
  footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/30 p-0 backdrop-blur-[2px] sm:items-center sm:p-6">
      <button className="absolute inset-0 cursor-default" aria-label="Close" onClick={onClose} />
      <div
        className={`relative z-10 max-h-[92vh] w-full ${width} overflow-y-auto rounded-t-2xl border border-line bg-surface shadow-lift sm:rounded-2xl`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-line bg-surface/95 px-5 py-4 backdrop-blur">
          <div>
            <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
            {subtitle ? <p className="mt-0.5 text-[12px] text-muted">{subtitle}</p> : null}
          </div>
          <button className="btn btn-ghost -mr-1 px-2 py-1" onClick={onClose} aria-label="Close dialog">
            <X size={16} />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer ? <div className="sticky bottom-0 border-t border-line bg-surface px-5 py-3">{footer}</div> : null}
      </div>
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="card px-4 py-3.5">
      <div className="flex items-center justify-between">
        <p className="eyebrow">{label}</p>
        {icon ? <span className="text-faint">{icon}</span> : null}
      </div>
      <p className="mt-2 text-[20px] font-semibold leading-none tracking-[-0.02em] text-ink">{value}</p>
      {hint ? <p className="mt-1.5 text-[11.5px] text-muted">{hint}</p> : null}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-[12.5px] text-muted">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-line-strong border-t-accent" />
      {label ?? "Loading…"}
    </div>
  );
}
