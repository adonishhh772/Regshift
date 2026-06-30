"use client";

import { useEffect, useRef } from "react";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useRegShiftStore } from "@/lib/store";

interface WorkspaceLayoutProps {
  children: React.ReactNode;
}

export function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  const setIndexStatus = useRegShiftStore((state) => state.setIndexStatus);
  const setGraphBackend = useRegShiftStore((state) => state.setGraphBackend);
  const setLangfuseUiUrl = useRegShiftStore((state) => state.setLangfuseUiUrl);
  const setBackendStatus = useRegShiftStore((state) => state.setBackendStatus);
  const pollGenerationRef = useRef(0);

  useEffect(() => {
    let isMounted = true;

    const refreshIndexStatus = async () => {
      try {
        const status = await api.indexStatus();
        if (isMounted) {
          setIndexStatus(status);
        }
      } catch {
        if (isMounted) {
          setIndexStatus(null);
        }
      }
    };

    const refreshBackendStatus = async (options?: { showChecking?: boolean }) => {
      const pollGeneration = pollGenerationRef.current + 1;
      pollGenerationRef.current = pollGeneration;

      if (options?.showChecking !== false) {
        const currentStatus = useRegShiftStore.getState().backendStatus;
        if (currentStatus !== "online") {
          setBackendStatus("checking");
        }
      }

      try {
        await api.getHealthLive();
        if (!isMounted || pollGeneration !== pollGenerationRef.current) {
          return;
        }

        setBackendStatus("online");

        void api
          .getHealth()
          .then((health) => {
            if (!isMounted || pollGeneration !== pollGenerationRef.current) {
              return;
            }
            setGraphBackend(health.neo4j.available ? "neo4j" : health.neo4j.backend);
            if (health.langfuse?.ui_url) {
              setLangfuseUiUrl(health.langfuse.ui_url);
            }
          })
          .catch(() => undefined);

        void refreshIndexStatus();
      } catch {
        if (pollGeneration !== pollGenerationRef.current) {
          return;
        }
        setBackendStatus("offline");
        if (isMounted) {
          setIndexStatus(null);
        }
      }
    };

    refreshBackendStatus({ showChecking: true });
    const intervalId = window.setInterval(() => refreshBackendStatus({ showChecking: false }), 15000);

    return () => {
      isMounted = false;
      pollGenerationRef.current += 1;
      window.clearInterval(intervalId);
    };
  }, [setBackendStatus, setGraphBackend, setIndexStatus, setLangfuseUiUrl]);

  return <AppShell>{children}</AppShell>;
}
