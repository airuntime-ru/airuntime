"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useProjects } from "@/lib/use-projects";

export default function ChatOverviewPage() {
  const { projects, error, refresh } = useProjects();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold text-[var(--ar-cloud)]">Chat</h1>
        <Button variant="ghost" onClick={refresh}>
          Refresh
        </Button>
      </div>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      {projects.length === 0 ? <Card>Select a project to start a chat session.</Card> : null}
      {projects.map((project) => (
        <Card key={project.id} className="flex items-center justify-between">
          <div>
            <p className="font-medium text-[var(--ar-cloud)]">{project.name}</p>
            <p className="text-sm text-[var(--ar-stone)]">{project.type}</p>
          </div>
          <Link href={`/app/projects/${project.id}/chat`} className="text-sm text-[var(--ar-sky)] hover:underline">
            Open Chat
          </Link>
        </Card>
      ))}
    </div>
  );
}
