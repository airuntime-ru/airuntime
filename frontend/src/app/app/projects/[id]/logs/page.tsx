"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Activity, AlertCircle, CheckCircle2, RefreshCw, Terminal } from "lucide-react";

import { Card } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/loader";
import { getProjectLogs, type ProjectLogsType } from "@/lib/api";
import { cn } from "@/lib/cn";
import { deploymentStatusLabel } from "@/lib/project-status";

function LogBlock({ title, value }: { title: string; value: string }) {
  return (
    <section className="overflow-hidden rounded-xl border border-black/10 bg-white/70">
      <div className="flex items-center gap-2 border-b border-black/8 px-4 py-3">
        <Terminal size={15} className="text-[var(--ar-sky)]" />
        <h2 className="text-sm font-semibold text-[var(--ar-black)]">{title}</h2>
      </div>
      <pre className="max-h-[42vh] overflow-auto whitespace-pre-wrap bg-[#fbfdff] p-4 font-mono text-xs leading-relaxed text-[var(--ar-graphite)]">
        {value}
      </pre>
    </section>
  );
}

export default function ProjectLogsPage() {
  const params = useParams<{ id: string }>();
  const [logs, setLogs] = useState<ProjectLogsType | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

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
                {logs?.deployment_status ? `Деплой: ${deploymentStatusLabel(logs.deployment_status)}` : "Логи проекта"}
              </p>
              <p className="text-xs text-[var(--ar-stone)]">
                {logs?.container_id ? `Контейнер ${logs.container_id.slice(0, 12)}` : "Обновляется автоматически"}
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

      {hasLogs && logs ? (
        <div className="grid gap-4">
          {logs.project_logs.trim() ? <LogBlock title="Проект" value={logs.project_logs} /> : null}
          {logs.deployment_logs.trim() ? <LogBlock title="Деплой" value={logs.deployment_logs} /> : null}
          {logs.runtime_logs.trim() ? <LogBlock title="Runtime" value={logs.runtime_logs} /> : null}
        </div>
      ) : (
        <Card hover={false}>
          <EmptyState
            title="Логов пока нет"
            description="Они появятся здесь во время сборки, запуска и работы проекта."
          />
        </Card>
      )}
    </div>
  );
}
