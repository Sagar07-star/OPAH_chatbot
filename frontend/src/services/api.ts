import type {
  AccountSummary,
  Board,
  ChatMessage,
  ChatResponse,
  Conversation,
  DeliverableFolder,
  Envelope,
  Package,
  ProjectDetail,
  ProjectDocument,
  ProjectSummary,
  Proposal,
  ProposalResponse,
  SessionMeta,
  SupportTicket,
  Talent,
  TalentProfile,
  UploadRecord,
} from "../types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(message: string, status: number, code = "error", details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function reportFailure(route: string, message: string, status: number) {
  if (status < 500 || route.includes("app-errors")) return;
  void fetch(`${BASE}/api/support/app-errors`, {
    method: "POST",
    credentials: "include",
    keepalive: true,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ route, message: message.slice(0, 400), status }),
  }).catch(() => undefined);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { credentials: "include", ...options, headers });
  } catch (error) {
    throw new ApiError(
      "The backend isn't reachable. Check that the FastAPI server is running on port 8000.",
      0,
      "network_error",
      error,
    );
  }
  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
  }
  if (!response.ok) {
    const body = (data ?? {}) as { message?: string; error?: string };
    const message = body.message || `Request failed (${response.status}).`;
    reportFailure(path, message, response.status);
    throw new ApiError(message, response.status, body.error || "error", data);
  }
  return data as T;
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  getSession: () => request<SessionMeta>("/api/session"),

  switchAccount: (user_id: string, role?: string) =>
    request<SessionMeta>("/api/session/switch", {
      method: "POST",
      body: JSON.stringify({ user_id, role }),
    }),

  signOut: () => request<SessionMeta>("/api/session/sign-out", { method: "POST" }),

  activeProject: (project_id: string | null) =>
    request<{ project: ProjectSummary | null; conversation: Conversation; messages: ChatMessage[] }>(
      "/api/session/active-project",
      { method: "POST", body: JSON.stringify({ project_id }) },
    ),

  conversations: () => request<{ conversations: Conversation[] }>("/api/session/conversations"),

  summary: () => request<AccountSummary>("/api/account/summary"),

  projects: (status?: string) =>
    request<{ count: number; projects: ProjectSummary[]; counts: Partial<Record<string, number>> }>(
      `/api/projects${query({ status })}`,
    ),

  project: (id: string) =>
    request<{ project: ProjectDetail; today: string }>(`/api/projects/${encodeURIComponent(id)}`),

  saveDocument: (
    projectId: string,
    payload: { type: string; title: string; content_md: string },
  ) =>
    request<{ document: ProjectDocument; saved: boolean }>(
      `/api/projects/${encodeURIComponent(projectId)}/documents`,
      { method: "POST", body: JSON.stringify(payload) },
    ),

  documents: () =>
    request<{ count: number; documents: ProjectDocument[] }>("/api/documents"),

  boards: () => request<{ count: number; boards: Board[] }>("/api/boards"),

  packages: (category?: string) =>
    request<{
      count: number;
      packages: Package[];
      service_area: string[];
      assistance_fee_rate: number;
    }>(`/api/packages${query({ category })}`),

  options: () =>
    request<{
      catalogs: Record<string, { label: string; multi: boolean; options: { value: string; label: string }[] }>;
      today: string;
    }>("/api/options"),

  talentSearch: (params: Record<string, string | number | undefined>) =>
    request<{
      count: number;
      returned: number;
      talent_ids: string[];
      talents: Talent[];
      applied: Record<string, unknown>;
      relaxed: string[];
      role_notice?: string;
      unrecognized?: Record<string, string>;
    }>(`/api/talent/search${query(params)}`),

  talentProfile: (id: string) => request<{ talent: TalentProfile }>(`/api/talent/${encodeURIComponent(id)}`),

  deliverables: () =>
    request<{ count: number; folders: DeliverableFolder[] }>("/api/deliverables"),

  proposals: (status = "pending") =>
    request<{ count: number; proposals: Proposal[] }>(`/api/proposals${query({ status })}`),

  proposal: (id: string) => request<{ proposal: Proposal }>(`/api/proposals/${encodeURIComponent(id)}`),

  approve: (id: string) =>
    request<ProposalResponse>(`/api/proposals/${encodeURIComponent(id)}/approve`, { method: "POST" }),

  reject: (id: string) =>
    request<ProposalResponse>(`/api/proposals/${encodeURIComponent(id)}/reject`, { method: "POST" }),

  messages: (conversationId: string) =>
    request<{ conversation: Conversation; messages: ChatMessage[] }>(
      `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    ),

  chat: (payload: {
    message: string;
    project_id?: string | null;
    conversation_id?: string | null;
    upload_ids?: string[];
    regenerate?: boolean;
  }) => request<ChatResponse>("/api/chat", { method: "POST", body: JSON.stringify(payload) }),

  chatStream: async (
    payload: {
      message: string;
      project_id?: string | null;
      conversation_id?: string | null;
      upload_ids?: string[];
      regenerate?: boolean;
    },
    handlers: {
      onStatus?: (status: { phase?: string; label?: string; tools?: string[] }) => void;
      onDelta?: (text: string) => void;
      onDone: (result: ChatResponse) => void;
      onError?: (error: ApiError) => void;
      signal?: AbortSignal;
    },
  ): Promise<void> => {
    let response: Response;
    try {
      response = await fetch(`${BASE}/api/chat/stream`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(payload),
        signal: handlers.signal,
      });
    } catch (error) {
      if ((error as Error)?.name === "AbortError") throw error;
      const failure = new ApiError(
        "The backend isn't reachable. Check that the FastAPI server is running on port 8000.",
        0,
        "network_error",
        error,
      );
      handlers.onError?.(failure);
      throw failure;
    }

    if (!response.ok) {
      const text = await response.text();
      let body: { message?: string; error?: string; detail?: { message?: string; error?: string } } | null = null;
      try {
        body = JSON.parse(text) as typeof body;
      } catch {
        body = { message: text };
      }
      const message = body?.message || body?.detail?.message || `Request failed (${response.status}).`;
      const code = body?.error || body?.detail?.error || "error";
      reportFailure("/api/chat/stream", message, response.status);
      const failure = new ApiError(message, response.status, code, body);
      handlers.onError?.(failure);
      throw failure;
    }
    if (!response.body) {
      const failure = new ApiError("This browser can't read a streamed reply.", 0, "stream_unsupported");
      handlers.onError?.(failure);
      throw failure;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let eventName = "message";
    let dataLines: string[] = [];

    const dispatch = () => {
      if (dataLines.length === 0) {
        eventName = "message";
        return;
      }
      const raw = dataLines.join("\n");
      const name = eventName;
      dataLines = [];
      eventName = "message";
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(raw) as Record<string, unknown>;
      } catch {
        return;
      }
      if (name === "delta") {
        handlers.onDelta?.(typeof parsed.text === "string" ? parsed.text : "");
      } else if (name === "status") {
        handlers.onStatus?.(parsed as { phase?: string; label?: string; tools?: string[] });
      } else if (name === "done") {
        handlers.onDone(parsed.result as ChatResponse);
      } else if (name === "error") {
        const failure = new ApiError(
          typeof parsed.message === "string" ? parsed.message : "The assistant couldn't finish that.",
          typeof parsed.status === "number" ? parsed.status : 500,
          typeof parsed.code === "string" ? parsed.code : "error",
          parsed,
        );
        handlers.onError?.(failure);
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let newline = buffer.indexOf("\n");
      while (newline >= 0) {
        const line = buffer.slice(0, newline).replace(/\r$/, "");
        buffer = buffer.slice(newline + 1);
        if (line === "") {
          dispatch();
        } else if (line.startsWith(":")) {
          // keep-alive comment
        } else if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).replace(/^ /, ""));
        }
        newline = buffer.indexOf("\n");
      }
    }
    dispatch();
  },

  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<{
      uploads: UploadRecord[];
      count: number;
      limits: { files: number; image_mb: number; pdf_mb: number; pdf_pages: number };
    }>("/api/uploads", { method: "POST", body: form });
  },

  uploadUrl: (id: string) => `${BASE}/api/uploads/${encodeURIComponent(id)}/raw`,

  tickets: () => request<{ tickets: SupportTicket[]; count: number; note: string }>("/api/support/tickets"),

  createTicket: (payload: { subject: string; topic: string; details: string; project_id?: string | null }) =>
    request<{ ticket: SupportTicket; stub: boolean; message: string }>("/api/support/tickets", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  config: () =>
    request<{
      dataset_today: string;
      assistance_fee_rate: number;
      model_configured: boolean;
      model: string;
      field_labels: Record<string, string>;
      upload_limits: { files: number; image_mb: number; pdf_mb: number; pdf_pages: number };
    }>("/api/config"),

  resetDemo: (conversations = true) =>
    request<{ status: string; dataset_today: string }>("/api/demo/reset", {
      method: "POST",
      body: JSON.stringify({ conversations }),
    }),
};

export function envelopeForError(error: unknown): Envelope {
  const message =
    error instanceof ApiError
      ? error.message
      : "Something went wrong before the assistant could answer. Nothing was changed.";
  const code = error instanceof ApiError ? error.code : "client_error";
  return {
    type: "error",
    message,
    data: { error_code: code },
    actions: [],
  };
}
