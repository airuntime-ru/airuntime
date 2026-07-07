"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import { useProfile } from "@/lib/use-profile";

export default function ProfilePage() {
  const { profile, error, loading, refresh } = useProfile();

  if (loading) return <PageLoader />;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-[var(--ar-cloud)] sm:text-3xl">Профиль</h1>
        <Button variant="ghost" onClick={refresh}>
          Обновить
        </Button>
      </div>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      {profile ? (
        <Card className="space-y-2" hover={false}>
          <p>
            <span className="text-[var(--ar-stone)]">Почта:</span> {profile.email}
          </p>
          <p>
            <span className="text-[var(--ar-stone)]">Подтверждена:</span> {profile.is_verified ? "Да" : "Нет"}
          </p>
          <p>
            <span className="text-[var(--ar-stone)]">Кредиты:</span> {profile.credits_balance.toLocaleString()}
          </p>
        </Card>
      ) : null}
    </div>
  );
}
