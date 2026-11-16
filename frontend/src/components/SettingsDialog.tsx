import { Moon, RotateCcw, Sun, X } from "lucide-react";
import { useState } from "react";
import { useSession } from "../contexts/SessionContext";
import { useTheme } from "../contexts/ThemeContext";
import { api, ApiError } from "../services/api";

export function SettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { meta } = useSession();
  const { theme, toggle } = useTheme();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  if (!open) return null;

  const resetDemo = async () => {
    setBusy(true);
    setNote(null);
    try {
      await api.resetDemo(true);
      setNote("Demo data reloaded and conversations cleared.");
      window.dispatchEvent(new CustomEvent("createchat:conversations-changed"));
      window.dispatchEvent(new CustomEvent("createchat:new-chat"));
    } catch (caught) {
      setNote(caught instanceof ApiError ? caught.message : "Could not reset the demo data.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/25 px-3 pb-3 backdrop-blur-sm sm:items-center sm:p-6">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        className="w-full max-w-md rounded-2xl border border-line bg-canvas shadow-lift"
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="text-[14px] font-semibold">Settings</h2>
          <button className="btn btn-ghost px-1.5 py-1" onClick={onClose} aria-label="Close settings">
            <X size={15} />
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          <section className="space-y-1">
            <p className="eyebrow">Signed in as</p>
            <p className="text-[13px] font-medium text-ink">{meta?.session.display_name ?? "Visitor"}</p>
            <p className="text-[11.5px] text-muted">
              {meta?.session.company ?? "Anonymous visitor"} · {meta?.session.user_id ?? "anonymous"}
            </p>
          </section>

          <section className="flex items-center justify-between gap-3 border-t border-line pt-3">
            <div>
              <p className="text-[12.5px] font-medium text-ink">Appearance</p>
              <p className="text-[11px] text-muted">Saved on this device.</p>
            </div>
            <button className="btn gap-1.5 py-1.5 text-[12px]" onClick={toggle}>
              {theme === "dark" ? <Sun size={13} /> : <Moon size={13} />}
              {theme === "dark" ? "Light" : "Dark"}
            </button>
          </section>

          <section className="space-y-1 border-t border-line pt-3">
            <p className="eyebrow">Assistant</p>
            <p className="text-[12px] text-ink">
              {meta?.model.configured ? `Live model · ${meta.model.name}` : "No model key configured"}
            </p>
            <p className="text-[11px] text-muted">Dataset day {meta?.dataset_today ?? "2026-11-16"} · Miami</p>
          </section>

          <section className="flex items-center justify-between gap-3 border-t border-line pt-3">
            <div>
              <p className="text-[12.5px] font-medium text-ink">Reset demo data</p>
              <p className="text-[11px] text-muted">Reloads the mock dataset and clears conversations.</p>
            </div>
            <button className="btn gap-1.5 py-1.5 text-[12px]" onClick={() => void resetDemo()} disabled={busy}>
              <RotateCcw size={13} />
              {busy ? "Resetting…" : "Reset"}
            </button>
          </section>

          {note ? <p className="text-[11px] leading-relaxed text-muted">{note}</p> : null}

          <p className="border-t border-line pt-3 text-[10.5px] leading-relaxed text-faint">
            CREATEchat proposes changes; you approve them. It never charges, cancels or messages a creative. Support
            tickets and notification settings are prototype stubs.
          </p>
        </div>
      </div>
    </div>
  );
}
