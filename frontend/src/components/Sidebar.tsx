import { ChevronDown, MessageSquare, Moon, Plus, Settings as SettingsIcon, Sun, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "../contexts/SessionContext";
import { useTheme } from "../contexts/ThemeContext";
import { api } from "../services/api";
import { timeAgo } from "../services/format";
import type { Conversation } from "../types";
import { AccountSwitcher } from "./AccountSwitcher";

export function Sidebar({
  open,
  onClose,
  onOpenSettings,
}: {
  open: boolean;
  onClose: () => void;
  onOpenSettings: () => void;
}) {
  const { meta, loading, conversationNonce } = useSession();
  const { theme, toggle } = useTheme();
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const authenticated = Boolean(meta?.session.authenticated);

  const load = useCallback(async () => {
    if (!authenticated) {
      setConversations([]);
      return;
    }
    try {
      const result = await api.conversations();
      setConversations(result.conversations);
    } catch {
      setConversations([]);
    }
  }, [authenticated]);

  useEffect(() => {
    void load();
  }, [load, conversationNonce, meta?.session.user_id]);

  useEffect(() => {
    const refresh = () => void load();
    const active = (event: Event) => {
      const detail = (event as CustomEvent<{ id: string | null }>).detail;
      setActiveId(detail?.id ?? null);
    };
    window.addEventListener("createchat:conversations-changed", refresh);
    window.addEventListener("createchat:data-changed", refresh);
    window.addEventListener("createchat:conversation-active", active);
    return () => {
      window.removeEventListener("createchat:conversations-changed", refresh);
      window.removeEventListener("createchat:data-changed", refresh);
      window.removeEventListener("createchat:conversation-active", active);
    };
  }, [load]);

  const newChat = () => {
    window.dispatchEvent(new CustomEvent("createchat:new-chat"));
    onClose();
  };

  const openConversation = (conversation: Conversation) => {
    window.dispatchEvent(
      new CustomEvent("createchat:open-conversation", {
        detail: { id: conversation.id, project_id: conversation.project_id ?? null },
      }),
    );
    onClose();
  };

  return (
    <>
      {open ? <div className="fixed inset-0 z-30 bg-ink/20 backdrop-blur-[1px] lg:hidden" onClick={onClose} /> : null}
      <aside
        className={`${
          open ? "translate-x-0" : "-translate-x-full"
        } fixed inset-y-0 left-0 z-40 flex w-[272px] flex-none flex-col border-r border-line bg-surface transition-transform duration-200 lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0`}
        aria-label="Chat sidebar"
      >
        <div className="flex items-center justify-between px-3 pb-2 pt-3.5">
          <button
            className="flex items-center gap-2.5 rounded-lg px-1 py-1 text-left"
            onClick={newChat}
            aria-label="CREATEchat home"
          >
            <span className="grid h-7 w-7 place-items-center rounded-[9px] bg-ink text-[12px] font-semibold text-canvas">
              C
            </span>
            <span className="text-[14px] font-semibold tracking-[-0.015em] text-ink">CREATEchat</span>
            <span className="rounded border border-line bg-canvas px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-faint">
              OPAH
            </span>
          </button>
          <button className="btn btn-ghost px-1.5 py-1 lg:hidden" onClick={onClose} aria-label="Close navigation">
            <X size={16} />
          </button>
        </div>

        <div className="px-2.5">
          <button
            className="btn w-full justify-start gap-2 px-2.5 py-2 text-[12.5px]"
            onClick={newChat}
            disabled={loading}
          >
            <Plus size={15} />
            New chat
          </button>
        </div>

        <div className="mt-4 flex min-h-0 flex-1 flex-col">
          <p className="eyebrow px-4 pb-1.5">Recent</p>
          <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2 scroll-area">
            {!authenticated ? (
              <p className="px-2 py-1 text-[11px] leading-relaxed text-faint">
                Sign in with a demo client to keep conversation history.
              </p>
            ) : conversations.length === 0 ? (
              <p className="px-2 py-1 text-[11px] leading-relaxed text-faint">Your conversations will appear here.</p>
            ) : (
              <ul className="space-y-0.5">
                {conversations.map((conversation) => {
                  const active = conversation.id === activeId;
                  return (
                    <li key={conversation.id}>
                      <button
                        onClick={() => openConversation(conversation)}
                        className={`group flex w-full items-center gap-2 rounded-lg px-2 py-[7px] text-left transition-colors ${
                          active ? "bg-accent-soft text-accent-ink" : "text-body hover:bg-canvas hover:text-ink"
                        }`}
                      >
                        <MessageSquare
                          size={13.5}
                          className={`flex-none ${active ? "text-accent-ink" : "text-faint"}`}
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[12px] font-medium">
                            {conversation.project_name ?? conversation.title ?? "General conversation"}
                          </span>
                          <span className="block truncate text-[10px] text-faint">
                            {conversation.message_count ? `${conversation.message_count} messages · ` : ""}
                            {timeAgo(conversation.updated_at)}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        <div className="border-t border-line px-2 py-2">
          <button
            className="flex w-full items-center gap-2 rounded-lg px-2 py-[7px] text-[12px] font-medium text-body transition-colors hover:bg-canvas hover:text-ink"
            onClick={toggle}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <Sun size={14} className="text-faint" /> : <Moon size={14} className="text-faint" />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
          <button
            className="flex w-full items-center gap-2 rounded-lg px-2 py-[7px] text-[12px] font-medium text-body transition-colors hover:bg-canvas hover:text-ink"
            onClick={onOpenSettings}
          >
            <SettingsIcon size={14} className="text-faint" />
            Settings
          </button>
        </div>

        <div className="border-t border-line p-2.5">
          <button
            className="flex w-full items-center justify-between gap-2 rounded-lg border border-line bg-canvas px-2.5 py-2 text-left transition-colors hover:border-line-strong"
            onClick={() => setSwitcherOpen((value) => !value)}
            aria-expanded={switcherOpen}
            aria-label="Switch demo account"
          >
            <span className="flex min-w-0 items-center gap-2">
              <span className="grid h-7 w-7 flex-none place-items-center rounded-full bg-ink text-[10.5px] font-semibold text-canvas">
                {meta?.session.initials ?? "V"}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[12px] font-medium text-ink">
                  {meta?.session.display_name ?? "Visitor"}
                </span>
                <span className="block truncate text-[10px] text-faint">
                  {meta?.session.company ?? meta?.session.user_id ?? "anonymous"}
                </span>
              </span>
            </span>
            <ChevronDown size={13} className="flex-none text-faint" />
          </button>
          <AccountSwitcher open={switcherOpen} onClose={() => setSwitcherOpen(false)} />
        </div>
      </aside>
    </>
  );
}
