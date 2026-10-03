export const CREDIT_BALANCE_CHANGED_EVENT = "airuntime:credit-balance-changed";

/** Ask the cabinet to reload the authoritative balance after billable work or payment. */
export function notifyCreditBalanceChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(CREDIT_BALANCE_CHANGED_EVENT));
  }
}
