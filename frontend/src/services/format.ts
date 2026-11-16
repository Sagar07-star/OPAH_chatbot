import type { AttentionItem, ProjectStatus } from "../types";

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  dispatching: "Finding creative",
  escrow_held: "Paid · held",
  assigned: "Assigned",
  initiated: "Shoot day",
  in_progress: "In progress",
  captured: "Captured",
  review: "In review",
  completed: "Completed",
  cancelled: "Cancelled",
};

const STATUS_TONES: Record<string, string> = {
  draft: "border-line bg-canvas text-muted",
  dispatching: "border-warning/25 bg-warning-soft text-warning",
  escrow_held: "border-accent/20 bg-accent-soft text-accent-ink",
  assigned: "border-accent/20 bg-accent-soft text-accent-ink",
  initiated: "border-warning/25 bg-warning-soft text-warning",
  in_progress: "border-warning/25 bg-warning-soft text-warning",
  captured: "border-info/20 bg-info-soft text-info",
  review: "border-info/20 bg-info-soft text-info",
  completed: "border-accent/20 bg-accent-soft text-accent-ink",
  cancelled: "border-danger/20 bg-danger-soft text-danger",
};

const REVIEW_LABELS: Record<string, string> = {
  pending_client: "Waiting for you",
  approved: "Approved",
  revision_requested: "Revision requested",
};

export function statusLabel(status: string | null | undefined): string {
  if (!status) return "Unknown";
  return STATUS_LABELS[status] ?? titleCase(status);
}

export function statusTone(status: string | null | undefined): string {
  return STATUS_TONES[status ?? ""] ?? "border-line bg-canvas text-muted";
}

export function reviewLabel(status: string | null | undefined): string {
  return REVIEW_LABELS[status ?? ""] ?? titleCase(status ?? "");
}

export function titleCase(value: string): string {
  const cleaned = value.replace(/_/g, " ").trim();
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

export function money(value: number | null | undefined, currency = "USD"): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "No date";
  const date = new Date(`${iso.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(date);
}

export function formatDateLong(iso: string | null | undefined): string {
  if (!iso) return "No date yet";
  const date = new Date(`${iso.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

export function formatTime(time: string | null | undefined): string {
  if (!time) return "—";
  const [hoursRaw, minutes] = time.split(":");
  const hours = Number(hoursRaw);
  if (Number.isNaN(hours)) return time;
  const suffix = hours >= 12 ? "PM" : "AM";
  const normalised = hours % 12 === 0 ? 12 : hours % 12;
  return `${normalised}:${minutes ?? "00"} ${suffix}`;
}

export function dayRange(start: string | null, end: string | null): string {
  if (!start) return "Dates not set";
  if (!end || end === start) return formatDate(start);
  return `${formatDate(start)} – ${formatDate(end)}`;
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(1, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(then).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function fileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function attentionTone(kind: string): { label: string; tone: string } {
  switch (kind) {
    case "counter_offer":
      return { label: "Counter-offer", tone: "border-warning/25 bg-warning-soft text-warning" };
    case "deliverables_to_review":
      return { label: "Deliverables", tone: "border-info/20 bg-info-soft text-info" };
    case "draft_incomplete":
      return { label: "Draft", tone: "border-line bg-canvas text-muted" };
    case "ready_to_pay":
      return { label: "Ready to pay", tone: "border-accent/20 bg-accent-soft text-accent-ink" };
    case "change_awaiting_talent":
      return { label: "Waiting on creative", tone: "border-warning/25 bg-warning-soft text-warning" };
    case "finding_creative":
      return { label: "Finding creative", tone: "border-warning/25 bg-warning-soft text-warning" };
    case "proposal_pending":
      return { label: "Approval needed", tone: "border-accent/20 bg-accent-soft text-accent-ink" };
    default:
      return { label: titleCase(kind), tone: "border-line bg-canvas text-muted" };
  }
}

export function attentionLink(item: AttentionItem): string | null {
  if (item.project_id) return `/projects/${item.project_id}`;
  return null;
}

export function isPaidStatus(status: ProjectStatus | string): boolean {
  return ["dispatching", "escrow_held", "assigned", "initiated", "in_progress", "captured", "review"].includes(
    status,
  );
}
