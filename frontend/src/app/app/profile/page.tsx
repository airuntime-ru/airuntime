"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, CreditCard, Sparkles, UserRound, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import { Modal } from "@/components/ui/modal";
import {
  type BillingSummaryType,
  type CreditTopUpType,
  createTopUp,
  getBillingSummary,
  listTopUps,
} from "@/lib/api";
import { useProfile } from "@/lib/use-profile";

const TOPUP_PRESETS = [10_000, 50_000, 200_000];

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ru-RU", { day: "2-digit", month: "long", year: "numeric" });
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
  const [topupOpen, setTopupOpen] = useState(false);
  const [topupCredits, setTopupCredits] = useState(TOPUP_PRESETS[0]);
  const [topupBusy, setTopupBusy] = useState(false);
  const [topupError, setTopupError] = useState<string | null>(null);

  const loadBilling = async () => {
    const [summary, invoices] = await Promise.all([getBillingSummary(), listTopUps()]);
    setBilling(summary);
    setTopups(invoices);
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadBilling();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const onRequestTopup = async () => {
    setTopupBusy(true);
    setTopupError(null);
    try {
      await createTopUp(topupCredits);
      await loadBilling();
      setTopupOpen(false);
    } catch (err) {
      setTopupError(err instanceof Error ? err.message : "Не удалось создать счёт");
    } finally {
      setTopupBusy(false);
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
            <Button variant="accent" onClick={() => setTopupOpen(true)}>
              <CreditCard size={15} />
              Пополнить баланс
            </Button>
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
    </div>
  );
}
