"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Rocket } from "lucide-react";

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

function formatDateTime(value: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ProjectDeploymentsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [deployments, setDeployments] = useState<DeploymentType[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadDeployments = useCallback(async (options?: { silent?: boolean }) => {
    if (!projectId) return;
    if (!options?.silent) setLoading(true);
    try {
      setDeployments(await listDeployments(projectId));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить деплои");
    } finally {
      if (!options?.silent) setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadDeployments();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadDeployments]);

  const hasActiveDeployments = deployments.some(
    (item) => item.status === "running" || item.status === "queued"
  );

  useEffect(() => {
    if (!hasActiveDeployments) return;
    const timer = window.setInterval(() => {
      void loadDeployments({ silent: true });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [hasActiveDeployments, loadDeployments]);

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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm leading-7 text-[var(--ar-mist)]">История запусков и состояние runtime-контейнеров.</p>
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
          <div className="h-2 overflow-hidden rounded-full bg-white/70">
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
          <div className="grid gap-1 text-xs text-[var(--ar-stone)] sm:grid-cols-2">
            <p>Старт: {formatDateTime(item.started_at)}</p>
            <p>Финиш: {formatDateTime(item.finished_at)}</p>
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
