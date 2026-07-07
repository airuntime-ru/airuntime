"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Globe2, Settings2 } from "lucide-react";

import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import { getProject, type ProjectType } from "@/lib/api";

export default function ProjectSettingsPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectType | null>(null);

  useEffect(() => {
    let active = true;
    void (async () => {
      if (!params.id) return;
      const row = await getProject(params.id);
      if (active) setProject(row);
    })();
    return () => {
      active = false;
    };
  }, [params.id]);

  if (!project) return <PageLoader />;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card hover={false}>
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-[var(--ar-radius-sm)] bg-sky-50 text-[var(--ar-sky)]">
            <Settings2 size={18} />
          </span>
          <div>
            <p className="text-sm text-[var(--ar-stone)]">Название проекта</p>
            <p className="mt-1 text-xl font-semibold text-[var(--ar-black)]">{project.name}</p>
          </div>
        </div>
      </Card>
      <Card hover={false}>
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-[var(--ar-radius-sm)] bg-emerald-50 text-emerald-600">
            <Globe2 size={18} />
          </span>
          <div>
            <p className="text-sm text-[var(--ar-stone)]">Runtime-домен</p>
            <p className="mt-1 text-sm leading-relaxed text-[var(--ar-mist)]">
              Домен настраивается через базовые параметры окружения и синхронизируется с метаданными деплоя.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
