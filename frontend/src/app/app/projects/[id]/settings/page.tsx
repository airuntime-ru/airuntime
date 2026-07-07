"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import { getProject } from "@/lib/api";

export default function ProjectSettingsPage() {
  const params = useParams<{ id: string }>();
  const [name, setName] = useState("");

  useEffect(() => {
    let active = true;
    void (async () => {
      if (!params.id) return;
      const project = await getProject(params.id);
      if (active) setName(project.name);
    })();
    return () => {
      active = false;
    };
  }, [params.id]);

  if (!name) return <PageLoader />;

  return (
    <Card hover={false}>
      <p className="text-sm text-[var(--ar-stone)]">Project name</p>
      <p className="mt-2 text-xl text-[var(--ar-cloud)]">{name}</p>
      <p className="mt-4 text-sm text-[var(--ar-mist)]">
        Runtime domain is configured via APP_DOMAIN. Project settings sync with deployment metadata.
      </p>
    </Card>
  );
}
