"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Clock3 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, PageLoader } from "@/components/ui/loader";
import { listDeployments, type DeploymentType } from "@/lib/api";

export default function ProjectHistoryPage() {
  const params = useParams<{ id: string }>();
  const [items, setItems] = useState<DeploymentType[] | null>(null);

  useEffect(() => {
    let active = true;
    void (async () => {
      if (!params.id) return;
      const rows = await listDeployments(params.id);
      if (active) setItems(rows);
    })();
    return () => {
      active = false;
    };
  }, [params.id]);

  if (!items) return <PageLoader />;

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <Card key={item.id} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" hover={false}>
          <div className="min-w-0">
            <p className="flex items-center gap-2 font-semibold text-[var(--ar-black)]">
              <Clock3 size={16} className="text-[var(--ar-sky)]" />
              Деплой {item.id.slice(0, 8)}
            </p>
            <p className="mt-1 break-all text-sm text-[var(--ar-mist)]">{item.image_ref ?? "Образ еще не создан"}</p>
          </div>
          <Badge>{item.status}</Badge>
        </Card>
      ))}
      {items.length === 0 ? (
        <EmptyState title="История пока пуста" description="После первого деплоя здесь появятся события проекта." />
      ) : null}
    </div>
  );
}
