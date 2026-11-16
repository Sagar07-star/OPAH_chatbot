import { AlertTriangle, ArrowUpRight, Ban, CreditCard, MessageSquare, Star } from "lucide-react";
import { useState } from "react";
import { formatDate, money, titleCase } from "../../services/format";
import type { Handoff } from "../../types";
import { Modal } from "../ui";

const SCREEN_ICONS: Record<string, typeof CreditCard> = {
  checkout: CreditCard,
  package_checkout: CreditCard,
  cancel_project: Ban,
  project_messages: MessageSquare,
  review_form: Star,
};

export function HandoffCard({ handoff }: { handoff: Handoff }) {
  const [open, setOpen] = useState(false);
  const Icon = SCREEN_ICONS[handoff.screen] ?? ArrowUpRight;
  const summary = handoff.summary as Record<string, unknown>;

  const headline =
    typeof summary.total === "number"
      ? money(summary.total)
      : typeof summary.refund_amount === "number"
        ? `${money(summary.refund_amount)} refund`
        : typeof summary.prefill === "string"
          ? "Message typed, not sent"
          : "Ready to review";

  return (
    <>
      <div className="rounded-xl border border-line bg-surface p-3.5 shadow-card">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 grid h-6 w-6 flex-none place-items-center rounded-md border border-line bg-canvas text-muted">
            <Icon size={13} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">Hand-off</p>
            <p className="mt-0.5 text-[13px] font-medium text-ink">{handoff.title}</p>
            <p className="mt-0.5 text-[11.5px] text-muted">{headline}</p>
          </div>
        </div>
        <button className="btn mt-3 w-full justify-center py-1.5" onClick={() => setOpen(true)}>
          Open demo screen
          <ArrowUpRight size={13} />
        </button>
        <p className="mt-2 text-[10px] leading-relaxed text-faint">
          Opens a clearly labelled prototype screen. Nothing is charged, sent or cancelled.
        </p>
      </div>
      <HandoffModal handoff={handoff} open={open} onClose={() => setOpen(false)} />
    </>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-[11.5px] text-muted">{label}</span>
      <span className={`text-[12px] ${strong ? "font-semibold text-ink" : "text-ink"}`}>{value}</span>
    </div>
  );
}

function HandoffModal({ handoff, open, onClose }: { handoff: Handoff; open: boolean; onClose: () => void }) {
  const summary = handoff.summary as Record<string, any>;
  const params = handoff.params as Record<string, any>;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={handoff.title}
      subtitle="Prototype hand-off · demo only"
      width="max-w-md"
      footer={
        <div className="flex items-center justify-between gap-3">
          <p className="text-[10.5px] leading-snug text-faint">No real OPAH screen is connected.</p>
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      }
    >
      <div className="mb-3 flex items-start gap-2 rounded-lg border border-warning/25 bg-warning-soft px-3 py-2">
        <AlertTriangle size={13} className="mt-0.5 flex-none text-warning" />
        <p className="text-[11px] leading-relaxed text-warning">{handoff.disclaimer}</p>
      </div>

      {handoff.screen === "checkout" || handoff.screen === "package_checkout" ? (
        <div>
          {handoff.screen === "package_checkout" && typeof summary.package === "string" ? (
            <p className="mb-2 text-[12.5px] font-medium text-ink">{summary.package}</p>
          ) : null}
          {Array.isArray(summary.lines)
            ? summary.lines.map((line: any) => (
                <div key={line.project_id} className="border-b border-line py-1.5">
                  <Row label={line.name} value={money(line.subtotal)} />
                  <Row label="Assistance fee" value={money(line.fee)} />
                </div>
              ))
            : null}
          <div className="pt-1">
            <Row label="Subtotal" value={money(summary.subtotal)} />
            <Row label="Assistance fee (10.5%)" value={money(summary.fee)} />
            <div className="mt-1 border-t border-line pt-1.5">
              <Row label="Total" value={money(summary.total)} strong />
            </div>
          </div>
          {typeof summary.note === "string" ? (
            <p className="mt-2 text-[11px] leading-relaxed text-muted">{summary.note}</p>
          ) : null}
          <div className="mt-3 rounded-lg border border-line bg-canvas px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-faint">Cancellation terms</p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted">
              {String(summary.cancellation_terms ?? "Shown by the checkout screen.")}
            </p>
          </div>
          <p className="mt-3 text-[11px] text-muted">
            This prototype never collects card details and never charges. In OPAH, this button opens the real
            checkout for the client.
          </p>
        </div>
      ) : null}

      {handoff.screen === "cancel_project" ? (
        <div>
          <div className="rounded-lg border border-line bg-canvas px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-faint">Refund if cancelled now</p>
            <p className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-ink">
              {typeof summary.refund_amount === "number" ? money(summary.refund_amount) : "—"}
            </p>
            <p className="text-[11.5px] text-muted">
              {summary.refund_percent === null || summary.refund_percent === undefined
                ? String(summary.message ?? "Nothing has been paid.")
                : `${summary.refund_percent}% of ${money(summary.paid_total)} · ${titleCase(summary.tier ?? "")}`}
            </p>
            {typeof summary.hours_until_start === "number" ? (
              <p className="mt-1 text-[11px] text-faint">
                {summary.hours_until_start} hours before the shoot starts
              </p>
            ) : null}
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-muted">
            Cancelling is a separate screen in OPAH. This prototype shows the policy preview only and does not cancel
            the project.
          </p>
          <button className="btn mt-3 w-full justify-center" disabled>
            <Ban size={13} /> Continue to cancellation (not connected)
          </button>
        </div>
      ) : null}

      {handoff.screen === "project_messages" ? (
        <div>
          <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12px]">
            <span className="text-muted">To</span>
            <span className="font-medium text-ink">{String(summary.to ?? "the creative")}</span>
            <span className="text-muted">Project</span>
            <span className="text-ink">{String(params.project_id ?? "")}</span>
          </div>
          <div className="mt-3 rounded-lg border border-line bg-canvas px-3 py-2.5 text-[12.5px] leading-relaxed text-ink">
            {String(summary.prefill ?? "")}
          </div>
          <button
            className="btn mt-3 w-full justify-center"
            onClick={() => void navigator.clipboard?.writeText(String(summary.prefill ?? ""))}
          >
            Copy message
          </button>
          <p className="mt-2 text-[11px] text-muted">
            Typed into the project conversation, not sent. The client sends it themselves in the app.
          </p>
        </div>
      ) : null}

      {handoff.screen === "review_form" ? (
        <div>
          <div className="flex items-center gap-1">
            {[1, 2, 3, 4, 5].map((value) => (
              <Star
                key={value}
                size={18}
                className={value <= Number(summary.rating ?? 0) ? "fill-warning text-warning" : "text-line-strong"}
              />
            ))}
            <span className="ml-2 text-[11.5px] text-muted">{String(summary.rating ?? "")} of 5</span>
          </div>
          <div className="mt-3 rounded-lg border border-line bg-canvas px-3 py-2.5 text-[12.5px] leading-relaxed text-ink">
            {String(summary.prefill ?? "")}
          </div>
          <button className="btn mt-3 w-full justify-center" disabled>
            <Star size={13} /> Submit review in OPAH (not connected)
          </button>
          <p className="mt-2 text-[11px] text-muted">
            The review is drafted for the client. This prototype never submits it.
          </p>
        </div>
      ) : null}

      {!["checkout", "package_checkout", "cancel_project", "project_messages", "review_form"].includes(
        handoff.screen,
      ) ? (
        <pre className="overflow-x-auto rounded-lg border border-line bg-canvas p-3 text-[11px] text-muted">
          {JSON.stringify(summary, null, 2)}
        </pre>
      ) : null}

      {handoff.screen === "package_checkout" ? (
        <div className="mt-3 border-t border-line pt-2 text-[11px] text-muted">
          <p>Address: {String(params.address ?? "—")}</p>
          <p>
            {formatDate(String(params.date ?? ""))} at {String(params.call_time ?? "")}
          </p>
        </div>
      ) : null}
    </Modal>
  );
}
