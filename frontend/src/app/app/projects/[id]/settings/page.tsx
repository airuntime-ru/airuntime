"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Globe2 } from "lucide-react";

import { ProjectSecretsSection } from "@/components/app/project-secrets-section";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoader } from "@/components/ui/loader";
import { getProject, updateProject, type ProjectType } from "@/lib/api";

const baseDomain = process.env.NEXT_PUBLIC_BASE_DOMAIN ?? "airuntime.ru";

export default function ProjectSettingsPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectType | null>(null);
  const [subdomain, setSubdomain] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      if (!params.id) return;
      const row = await getProject(params.id);
      if (!active) return;
      setProject(row);
      setSubdomain(row.deploy_subdomain ?? "");
    })();
    return () => {
      active = false;
    };
  }, [params.id]);

  const previewUrl = useMemo(() => {
    if (subdomain.trim()) {
      return `https://${subdomain.trim()}.${baseDomain}`;
    }
    if (project?.planned_site_url) {
      return project.planned_site_url;
    }
    return `https://ваш-поддомен.${baseDomain}`;
  }, [subdomain, project?.planned_site_url]);

  const onSaveSubdomain = async () => {
    if (!project || !params.id) return;
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const updated = await updateProject(params.id, {
        deploy_subdomain: subdomain.trim() || null,
      });
      setProject(updated);
      setSubdomain(updated.deploy_subdomain ?? "");
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить поддомен");
    } finally {
      setSaving(false);
    }
  };

  if (!project || !params.id) return <PageLoader />;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {project.type === "website" ? (
        <Card hover={false} className="md:col-span-2">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--ar-radius-sm)] bg-white/80 text-emerald-600 shadow-sm shadow-sky-950/5">
              <Globe2 size={18} />
            </span>
            <div className="min-w-0 flex-1 space-y-4">
              <div>
                <p className="text-sm font-semibold text-[var(--ar-black)]">Поддомен сайта</p>
                <p className="mt-1 text-sm leading-7 text-[var(--ar-mist)]">
                  Адрес, на котором откроется проект после следующего деплоя.
                </p>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="flex-1 space-y-2">
                  <label htmlFor="deploy-subdomain" className="text-xs font-medium text-[var(--ar-stone)]">
                    Поддомен
                  </label>
                  <div className="flex overflow-hidden rounded-[var(--ar-radius-sm)] border border-white/70 bg-white/72 shadow-sm shadow-sky-950/5">
                    <Input
                      id="deploy-subdomain"
                      value={subdomain}
                      onChange={(event) => {
                        setSubdomain(event.target.value.toLowerCase());
                        setSaved(false);
                      }}
                      placeholder="my-landing"
                      className="border-0 bg-transparent shadow-none focus:ring-0"
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <span className="flex items-center border-l border-white/70 bg-white/58 px-3 text-sm text-[var(--ar-mist)]">
                      .{baseDomain}
                    </span>
                  </div>
                </div>
                <Button variant="accent" onClick={() => void onSaveSubdomain()} disabled={saving}>
                  {saving ? "Сохраняем..." : "Сохранить"}
                </Button>
              </div>

              <p className="text-sm text-[var(--ar-mist)]">
                Будет доступен по адресу: <span className="font-medium text-[var(--ar-black)]">{previewUrl}</span>
              </p>
              <p className="text-xs text-[var(--ar-stone)]">Поддомен проверяется на уникальность по всей системе.</p>
              {project.deployment_url ? (
                <p className="text-xs leading-6 text-[var(--ar-stone)]">
                  Текущий деплой: {project.deployment_url}. Новый поддомен применится при следующем запуске.
                </p>
              ) : null}
              {error ? <p className="text-sm text-rose-600">{error}</p> : null}
              {saved ? <p className="text-sm text-emerald-600">Поддомен сохранен</p> : null}
            </div>
          </div>
        </Card>
      ) : (
        <Card hover={false}>
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-[var(--ar-radius-sm)] bg-white/80 text-emerald-600 shadow-sm shadow-sky-950/5">
              <Globe2 size={18} />
            </span>
            <div>
              <p className="text-sm text-[var(--ar-stone)]">Публикация</p>
              <p className="mt-1 text-sm leading-7 text-[var(--ar-mist)]">
                Для Telegram-бота отдельный поддомен не нужен.
              </p>
            </div>
          </div>
        </Card>
      )}

      <ProjectSecretsSection projectId={params.id} />
    </div>
  );
}
