import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "@/lib/auth";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type TokenResponse = {
  access_token: string;
  refresh_token: string;
};

export type ProjectType = {
  id: string;
  type: string;
  name: string;
  description: string;
  status: string;
  logs: string;
  deployment_url: string | null;
  deploy_subdomain: string | null;
  blocked_reason: string | null;
  planned_site_url: string | null;
  git_history: string;
};

export type DeploymentType = {
  id: string;
  project_id: string;
  status: string;
  image_ref: string | null;
  container_id: string | null;
  logs_ref: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type ProjectLogsType = {
  project_logs: string;
  deployment_logs: string;
  runtime_logs: string;
  runtime_error: string | null;
  deployment_status: string | null;
  container_id: string | null;
  logs_ref: string | null;
};

export type MeType = {
  id: string;
  email: string;
  is_verified: boolean;
  credits_balance: number;
  onboarding_completed: boolean;
};

export type ChatType = {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type MessageType = {
  id: string;
  role: string;
  content_markdown: string;
  created_at: string;
  attachments?: ChatFileType[];
};

export type ChatFileType = {
  id: string;
  project_id: string;
  chat_id: string;
  message_id: string | null;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  download_url: string | null;
  created_at: string;
};

export type ProvidersType = {
  active: string;
  supported: string[];
  configured: Record<string, boolean>;
};

export type ProjectRuntimeLimitsType = {
  running: number;
  max_running: number;
};

export type TelegramBotProfileType = {
  username: string;
  url: string;
  name: string;
  description: string;
  short_description: string;
};

async function rawRequest(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const token = getAccessToken();
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (response.status !== 401 || !retry) return response;

  const refreshed = await refreshSession();
  if (!refreshed) return response;
  return rawRequest(path, init, false);
}

async function parseErrorMessage(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
  } catch {
    // Response body is not JSON.
  }
  return text || `Request failed: ${response.status}`;
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await rawRequest(path, init);
  if (!response.ok) {
    throw new Error(await parseErrorMessage(response));
  }
  return (await response.json()) as T;
}

export async function requestAuthCode(email: string): Promise<void> {
  await requestJson<{ message: string }>("/auth/request-code", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function verifyAuthCode(email: string, code: string): Promise<void> {
  const data = await requestJson<TokenResponse>("/auth/verify-code", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
  setTokens(data.access_token, data.refresh_token);
}

/** @deprecated Password login is legacy; use requestAuthCode + verifyAuthCode */
export async function login(email: string, password: string): Promise<void> {
  const data = await requestJson<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setTokens(data.access_token, data.refresh_token);
}

export async function register(email: string, password: string): Promise<void> {
  const data = await requestJson<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setTokens(data.access_token, data.refresh_token);
}

export async function refreshSession(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  try {
    const data = await requestJson<TokenResponse>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken();
  try {
    if (refreshToken) {
      await rawRequest("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) }, false);
    }
  } finally {
    clearTokens();
  }
}

export type PagedResult<T> = {
  items: T[];
  total: number;
};

export type ProjectListResult = PagedResult<ProjectType> & { deployed_total: number };

export async function listProjects(limit = 20, offset = 0): Promise<ProjectListResult> {
  return requestJson<ProjectListResult>(`/projects?limit=${limit}&offset=${offset}`);
}

export async function getProjectRuntimeLimits(): Promise<ProjectRuntimeLimitsType> {
  return requestJson<ProjectRuntimeLimitsType>("/projects/runtime-limits");
}

export async function stopProject(projectId: string): Promise<ProjectType> {
  return requestJson<ProjectType>(`/projects/${projectId}/stop`, { method: "POST" });
}

export async function startProject(projectId: string): Promise<ProjectType> {
  return requestJson<ProjectType>(`/projects/${projectId}/start`, { method: "POST" });
}

export async function getProject(projectId: string): Promise<ProjectType> {
  return requestJson<ProjectType>(`/projects/${projectId}`);
}

export async function deleteProject(projectId: string): Promise<void> {
  await requestJson(`/projects/${projectId}`, { method: "DELETE" });
}

export async function getProjectLogs(projectId: string): Promise<ProjectLogsType> {
  return requestJson<ProjectLogsType>(`/projects/${projectId}/logs`);
}

export async function createProject(payload: {
  type?: "telegram_bot" | "website" | "mixed";
  name: string;
  description?: string;
}): Promise<ProjectType> {
  return requestJson<ProjectType>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateProject(
  projectId: string,
  payload: {
    name?: string;
    description?: string;
    deploy_subdomain?: string | null;
  }
): Promise<ProjectType> {
  return requestJson<ProjectType>(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function createChat(projectId: string): Promise<ChatType> {
  return requestJson<ChatType>(`/projects/${projectId}/chats`, { method: "POST" });
}

export async function listChats(projectId: string): Promise<ChatType[]> {
  return requestJson<ChatType[]>(`/projects/${projectId}/chats`);
}

export async function listMessages(projectId: string, chatId: string): Promise<MessageType[]> {
  return requestJson<MessageType[]>(`/projects/${projectId}/chats/${chatId}/messages`);
}

export async function createMessage(
  projectId: string,
  chatId: string,
  content: string,
  attachmentIds: string[] = []
): Promise<void> {
  await requestJson(`/projects/${projectId}/chats/${chatId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, attachment_ids: attachmentIds }),
  });
}

export function streamChat(
  projectId: string,
  chatId: string,
  content: string,
  attachmentIds: string[] = [],
  options: { provider?: string | null; model?: string | null; signal?: AbortSignal } = {}
): Promise<Response> {
  return rawRequest(`/projects/${projectId}/chats/${chatId}/stream`, {
    method: "POST",
    body: JSON.stringify({
      content,
      attachment_ids: attachmentIds,
      provider: options.provider || undefined,
      model: options.model || undefined,
    }),
    signal: options.signal,
  });
}

export async function uploadChatFile(projectId: string, chatId: string, file: File): Promise<ChatFileType> {
  const token = getAccessToken();
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${apiBase}/projects/${projectId}/chats/${chatId}/files`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Upload failed: ${response.status}`);
  }
  return (await response.json()) as ChatFileType;
}

export async function deleteChatFile(projectId: string, chatId: string, fileId: string): Promise<void> {
  await requestJson(`/projects/${projectId}/chats/${chatId}/files/${fileId}`, { method: "DELETE" });
}

export type SecretType = {
  id: string;
  key: string;
  reason: string | null;
  has_value: boolean;
  created_at: string;
};

export async function listSecrets(projectId: string): Promise<SecretType[]> {
  return requestJson<SecretType[]>(`/projects/${projectId}/secrets`);
}

export async function setSecretValue(
  projectId: string,
  secretId: string,
  value: string
): Promise<SecretType & { url?: string }> {
  return requestJson(`/projects/${projectId}/secrets/${secretId}`, {
    method: "PATCH",
    body: JSON.stringify({ value }),
  });
}

export async function getTelegramBotProfile(projectId: string): Promise<TelegramBotProfileType> {
  return requestJson<TelegramBotProfileType>(`/projects/${projectId}/telegram/profile`);
}

export async function updateTelegramBotProfile(
  projectId: string,
  payload: {
    name?: string;
    description?: string;
    short_description?: string;
  },
): Promise<TelegramBotProfileType> {
  return requestJson<TelegramBotProfileType>(`/projects/${projectId}/telegram/profile`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateTelegramBotAvatar(
  projectId: string,
  file: File,
): Promise<TelegramBotProfileType> {
  const token = getAccessToken();
  const form = new FormData();
  form.append("photo", file);
  const response = await fetch(`${apiBase}/projects/${projectId}/telegram/profile/photo`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Avatar upload failed: ${response.status}`);
  }
  return (await response.json()) as TelegramBotProfileType;
}

export async function listDeployments(
  projectId: string,
  limit = 20,
  offset = 0,
): Promise<PagedResult<DeploymentType>> {
  return requestJson<PagedResult<DeploymentType>>(
    `/projects/${projectId}/deployments?limit=${limit}&offset=${offset}`,
  );
}

export async function createDeployment(projectId: string): Promise<DeploymentType> {
  return requestJson<DeploymentType>(`/projects/${projectId}/deployments`, { method: "POST" });
}

export type DeploymentCheckResultType = {
  checked: boolean;
  found_errors: boolean;
  fixed: boolean;
  summary: string;
};

export async function checkDeployment(projectId: string): Promise<DeploymentCheckResultType> {
  return requestJson<DeploymentCheckResultType>(`/projects/${projectId}/check-deployment`, {
    method: "POST",
  });
}

export async function getMe(): Promise<MeType> {
  return requestJson<MeType>("/auth/me");
}

export async function completeOnboarding(): Promise<MeType> {
  return requestJson<MeType>("/auth/me/onboarding-complete", { method: "POST" });
}

export async function getProviders(): Promise<ProvidersType> {
  return requestJson<ProvidersType>("/providers");
}

export type ProjectVersionType = {
  commit_hash: string;
  created_at: string;
  message: string;
};

export async function listProjectVersions(projectId: string): Promise<ProjectVersionType[]> {
  return requestJson<ProjectVersionType[]>(`/projects/${projectId}/versions`);
}

export async function rollbackProjectVersion(
  projectId: string,
  commitHash: string,
): Promise<{ rollback_commit_hash: string; deployment: DeploymentType }> {
  return requestJson<{ rollback_commit_hash: string; deployment: DeploymentType }>(
    `/projects/${projectId}/versions/${commitHash}/rollback`,
    { method: "POST" },
  );
}

export async function downloadProjectVersionArchive(projectId: string, commitHash: string): Promise<Blob> {
  const token = getAccessToken();
  const response = await fetch(`${apiBase}/projects/${projectId}/versions/${commitHash}/archive`, {
    method: "GET",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Download failed: ${response.status}`);
  }
  return await response.blob();
}

export type ProjectVersionTreeEntryType = {
  name: string;
  entry_type: string;
  size_bytes?: number | null;
};

export async function listProjectVersionTree(
  projectId: string,
  commitHash: string,
  path: string,
): Promise<ProjectVersionTreeEntryType[]> {
  const token = getAccessToken();
  const url = new URL(
    `${apiBase}/projects/${projectId}/versions/${commitHash}/tree`,
  );
  url.searchParams.set("path", path);
  const response = await fetch(url.toString(), {
    method: "GET",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Tree load failed: ${response.status}`);
  }
  return (await response.json()) as ProjectVersionTreeEntryType[];
}

export type ProjectVersionFileType = {
  path: string;
  content: string;
  is_binary: boolean;
  truncated: boolean;
  size_bytes: number;
};

export async function getProjectVersionFile(
  projectId: string,
  commitHash: string,
  path: string,
): Promise<ProjectVersionFileType> {
  const token = getAccessToken();
  const url = new URL(
    `${apiBase}/projects/${projectId}/versions/${commitHash}/file`,
  );
  url.searchParams.set("path", path);
  const response = await fetch(url.toString(), {
    method: "GET",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `File load failed: ${response.status}`);
  }
  return (await response.json()) as ProjectVersionFileType;
}

export type PlanType = {
  id: string;
  key: string;
  name: string;
  description: string | null;
  monthly_credits: number;
  max_concurrent_projects: number;
  price_rub: number;
};

export type BillingSummaryType = {
  credits_balance: number;
  billing_period_start: string | null;
  billing_period_end: string | null;
  plan: PlanType | null;
};

export type CreditTopUpType = {
  id: string;
  credits: number;
  amount_rub: number;
  status: "pending" | "paid" | "cancelled";
  created_at: string;
  paid_at: string | null;
};

export async function listPlans(): Promise<PlanType[]> {
  return requestJson<PlanType[]>("/billing/plans");
}

export async function getBillingSummary(): Promise<BillingSummaryType> {
  return requestJson<BillingSummaryType>("/billing/me");
}

export async function createTopUp(credits: number): Promise<CreditTopUpType> {
  return requestJson<CreditTopUpType>("/billing/topups", {
    method: "POST",
    body: JSON.stringify({ credits }),
  });
}

export async function listTopUps(): Promise<CreditTopUpType[]> {
  return requestJson<CreditTopUpType[]>("/billing/topups");
}

export async function switchPlan(planId: string): Promise<BillingSummaryType> {
  return requestJson<BillingSummaryType>("/billing/plan", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId }),
  });
}

export type CreditLedgerEntryType = {
  id: string;
  amount: number;
  reason: "chat_message" | "topup" | "period_renewal" | "plan_change";
  project_id: string | null;
  created_at: string;
};

export async function getUsageHistory(): Promise<CreditLedgerEntryType[]> {
  return requestJson<CreditLedgerEntryType[]>("/billing/usage");
}
