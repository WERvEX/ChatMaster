import { useEffect, useState } from "react";
import { getIdentities } from "../api/client";
import type { IdentityOut } from "../types/api";

export function useIdentities() {
  const [identities, setIdentities] = useState<IdentityOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getIdentities()
      .then(setIdentities)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  return { identities, loading, error };
}
