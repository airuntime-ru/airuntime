"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { KeyRound, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/loader";
import { Input } from "@/components/ui/input";
import { createSecret, deleteSecret, listSecrets, type SecretType } from "@/lib/api";

export default function ProjectSecretsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [secrets, setSecrets] = useState<SecretType[]>([]);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    if (!projectId) return;
    setLoading(true);
    setSecrets(await listSecrets(projectId));
    setLoading(false);
  };

  useEffect(() => {
    let active = true;
    void (async () => {
      if (!projectId) return;
      setLoading(true);
      try {
        const rows = await listSecrets(projectId);
        if (!active) return;
        setSecrets(rows);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [projectId]);

  const onCreate = async () => {
    if (!projectId || !key || !value) return;
    await createSecret(projectId, key, value);
    setKey("");
    setValue("");
    await refresh();
  };

  const onDelete = async (secretId: string) => {
    if (!projectId) return;
    await deleteSecret(projectId, secretId);
    await refresh();
  };

  if (loading) return <PageLoader />;

  return (
    <div className="space-y-4">
      <Card className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" hover={false}>
        <Input placeholder="Ключ, например TELEGRAM_TOKEN" value={key} onChange={(e) => setKey(e.target.value)} />
        <Input placeholder="Значение секрета" type="password" value={value} onChange={(e) => setValue(e.target.value)} />
        <Button variant="accent" className="w-full md:w-auto" onClick={onCreate}>
          <KeyRound size={16} />
          Сохранить
        </Button>
      </Card>
      <div className="grid gap-3">
        {secrets.map((secret) => (
          <Card key={secret.id} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" hover={false}>
            <div>
              <p className="font-semibold text-[var(--ar-black)]">{secret.key}</p>
              <p className="text-xs text-[var(--ar-stone)]">Зашифровано и доступно runtime проекта</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => onDelete(secret.id)}>
              <Trash2 size={15} />
              Удалить
            </Button>
          </Card>
        ))}
      </div>
      {secrets.length === 0 ? (
        <EmptyState
          title="Секретов пока нет"
          description="Сохраните API-ключи и токены здесь, чтобы не вставлять их в чат."
        />
      ) : null}
    </div>
  );
}
