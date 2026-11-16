import { Check, ShieldAlert, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSession } from "../contexts/SessionContext";

export function AccountSwitcher({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { meta, switchAccount, loading } = useSession();
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, onClose]);

  if (!open) return null;
  const current = meta?.session.user_id;

  const choose = async (userId: string, role?: string) => {
    setError(null);
    try {
      await switchAccount(userId, role);
      onClose();
    } catch {
      setError("That account isn't part of the prototype dataset.");
    }
  };

  return (
    <div
      ref={ref}
      className="absolute bottom-[calc(100%-4px)] left-0 z-40 w-full origin-bottom animate-fade-up rounded-xl border border-line bg-surface p-1.5 shadow-lift"
      role="menu"
      aria-label="Switch demo account"
    >
      <p className="px-2 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">
        Switch identity
      </p>
      {(meta?.accounts ?? []).map((account) => (
        <button
          key={account.id}
          className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-canvas disabled:opacity-60"
          onClick={() => void choose(account.id)}
          disabled={loading}
          role="menuitem"
        >
          <span className="grid h-6 w-6 flex-none place-items-center rounded-full border border-line bg-canvas text-[9.5px] font-semibold text-muted">
            {account.name
              .split(" ")
              .map((part) => part[0])
              .join("")}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[12px] font-medium text-ink">{account.name}</span>
            <span className="block truncate text-[10px] text-faint">
              {account.company ?? "New client"} · {account.id}
            </span>
          </span>
          {current === account.id ? <Check size={13} className="text-accent" /> : null}
        </button>
      ))}
      <div className="my-1 h-px bg-line" />
      <button
        className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-canvas disabled:opacity-60"
        onClick={() => void choose("anonymous")}
        disabled={loading}
        role="menuitem"
      >
        <span className="grid h-6 w-6 flex-none place-items-center rounded-full border border-line bg-canvas text-muted">
          <UserRound size={12} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12px] font-medium text-ink">Visitor</span>
          <span className="block text-[10px] text-faint">No account · public tools only</span>
        </span>
        {current === "anonymous" ? <Check size={13} className="text-accent" /> : null}
      </button>
      <button
        className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-canvas disabled:opacity-60"
        onClick={() => void choose("tal_001", "talent")}
        disabled={loading}
        role="menuitem"
      >
        <span className="grid h-6 w-6 flex-none place-items-center rounded-full border border-danger/20 bg-danger-soft text-danger">
          <ShieldAlert size={12} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12px] font-medium text-ink">Creative demo</span>
          <span className="block text-[10px] text-faint">Hana L. · blocked from the assistant</span>
        </span>
      </button>
      {error ? <p className="px-2 py-1 text-[10.5px] text-danger">{error}</p> : null}
    </div>
  );
}
