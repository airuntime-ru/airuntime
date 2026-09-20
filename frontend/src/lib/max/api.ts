/**
 * Mini app API client.
 *
 * Authentication is the MAX launch string and nothing else: no JWT, no cookie, no user id
 * in a body. Every call carries `X-Max-Init-Data`, the backend verifies its signature
 * against the bot token, and whatever user it resolves to is the user the request is for.
 */

import { getInitData } from "@/lib/max/bridge";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type ServiceItem = {
  title: string;
  description: string;
  price_rub: number | null;
  duration_min: number | null;
};

export type ServiceConfig = {
  kind: "booking" | "menu" | "landing";
  title: string;
  tagline: string;
  about: string;
  accent: string;
  contacts: { phone: string; address: string; hours: string };
  items: ServiceItem[];
  slots: string[];
  cta_label: string;
  success_message: string;
  ask_phone: boolean;
  ask_comment: boolean;
};

export type ServiceResponse = {
  slug: string;
  status: string;
  config: ServiceConfig;
};

export type OwnerService = ServiceResponse & {
  link: string;
  new_leads: number;
};

export type OwnerOverview = {
  owner: { name: string; username: string } | null;
  services: OwnerService[];
};

export type Lead = {
  id: string;
  service_title: string;
  service_slug: string;
  customer_name: string;
  phone: string | null;
  item_title: string;
  slot_label: string;
  comment: string;
  status: "new" | "confirmed" | "declined" | "done";
  created_at: string | null;
};

export class MaxApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "MaxApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const initData = getInitData();
  if (!initData) {
    throw new MaxApiError("Откройте страницу внутри MAX", 401);
  }

  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Max-Init-Data": initData,
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    // A dropped connection inside a messenger webview is common enough that it deserves
    // its own wording rather than a generic failure.
    throw new MaxApiError("Нет связи с сервером", 0);
  }

  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : "";
    } catch {
      detail = "";
    }
    throw new MaxApiError(detail || `Ошибка ${response.status}`, response.status);
  }

  return (await response.json()) as T;
}

export function fetchService(slug: string): Promise<ServiceResponse> {
  return request<ServiceResponse>(`/max/miniapp/service/${encodeURIComponent(slug)}`);
}

export function fetchOwnerOverview(): Promise<OwnerOverview> {
  return request<OwnerOverview>("/max/miniapp/owner/overview");
}

export function fetchOwnerLeads(slug?: string): Promise<{ leads: Lead[] }> {
  const query = slug ? `?slug=${encodeURIComponent(slug)}` : "";
  return request<{ leads: Lead[] }>(`/max/miniapp/owner/leads${query}`);
}

export function setLeadStatus(leadId: string, status: Lead["status"]): Promise<Lead> {
  return request<Lead>(`/max/miniapp/owner/leads/${leadId}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export type CreateLeadInput = {
  slug: string;
  item_title?: string;
  slot_label?: string;
  customer_name?: string;
  phone?: string;
  comment?: string;
};

export function createLead(
  input: CreateLeadInput
): Promise<{ id: string; status: string; success_message: string }> {
  return request("/max/miniapp/lead", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
