import { Sparkles } from "lucide-react";
import { useState } from "react";
import { useSession } from "../contexts/SessionContext";
import { ChatPanel } from "./chat/ChatPanel";
import { SettingsDialog } from "./SettingsDialog";
import { Sidebar } from "./Sidebar";

export function ChatShell() {
  const { meta, loading, switchAccount } = useSession();
  const [navOpen, setNavOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const blocked = meta?.session.role === "talent";

  return (
    <div className="flex h-dvh overflow-hidden bg-canvas text-body">
      <Sidebar
        open={navOpen}
        onClose={() => setNavOpen(false)}
        onOpenSettings={() => {
          setNavOpen(false);
          setSettingsOpen(true);
        }}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        {blocked ? (
          <BlockedCreative onSwitch={() => void switchAccount("clt_001")} />
        ) : loading && !meta ? (
          <div className="flex flex-1 items-center justify-center text-[13px] text-muted">Loading your account…</div>
        ) : (
          <ChatPanel onOpenNav={() => setNavOpen(true)} onOpenSettings={() => setSettingsOpen(true)} />
        )}
      </div>
      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

function BlockedCreative({ onSwitch }: { onSwitch: () => void }) {
  const { meta, switchAccount } = useSession();
  return (
    <div className="flex flex-1 items-center justify-center px-6 py-16">
      <div className="card max-w-md px-7 py-8">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-canvas text-muted">
          <Sparkles size={17} />
        </span>
        <h1 className="mt-4 text-[17px] font-semibold">This assistant is for clients</h1>
        <p className="mt-2 text-[13px] leading-relaxed text-muted">
          You're signed in as a creative account ({meta?.session.display_name}). CREATEchat is blocked before the model
          runs for creatives; bookings are managed in the creative dashboard.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <button className="btn btn-primary" onClick={onSwitch}>
            Switch to Maya Torres
          </button>
          <button className="btn" onClick={() => void switchAccount("anonymous")}>
            Continue as visitor
          </button>
        </div>
      </div>
    </div>
  );
}
