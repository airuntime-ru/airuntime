"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Bot, Globe2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Textarea } from "@/components/ui/textarea";
import { createProject } from "@/lib/api";
import { cn } from "@/lib/cn";

const projectTypes = [
  { value: "website" as const, label: "Сайт", icon: Globe2, description: "Лендинг, MVP или веб-инструмент" },
  { value: "telegram_bot" as const, label: "Telegram-бот", icon: Bot, description: "Сценарии, заявки, уведомления" },
];

type CreateProjectModalProps = {
  open: boolean;
  onClose: () => void;
  onCreated?: () => void | Promise<void>;
};

export function CreateProjectModal({ open, onClose, onCreated }: CreateProjectModalProps) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<"telegram_bot" | "website">("website");
  const [createError, setCreateError] = useState("");
  const [creating, setCreating] = useState(false);

  const reset = () => {
    setName("");
    setDescription("");
    setType("website");
    setCreateError("");
    setCreating(false);
  };

  const handleClose = () => {
    if (creating) return;
    reset();
    onClose();
  };

  const onCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    setCreateError("");
    try {
      const project = await createProject({ type, name: name.trim(), description });
      await onCreated?.();
      reset();
      onClose();
      router.push(`/app/projects/${project.id}/chat`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Не удалось создать проект");
    } finally {
      setCreating(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Новый проект"
      description="Сайт или Telegram-бот — выберите формат и опишите задачу"
    >
      <div data-tour="project-create-form" className="space-y-5">
        <div className="grid gap-2 sm:grid-cols-2">
          {projectTypes.map((item) => {
            const active = type === item.value;
            return (
              <button
                key={item.value}
                type="button"
                onClick={() => setType(item.value)}
                className={cn(
                  "flex items-start gap-3 rounded-[var(--ar-radius-sm)] border p-3 text-left transition-all",
                  active
                    ? "border-[var(--ar-sky)] bg-sky-50/80 ring-2 ring-[var(--ar-sky)]/15"
                    : "border-[var(--ar-border)] bg-white hover:border-[var(--ar-border-strong)]"
                )}
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--ar-radius-sm)] bg-white text-[var(--ar-sky)] shadow-sm shadow-sky-950/5">
                  <item.icon size={17} />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-[var(--ar-black)]">{item.label}</span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-[var(--ar-mist)]">
                    {item.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        <div className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="project-name" className="text-sm font-semibold text-[var(--ar-black)]">
              Название
            </label>
            <Input
              id="project-name"
              placeholder="Например: Лендинг для консультаций"
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={creating}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="project-description" className="text-sm font-semibold text-[var(--ar-black)]">
              Описание
            </label>
            <Textarea
              id="project-description"
              className="min-h-[96px] resize-none"
              rows={3}
              placeholder="Кто пользователь, что должно произойти и какие детали важны"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              disabled={creating}
            />
          </div>
        </div>

        {createError ? <p className="text-sm text-rose-600">{createError}</p> : null}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="ghost" onClick={handleClose} disabled={creating}>
            Отмена
          </Button>
          <Button variant="accent" onClick={() => void onCreate()} disabled={creating || !name.trim()}>
            <Sparkles size={16} />
            {creating ? "Создаём..." : "Создать проект"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
