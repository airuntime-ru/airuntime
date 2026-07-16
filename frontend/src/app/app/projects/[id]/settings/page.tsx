"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Bot, ExternalLink, Globe2, ImageUp, Trash2 } from "lucide-react";

import { ProjectSecretsSection } from "@/components/app/project-secrets-section";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageLoader } from "@/components/ui/loader";
import { Textarea } from "@/components/ui/textarea";
import {
  deleteProject,
  getProject,
  getTelegramBotProfile,
  updateProject,
  updateTelegramBotAvatar,
  updateTelegramBotProfile,
  type ProjectType,
  type SecretType,
  type TelegramBotProfileType,
} from "@/lib/api";

const baseDomain = process.env.NEXT_PUBLIC_BASE_DOMAIN ?? "airuntime.ru";

function TelegramBotAppearanceCard({ projectId }: { projectId: string }) {
  const [profile, setProfile] = useState<TelegramBotProfileType | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    let active = true;
    void (async () => {
      setLoading(true);
      setError("");
      try {
        const row = await getTelegramBotProfile(projectId);
        if (!active) return;
        setProfile(row);
        setName(row.name ?? "");
        setDescription(row.description ?? "");
        setShortDescription(row.short_description ?? "");
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Не удалось загрузить настройки бота");
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [projectId]);

  const onSave = async () => {
    setSaving(true);
    setError("");
    setSaved("");
    try {
      const row = await updateTelegramBotProfile(projectId, {
        name: name.trim(),
        description,
        short_description: shortDescription,
      });
      setProfile(row);
      setName(row.name ?? "");
      setDescription(row.description ?? "");
      setShortDescription(row.short_description ?? "");
      setSaved("Настройки бота сохранены в Telegram");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить настройки бота");
    } finally {
      setSaving(false);
    }
  };

  const onAvatarSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    setError("");
    setSaved("");
    try {
      const row = await updateTelegramBotAvatar(projectId, file);
      setProfile(row);
      setSaved("Аватар бота обновлен в Telegram");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось обновить аватар бота");
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card hover={false} className="md:col-span-2">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--ar-radius-sm)] bg-white/80 text-sky-600 shadow-sm shadow-sky-950/5">
          <Bot size={18} />
        </span>
        <div className="min-w-0 flex-1 space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-[var(--ar-black)]">Оформление Telegram-бота</p>
              <p className="mt-1 text-sm leading-7 text-[var(--ar-mist)]">
                Имя, описание и аватар применяются напрямую в Telegram. Username меняется только через BotFather.
              </p>
            </div>
            {profile?.url ? (
              <a href={profile.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--ar-sky)]">
                @{profile.username}
                <ExternalLink size={15} />
              </a>
            ) : null}
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="telegram-name" className="text-xs font-medium text-[var(--ar-stone)]">
                Имя бота
              </label>
              <Input
                id="telegram-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={64}
                placeholder="AIRuntime Assistant"
                disabled={loading}
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="telegram-short-description" className="text-xs font-medium text-[var(--ar-stone)]">
                Короткое описание
              </label>
              <Input
                id="telegram-short-description"
                value={shortDescription}
                onChange={(event) => setShortDescription(event.target.value)}
                maxLength={120}
                placeholder="Помогает клиентам в Telegram"
                disabled={loading}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label htmlFor="telegram-description" className="text-xs font-medium text-[var(--ar-stone)]">
                Описание
              </label>
              <Textarea
                id="telegram-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={512}
                placeholder="Расскажите, что умеет бот и когда им пользоваться."
                disabled={loading}
              />
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button variant="accent" onClick={() => void onSave()} disabled={loading || saving || !name.trim()}>
              {saving ? "Сохраняем..." : "Сохранить оформление"}
            </Button>
            <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-[var(--ar-radius-sm)] border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-[var(--ar-black)] transition hover:bg-black/5">
              <ImageUp size={16} />
              {uploading ? "Загружаем..." : "Загрузить аватар"}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                disabled={uploading}
                onChange={(event) => void onAvatarSelected(event)}
              />
            </label>
          </div>

          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          {saved ? <p className="text-sm text-emerald-600">{saved}</p> : null}
        </div>
      </div>
    </Card>
  );
}

export default function ProjectSettingsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<ProjectType | null>(null);
  const [subdomain, setSubdomain] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [secrets, setSecrets] = useState<SecretType[] | null>(null);
  const botTokenConfigured = secrets?.some(
    (secret) => secret.key === "TELEGRAM_BOT_TOKEN" && secret.has_value
  );

  const [deleteStep, setDeleteStep] = useState<0 | 1 | 2>(0);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const onDeleteProject = async () => {
    if (!params.id) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await deleteProject(params.id);
      router.push("/app");
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Не удалось удалить проект");
      setDeleting(false);
    }
  };

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

  useEffect(() => {
    if (typeof window === "undefined" || window.location.hash !== "#secrets") return;
    const timer = window.setTimeout(() => {
      document.getElementById("secrets")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
    return () => window.clearTimeout(timer);
  }, [project?.id]);

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

  const hasTelegramTokenSlot =
    secrets?.some((secret) => secret.key === "TELEGRAM_BOT_TOKEN") ?? false;
  // Subdomain is only meaningful for projects that actually have a website.
  // Backend sets planned_site_url=null for telegram_bot; also hide a misclassified
  // "website" that already has a Telegram token slot.
  const showSubdomainCard =
    Boolean(project.planned_site_url) &&
    !(project.type === "website" && hasTelegramTokenSlot);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {showSubdomainCard ? (
        <Card hover={false} className="md:col-span-2">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--ar-radius-sm)] bg-white/80 text-emerald-600 shadow-sm shadow-sky-950/5">
              <Globe2 size={18} />
            </span>
            <div className="min-w-0 flex-1 space-y-4">
              <div>
                <p className="text-sm font-semibold text-[var(--ar-black)]">Поддомен сайта</p>
                <p className="mt-1 text-sm leading-7 text-[var(--ar-mist)]">
                  Адрес, на котором откроется сайт после следующего деплоя.
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
      ) : null}

      {(project.type === "telegram_bot" || project.type === "mixed") && botTokenConfigured ? (
        <TelegramBotAppearanceCard projectId={params.id} />
      ) : null}

      <ProjectSecretsSection projectId={params.id} onChange={setSecrets} />

      <Card hover={false} className="md:col-span-2 border-rose-200 bg-rose-50/40">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--ar-radius-sm)] bg-rose-100 text-rose-600">
            <AlertTriangle size={18} />
          </span>
          <div className="min-w-0 flex-1 space-y-3">
            <div>
              <p className="text-sm font-semibold text-[var(--ar-black)]">Опасная зона</p>
              <p className="mt-1 text-sm leading-7 text-[var(--ar-mist)]">
                Удаление проекта необратимо: остановится и удалится контейнер, пропадут чаты, файлы,
                деплои и секреты.
              </p>
            </div>
            <Button variant="outline" className="border-rose-300 text-rose-700 hover:bg-rose-100" onClick={() => setDeleteStep(1)}>
              <Trash2 size={16} />
              Удалить проект
            </Button>
          </div>
        </div>
      </Card>

      <Modal
        open={deleteStep === 1}
        onClose={() => setDeleteStep(0)}
        title="Удалить проект?"
        description={`Проект «${project.name}» и всё его содержимое будут удалены безвозвратно.`}
      >
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="ghost" onClick={() => setDeleteStep(0)}>
            Отмена
          </Button>
          <Button
            variant="outline"
            className="border-rose-300 text-rose-700 hover:bg-rose-100"
            onClick={() => {
              setDeleteConfirmName("");
              setDeleteStep(2);
            }}
          >
            Продолжить удаление
          </Button>
        </div>
      </Modal>

      <Modal
        open={deleteStep === 2}
        onClose={() => setDeleteStep(0)}
        title="Подтвердите удаление"
        description={`Чтобы окончательно удалить проект, введите его название: ${project.name}`}
      >
        <div className="space-y-4">
          <Input
            value={deleteConfirmName}
            onChange={(event) => setDeleteConfirmName(event.target.value)}
            placeholder={project.name}
            autoComplete="off"
          />
          {deleteError ? <p className="text-sm text-rose-600">{deleteError}</p> : null}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="ghost" onClick={() => setDeleteStep(0)} disabled={deleting}>
              Отмена
            </Button>
            <Button
              variant="outline"
              className="border-rose-300 text-rose-700 hover:bg-rose-100"
              disabled={deleteConfirmName !== project.name || deleting}
              onClick={() => void onDeleteProject()}
            >
              <Trash2 size={16} />
              {deleting ? "Удаляем..." : "Удалить навсегда"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
