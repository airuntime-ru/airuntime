/**
 * MAX Bridge wrapper.
 *
 * The SDK is a CDN script that attaches `window.WebApp`, so everything here has to cope
 * with three realities at once: the script may not have loaded yet, the page may be open
 * in a plain browser (during development, or when someone pastes the URL), and the client
 * may be an older MAX build without a given method. Every accessor therefore degrades to
 * a sane value rather than throwing - a storefront that blanks out because a brightness
 * API is missing would be worse than one that simply renders.
 */

export const MAX_BRIDGE_SRC = "https://st.max.ru/js/max-web-app.js";

export type MaxPlatform = "ios" | "android" | "desktop" | "web" | "unknown";

export type MaxUser = {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string | null;
  language_code?: string;
  photo_url?: string | null;
};

type MaxInitDataUnsafe = {
  user?: MaxUser;
  chat?: { id: number; type: "DIALOG" | "CHAT" | "CHANNEL" };
  start_param?: string;
  auth_date?: number;
};

type MaxContactResponse = { phone: string; authDate: string; hash: string };

type MaxWebApp = {
  initData?: string;
  initDataUnsafe?: MaxInitDataUnsafe;
  platform?: string;
  version?: string;
  getViewportSize?: () => Promise<{ height: string; width: string }>;
  getLaunchContext?: () => Promise<{ entryPoint: "tabbar" | "default" }>;
  requestContact?: () => Promise<MaxContactResponse>;
};

declare global {
  interface Window {
    WebApp?: MaxWebApp;
  }
}

function webApp(): MaxWebApp | null {
  if (typeof window === "undefined") return null;
  return window.WebApp ?? null;
}

/** Resolves once `window.WebApp` exists, or after `timeoutMs` if it never shows up. */
export function waitForBridge(timeoutMs = 4000): Promise<MaxWebApp | null> {
  if (typeof window === "undefined") return Promise.resolve(null);
  if (window.WebApp) return Promise.resolve(window.WebApp);

  return new Promise((resolve) => {
    const started = Date.now();
    const tick = () => {
      if (window.WebApp) {
        resolve(window.WebApp);
        return;
      }
      if (Date.now() - started >= timeoutMs) {
        resolve(null);
        return;
      }
      window.setTimeout(tick, 80);
    };
    tick();
  });
}

/** The signed launch string. Sent to the backend as-is; never parsed for identity here. */
export function getInitData(): string {
  return webApp()?.initData ?? "";
}

/** Display-only launch data. The backend re-derives all of this from the signed string. */
export function getInitDataUnsafe(): MaxInitDataUnsafe {
  return webApp()?.initDataUnsafe ?? {};
}

export function getPlatform(): MaxPlatform {
  const platform = webApp()?.platform;
  if (platform === "ios" || platform === "android" || platform === "desktop" || platform === "web") {
    return platform;
  }
  return "unknown";
}

export function isInsideMax(): boolean {
  return Boolean(webApp()?.initData);
}

/**
 * The slug of the storefront to show.
 *
 * `start_param` is what MAX fills from `?startapp=<slug>`; the query string is the
 * fallback that keeps the page testable in a browser and survives a client that opened
 * the URL directly.
 */
export function getStartParam(): string {
  const fromBridge = (getInitDataUnsafe().start_param ?? "").trim();
  if (fromBridge) return fromBridge;
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("startapp")?.trim() ?? "";
}

/** MAX reports its own usable height; on desktop the webview can be shorter than the page. */
export async function getViewportHeight(): Promise<number | null> {
  const app = webApp();
  if (!app?.getViewportSize) return null;
  try {
    const size = await app.getViewportSize();
    const height = Number.parseFloat(String(size.height));
    return Number.isFinite(height) && height > 0 ? height : null;
  } catch {
    return null;
  }
}

/** 'tabbar' when launched from the MAX tab bar rather than a chat. */
export async function getEntryPoint(): Promise<"tabbar" | "default"> {
  const app = webApp();
  if (!app?.getLaunchContext) return "default";
  try {
    const context = await app.getLaunchContext();
    return context.entryPoint === "tabbar" ? "tabbar" : "default";
  } catch {
    return "default";
  }
}

/**
 * Ask MAX for the user's phone number.
 *
 * Returns the platform's signed triple untouched: the backend re-checks the hash against
 * the bot token, so a number that never went through this dialog cannot be passed off as
 * a verified one.
 */
export async function requestContact(): Promise<MaxContactResponse | null> {
  const app = webApp();
  if (!app?.requestContact) return null;
  try {
    const contact = await app.requestContact();
    return contact?.phone ? contact : null;
  } catch {
    // The user declining is the common case, and it is not an error worth surfacing.
    return null;
  }
}
