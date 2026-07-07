"use client";

import { CheckCircle2, UserRound } from "lucide-react";

import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import { useProfile } from "@/lib/use-profile";

export default function ProfilePage() {
  const { profile, error, loading } = useProfile();

  if (loading) return <PageLoader />;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">Аккаунт</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">Профиль</h1>
      </div>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {profile ? (
        <Card className="grid gap-4 sm:grid-cols-3" hover={false}>
          <div className="sm:col-span-3 flex items-center gap-3 border-b border-[var(--ar-border)] pb-4">
            <span className="flex h-11 w-11 items-center justify-center rounded-[var(--ar-radius-sm)] bg-sky-50 text-[var(--ar-sky)]">
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
    </div>
  );
}
