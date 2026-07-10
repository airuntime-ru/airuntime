"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Pause, Play, Rocket } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/loader";
import {
  createDeployment,
  getProject,
  getProjectRuntimeLimits,
  listDeployments,
  startProject,
  stopProject,
  type DeploymentType,
  type ProjectRuntimeLimitsType,
  type ProjectType,
} from "@/lib/api";
import {
  canStartProject,
  canStopProject,
  deploymentStatusLabel,
  isProjectRunning,
  projectStatusLabel,
} from "@/lib/project-status";

function statusTone(status: string) {
  if (status === "completed") return "text-emerald-700";
  if (status === "failed" || status === "cancelled") return "text-rose-700";
  if (status === "running") return "text-[var(--ar-sky)]";
  return "text-[var(--ar-stone)]";
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
  const [project, setProject] = useState<ProjectType | null>(null);
  const [limits, setLimits] = useState<ProjectRuntimeLimitsType | null>(null);
  const [deployments, setDeployments] = useState<DeploymentType[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const loadPage = useCallback(async (options?: { silent?: boolean }) => {
    if (!projectId) return;
    if (!options?.silent) setLoading(true);
    try {
      const [projectRow, deploymentRows, runtimeLimits] = await Promise.all([
        getProject(projectId),
        listDeployments(projectId),
        getProjectRuntimeLimits(),
      ]);
      setProject(projectRow);
      setDeployments(deploymentRows);
      setLimits(runtimeLimits);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить деплои");
    } finally {
      if (!options?.silent) setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadPage();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadPage]);

  const hasActiveDeployments = deployments.some(
    (item) => item.status === "running" || item.status === "queued",
  );

  useEffect(() => {
    if (!hasActiveDeployments) return;
    const timer = window.setInterval(() => {
      void loadPage({ silent: true });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [hasActiveDeployments, loadPage]);

  const onDeploy = async () => {
    if (!projectId) return;
    setActionLoading(true);
    setError("");
    try {
      await createDeployment(projectId);
      await loadPage({ silent: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось поставить деплой в очередь");
    } finally {
      setActionLoading(false);
    }
  };

  const onStop = async () => {
    if (!projectId) return;
    setActionLoading(true);
    setError("");
    try {
      setProject(await stopProject(projectId));
      setLimits(await getProjectRuntimeLimits());
      await loadPage({ silent: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось остановить проект");
    } finally {
      setActionLoading(false);
    }
  };

  const onStart = async () => {
    if (!projectId) return;
    setActionLoading(true);
    setError("");
    try {
      setProject(await startProject(projectId));
      setLimits(await getProjectRuntimeLimits());
      await loadPage({ silent: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось запустить проект");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <PageLoader />;

  const atLimit = limits ? limits.running >= limits.max_running : false;
  const startDisabled = actionLoading || !project || (atLimit && !isProjectRunning(project.status));

  return (
    <div className="space-y-4">
      {limits ? (
        <Card hover={false} className="border-[var(--ar-sky)]/20 bg-[var(--ar-sky)]/5">
          <p className="text-sm text-[var(--ar-mist)]">
            Запущено проектов:{" "}
            <span className="font-semibold text-[var(--ar-black)]">
              {limits.running} / {limits.max_running}
            </span>
            {project ? (
              <>
                {" "}
                · текущий статус: <Badge>{projectStatusLabel(project.status)}</Badge>
              </>
            ) : null}
          </p>
        </Card>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm leading-7 text-[var(--ar-mist)]">История запусков проекта и его текущее состояние.</p>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          {project && canStopProject(project.status) ? (
            <Button variant="outline" size="sm" className="w-full sm:w-auto" disabled={actionLoading} onClick={onStop}>
              <Pause size={15} />
              Остановить
            </Button>
          ) : null}
          {project && canStartProject(project.status) ? (
            <Button variant="outline" size="sm" className="w-full sm:w-auto" disabled={startDisabled} onClick={onStart}>
              <Play size={15} />
              Запустить
            </Button>
          ) : null}
          <Button variant="accent" size="sm" className="w-full sm:w-auto" disabled={actionLoading || startDisabled} onClick={onDeploy}>
            <Rocket size={15} />
            Собрать и запустить
          </Button>
        </div>
      </div>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {deployments.map((item) => (
        <Card key={item.id} className="space-y-3" hover={false}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="break-all font-semibold text-[var(--ar-black)]">{item.image_ref ?? "Образ приложения"}</p>
              <p className="mt-1 text-xs text-[var(--ar-stone)]">ID: {item.id}</p>
            </div>
            <Badge className={statusTone(item.status)}>{deploymentStatusLabel(item.status)}</Badge>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/70">
            <div
              className={`h-full rounded-full transition-all ${
                item.status === "completed"
                  ? "w-full bg-emerald-400"
                  : item.status === "running"
                    ? "w-2/3 bg-[var(--ar-sky)]"
                    : item.status === "failed" || item.status === "cancelled"
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
            <Button variant="accent" disabled={startDisabled} onClick={onDeploy}>
              <Rocket size={16} />
              Собрать и запустить
            </Button>
          }
        />
      ) : null}
    </div>
  );
}
