"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Activity, AlertCircle, CheckCircle2, Maximize2, RefreshCw, ShieldCheck, Terminal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/loader";
import { Modal } from "@/components/ui/modal";
import { getProjectLogs, type ProjectLogsType } from "@/lib/api";
import { stashPendingRepair } from "@/lib/chat-stream-runtime";
import { cn } from "@/lib/cn";
import { deploymentStatusLabel } from "@/lib/project-status";

const REPAIR_LOG_BUDGET = 100_000;

function buildRepairLogExcerpt(logs: ProjectLogsType): string {
  const parts: string[] = [];
  if (logs.runtime_error?.trim()) {
    parts.push(logs.runtime_error.trim());
  }
  if (logs.deployment_logs.trim()) {
    parts.push(`--- Деплой / сборка ---\n${logs.deployment_logs.trim()}`);
  }
  if (logs.runtime_logs.trim()) {
    parts.push(`--- Runtime ---\n${logs.runtime_logs.trim()}`);
  }
  const joined = parts.join("\n\n").trim();
  if (!joined) return "";
  return joined.length > REPAIR_LOG_BUDGET ? joined.slice(-REPAIR_LOG_BUDGET) : joined;
}

function LogBlock({
  title,
  hint,
  value,
  onExpand,
}: {
  title: string;
  hint?: string;
  value: string;
  onExpand: () => void;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-black/10 bg-white/70">
      <div className="flex items-center justify-between gap-2 border-b border-black/8 px-4 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Terminal size={15} className="shrink-0 text-[var(--ar-sky)]" />
            <h2 className="text-sm font-semibold text-[var(--ar-black)]">{title}</h2>
          </div>
          {hint ? <p className="mt-1 pl-6 text-xs text-[var(--ar-stone)]">{hint}</p> : null}
        </div>
        <button
          type="button"
          onClick={onExpand}
          className="rounded-[var(--ar-radius-sm)] p-1.5 text-[var(--ar-stone)] hover:bg-black/5 hover:text-[var(--ar-black)]"
          aria-label={`Раскрыть логи: ${title}`}
        >
          <Maximize2 size={14} />
        </button>
      </div>
      <pre className="max-h-[42vh] overflow-auto whitespace-pre-wrap bg-[#fbfdff] p-4 font-mono text-xs leading-relaxed text-[var(--ar-graphite)]">
        {value}
      </pre>
    </section>
  );
}

export default function ProjectLogsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [logs, setLogs] = useState<ProjectLogsType | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [expanded, setExpanded] = useState<{ title: string; value: string } | null>(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      if (!params.id) return;
      try {
        setRefreshing(true);
        const next = await getProjectLogs(params.id);
        if (active) {
          setLogs(next);
          setError("");
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Не удалось загрузить логи");
        }
      } finally {
        if (active) setRefreshing(false);
      }
    };

    void load();
    const timer = window.setInterval(() => {
      void load();
    }, 2500);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [params.id]);

  const hasLogs = useMemo(() => {
    if (!logs) return false;
    return Boolean(
      logs.project_logs.trim() ||
        logs.deployment_logs.trim() ||
        logs.runtime_logs.trim() ||
        logs.runtime_error
    );
  }, [logs]);

  const canAnalyze = useMemo(() => {
    if (!logs) return false;
    return Boolean(
      logs.deployment_status === "failed" ||
        logs.runtime_error ||
        logs.runtime_logs.trim() ||
        (logs.deployment_logs.trim() && logs.deployment_status === "failed") ||
        logs.container_id
    );
  }, [logs]);

  const onAnalyzeRuntimeLogs = () => {
    if (!params.id || !logs) return;
    const excerpt = buildRepairLogExcerpt(logs);
    stashPendingRepair(params.id, excerpt);
    router.push(`/app/projects/${params.id}/chat?repair=1`);
  };

  if (logs === null && !error) return <PageLoader />;

  return (
    <div className="space-y-4">
      <Card hover={false} className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-xl",
                logs?.deployment_status === "completed"
                  ? "bg-emerald-50 text-emerald-600"
                  : "bg-sky-50 text-[var(--ar-sky)]"
              )}
            >
              {logs?.deployment_status === "completed" ? (
                <CheckCircle2 size={18} />
              ) : (
                <Activity size={18} />
              )}
            </span>
            <div>
              <p className="text-sm font-semibold text-[var(--ar-black)]">
                {logs?.deployment_status
                  ? `Деплой: ${deploymentStatusLabel(logs.deployment_status)}`
                  : "Логи проекта"}
              </p>
              <p className="text-xs text-[var(--ar-stone)]">
                {logs?.container_id
                  ? `Контейнер ${logs.container_id.slice(0, 12)}`
                  : "Обновляется автоматически"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-[var(--ar-stone)]">
            <RefreshCw size={14} className={cn(refreshing && "animate-spin")} />
            в реальном времени
          </div>
        </div>
      </Card>

      {error ? (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {logs?.runtime_error ? (
        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertCircle size={16} className="mt-0.5 shrink-0" />
          <span>{logs.runtime_error}</span>
        </div>
      ) : null}

      {canAnalyze ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-black/10 bg-white/70 px-4 py-3">
          <p className="text-sm text-[var(--ar-mist)]">
            ИИ получит тот же фрагмент логов, что вы видите здесь, исправит код в чате и пересоберёт
            проект.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="w-full sm:w-auto"
            onClick={onAnalyzeRuntimeLogs}
          >
            <ShieldCheck size={15} />
            Проверить и исправить в чате
          </Button>
        </div>
      ) : null}

      {hasLogs && logs ? (
        <div className="grid gap-4">
          {logs.project_logs.trim() ? (
            <LogBlock
              title="События платформы"
              hint="DNS, остановки, служебные заметки — не вывод контейнера"
              value={logs.project_logs}
              onExpand={() =>
                setExpanded({ title: "События платформы", value: logs.project_logs })
              }
            />
          ) : null}
          {logs.deployment_logs.trim() ? (
            <LogBlock
              title="Деплой / сборка"
              hint="Статус последнего деплоя и полный текст ошибки сборки, если есть"
              value={logs.deployment_logs}
              onExpand={() => setExpanded({ title: "Деплой / сборка", value: logs.deployment_logs })}
            />
          ) : null}
          {logs.runtime_logs.trim() ? (
            <LogBlock
              title="Контейнер (runtime)"
              hint="Живой stdout/stderr работающего контейнера"
              value={logs.runtime_logs}
              onExpand={() =>
                setExpanded({ title: "Контейнер (runtime)", value: logs.runtime_logs })
              }
            />
          ) : null}
        </div>
      ) : (
        <Card hover={false}>
          <EmptyState
            title="Логов пока нет"
            description="Лог сборки смотрите во вкладке «Деплои» (разверните строку). Здесь — события платформы и runtime контейнера."
          />
        </Card>
      )}

      <Modal
        open={expanded !== null}
        onClose={() => setExpanded(null)}
        title={expanded ? `Логи: ${expanded.title}` : ""}
        className="max-w-4xl"
      >
        <pre className="max-h-[75vh] overflow-auto whitespace-pre-wrap bg-[#fbfdff] p-4 font-mono text-xs leading-relaxed text-[var(--ar-graphite)]">
          {expanded?.value}
        </pre>
      </Modal>
    </div>
  );
}
