"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ExternalLink, MessageSquare, Rocket, Settings, Square } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import {
  createDeployment,
  getProject,
  getProjectRuntimeLimits,
  stopProject,
  type ProjectRuntimeLimitsType,
  type ProjectType,
} from "@/lib/api";
import {
  canStartProject,
  canStopProject,
  isProjectRunning,
  projectStatusLabel,
} from "@/lib/project-status";

const TYPE_LABELS: Record<string, string> = {
  website: "Сайт",
  telegram_bot: "Telegram-бот",
  mixed: "Сайт и бот",
};

export default function ProjectOverviewPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectType | null>(null);
  const [limits, setLimits] = useState<ProjectRuntimeLimitsType | null>(null);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const loadProject = useCallback(async () => {
    if (!params.id) return;
    const [row, runtimeLimits] = await Promise.all([
      getProject(params.id),
      getProjectRuntimeLimits(),
    ]);
    setProject(row);
    setLimits(runtimeLimits);
    setError("");
  }, [params.id]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await loadProject();
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Не удалось загрузить проект");
      }
    })();
    return () => {
      active = false;
    };
  }, [loadProject]);

  const onStop = async () => {
    if (!project) return;
    setActionLoading(true);
    setError("");
    try {
      setProject(await stopProject(project.id));
      setLimits(await getProjectRuntimeLimits());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось остановить проект");
    } finally {
      setActionLoading(false);
    }
  };

  const onStart = async () => {
    if (!project) return;
    setActionLoading(true);
    setError("");
    try {
      await createDeployment(project.id);
      await loadProject();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось запустить проект");
    } finally {
      setActionLoading(false);
    }
  };

  if (!project) return <PageLoader />;

  const atLimit = limits ? limits.running >= limits.max_running : false;
  const startDisabled = actionLoading || (atLimit && !isProjectRunning(project.status));
  const chatHref = `/app/projects/${project.id}/chat`;
  const isLive = project.status === "live";
  const isDeploying = project.status === "deploying";
  const needsConfig = project.status === "needs_configuration";
  const canRun = canStartProject(project.status) && !needsConfig;

  return (
    <div className="space-y-4">
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card hover={false} className="p-4">
          <p className="text-xs font-medium uppercase tracking-[0.12em] text-[var(--ar-stone)]">Статус</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge>{projectStatusLabel(project.status)}</Badge>
            {canStopProject(project.status) ? (
              <Button variant="ghost" size="sm" disabled={actionLoading} onClick={onStop}>
                <Square size={13} />
                Стоп
              </Button>
            ) : null}
          </div>
        </Card>
        <Card hover={false} className="p-4">
          <p className="text-xs font-medium uppercase tracking-[0.12em] text-[var(--ar-stone)]">Тип</p>
          <p className="mt-2 text-sm font-medium text-[var(--ar-black)]">
            {TYPE_LABELS[project.type] ?? project.type}
          </p>
        </Card>
        <Card hover={false} className="p-4 sm:col-span-2">
          <p className="text-xs font-medium uppercase tracking-[0.12em] text-[var(--ar-stone)]">Публичная ссылка</p>
          {project.deployment_url ? (
            <a
              href={project.deployment_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-flex items-center gap-1.5 break-all text-sm font-medium text-[var(--ar-sky)] hover:underline"
            >
              {project.deployment_url}
              <ExternalLink size={14} aria-hidden />
            </a>
          ) : (
            <p className="mt-2 text-sm text-[var(--ar-mist)]">Появится после первого запуска</p>
          )}
        </Card>
      </div>

      {limits && atLimit && !isProjectRunning(project.status) ? (
        <Card hover={false} className="border-amber-200 bg-amber-50 p-4">
          <p className="text-sm text-amber-900">
            Лимит одновременных проектов: {limits.running}/{limits.max_running}. Остановите другой проект,
            чтобы запустить этот.
          </p>
        </Card>
      ) : null}

      <Card hover={false} className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--ar-black)]">
            {isLive
              ? "Проект запущен"
              : isDeploying
                ? "Идёт сборка и запуск"
                : needsConfig
                  ? "Нужна настройка"
                  : canRun
                    ? "Готов к запуску"
                    : "Продолжите в чате"}
          </p>
          <p className="mt-1 text-sm text-[var(--ar-mist)]">
            {isLive
              ? "Правки вносите через чат — платформа пересоберёт проект."
              : isDeploying
                ? "Статус обновится сам. Подробности — во вкладках «Деплои» и «Логи»."
                : needsConfig
                  ? "Заполните секреты в настройках — запуск продолжится автоматически."
                  : canRun
                    ? "Сборка создаст образ и поднимет контейнер."
                    : "Опишите задачу в чате, чтобы собрать первую версию."}
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:min-w-[14rem]">
          {isLive && project.deployment_url ? (
            <a href={project.deployment_url} target="_blank" rel="noreferrer">
              <Button variant="accent" className="w-full">
                <ExternalLink size={16} />
                Открыть
              </Button>
            </a>
          ) : null}
          {isDeploying ? (
            <Link href={`/app/projects/${project.id}/deployments`}>
              <Button variant="accent" className="w-full">
                Смотреть деплои
              </Button>
            </Link>
          ) : null}
          {needsConfig ? (
            <Link href={`/app/projects/${project.id}/settings`}>
              <Button variant="accent" className="w-full">
                <Settings size={16} />
                Настройки
              </Button>
            </Link>
          ) : null}
          {canRun ? (
            <Button variant="accent" className="w-full" disabled={startDisabled} onClick={() => void onStart()}>
              <Rocket size={16} />
              {actionLoading ? "Запускаем…" : "Собрать и запустить"}
            </Button>
          ) : null}
          <Link href={chatHref}>
            <Button variant="outline" className="w-full">
              <MessageSquare size={16} />
              Открыть чат
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
