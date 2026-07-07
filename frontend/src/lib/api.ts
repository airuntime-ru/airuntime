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
  git_history: string;
};

export type DeploymentType = {
  id: string;
  project_id: string;
  status: string;
  image_ref: string | null;
  container_id: string | null;
  logs_ref: string | null;
};

export type MeType = {
  id: string;
  email: string;
  is_verified: boolean;
  credits_balance: number;
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

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await rawRequest(path, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
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

export async function listProjects(): Promise<ProjectType[]> {
  return requestJson<ProjectType[]>("/projects");
}

export async function getProject(projectId: string): Promise<ProjectType> {
  return requestJson<ProjectType>(`/projects/${projectId}`);
}

export async function createProject(payload: {
  type: "telegram_bot" | "website";
  name: string;
  description: string;
}): Promise<ProjectType> {
  return requestJson<ProjectType>("/projects", {
    method: "POST",
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
  attachmentIds: string[] = []
): Promise<Response> {
  return rawRequest(`/projects/${projectId}/chats/${chatId}/stream`, {
    method: "POST",
    body: JSON.stringify({ content, attachment_ids: attachmentIds }),
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

export type SecretType = { id: string; key: string; created_at: string };

export async function listSecrets(projectId: string): Promise<SecretType[]> {
  return requestJson<SecretType[]>(`/projects/${projectId}/secrets`);
}

export async function createSecret(projectId: string, key: string, value: string): Promise<void> {
  await requestJson(`/projects/${projectId}/secrets`, {
    method: "POST",
    body: JSON.stringify({ key, value }),
  });
}

export async function deleteSecret(projectId: string, secretId: string): Promise<void> {
  await requestJson(`/projects/${projectId}/secrets/${secretId}`, { method: "DELETE" });
}

export async function listDeployments(projectId: string): Promise<DeploymentType[]> {
  return requestJson<DeploymentType[]>(`/projects/${projectId}/deployments`);
}

export async function createDeployment(projectId: string): Promise<DeploymentType> {
  return requestJson<DeploymentType>(`/projects/${projectId}/deployments`, { method: "POST" });
}

export async function getMe(): Promise<MeType> {
  return requestJson<MeType>("/auth/me");
}

export async function getProviders(): Promise<ProvidersType> {
  return requestJson<ProvidersType>("/providers");
}
