"use client";

import Link from "next/link";
import { ArrowRight, FolderKanban, RefreshCw, Rocket, Shapes } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useProjects } from "@/lib/use-projects";

export default function DashboardPage() {
  const { projects, error, refresh } = useProjects();
  const ready = projects.filter((project) => project.status === "ready").length;
  const types = new Set(projects.map((project) => project.type)).size;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">Кабинет</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">Обзор</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--ar-mist)]">
            Следите за проектами, запускайте новые идеи и возвращайтесь к доработкам в одном месте.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={refresh}>
            <RefreshCw size={16} />
            Обновить
          </Button>
          <Link href="/app/projects" data-tour="dashboard-create">
            <Button variant="accent">
              Создать
              <ArrowRight size={16} />
            </Button>
          </Link>
        </div>
      </div>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { label: "Проекты", value: projects.length, icon: FolderKanban },
          { label: "Типы", value: types, icon: Shapes },
          { label: "Готовы к деплою", value: ready, icon: Rocket },
        ].map((item) => (
          <Card key={item.label} hover={false}>
            <div className="flex items-center justify-between">
              <p className="text-sm text-[var(--ar-stone)]">{item.label}</p>
              <item.icon size={18} className="text-[var(--ar-sky)]" />
            </div>
            <p className="mt-3 text-3xl font-semibold tabular-nums text-[var(--ar-black)]">{item.value}</p>
          </Card>
        ))}
      </div>

      <Card hover={false} className="overflow-hidden p-0">
        <div className="grid gap-0 md:grid-cols-[1.1fr_0.9fr]">
          <div className="p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--ar-cyan)]">Следующий шаг</p>
            <h2 className="mt-3 text-2xl font-semibold text-[var(--ar-black)]">Опишите первый или следующий продукт</h2>
            <p className="mt-3 text-sm leading-relaxed text-[var(--ar-mist)]">
              Лучше всего начинать с конкретного результата: кто будет пользоваться, что должно произойти и какой формат запуска нужен.
            </p>
            <Link href="/app/projects" className="mt-5 inline-block" data-tour="dashboard-create">
              <Button variant="accent">
                Перейти к проектам
                <ArrowRight size={16} />
              </Button>
            </Link>
          </div>
          <div className="border-t border-[var(--ar-border)] bg-white/60 p-6 md:border-l md:border-t-0">
            <div className="space-y-3 text-sm text-[var(--ar-mist)]">
              <p className="font-medium text-[var(--ar-black)]">Хороший стартовый запрос:</p>
              <p className="rounded-[var(--ar-radius-sm)] bg-white p-4 shadow-sm shadow-sky-950/5">
                “Сделай лендинг для записи на консультацию, с формой заявки, блоком преимуществ и отправкой заявок в Telegram.”
              </p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
