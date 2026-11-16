import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, ApiError } from "../services/api";
import type { SessionMeta } from "../types";

interface SessionValue {
  meta: SessionMeta | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  switchAccount: (userId: string, role?: string) => Promise<void>;
  signOut: () => Promise<void>;
  activeProjectId: string | null;
  setActiveProjectId: (projectId: string | null) => void;
  conversationNonce: number;
  startNewConversation: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<SessionMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [conversationNonce, setConversationNonce] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const next = await api.getSession();
      setMeta(next);
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not reach the CREATEchat backend.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const switchAccount = useCallback(async (userId: string, role?: string) => {
    setLoading(true);
    try {
      const next = await api.switchAccount(userId, role);
      setMeta(next);
      setActiveProjectId(null);
      setConversationNonce((value) => value + 1);
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not switch accounts.");
      throw caught;
    } finally {
      setLoading(false);
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      const next = await api.signOut();
      setMeta(next);
      setActiveProjectId(null);
      setConversationNonce((value) => value + 1);
    } finally {
      setLoading(false);
    }
  }, []);

  const startNewConversation = useCallback(() => {
    setConversationNonce((value) => value + 1);
  }, []);

  const value = useMemo<SessionValue>(
    () => ({
      meta,
      loading,
      error,
      refresh,
      switchAccount,
      signOut,
      activeProjectId,
      setActiveProjectId,
      conversationNonce,
      startNewConversation,
    }),
    [meta, loading, error, refresh, switchAccount, signOut, activeProjectId, conversationNonce, startNewConversation],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside SessionProvider");
  return context;
}
