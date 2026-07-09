"use client";

import { useCallback, useEffect, useState } from "react";
import { KeyRound, ShieldCheck, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/loader";
import { Input } from "@/components/ui/input";
import { createSecret, deleteSecret, listSecrets, type SecretType } from "@/lib/api";

export function ProjectSecretsSection({ projectId }: { projectId: string }) {
  const [secrets, setSecrets] = useState<SecretType[]>([]);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setSecrets(await listSecrets(projectId));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить секреты");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  const onCreate = async () => {
    if (!key.trim() || !value.trim()) return;
    setSaving(true);
    setError("");
    try {
      await createSecret(projectId, key.trim().toUpperCase(), value);
      setKey("");
      setValue("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить секрет");
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (secretId: string) => {
    setError("");
    try {
      await deleteSecret(projectId, secretId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить секрет");
    }
  };

  return (
    <Card hover={false} className="md:col-span-2" id="secrets">
      <div className="space-y-4">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--ar-radius-sm)] bg-white/80 text-[var(--ar-sky)] shadow-sm shadow-sky-950/5">
            <ShieldCheck size={18} />
          </span>
          <div>
            <p className="text-sm font-semibold text-[var(--ar-black)]">Защищенный контур</p>
            <p className="mt-1 text-sm leading-7 text-[var(--ar-mist)]">
              API-ключи и токены хранятся зашифрованно и доступны только при сборке и запуске проекта.
            </p>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <Input
            placeholder="Ключ, например TELEGRAM_BOT_TOKEN"
            value={key}
            onChange={(event) => setKey(event.target.value.toUpperCase())}
            autoComplete="off"
            spellCheck={false}
          />
          <Input
            placeholder="Значение"
            type="password"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            autoComplete="off"
          />
          <Button variant="accent" className="w-full md:w-auto" onClick={() => void onCreate()} disabled={saving || !key || !value}>
            <KeyRound size={16} />
            {saving ? "Сохраняем..." : "Добавить"}
          </Button>
        </div>

        <div className="rounded-[var(--ar-radius-sm)] border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm leading-6 text-amber-900">
          Для Telegram-бота добавьте секрет{" "}
          <button
            type="button"
            className="font-semibold underline underline-offset-2"
            onClick={() => setKey("TELEGRAM_BOT_TOKEN")}
          >
            TELEGRAM_BOT_TOKEN
          </button>
          . Токен выдаёт{" "}
          <a
            href="/help/telegram-token"
            className="font-semibold underline underline-offset-2"
          >
            инструкция
          </a>
          : откройте его в Telegram, выполните /newbot и вставьте полученный token сюда.
        </div>

        {error ? <p className="text-sm text-rose-600">{error}</p> : null}

        {loading ? (
          <p className="text-sm text-[var(--ar-stone)]">Загрузка...</p>
        ) : secrets.length === 0 ? (
          <EmptyState
            title="Секретов пока нет"
            description="Добавьте токены и ключи, если проекту нужен внешний сервис, Telegram или платежи."
          />
        ) : (
          <div className="grid gap-2">
            {secrets.map((secret) => (
              <div
                key={secret.id}
                className="flex flex-col gap-3 rounded-[var(--ar-radius-sm)] border border-white/70 bg-white/64 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-medium text-[var(--ar-black)]">{secret.key}</p>
                  <p className="text-xs text-[var(--ar-stone)]">Значение скрыто</p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => void onDelete(secret.id)}>
                  <Trash2 size={15} />
                  Удалить
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
