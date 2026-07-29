import { useCallback, useEffect, useState } from "react";
import {
  archiveIdentity,
  createIdentity,
  duplicateIdentity,
  getIdentities,
  restoreIdentity,
  updateIdentity,
} from "../api/client";
import type { IdentityOut, IdentityPayload } from "../types/api";

export function useIdentities() {
  const [identities, setIdentities] = useState<IdentityOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setIdentities(await getIdentities(true));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const runAndRefresh = useCallback(
    async <T,>(action: () => Promise<T>) => {
      const result = await action();
      await refresh();
      return result;
    },
    [refresh]
  );

  return {
    identities,
    loading,
    error,
    refresh,
    create: (payload: IdentityPayload) => runAndRefresh(() => createIdentity(payload)),
    update: (id: string, payload: IdentityPayload) =>
      runAndRefresh(() => updateIdentity(id, payload)),
    archive: (id: string) => runAndRefresh(() => archiveIdentity(id)),
    restore: (id: string) => runAndRefresh(() => restoreIdentity(id)),
    duplicate: (id: string) => runAndRefresh(() => duplicateIdentity(id)),
  };
}
