import { AlertCircle, ChevronDown, Menu, Plus, Sparkles, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSession } from "../../contexts/SessionContext";
import { api, ApiError } from "../../services/api";
import { extractPartialMessage } from "../../services/stream";
import type { ChatMessage, ProjectSummary, UploadRecord } from "../../types";
import { TalentProfileModal } from "../TalentProfileModal";
import { Composer } from "./Composer";
import type { CardContext } from "./CardRenderer";
import { MessageView } from "./Message";

interface Streaming {
  text: string;
  label: string;
}

export function ChatPanel({ onOpenNav, onOpenSettings }: { onOpenNav: () => void; onOpenSettings: () => void }) {
  const { meta, activeProjectId, setActiveProjectId, conversationNonce } = useSession();
  const isClient = Boolean(meta?.session.authenticated);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [streaming, setStreaming] = useState<Streaming | null>(null);
  const [loadingThread, setLoadingThread] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [personaLabel, setPersonaLabel] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const abortRef = useRef<AbortController | null>(null);
  const sendRef = useRef<(text?: string, options?: { regenerate?: boolean }) => void>(() => undefined);

  const activeProject = useMemo(
    () => projects.find((project) => project.id === activeProjectId) ?? null,
    [projects, activeProjectId],
  );

  useEffect(() => {
    if (!isClient) {
      setProjects([]);
      return;
    }
    let cancelled = false;
    api
      .projects()
      .then((result) => {
        if (!cancelled) setProjects(result.projects);
      })
      .catch(() => {
        if (!cancelled) setProjects([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isClient, meta?.session.user_id, conversationNonce]);

  // Load the thread for the current scope. Threads are unique per client+project.
  useEffect(() => {
    if (!meta?.session.user_id) return;
    if (!isClient) {
      setMessages([]);
      setConversationId(null);
      setPersonaLabel(null);
      return;
    }
    let cancelled = false;
    setLoadingThread(true);
    setError(null);
    api
      .activeProject(activeProjectId)
      .then((result) => {
        if (cancelled) return;
        setMessages(result.messages ?? []);
        setConversationId(result.conversation.id);
        setPersonaLabel(null);
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof ApiError ? caught.message : "Could not load that conversation.");
      })
      .finally(() => {
        if (!cancelled) setLoadingThread(false);
      });
    return () => {
      cancelled = true;
    };
  }, [meta?.session.user_id, isClient, activeProjectId, conversationNonce]);

  useEffect(() => {
    if (!conversationId) return;
    window.dispatchEvent(new CustomEvent("createchat:conversation-active", { detail: { id: conversationId } }));
  }, [conversationId]);

  useEffect(() => {
    const open = async (event: Event) => {
      const detail = (event as CustomEvent<{ id: string; project_id?: string | null }>).detail;
      if (!detail?.id) return;
      const scope = detail.project_id ?? null;
      if (scope !== activeProjectId) {
        setActiveProjectId(scope);
        return;
      }
      // Same project scope: the effect won't rerun, so load the thread directly.
      try {
        const result = await api.messages(detail.id);
        setMessages(result.messages ?? []);
        setConversationId(result.conversation.id);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Could not load that conversation.");
      }
    };
    const fresh = () => {
      setMessages([]);
      setConversationId(null);
      setPersonaLabel(null);
    };
    window.addEventListener("createchat:open-conversation", open);
    window.addEventListener("createchat:new-chat", fresh);
    return () => {
      window.removeEventListener("createchat:open-conversation", open);
      window.removeEventListener("createchat:new-chat", fresh);
    };
  }, [setActiveProjectId, activeProjectId]);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node || !stickRef.current) return;
    node.scrollTop = node.scrollHeight;
  }, [messages, streaming?.text]);

  const onScroll = () => {
    const node = scrollRef.current;
    if (!node) return;
    stickRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 140;
  };

  const run = useCallback(
    async (raw?: string, options?: { regenerate?: boolean }) => {
      const regenerate = Boolean(options?.regenerate);
      const text = regenerate ? "" : (raw ?? draft).trim();
      if (sending) return;
      if (!regenerate && !text && uploads.length === 0) return;

      const projectForTurn = isClient ? activeProjectId : null;
      const cleanedUploads = regenerate ? [] : uploads;
      const tempId = `temp-${Date.now()}`;
      const controller = new AbortController();
      abortRef.current = controller;

      setError(null);
      setUploadError(null);
      setDraft("");
      setSending(true);
      setStreaming({ text: "", label: "Thinking" });
      stickRef.current = true;

      if (!regenerate) {
        setMessages((previous) => [
          ...previous,
          {
            id: tempId,
            conversation_id: conversationId ?? "",
            role: "user",
            content: text || `Attached ${cleanedUploads.length} file(s)`,
            envelope: null,
            created_at: new Date().toISOString(),
            pending: true,
          },
        ]);
      }

      let buffer = "";
      try {
        await api.chatStream(
          {
            message: text,
            project_id: projectForTurn,
            conversation_id: conversationId,
            upload_ids: cleanedUploads.map((upload) => upload.id),
            regenerate,
          },
          {
            signal: controller.signal,
            onStatus: (status) => {
              setMessages((previous) =>
                previous.map((message) => (message.id === tempId ? { ...message, pending: false } : message)),
              );
              setStreaming((current) => (current ? { ...current, label: status.label ?? current.label } : current));
            },
            onDelta: (chunk) => {
              buffer += chunk;
              const partial = extractPartialMessage(buffer);
              setStreaming((current) => (current ? { ...current, text: partial } : current));
            },
            onDone: (result) => {
              setConversationId(result.conversation_id);
              setPersonaLabel(result.persona.label);
              setMessages((previous) => {
                const rest = regenerate
                  ? previous
                  : previous.map((message) =>
                      message.id === tempId ? { ...message, pending: false } : message,
                    );
                return [
                  ...rest,
                  {
                    id: result.message_id,
                    conversation_id: result.conversation_id,
                    role: "assistant",
                    content: result.envelope.message,
                    envelope: result.envelope,
                    created_at: result.created_at,
                  },
                ];
              });
              setUploads([]);
              setStreaming(null);
              window.dispatchEvent(new CustomEvent("createchat:conversations-changed"));
              if (result.envelope.type === "action_proposal" || result.envelope.type === "handoff") {
                window.dispatchEvent(new CustomEvent("createchat:data-changed"));
              }
            },
            onError: (failure) => {
              setError(failure.message);
            },
          },
        );
      } catch (caught) {
        if ((caught as Error)?.name === "AbortError") {
          const partial = buffer ? extractPartialMessage(buffer) : "";
          if (partial) {
            setMessages((previous) => [
              ...previous,
              {
                id: `stopped-${Date.now()}`,
                conversation_id: conversationId ?? "",
                role: "assistant",
                content: `${partial}\n\n[Stopped]`,
                envelope: null,
                created_at: new Date().toISOString(),
              },
            ]);
          }
        } else if (!(caught instanceof ApiError)) {
          setError("The message didn't reach the assistant.");
        }
        if (!regenerate && !buffer) {
          setDraft(text);
          setMessages((previous) => previous.filter((message) => message.id !== tempId));
        }
      } finally {
        setSending(false);
        setStreaming(null);
        abortRef.current = null;
      }
    },
    [sending, draft, uploads, isClient, activeProjectId, conversationId],
  );

  sendRef.current = run;

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ text: string; projectId?: string | null }>).detail;
      if (!detail?.text) return;
      if (detail.projectId !== undefined) setActiveProjectId(detail.projectId);
      void sendRef.current(detail.text);
    };
    window.addEventListener("createchat:prompt", handler);
    return () => window.removeEventListener("createchat:prompt", handler);
  }, [setActiveProjectId]);

  const stop = () => {
    abortRef.current?.abort();
  };

  const regenerate = () => {
    const lastUser = [...messages].reverse().find((message) => message.role === "user");
    if (!lastUser || sending) return;
    setMessages((previous) => {
      const copy = [...previous];
      const index = copy.map((message) => message.role).lastIndexOf("assistant");
      if (index >= 0) copy.splice(index, 1);
      return copy;
    });
    void sendRef.current("", { regenerate: true });
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploadError(null);
    const list = Array.from(files);
    if (uploads.length + list.length > 10) {
      setUploadError("At most 10 files per message.");
      return;
    }
    setUploading(true);
    try {
      const result = await api.upload(list);
      setUploads((previous) => [...previous, ...result.uploads]);
    } catch (caught) {
      setUploadError(caught instanceof ApiError ? caught.message : "That file couldn't be read.");
    } finally {
      setUploading(false);
    }
  };

  const onProposalUpdated = useCallback((proposalId: string, status: string) => {
    setMessages((previous) =>
      previous.map((message) => {
        const cards = message.envelope?.data?.cards;
        if (!message.envelope || !cards?.some((card) => card.proposal?.proposal_id === proposalId)) {
          return message;
        }
        return {
          ...message,
          envelope: {
            ...message.envelope,
            data: {
              ...message.envelope.data,
              cards: cards.map((card) =>
                card.proposal?.proposal_id === proposalId
                  ? { ...card, proposal: { ...card.proposal, status } }
                  : card,
              ),
            },
          },
        };
      }),
    );
  }, []);

  const cardContext: CardContext = useMemo(
    () => ({
      isClient,
      projectId: activeProjectId,
      projectName: activeProject?.name ?? null,
      onProposalUpdated,
      onOpenProfile: (talentId: string) => setProfileId(talentId),
      onPrompt: (text: string) => void sendRef.current(text),
    }),
    [isClient, activeProjectId, activeProject?.name, onProposalUpdated],
  );

  const prompts = isClient
    ? activeProject
      ? ["What needs my attention on this project?", "What's the shoot-day plan?", "Who is free on the shoot date?"]
      : ["What needs my attention?", "I need photos of my new menu next month, budget $900", "Find videographers in Miami Beach"]
    : ["Show me videographers in Miami Beach", "What packages do you offer for a listing?", "How does booking a creative work?"];

  const lastAssistantId = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant")?.id,
    [messages],
  );
  const empty = messages.length === 0 && !loadingThread && !streaming;

  return (
    <section className="flex h-dvh min-w-0 flex-col bg-canvas" aria-label="CREATEchat assistant">
      <header className="flex h-[54px] flex-none items-center gap-2 border-b border-line px-2.5 sm:px-5">
        <button className="btn btn-ghost px-1.5 py-1 lg:hidden" onClick={onOpenNav} aria-label="Open navigation">
          <Menu size={17} />
        </button>
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="grid h-7 w-7 flex-none place-items-center rounded-lg border border-line bg-surface">
            <Sparkles size={14} className="text-accent" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-[13px] font-semibold leading-tight text-ink">CREATEchat</p>
            <p className="flex items-center gap-1.5 truncate text-[10.5px] text-faint">
              <span className={`h-1.5 w-1.5 rounded-full ${meta?.model.configured ? "bg-accent" : "bg-warning"}`} />
              {streaming ? streaming.label : personaLabel ?? (meta?.model.configured ? "Ready" : "Model key needed")}
            </p>
          </div>
        </div>

        <div className="ml-auto flex min-w-0 items-center gap-1.5">
          {isClient ? (
            <div className="relative hidden min-w-0 sm:block">
              <select
                className="h-8 max-w-[190px] appearance-none truncate rounded-lg border border-line bg-canvas py-1 pl-2.5 pr-7 text-[11.5px] text-body focus:border-accent-ring focus:outline-none"
                value={activeProjectId ?? ""}
                onChange={(event) => setActiveProjectId(event.target.value || null)}
                aria-label="Project scope"
              >
                <option value="">All projects</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
              <ChevronDown size={12} className="pointer-events-none absolute right-2 top-2.5 text-faint" />
            </div>
          ) : null}
          <button
            className="btn btn-ghost px-1.5 py-1"
            onClick={() => {
              setMessages([]);
              setConversationId(null);
              setPersonaLabel(null);
            }}
            aria-label="New chat"
            title="New chat"
          >
            <Plus size={16} />
          </button>
        </div>
      </header>

      <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto scroll-area">
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
          {loadingThread ? (
            <div className="space-y-4">
              <div className="h-4 w-2/3 animate-pulse rounded bg-line/60" />
              <div className="h-4 w-1/2 animate-pulse rounded bg-line/60" />
            </div>
          ) : empty ? (
            <Welcome
              isClient={isClient}
              name={meta?.session.display_name ?? ""}
              prompts={prompts}
              onPrompt={(prompt) => void run(prompt)}
            />
          ) : (
            <div className="space-y-6">
              {messages.map((message) => (
                <MessageView
                  key={message.id}
                  message={message}
                  context={cardContext}
                  personaLabel={message.role === "assistant" ? personaLabel : null}
                  showActions={message.id === lastAssistantId && !sending}
                  canRegenerate={message.id === lastAssistantId && !sending}
                  onRegenerate={regenerate}
                />
              ))}
              {streaming ? <StreamingBubble state={streaming} /> : null}
            </div>
          )}
        </div>
      </div>

      {error ? (
        <div className="flex-none border-t border-danger/20 bg-danger-soft px-4 py-2">
          <div className="mx-auto flex max-w-3xl items-start justify-between gap-2">
            <p className="flex items-start gap-1.5 text-[11.5px] leading-relaxed text-danger">
              <AlertCircle size={13} className="mt-0.5 flex-none" />
              {error}
            </p>
            <button className="text-danger" onClick={() => setError(null)} aria-label="Dismiss error">
              <X size={13} />
            </button>
          </div>
        </div>
      ) : null}
      {uploadError ? (
        <div className="flex-none border-t border-danger/20 bg-danger-soft px-4 py-2">
          <div className="mx-auto flex max-w-3xl items-start justify-between gap-2">
            <p className="text-[11.5px] leading-relaxed text-danger">{uploadError}</p>
            <button className="text-danger" onClick={() => setUploadError(null)} aria-label="Dismiss upload error">
              <X size={13} />
            </button>
          </div>
        </div>
      ) : null}

      <div className="flex-none bg-canvas px-3 pb-3 pt-1 sm:px-6 sm:pb-5">
        <div className="mx-auto w-full max-w-3xl">
          <Composer
            value={draft}
            onChange={setDraft}
            onSend={() => void run()}
            onStop={stop}
            sending={sending}
            uploads={uploads}
            onFiles={(files) => void handleFiles(files)}
            onRemoveUpload={(id) => setUploads((previous) => previous.filter((upload) => upload.id !== id))}
            uploading={uploading}
            disabled={meta?.session.role === "talent"}
            placeholder={
              activeProject
                ? `Ask about ${activeProject.name}…`
                : isClient
                  ? "Ask about your projects, talent or packages…"
                  : "Ask about talent, packages or booking…"
            }
          />
          <p className="mt-2 text-center text-[10px] leading-relaxed text-faint">
            CREATEchat proposes changes; you approve them. It never charges, cancels or messages a creative.
            {isClient ? (
              <>
                {" "}
                <button className="underline decoration-line-strong underline-offset-2 hover:text-ink" onClick={onOpenSettings}>
                  Settings
                </button>
              </>
            ) : (
              <>
                {" "}
                <button className="underline decoration-line-strong underline-offset-2 hover:text-ink" onClick={onOpenSettings}>
                  Switch demo client
                </button>
              </>
            )}
          </p>
        </div>
      </div>

      <TalentProfileModal
        talentId={profileId}
        projectName={activeProject?.name ?? null}
        isClient={isClient}
        onClose={() => setProfileId(null)}
        onPrompt={(text) => {
          setProfileId(null);
          void run(text);
        }}
      />
    </section>
  );
}

function Welcome({
  isClient,
  name,
  prompts,
  onPrompt,
}: {
  isClient: boolean;
  name: string;
  prompts: string[];
  onPrompt: (prompt: string) => void;
}) {
  const first = name.split(" ")[0];
  return (
    <div className="flex min-h-[52vh] flex-col items-center justify-center px-1 text-center">
      <span className="grid h-11 w-11 place-items-center rounded-2xl border border-line bg-surface shadow-card">
        <Sparkles size={19} className="text-accent" />
      </span>
      <h1 className="mt-4 text-[22px] font-semibold tracking-[-0.02em] text-ink sm:text-[24px]">
        {isClient && first ? `Hi ${first}, what are we shooting?` : "What are we creating?"}
      </h1>
      <p className="mt-1.5 max-w-md text-[12.5px] leading-relaxed text-muted">
        {isClient
          ? "I can read your projects, find creatives, check prices and prepare changes for you to approve."
          : "Ask about photographers, videographers and fixed-price packages across South Florida."}
      </p>
      <div className="mt-6 grid w-full max-w-xl gap-2 sm:grid-cols-2">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            className="rounded-xl border border-line bg-surface px-3.5 py-2.5 text-left text-[12px] leading-snug text-body transition-colors hover:border-line-strong hover:text-ink"
            onClick={() => onPrompt(prompt)}
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}

function StreamingBubble({ state }: { state: Streaming }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 grid h-6 w-6 flex-none place-items-center rounded-md border border-line bg-surface">
        <Sparkles size={12.5} className="text-accent" />
      </span>
      <div className="min-w-0 flex-1">
        {state.text ? (
          <p className="prose-chat">
            {state.text}
            <span className="ml-0.5 inline-block h-[1em] w-[2px] animate-caret bg-ink align-[-0.15em]" />
          </p>
        ) : (
          <div className="flex items-center gap-1.5 py-1">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-accent"
                style={{ animationDelay: `${dot * 0.16}s` }}
              />
            ))}
            <span className="ml-1 text-[11px] text-faint">{state.label}</span>
          </div>
        )}
        {state.text ? <p className="mt-1 text-[10px] text-faint">{state.label}</p> : null}
      </div>
    </div>
  );
}
