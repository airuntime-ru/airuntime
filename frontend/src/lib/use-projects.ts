"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { listProjects, type ProjectType } from "@/lib/api";

export function useProjects() {
  const [projects, setProjects] = useState<ProjectType[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listProjects();
      setProjects(rows);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      setLoading(true);
      try {
        const rows = await listProjects();
        if (!active) return;
        setProjects(rows);
        setError("");
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load projects");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  return useMemo(() => ({ projects, error, loading, refresh }), [projects, error, loading, refresh]);
}
