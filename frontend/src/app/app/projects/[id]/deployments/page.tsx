"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { RefreshCw, Rocket } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/loader";
import { createDeployment, listDeployments, type DeploymentType } from "@/lib/api";

function statusTone(status: string) {
  if (status === "completed") return "text-emerald-700";
  if (status === "failed") return "text-rose-700";
  if (status === "running") return "text-[var(--ar-sky)]";
  return "text-[var(--ar-stone)]";
}

function statusLabel(status: string) {
  if (status === "completed") return "Готово";
  if (status === "failed") return "Ошибка";
  if (status === "running") return "Запускается";
  if (status === "queued") return "В очереди";
  return status;
}

export default function ProjectDeploymentsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [deployments, setDeployments] = useState<DeploymentType[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadDeployments = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      setDeployments(await listDeployments(projectId));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить деплои");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    void (async () => {
      if (!projectId) return;
      setLoading(true);
      try {
        const rows = await listDeployments(projectId);
        if (!active) return;
        setDeployments(rows);
        setError("");
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Не удалось загрузить деплои");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [projectId]);

  const onDeploy = async () => {
    if (!projectId) return;
    try {
      await createDeployment(projectId);
      await loadDeployments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось поставить деплой в очередь");
    }
  };

  if (loading) return <PageLoader />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="outline" size="sm" onClick={loadDeployments}>
          <RefreshCw size={15} />
          Обновить
        </Button>
        <Button variant="accent" size="sm" className="w-full sm:w-auto" onClick={onDeploy}>
          <Rocket size={15} />
          Запустить
        </Button>
      </div>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {deployments.map((item) => (
        <Card key={item.id} className="space-y-3" hover={false}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="break-all font-semibold text-[var(--ar-black)]">{item.image_ref ?? "Образ приложения"}</p>
              <p className="mt-1 text-xs text-[var(--ar-stone)]">ID: {item.id}</p>
            </div>
            <Badge className={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-sky-50">
            <div
              className={`h-full rounded-full transition-all ${
                item.status === "completed"
                  ? "w-full bg-emerald-400"
                  : item.status === "running"
                    ? "w-2/3 bg-[var(--ar-sky)]"
                    : item.status === "failed"
                      ? "w-full bg-rose-400"
                      : "w-1/3 bg-[var(--ar-stone)]"
              }`}
            />
          </div>
          <p className="text-xs text-[var(--ar-stone)]">{item.logs_ref ?? "Логи появятся после запуска"}</p>
        </Card>
      ))}
      {deployments.length === 0 ? (
        <EmptyState
          title="Деплоев пока нет"
          description="Запустите первую сборку, чтобы получить рабочий runtime."
          action={
            <Button variant="accent" onClick={onDeploy}>
              <Rocket size={16} />
              Запустить сейчас
            </Button>
          }
        />
      ) : null}
    </div>
  );
}
