"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ChevronLeft, ChevronRight, CreditCard, History, Layers, Sparkles, UserRound, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import { Modal } from "@/components/ui/modal";
import {
  type BillingSummaryType,
  type CreditLedgerEntryType,
  type CreditTopUpType,
  type LedgerDirection,
  type PlanType,
  createTopUp,
  getBillingSummary,
  getUsageHistory,
  listPlans,
  listTopUps,
  switchPlan,
} from "@/lib/api";
import { useProfile } from "@/lib/use-profile";

const TOPUP_PRESETS = [10_000, 50_000, 200_000];
const LEDGER_PAGE_SIZE = 10;

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ru-RU", { day: "2-digit", month: "long", year: "numeric" });
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const LEDGER_REASON_LABEL: Record<CreditLedgerEntryType["reason"], string> = {
  chat_message: "Сообщение в чате",
  topup: "Пополнение баланса",
  period_renewal: "Обновление тарифного периода",
  plan_change: "Смена тарифа",
};

const LEDGER_DIRECTION_OPTIONS: { value: LedgerDirection; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "debit", label: "Списания" },
  { value: "credit", label: "Начисления" },
];

function ledgerTitle(entry: CreditLedgerEntryType): string {
  if (entry.project_name) return entry.project_name;
  return LEDGER_REASON_LABEL[entry.reason] ?? entry.reason;
}

function ledgerSubtitle(entry: CreditLedgerEntryType): string {
  const reason = LEDGER_REASON_LABEL[entry.reason] ?? entry.reason;
  if (entry.project_name && entry.reason === "chat_message") {
    return `${reason} · ${formatDateTime(entry.created_at)}`;
  }
  return formatDateTime(entry.created_at);
}

// "до N проектов": genitive case throughout, so only the "N=1" form differs ("до 1 проекта" vs "до 5 проектов").
function pluralizeProjects(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  return mod10 === 1 && mod100 !== 11 ? "проекта" : "проектов";
}

const TOPUP_STATUS_LABEL: Record<CreditTopUpType["status"], string> = {
  pending: "Ожидает оплаты",
  paid: "Оплачен",
  cancelled: "Отменён",
};

export default function ProfilePage() {
  const { profile, error, loading } = useProfile();
  const [billing, setBilling] = useState<BillingSummaryType | null>(null);
  const [topups, setTopups] = useState<CreditTopUpType[]>([]);
  const [usage, setUsage] = useState<CreditLedgerEntryType[]>([]);
  const [usageTotal, setUsageTotal] = useState(0);
  const [usagePage, setUsagePage] = useState(0);
  const [usageDirection, setUsageDirection] = useState<LedgerDirection>("all");
  const [usageLoading, setUsageLoading] = useState(false);
  const [plans, setPlans] = useState<PlanType[]>([]);
  const [topupOpen, setTopupOpen] = useState(false);
  const [topupCredits, setTopupCredits] = useState(TOPUP_PRESETS[0]);
  const [topupBusy, setTopupBusy] = useState(false);
  const [topupError, setTopupError] = useState<string | null>(null);
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [confirmPlan, setConfirmPlan] = useState<PlanType | null>(null);
  const [planBusy, setPlanBusy] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);

  const loadUsage = useCallback(async (page: number, direction: LedgerDirection) => {
    setUsageLoading(true);
    try {
      const usagePageResult = await getUsageHistory(LEDGER_PAGE_SIZE, page * LEDGER_PAGE_SIZE, direction);
      setUsage(usagePageResult.items);
      setUsageTotal(usagePageResult.total);
    } finally {
      setUsageLoading(false);
    }
  }, []);

  const loadBilling = useCallback(async () => {
    const [summary, invoices, planRows] = await Promise.all([
      getBillingSummary(),
      listTopUps(),
      listPlans(),
    ]);
    setBilling(summary);
    setTopups(invoices);
    setPlans(planRows);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadBilling();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadBilling]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadUsage(usagePage, usageDirection);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [usagePage, usageDirection, loadUsage]);

  const usagePageCount = Math.max(1, Math.ceil(usageTotal / LEDGER_PAGE_SIZE));

  const onDirectionChange = (direction: LedgerDirection) => {
    setUsageDirection(direction);
    setUsagePage(0);
  };

  const onRequestTopup = async () => {
    setTopupBusy(true);
    setTopupError(null);
    try {
      await createTopUp(topupCredits);
      setUsagePage(0);
      await loadBilling();
      await loadUsage(0, usageDirection);
      setTopupOpen(false);
    } catch (err) {
      setTopupError(err instanceof Error ? err.message : "Не удалось создать счёт");
    } finally {
      setTopupBusy(false);
    }
  };

  const onConfirmPlanSwitch = async () => {
    if (!confirmPlan) return;
    setPlanBusy(true);
    setPlanError(null);
    try {
      await switchPlan(confirmPlan.id);
      setUsagePage(0);
      await loadBilling();
      await loadUsage(0, usageDirection);
      setConfirmPlan(null);
      setPlanModalOpen(false);
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : "Не удалось сменить тариф");
    } finally {
      setPlanBusy(false);
    }
  };

  const rubForCredits = (credits: number) => Math.max(1, Math.ceil((credits * 10) / 1000));

  if (loading) return <PageLoader />;

  return (
    <div className="space-y-5">
      <div>
        <p className="inline-flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">
          <Sparkles size={15} />
          Аккаунт
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-normal text-[var(--ar-black)] sm:text-5xl">Профиль</h1>
      </div>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {profile ? (
        <Card className="grid gap-4 sm:grid-cols-3" hover={false}>
          <div className="flex items-center gap-3 border-b border-white/60 pb-4 sm:col-span-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-[var(--ar-radius-sm)] bg-white/80 text-[var(--ar-sky)] shadow-sm shadow-sky-950/5">
              <UserRound size={20} />
            </span>
            <div className="min-w-0">
              <p className="truncate font-semibold text-[var(--ar-black)]">{profile.email}</p>
              <p className="text-sm text-[var(--ar-mist)]">Личный аккаунт AIRuntime</p>
            </div>
          </div>
          <div>
            <p className="text-sm text-[var(--ar-stone)]">Почта</p>
            <p className="mt-1 break-all font-medium text-[var(--ar-black)]">{profile.email}</p>
          </div>
          <div>
            <p className="text-sm text-[var(--ar-stone)]">Статус</p>
            <p className="mt-1 inline-flex items-center gap-1.5 font-medium text-[var(--ar-black)]">
              <CheckCircle2 size={16} className={profile.is_verified ? "text-emerald-500" : "text-[var(--ar-stone)]"} />
              {profile.is_verified ? "Подтверждена" : "Не подтверждена"}
            </p>
          </div>
          <div>
            <p className="text-sm text-[var(--ar-stone)]">Кредиты</p>
            <p className="mt-1 font-semibold tabular-nums text-[var(--ar-black)]">
              {profile.credits_balance.toLocaleString()}
            </p>
          </div>
        </Card>
      ) : null}

      {billing ? (
        <Card className="space-y-4" hover={false}>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/60 pb-4">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-[var(--ar-radius-sm)] bg-white/80 text-[var(--ar-sky)] shadow-sm shadow-sky-950/5">
                <Zap size={20} />
              </span>
              <div>
                <p className="font-semibold text-[var(--ar-black)]">
                  Тариф «{billing.plan?.name ?? "не назначен"}»
                </p>
                <p className="text-sm text-[var(--ar-mist)]">
                  {billing.plan
                    ? `${billing.plan.monthly_credits.toLocaleString()} кредитов в месяц · до ${billing.plan.max_concurrent_projects} ${pluralizeProjects(billing.plan.max_concurrent_projects)} одновременно`
                    : "Обратитесь в поддержку, чтобы подключить тариф"}
                </p>
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button variant="outline" onClick={() => setPlanModalOpen(true)}>
                <Layers size={15} />
                Сменить тариф
              </Button>
              <Button variant="accent" onClick={() => setTopupOpen(true)}>
                <CreditCard size={15} />
                Пополнить баланс
              </Button>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-sm text-[var(--ar-stone)]">Баланс кредитов</p>
              <p className="mt-1 font-semibold tabular-nums text-[var(--ar-black)]">
                {billing.credits_balance.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-sm text-[var(--ar-stone)]">Период начался</p>
              <p className="mt-1 font-medium text-[var(--ar-black)]">{formatDate(billing.billing_period_start)}</p>
            </div>
            <div>
              <p className="text-sm text-[var(--ar-stone)]">Обновление тарифа</p>
              <p className="mt-1 font-medium text-[var(--ar-black)]">{formatDate(billing.billing_period_end)}</p>
            </div>
          </div>

          {topups.length > 0 ? (
            <div className="border-t border-white/60 pt-4">
              <p className="mb-2 text-sm text-[var(--ar-stone)]">Счета на пополнение</p>
              <div className="space-y-2">
                {topups.map((invoice) => (
                  <div
                    key={invoice.id}
                    className="flex items-center justify-between rounded-[var(--ar-radius-sm)] border border-black/5 bg-white/60 px-3 py-2 text-sm"
                  >
                    <span className="font-medium text-[var(--ar-black)]">
                      {invoice.credits.toLocaleString()} кредитов · {invoice.amount_rub} ₽
                    </span>
                    <Badge>{TOPUP_STATUS_LABEL[invoice.status]}</Badge>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="border-t border-white/60 pt-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <p className="flex items-center gap-1.5 text-sm text-[var(--ar-stone)]">
                <History size={14} />
                История списаний и начислений
              </p>
              <div className="flex flex-wrap gap-1">
                {LEDGER_DIRECTION_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => onDirectionChange(option.value)}
                    className={`rounded-[var(--ar-radius-sm)] border px-2.5 py-1 text-xs font-medium transition ${
                      usageDirection === option.value
                        ? "border-[var(--ar-sky)] bg-[var(--ar-sky)]/10 text-[var(--ar-sky)]"
                        : "border-black/10 text-[var(--ar-mist)] hover:border-black/20 hover:text-[var(--ar-black)]"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
            {usage.length > 0 ? (
              <div className={`space-y-2 ${usageLoading ? "opacity-60" : ""}`}>
                {usage.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-center justify-between rounded-[var(--ar-radius-sm)] border border-black/5 bg-white/60 px-3 py-2 text-sm"
                  >
                    <div className="min-w-0 pr-3">
                      <p className="truncate font-medium text-[var(--ar-black)]">{ledgerTitle(entry)}</p>
                      <p className="text-xs text-[var(--ar-stone)]">{ledgerSubtitle(entry)}</p>
                    </div>
                    <span
                      className={`shrink-0 font-semibold tabular-nums ${entry.amount >= 0 ? "text-emerald-600" : "text-[var(--ar-black)]"}`}
                    >
                      {entry.amount >= 0 ? "+" : ""}
                      {entry.amount.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--ar-mist)]">
                {usageLoading ? "Загружаем историю…" : "Пока нет записей по выбранному фильтру"}
              </p>
            )}
            {usageTotal > LEDGER_PAGE_SIZE ? (
              <div className="mt-3 flex items-center justify-center gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={usagePage <= 0 || usageLoading}
                  onClick={() => setUsagePage((page) => Math.max(0, page - 1))}
                >
                  <ChevronLeft size={15} />
                  Назад
                </Button>
                <span className="text-xs tabular-nums text-[var(--ar-stone)]">
                  {usagePage + 1} / {usagePageCount}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={usagePage >= usagePageCount - 1 || usageLoading}
                  onClick={() => setUsagePage((page) => Math.min(usagePageCount - 1, page + 1))}
                >
                  Вперёд
                  <ChevronRight size={15} />
                </Button>
              </div>
            ) : null}
          </div>
        </Card>
      ) : null}

      <Modal
        open={topupOpen}
        onClose={() => setTopupOpen(false)}
        title="Пополнить баланс"
        description="Выберите объём кредитов. После создания счёта администратор подтвердит оплату вручную и кредиты зачислятся автоматически."
      >
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-2">
            {TOPUP_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => setTopupCredits(preset)}
                className={`rounded-[var(--ar-radius-sm)] border px-3 py-2 text-sm font-medium transition ${
                  topupCredits === preset
                    ? "border-[var(--ar-sky)] bg-[var(--ar-sky)]/10 text-[var(--ar-sky)]"
                    : "border-black/10 text-[var(--ar-black)] hover:border-black/20"
                }`}
              >
                {preset.toLocaleString()}
              </button>
            ))}
          </div>
          <p className="text-sm text-[var(--ar-mist)]">
            Стоимость: <span className="font-semibold text-[var(--ar-black)]">{rubForCredits(topupCredits)} ₽</span>
          </p>
          {topupError ? <p className="text-sm text-rose-600">{topupError}</p> : null}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="ghost" onClick={() => setTopupOpen(false)} disabled={topupBusy}>
              Отмена
            </Button>
            <Button variant="accent" onClick={() => void onRequestTopup()} disabled={topupBusy}>
              {topupBusy ? "Создаём счёт…" : "Создать счёт"}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={planModalOpen}
        onClose={() => setPlanModalOpen(false)}
        title="Выберите тариф"
        description="Смена тарифа сразу обновляет баланс до месячного лимита нового тарифа и начинает новый период."
      >
        <div className="space-y-2">
          {plans.map((plan) => {
            const isCurrent = billing?.plan?.id === plan.id;
            return (
              <button
                key={plan.id}
                type="button"
                disabled={isCurrent}
                onClick={() => setConfirmPlan(plan)}
                className={`w-full rounded-[var(--ar-radius-sm)] border p-3 text-left transition ${
                  isCurrent
                    ? "cursor-default border-[var(--ar-sky)]/40 bg-[var(--ar-sky)]/5"
                    : "border-black/10 hover:border-black/20"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold text-[var(--ar-black)]">
                    {plan.name}
                    {isCurrent ? <span className="ml-2 text-xs font-normal text-[var(--ar-sky)]">текущий</span> : null}
                  </p>
                  <p className="font-semibold tabular-nums text-[var(--ar-black)]">
                    {plan.price_rub > 0 ? `${plan.price_rub} ₽/мес` : "Бесплатно"}
                  </p>
                </div>
                <p className="mt-1 text-sm text-[var(--ar-mist)]">
                  {plan.monthly_credits.toLocaleString()} кредитов в месяц · до {plan.max_concurrent_projects}{" "}
                  {pluralizeProjects(plan.max_concurrent_projects)} одновременно
                </p>
              </button>
            );
          })}
        </div>
      </Modal>

      <Modal
        open={Boolean(confirmPlan)}
        onClose={() => setConfirmPlan(null)}
        title="Сменить тариф?"
        description={
          confirmPlan
            ? `Тариф изменится на «${confirmPlan.name}». Баланс сразу станет ${confirmPlan.monthly_credits.toLocaleString()} кредитов, текущий тарифный период начнётся заново.`
            : undefined
        }
      >
        <div className="space-y-4">
          {planError ? <p className="text-sm text-rose-600">{planError}</p> : null}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="ghost" onClick={() => setConfirmPlan(null)} disabled={planBusy}>
              Отмена
            </Button>
            <Button variant="accent" onClick={() => void onConfirmPlanSwitch()} disabled={planBusy}>
              {planBusy ? "Меняем тариф…" : "Да, сменить тариф"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
