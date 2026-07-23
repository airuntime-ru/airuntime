export type LandingEventName =
  | "hero_start_project"
  | "hero_view_process"
  | "use_case_selected"
  | "final_start_project"
  | "faq_opened";

type LandingEventPayload = Record<string, string | number | boolean | undefined>;

declare global {
  interface Window {
    dataLayer?: Array<Record<string, unknown>>;
  }
}

/** Lightweight landing analytics: CustomEvent + optional dataLayer if present. */
export function trackLandingEvent(name: LandingEventName, payload: LandingEventPayload = {}) {
  if (typeof window === "undefined") return;

  window.dispatchEvent(
    new CustomEvent("airuntime:landing", {
      detail: { name, ...payload },
    })
  );

  window.dataLayer?.push({ event: name, ...payload });
}
