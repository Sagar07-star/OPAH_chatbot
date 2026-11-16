import { AlertTriangle, Check, Loader2, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../../services/api";
import type { Proposal } from "../../types";
import { changeValue } from "./display";

interface Props {
  proposal: Proposal;
  onUpdated?: (proposalId: string, status: string) => void;
}

export function ProposalCard({ proposal, onUpdated }: Props) {
  const [status, setStatus] = useState(proposal.status);
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(
    typeof proposal.result?.note === "string" ? proposal.result.note : null,
  );
  const [error, setError] = useState<string | null>(null);

  const pending = status === "pending";
  const applied = status === "applied";
  const rejected = status === "rejected";

  const act = async (action: "approve" | "reject") => {
    if (!pending || busy) return;
    setBusy(action);
    setError(null);
    try {
      const result = action === "approve" ? await api.approve(proposal.proposal_id) : await api.reject(proposal.proposal_id);
      const nextStatus = result.proposal?.status ?? result.status;
      setStatus(nextStatus === "already_applied" ? "applied" : nextStatus);
      setMessage(result.message ?? null);
      const resultNote = result.result?.note;
      if (typeof resultNote === "string") setNote(resultNote);
      onUpdated?.(proposal.proposal_id, nextStatus);
      window.dispatchEvent(new CustomEvent("createchat:data-changed"));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The change couldn't be applied.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface shadow-card">
      <div className="flex items-start gap-2.5 border-b border-line bg-canvas/60 px-3.5 py-2.5">
        <span className="mt-0.5 grid h-6 w-6 flex-none place-items-center rounded-md border border-accent/15 bg-accent-soft text-accent-ink">
          <ShieldCheck size={13} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">Approval needed</p>
          <p className="mt-0.5 text-[13px] font-medium leading-snug text-ink">{proposal.summary}</p>
          {proposal.project_name ? (
            <p className="mt-0.5 text-[11px] text-muted">{proposal.project_name}</p>
          ) : null}
        </div>
      </div>

      <div className="divide-y divide-line/70">
        {proposal.changes.map((change, index) => {
          const values = changeValue(change);
          return (
            <div key={`${change.field}-${index}`} className="grid grid-cols-[1fr_auto_1fr] items-start gap-2 px-3.5 py-2">
              <div className="min-w-0">
                <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-faint">{change.label}</p>
                <p className="mt-0.5 break-words text-[12px] text-muted line-through decoration-line-strong">
                  {values.old}
                </p>
              </div>
              <span className="mt-3 text-[11px] text-faint" aria-hidden>
                →
              </span>
              <div className="min-w-0 text-right">
                <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-accent">Proposed</p>
                <p className="mt-0.5 break-words text-[12px] font-medium text-ink">{values.next}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="border-t border-line px-3.5 py-2.5">
        {proposal.applies && pending ? (
          <p className="mb-2 text-[11px] leading-relaxed text-muted">{proposal.applies}</p>
        ) : null}

        {pending ? (
          <div className="flex items-center gap-2">
            <button className="btn btn-accent flex-1 py-1.5" onClick={() => void act("approve")} disabled={busy !== null}>
              {busy === "approve" ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
              {busy === "approve" ? "Applying…" : "Approve"}
            </button>
            <button className="btn flex-1 py-1.5" onClick={() => void act("reject")} disabled={busy !== null}>
              {busy === "reject" ? <Loader2 size={13} className="animate-spin" /> : <X size={13} />}
              Decline
            </button>
          </div>
        ) : (
          <div className="flex items-start gap-2">
            <span
              className={`mt-0.5 grid h-5 w-5 flex-none place-items-center rounded-full ${
                applied ? "bg-accent-soft text-accent-ink" : "bg-danger-soft text-danger"
              }`}
            >
              {applied ? <Check size={12} /> : <X size={12} />}
            </span>
            <div className="min-w-0">
              <p className={`text-[12px] font-medium ${applied ? "text-accent-ink" : "text-danger"}`}>
                {applied ? "Applied" : rejected ? "Declined" : `Status: ${status}`}
              </p>
              {note ? <p className="mt-0.5 text-[11px] leading-relaxed text-muted">{note}</p> : null}
              {message ? <p className="mt-0.5 text-[11px] text-muted">{message}</p> : null}
            </div>
          </div>
        )}

        {error ? (
          <p className="mt-2 flex items-start gap-1.5 text-[11px] text-danger">
            <AlertTriangle size={12} className="mt-0.5 flex-none" />
            {error}
          </p>
        ) : null}
        <p className="mt-2 border-t border-line/70 pt-1.5 text-[10px] text-faint">
          Only this button applies the change. Typing “yes” in chat never does.
        </p>
      </div>
    </div>
  );
}
