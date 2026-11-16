import { AlertTriangle, ArrowRight, Check, Copy, RotateCcw, Sparkles } from "lucide-react";
import { memo, useState } from "react";
import { timeAgo } from "../../services/format";
import type { ChatMessage } from "../../types";
import { CardRenderer } from "./CardRenderer";
import type { CardContext } from "./CardRenderer";

export const MessageView = memo(function MessageView({
  message,
  context,
  personaLabel,
  showActions,
  canRegenerate,
  onRegenerate,
}: {
  message: ChatMessage;
  context: CardContext;
  personaLabel?: string | null;
  showActions?: boolean;
  canRegenerate?: boolean;
  onRegenerate?: () => void;
}) {
  const [copied, setCopied] = useState(false);

  if (message.role === "user") {
    return (
      <div className="flex animate-fade-up justify-end">
        <div className="max-w-[88%] rounded-2xl rounded-br-md bg-ink px-3.5 py-2.5 text-[13px] leading-relaxed text-canvas shadow-card">
          <p className="whitespace-pre-wrap">{message.content}</p>
          {message.pending ? <span className="mt-1 block text-[9.5px] text-canvas/50">Sending…</span> : null}
        </div>
      </div>
    );
  }

  const envelope = message.envelope;
  const cards = envelope?.data?.cards ?? [];
  const enveltype = envelope?.type ?? "text";
  const isError = enveltype === "error";
  const reference = typeof envelope?.data?.reference === "string" ? envelope.data.reference : null;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="group flex animate-fade-up gap-2.5">
      <span
        className={`mt-0.5 grid h-6 w-6 flex-none place-items-center rounded-md border ${
          isError ? "border-danger/20 bg-danger-soft text-danger" : "border-accent/15 bg-accent-soft text-accent-ink"
        }`}
        aria-hidden
      >
        {isError ? <AlertTriangle size={12.5} /> : <Sparkles size={12.5} />}
      </span>
      <div className="min-w-0 flex-1 space-y-2.5">
        {isError ? (
          <div className="rounded-xl border border-danger/20 bg-danger-soft px-3.5 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-danger">Not completed</p>
            <p className="mt-1 whitespace-pre-wrap text-[13px] leading-relaxed text-danger">
              {envelope?.message ?? message.content}
            </p>
            {reference ? <p className="mt-1 font-mono text-[9.5px] text-danger/70">ref {reference}</p> : null}
            {envelope?.data?.setup_required ? (
              <p className="mt-1.5 text-[10.5px] leading-relaxed text-danger/80">
                Add your own key in <code className="font-mono">.env</code> and restart the backend. The rest of the
                app keeps working without it.
              </p>
            ) : null}
          </div>
        ) : (
          <p className="prose-chat">{envelope?.message ?? message.content}</p>
        )}

        {cards.length > 0 ? (
          <div className="space-y-2.5">
            {cards.map((card, index) => (
              <CardRenderer key={`${card.type}-${index}`} card={card} context={context} />
            ))}
          </div>
        ) : null}

        {showActions && envelope?.actions?.length ? (
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {envelope.actions.map((action) => (
              <button
                key={action.prompt}
                className="group/action inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2.5 py-1 text-[11px] text-body transition-colors hover:border-line-strong hover:text-ink"
                onClick={() => context.onPrompt(action.prompt)}
              >
                {action.label}
                <ArrowRight size={10} className="text-faint transition-transform group-hover/action:translate-x-0.5" />
              </button>
            ))}
          </div>
        ) : null}

        <div className="flex min-h-[18px] items-center gap-2">
          <p className="flex items-center gap-1.5 text-[9.5px] text-faint">
            <span>CREATEchat</span>
            {personaLabel ? (
              <>
                <span aria-hidden>·</span>
                <span>{personaLabel}</span>
              </>
            ) : null}
            <span aria-hidden>·</span>
            <span>{timeAgo(message.created_at)}</span>
          </p>
          <span className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
            <button
              className="rounded p-1 text-faint transition-colors hover:bg-surface hover:text-ink"
              onClick={() => void copy()}
              aria-label="Copy message"
              title="Copy"
            >
              {copied ? <Check size={11.5} className="text-accent" /> : <Copy size={11.5} />}
            </button>
            {canRegenerate && onRegenerate ? (
              <button
                className="rounded p-1 text-faint transition-colors hover:bg-surface hover:text-ink"
                onClick={onRegenerate}
                aria-label="Regenerate response"
                title="Regenerate"
              >
                <RotateCcw size={11.5} />
              </button>
            ) : null}
          </span>
        </div>
      </div>
    </div>
  );
});

export function TypingIndicator() {
  return (
    <div className="flex animate-fade-up gap-2.5">
      <span className="mt-0.5 grid h-6 w-6 flex-none place-items-center rounded-md border border-accent/15 bg-accent-soft text-accent-ink">
        <Sparkles size={12.5} />
      </span>
      <div className="flex items-center gap-1 rounded-lg border border-line bg-surface px-2.5 py-2 shadow-card">
        {[0, 1, 2].map((dot) => (
          <span
            key={dot}
            className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-accent"
            style={{ animationDelay: `${dot * 0.16}s` }}
          />
        ))}
        <span className="ml-1.5 text-[10.5px] text-faint">Reading your account…</span>
      </div>
    </div>
  );
}
