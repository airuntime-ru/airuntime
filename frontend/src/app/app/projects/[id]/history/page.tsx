"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import { listDeployments, type DeploymentType } from "@/lib/api";

export default function ProjectHistoryPage() {
  const params = useParams<{ id: string }>();
  const [items, setItems] = useState<DeploymentType[]>([]);

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
        <Card key={item.id} hover={false}>
          <p className="text-sm text-[var(--ar-stone)]">{item.status}</p>
          <p className="text-[var(--ar-cloud)]">{item.image_ref}</p>
        </Card>
      ))}
      {items.length === 0 ? <Card hover={false}>No deployment history yet.</Card> : null}
    </div>
  );
}
