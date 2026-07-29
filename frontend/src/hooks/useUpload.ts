import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ingestDocuments } from "../api/client";
import type { IngestSubmission } from "../types/api";

export function useUpload(identityId: string | null) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IngestSubmission | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(
    async (files: File[], target: "private" | "common") => {
      if (!identityId || files.length === 0) return;
      setBusy(true);
      setError(null);
      try {
        const res = await ingestDocuments(files, identityId, target);
        setResult(res);
        await queryClient.invalidateQueries({ queryKey: ["documents"] });
        await queryClient.invalidateQueries({ queryKey: ["ingest-jobs"] });
      } catch (e) {
        setError(String(e));
      } finally {
        setBusy(false);
      }
    },
    [identityId, queryClient]
  );

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { busy, result, error, upload, reset };
}
