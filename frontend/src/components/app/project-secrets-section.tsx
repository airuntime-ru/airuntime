"use client";

import { useEffect, useState } from "react";
import { KeyRound, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/loader";
import { Input } from "@/components/ui/input";
import { createSecret, deleteSecret, listSecrets, type SecretType } from "@/lib/api";

const commonKeys = ["TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY", "STRIPE_SECRET_KEY", "DATABASE_URL"];

export function ProjectSecretsSection({ projectId }: { projectId: string }) {
  const [secrets, setSecrets] = useState<SecretType[]>([]);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setLoading(true);
    try {
      setSecrets(await listSecrets(projectId));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить секреты");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [projectId]);

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
        <div>
          <p className="text-sm font-semibold text-[var(--ar-black)]">Секреты</p>
          <p className="mt-1 text-sm text-[var(--ar-mist)]">
            API-ключи и токены для проекта. Хранятся зашифрованно и не попадают в чат.
          </p>
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

        <div className="flex flex-wrap gap-2">
          {commonKeys.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setKey(item)}
              className="rounded-full border border-[var(--ar-border)] bg-white px-3 py-1 text-xs text-[var(--ar-mist)] hover:border-[var(--ar-border-strong)] hover:text-[var(--ar-black)]"
            >
              {item}
            </button>
          ))}
        </div>

        {error ? <p className="text-sm text-rose-600">{error}</p> : null}

        {loading ? (
          <p className="text-sm text-[var(--ar-stone)]">Загрузка...</p>
        ) : secrets.length === 0 ? (
          <EmptyState
            title="Секретов пока нет"
            description="Добавьте токены и ключи — они будут доступны при сборке и запуске проекта."
          />
        ) : (
          <div className="grid gap-2">
            {secrets.map((secret) => (
              <div
                key={secret.id}
                className="flex flex-col gap-3 rounded-[var(--ar-radius-sm)] border border-[var(--ar-border)] bg-white/70 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
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
