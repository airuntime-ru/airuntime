"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageLoader } from "@/components/ui/loader";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { getProject, type ProjectType } from "@/lib/api";

export default function ProjectOverviewPage() {
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
    <div className="grid gap-4 md:grid-cols-3">
      <Card>
        <p className="text-sm text-[var(--ar-stone)]">Status</p>
        <div className="mt-2">
          <Badge>{project.status}</Badge>
        </div>
      </Card>
      <Card>
        <p className="text-sm text-[var(--ar-stone)]">Type</p>
        <p className="mt-2 text-xl text-[var(--ar-cloud)]">{project.type}</p>
      </Card>
      <Card>
        <p className="text-sm text-[var(--ar-stone)]">Deployment URL</p>
        <p className="mt-2 text-sm text-[var(--ar-sky)]">{project.deployment_url ?? "Deploy to generate a live URL"}</p>
      </Card>
    </div>
  );
}
