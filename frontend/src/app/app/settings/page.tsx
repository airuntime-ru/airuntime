"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import { getProviders, type ProvidersType } from "@/lib/api";

export default function SettingsPage() {
  const [providers, setProviders] = useState<ProvidersType | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadProviders = async () => {
    setLoading(true);
    try {
      setProviders(await getProviders());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить настройки провайдеров");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    void (async () => {
      setLoading(true);
      try {
        const row = await getProviders();
        if (!active) return;
        setProviders(row);
        setError("");
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Не удалось загрузить настройки провайдеров");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (loading) return <PageLoader />;

  const baseDomain = process.env.NEXT_PUBLIC_BASE_DOMAIN ?? "localhost";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-[var(--ar-cloud)] sm:text-3xl">Настройки</h1>
        <Button variant="ghost" onClick={loadProviders}>
          Обновить
        </Button>
      </div>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      <Card className="space-y-2" hover={false}>
        <p className="text-[var(--ar-mist)]">Базовый домен: {baseDomain}</p>
        {providers ? (
          <>
            <p className="text-[var(--ar-mist)]">Активный провайдер: {providers.active}</p>
            {providers.supported.map((provider) => (
              <p key={provider} className="text-sm text-[var(--ar-stone)]">
                {provider}: {providers.configured[provider] ? "настроен" : "ключ не задан"}
              </p>
            ))}
          </>
        ) : null}
      </Card>
    </div>
  );
}
