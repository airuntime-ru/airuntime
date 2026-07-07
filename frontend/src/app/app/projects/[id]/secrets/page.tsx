"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

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
      <Card className="space-y-3" hover={false}>
        <Input placeholder="Secret key" value={key} onChange={(e) => setKey(e.target.value)} />
        <Input placeholder="Secret value" type="password" value={value} onChange={(e) => setValue(e.target.value)} />
        <Button variant="accent" onClick={onCreate}>
          Store secret
        </Button>
      </Card>
      {secrets.map((secret) => (
        <Card key={secret.id} className="flex items-center justify-between" hover={false}>
          <div>
            <p className="font-medium text-[var(--ar-cloud)]">{secret.key}</p>
            <p className="text-xs text-[var(--ar-stone)]">Encrypted at rest</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => onDelete(secret.id)}>
            Delete
          </Button>
        </Card>
      ))}
      {secrets.length === 0 ? <EmptyState title="No secrets" description="Store API keys and tokens securely for this project." /> : null}
    </div>
  );
}
