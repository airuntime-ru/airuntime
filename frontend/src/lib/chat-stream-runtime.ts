/**
 * Project-scoped chat stream runtime that survives Next.js page unmounts.
 *
 * Leaving chat → deployments/logs/settings unmounts chat/page.tsx. Without this
 * store, React state (status panel + streaming assistant text) is lost and the
 * orphaned reader can no longer update the UI — which feels like the prompt
 * "отвалился и стоп". The fetch itself was not aborted on unmount; the UI was.
 */

export type AgentStatus = {
  phase: string;
  label: string;
  state: "running" | "done" | "error" | "waiting";
};

export type ChatFileAttachment = {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  download_url: string | null;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  attachments?: ChatFileAttachment[];
};

export type ToolActivityItem = {
  id: number;
  label: string;
  state: "running" | "done" | "error";
};

export type ChatStreamSnapshot = {
  projectId: string;
  chatId: string;
  loading: boolean;
  messages: ChatMessage[] | null;
  agentStatus: AgentStatus | null;
  toolActivity: ToolActivityItem[];
  chatError: string;
};

type InternalSession = ChatStreamSnapshot & {
  controller: AbortController | null;
  toolActivityId: number;
  listeners: Set<() => void>;
  // True only in the tab that actually owns the fetch for this session (set in runStreamLoop).
  // Every other tab holding a mirrored copy (see the cross-tab sync section below) keeps this
  // false, so it knows to apply incoming broadcasts instead of treating itself as authoritative.
  isLeader: boolean;
};

const sessions = new Map<string, InternalSession>();

function storageKey(projectId: string, chatId: string) {
  // Keep the same key chat/page.tsx used historically.
  return `airuntime_agent_status_${projectId}_${chatId}`;
}

function sessionKey(projectId: string, chatId: string) {
  return `${projectId}:${chatId}`;
}

function readPersistedStatus(projectId: string, chatId: string): AgentStatus | null {
  if (typeof window === "undefined" || !projectId || !chatId) return null;
  try {
    const raw = sessionStorage.getItem(storageKey(projectId, chatId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AgentStatus;
    if (!parsed?.phase || !parsed?.label || !parsed?.state) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writePersistedStatus(projectId: string, chatId: string, status: AgentStatus | null) {
  if (typeof window === "undefined" || !projectId || !chatId) return;
  const key = storageKey(projectId, chatId);
  if (!status) {
    sessionStorage.removeItem(key);
    return;
  }
  sessionStorage.setItem(key, JSON.stringify(status));
}

function ensureSession(projectId: string, chatId: string): InternalSession {
  const key = sessionKey(projectId, chatId);
  let session = sessions.get(key);
  if (!session) {
    session = {
      projectId,
      chatId,
      loading: false,
      messages: null,
      agentStatus: readPersistedStatus(projectId, chatId),
      toolActivity: [],
      chatError: "",
      controller: null,
      toolActivityId: 0,
      listeners: new Set(),
      isLeader: false,
    };
    sessions.set(key, session);
    // Brand new locally - another tab may already be mid-stream for this exact chat (e.g. this
    // chat page just mounted while a turn started elsewhere). Ask around; a leader tab answers
    // with its current snapshot (see handleBroadcastMessage), a no-op if nobody responds.
    requestRemoteState(projectId, chatId);
  }
  return session;
}

function notify(session: InternalSession) {
  session.listeners.forEach((listener) => {
    try {
      listener();
    } catch {
      // subscriber errors must not break the stream loop
    }
  });
}

function snapshotOf(session: InternalSession): ChatStreamSnapshot {
  return {
    projectId: session.projectId,
    chatId: session.chatId,
    loading: session.loading,
    messages: session.messages,
    agentStatus: session.agentStatus,
    toolActivity: session.toolActivity,
    chatError: session.chatError,
  };
}

// --- Cross-tab sync ---------------------------------------------------------------------------
// Everything above lives only in this tab's JS module instance - a second tab opened on the same
// chat gets a brand new, empty `sessions` map with no idea a turn is running elsewhere, so it
// showed no animation/status at all until the turn finished and a plain page load picked up the
// persisted messages. BroadcastChannel is same-origin, same-browser messaging to every other open
// tab: the tab that actually owns the fetch (session.isLeader) rebroadcasts its state on every
// change; any other tab mirrors that into its own local session so the existing
// notify()/subscribeChatStream() rendering path in chat/page.tsx needs no changes at all. A tab
// that mounts fresh asks the others for current state in case a turn is already mid-flight.
type ChatBroadcastMessage =
  | { type: "state"; projectId: string; chatId: string; snapshot: ChatStreamSnapshot }
  | { type: "request-state"; projectId: string; chatId: string }
  | { type: "abort-request"; projectId: string; chatId: string };

let broadcastChannel: BroadcastChannel | null = null;

function getBroadcastChannel(): BroadcastChannel | null {
  if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") return null;
  if (!broadcastChannel) {
    broadcastChannel = new BroadcastChannel("airuntime_chat_stream");
    broadcastChannel.onmessage = (event: MessageEvent<ChatBroadcastMessage>) => {
      handleBroadcastMessage(event.data);
    };
  }
  return broadcastChannel;
}

function postToOtherTabs(message: ChatBroadcastMessage) {
  // BroadcastChannel never delivers a message back to the tab that posted it, so leader tabs
  // never need to filter out their own broadcasts.
  getBroadcastChannel()?.postMessage(message);
}

function handleBroadcastMessage(message: ChatBroadcastMessage) {
  const key = sessionKey(message.projectId, message.chatId);

  if (message.type === "request-state") {
    const session = sessions.get(key);
    if (session?.isLeader && session.loading) {
      postToOtherTabs({
        type: "state",
        projectId: message.projectId,
        chatId: message.chatId,
        snapshot: snapshotOf(session),
      });
    }
    return;
  }

  if (message.type === "abort-request") {
    // Lets "Остановить генерацию" clicked from a follower tab actually reach the leader's fetch.
    const session = sessions.get(key);
    if (session?.isLeader) session.controller?.abort();
    return;
  }

  // message.type === "state"
  const session = ensureSession(message.projectId, message.chatId);
  if (session.isLeader) return; // this tab owns the real fetch - it's authoritative, not a mirror
  session.loading = message.snapshot.loading;
  session.messages = message.snapshot.messages;
  session.agentStatus = message.snapshot.agentStatus;
  session.toolActivity = message.snapshot.toolActivity;
  session.chatError = message.snapshot.chatError;
  writePersistedStatus(message.projectId, message.chatId, session.agentStatus);
  notify(session);
}

function broadcastState(projectId: string, chatId: string, session: InternalSession) {
  postToOtherTabs({ type: "state", projectId, chatId, snapshot: snapshotOf(session) });
}

function requestRemoteState(projectId: string, chatId: string) {
  postToOtherTabs({ type: "request-state", projectId, chatId });
}

export function getChatStreamSnapshot(projectId: string, chatId: string): ChatStreamSnapshot {
  return snapshotOf(ensureSession(projectId, chatId));
}

export function subscribeChatStream(
  projectId: string,
  chatId: string,
  listener: () => void
): () => void {
  const session = ensureSession(projectId, chatId);
  session.listeners.add(listener);
  return () => {
    session.listeners.delete(listener);
  };
}

export function setChatStreamMessages(
  projectId: string,
  chatId: string,
  messages: ChatMessage[] | null
) {
  const session = ensureSession(projectId, chatId);
  // Don't clobber an in-flight stream with a stale server fetch.
  if (session.loading && session.messages) return;
  session.messages = messages;
  notify(session);
}

export function setChatStreamAgentStatus(
  projectId: string,
  chatId: string,
  status: AgentStatus | null
) {
  const session = ensureSession(projectId, chatId);
  session.agentStatus = status;
  // Persist running too so returning to chat restores the panel mid-turn.
  writePersistedStatus(projectId, chatId, status);
  notify(session);
}

export function clearChatStreamSession(projectId: string, chatId: string) {
  const key = sessionKey(projectId, chatId);
  const session = sessions.get(key);
  if (!session) return;
  session.controller?.abort();
  session.controller = null;
  session.loading = false;
  session.messages = null;
  session.agentStatus = null;
  session.toolActivity = [];
  session.chatError = "";
  writePersistedStatus(projectId, chatId, null);
  notify(session);
}

export function abortChatStream(projectId: string, chatId: string) {
  const session = ensureSession(projectId, chatId);
  session.controller?.abort();
  // No-op if this tab is the leader (already aborted above); reaches the leader if it's a
  // different tab and this one is only showing a mirrored copy of the stream.
  postToOtherTabs({ type: "abort-request", projectId, chatId });
}

export function isChatStreamLoading(projectId: string, chatId: string): boolean {
  return ensureSession(projectId, chatId).loading;
}

type StreamHandlers = {
  onStart: (session: InternalSession) => void;
  createRequest: (signal: AbortSignal) => Promise<Response>;
  doneLabel: string;
  /** When stream ends on phase=deploy, mark done (repair) instead of leaving spinner. */
  completeDeployPhase?: boolean;
};

function formatApiError(raw: string, status: number): string {
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      const parts = parsed.detail.map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          const row = item as { loc?: unknown[]; msg?: string; type?: string };
          const field = Array.isArray(row.loc) ? row.loc.filter((x) => x !== "body").join(".") : "";
          const msg = row.msg || "Ошибка валидации";
          if (row.type === "string_too_long" || /at most \d+ characters/i.test(msg)) {
            return field
              ? `Сообщение слишком длинное (${field}). Вставьте лог короче или используйте «Проверить и исправить» на странице логов.`
              : "Сообщение слишком длинное для отправки.";
          }
          return field ? `${field}: ${msg}` : msg;
        }
        return String(item);
      });
      return parts.filter(Boolean).join("; ") || `Ошибка запроса (код ${status})`;
    }
  } catch {
    // not JSON
  }
  return raw || `Ошибка запроса (код ${status})`;
}

async function runStreamLoop(projectId: string, chatId: string, handlers: StreamHandlers) {
  const session = ensureSession(projectId, chatId);
  if (session.loading) return;

  session.controller?.abort();
  const controller = new AbortController();
  session.controller = controller;
  session.isLeader = true;
  session.loading = true;
  session.chatError = "";
  session.toolActivity = [];
  session.toolActivityId = 0;
  handlers.onStart(session);
  writePersistedStatus(projectId, chatId, session.agentStatus);

  // This tab owns the fetch below - every state change also goes out to any other tab with the
  // same chat open (see the cross-tab sync section above snapshotOf/broadcastState).
  const syncSession = () => {
    notify(session);
    broadcastState(projectId, chatId, session);
  };
  syncSession();

  const applyStatus = (status: AgentStatus) => {
    // A "tool" phase frame with state done/error is one finished tool call (e.g. a shell
    // command that happened to exit non-zero) - normal mid-turn agent activity, logged in the
    // activity feed below, but never the reason the whole request "failed". Only a tool
    // *request* (state running) should become the sticky top-level headline; a per-call
    // result must not overwrite it with e.g. "⚠ exit 1: ..." styled as a fatal turn error.
    const isToolResult = status.phase === "tool" && status.state !== "running";
    if (!isToolResult) {
      session.agentStatus = status;
      writePersistedStatus(projectId, chatId, status);
    }
    if (status.phase === "tool") {
      session.toolActivityId += 1;
      session.toolActivity = [
        ...session.toolActivity.slice(-49),
        {
          id: session.toolActivityId,
          label: status.label,
          state: status.state === "error" ? "error" : status.state === "done" ? "done" : "running",
        },
      ];
    }
    syncSession();
  };

  const appendAssistant = (chunk: string) => {
    if (!session.messages?.length) return;
    const copy = [...session.messages];
    const lastIndex = copy.length - 1;
    const last = copy[lastIndex];
    if (last?.role !== "assistant") return;
    copy[lastIndex] = { ...last, content: last.content + chunk };
    session.messages = copy;
    syncSession();
  };

  try {
    const response = await handlers.createRequest(controller.signal);
    if (!response.ok) {
      const raw = await response.text();
      throw new Error(formatApiError(raw, response.status));
    }
    if (!response.body) throw new Error("Пустой ответ сервера");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let partial = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      partial += decoder.decode(value, { stream: true });
      const lines = partial.split("\n\n");
      partial = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.replace("data: ", "");
        if (payload === "[DONE]") {
          const latest = session.agentStatus;
          if (latest && latest.state !== "running") continue;
          if (latest?.phase === "deploy") {
            if (handlers.completeDeployPhase) {
              applyStatus({
                phase: "done",
                label: latest.label || "Повторный запуск в очереди",
                state: "done",
              });
            }
            continue;
          }
          applyStatus({
            phase: "done",
            label: handlers.doneLabel,
            state: "done",
          });
          continue;
        }
        const parsed = JSON.parse(payload) as { chunk?: string; status?: AgentStatus };
        if (parsed.status) applyStatus(parsed.status);
        if (parsed.chunk) appendAssistant(parsed.chunk);
      }
    }
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === "AbortError";
    if (aborted) {
      applyStatus({ phase: "done", label: "Остановлено пользователем", state: "done" });
      if (session.messages?.length) {
        const last = session.messages[session.messages.length - 1];
        if (last?.role === "assistant" && !last.content) {
          session.messages = session.messages.slice(0, -1);
        }
      }
    } else {
      const message = err instanceof Error ? err.message : "Не удалось получить ответ агента";
      session.chatError = message;
      applyStatus({ phase: "error", label: "Не удалось получить ответ агента", state: "error" });
      if (session.messages?.length) {
        const copy = [...session.messages];
        const lastIndex = copy.length - 1;
        const last = copy[lastIndex];
        if (last?.role === "assistant") {
          copy[lastIndex] = { ...last, content: message };
          session.messages = copy;
        }
      }
    }
    syncSession();
  } finally {
    if (session.controller === controller) {
      session.controller = null;
    }
    session.isLeader = false;
    session.loading = false;
    syncSession();
  }
}

export async function startChatTurn(options: {
  projectId: string;
  chatId: string;
  userMessage: string;
  attachments: ChatFileAttachment[];
  displayUserContent: string;
  createMessage: () => Promise<void>;
  streamRequest: (signal: AbortSignal) => Promise<Response>;
  seedMessages: ChatMessage[];
}) {
  const { projectId, chatId } = options;
  await runStreamLoop(projectId, chatId, {
    doneLabel: "Изменения сохранены",
    onStart: (session) => {
      session.agentStatus = {
        phase: "thinking",
        label: "AIRuntime анализирует задачу",
        state: "running",
      };
      session.messages = [
        ...options.seedMessages,
        {
          role: "user",
          content: options.displayUserContent,
          attachments: options.attachments,
        },
        { role: "assistant", content: "" },
      ];
    },
    createRequest: async (signal) => {
      await options.createMessage();
      return options.streamRequest(signal);
    },
  });
}

export async function startRepairTurn(options: {
  projectId: string;
  chatId: string;
  userNote: string;
  seedMessages: ChatMessage[];
  streamRequest: (signal: AbortSignal) => Promise<Response>;
}) {
  const { projectId, chatId } = options;
  await runStreamLoop(projectId, chatId, {
    doneLabel: "Проверка завершена",
    completeDeployPhase: true,
    onStart: (session) => {
      session.agentStatus = {
        phase: "thinking",
        label: "Проверяю последний деплой",
        state: "running",
      };
      session.messages = [
        ...options.seedMessages,
        { role: "user", content: options.userNote },
        { role: "assistant", content: "" },
      ];
    },
    createRequest: options.streamRequest,
  });
}

/** Pending repair handoff from logs/deployments → chat (?repair=1). */
const REPAIR_PENDING_PREFIX = "airuntime_pending_repair:";

export function stashPendingRepair(projectId: string, errorLog: string) {
  if (typeof window === "undefined" || !projectId) return;
  sessionStorage.setItem(
    `${REPAIR_PENDING_PREFIX}${projectId}`,
    JSON.stringify({ errorLog, at: Date.now() })
  );
}

export function takePendingRepair(projectId: string): string | null {
  if (typeof window === "undefined" || !projectId) return null;
  const key = `${REPAIR_PENDING_PREFIX}${projectId}`;
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    sessionStorage.removeItem(key);
    const parsed = JSON.parse(raw) as { errorLog?: string };
    return typeof parsed.errorLog === "string" ? parsed.errorLog : "";
  } catch {
    sessionStorage.removeItem(key);
    return null;
  }
}

export function peekPendingRepair(projectId: string): boolean {
  if (typeof window === "undefined" || !projectId) return false;
  return Boolean(sessionStorage.getItem(`${REPAIR_PENDING_PREFIX}${projectId}`));
}

export function getActiveProjectChatStream(projectId: string): ChatStreamSnapshot | null {
  if (!projectId) return null;
  for (const session of sessions.values()) {
    if (session.projectId === projectId && (session.loading || session.agentStatus?.state === "running")) {
      return snapshotOf(session);
    }
  }
  return null;
}
