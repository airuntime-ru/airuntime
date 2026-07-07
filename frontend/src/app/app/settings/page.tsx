"use client";

import { CheckCircle2, RefreshCw, ServerCog, XCircle } from "lucide-react";
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
    <div className="mx-auto max-w-6xl space-y-5" data-tour="settings-screen">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">Система</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">
            Настройки
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--ar-mist)]">
            Проверьте домен и состояние провайдеров, которые используются для сборки проектов.
          </p>
        </div>
        <Button variant="outline" onClick={loadProviders}>
          <RefreshCw size={16} />
          Обновить
        </Button>
      </div>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      <Card className="space-y-5" hover={false}>
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-[var(--ar-radius-sm)] bg-sky-50 text-[var(--ar-sky)]">
            <ServerCog size={20} />
          </span>
          <div>
            <p className="text-sm text-[var(--ar-stone)]">Базовый домен</p>
            <p className="mt-1 font-semibold text-[var(--ar-black)]">{baseDomain}</p>
          </div>
        </div>
        {providers ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-[var(--ar-radius-sm)] border border-[var(--ar-border)] bg-white/70 p-4">
              <p className="text-sm text-[var(--ar-stone)]">Активный провайдер</p>
              <p className="mt-1 font-semibold text-[var(--ar-black)]">{providers.active}</p>
            </div>
            {providers.supported.map((provider) => {
              const configured = providers.configured[provider];
              return (
                <div key={provider} className="rounded-[var(--ar-radius-sm)] border border-[var(--ar-border)] bg-white/70 p-4">
                  <p className="font-medium text-[var(--ar-black)]">{provider}</p>
                  <p className="mt-1 inline-flex items-center gap-1.5 text-sm text-[var(--ar-mist)]">
                    {configured ? (
                      <CheckCircle2 size={15} className="text-emerald-500" />
                    ) : (
                      <XCircle size={15} className="text-amber-500" />
                    )}
                    {configured ? "Настроен" : "Ключ не задан"}
                  </p>
                </div>
              );
            })}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
