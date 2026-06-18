import { useCallback, useState } from "react";
import { ingestDocuments } from "../api/client";
import type { IngestResult } from "../types/api";

export function useUpload(identityId: string | null) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(
    async (files: File[], target: "private" | "common") => {
      if (!identityId || files.length === 0) return;
      setBusy(true);
      setError(null);
      try {
        const res = await ingestDocuments(files, identityId, target);
        setResult(res);
      } catch (e) {
        setError(String(e));
      } finally {
        setBusy(false);
      }
    },
    [identityId]
  );

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { busy, result, error, upload, reset };
}
