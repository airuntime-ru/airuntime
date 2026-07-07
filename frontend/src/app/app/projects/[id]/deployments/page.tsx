"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState, PageLoader } from "@/components/ui/loader";
import { createDeployment, listDeployments, type DeploymentType } from "@/lib/api";

function statusTone(status: string) {
  if (status === "completed") return "text-[var(--ar-cyan)]";
  if (status === "failed") return "text-rose-300";
  if (status === "running") return "text-[var(--ar-sky)]";
  return "text-[var(--ar-stone)]";
}

export default function ProjectDeploymentsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [deployments, setDeployments] = useState<DeploymentType[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadDeployments = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      setDeployments(await listDeployments(projectId));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load deployments");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    void (async () => {
      if (!projectId) return;
      setLoading(true);
      try {
        const rows = await listDeployments(projectId);
        if (!active) return;
        setDeployments(rows);
        setError("");
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load deployments");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [projectId]);

  const onDeploy = async () => {
    if (!projectId) return;
    try {
      await createDeployment(projectId);
      await loadDeployments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to queue deployment");
    }
  };

  if (loading) return <PageLoader />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={loadDeployments}>
          Refresh
        </Button>
        <Button variant="accent" onClick={onDeploy}>
          Deploy
        </Button>
      </div>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      {deployments.map((item) => (
        <Card key={item.id} className="space-y-3" hover={false}>
          <div className="flex items-center justify-between">
            <p className="font-medium text-[var(--ar-cloud)]">{item.image_ref ?? "runtime image"}</p>
            <Badge className={statusTone(item.status)}>{item.status}</Badge>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-[var(--ar-surface-1)]">
            <div
              className={`h-full rounded-full transition-all ${
                item.status === "completed"
                  ? "w-full bg-[var(--ar-cyan)]"
                  : item.status === "running"
                    ? "w-2/3 bg-[var(--ar-sky)]"
                    : item.status === "failed"
                      ? "w-full bg-rose-400"
                      : "w-1/3 bg-[var(--ar-stone)]"
              }`}
            />
          </div>
          <p className="text-xs text-[var(--ar-stone)]">{item.logs_ref ?? "Awaiting logs"}</p>
        </Card>
      ))}
      {deployments.length === 0 ? (
        <EmptyState
          title="No deployments yet"
          description="Launch your first runtime deployment."
          action={
            <Button variant="accent" onClick={onDeploy}>
              Deploy now
            </Button>
          }
        />
      ) : null}
    </div>
  );
}
