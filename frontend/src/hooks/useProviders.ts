import { useCallback, useEffect, useState } from "react";
import { getProviders, saveProviders, testProviders } from "../api/client";
import type { ProvidersConfig, ProviderTestResult } from "../types/api";

const empty: ProvidersConfig = {
  chat: { provider: "openai", base_url: "", api_key: "", model: "" },
  embedding: {
    provider: "huggingface",
    base_url: "",
    api_key: "",
    model: "",
    huggingface_endpoint: "",
  },
};

export function useProviders() {
  const [config, setConfig] = useState<ProvidersConfig>(empty);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<ProviderTestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    getProviders()
      .then((c) => {
        setConfig(c);
        setDirty(false);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const update = useCallback((next: ProvidersConfig) => {
    setConfig(next);
    setDirty(true);
    setError(null);
  }, []);

  const save = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      const saved = await saveProviders(config);
      setConfig(saved);
      setDirty(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }, [config]);

  const test = useCallback(async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      // Test against the currently SAVED config (save first if there are edits).
      if (dirty) await save();
      setTestResult(await testProviders());
    } catch (e) {
      setError(String(e));
    } finally {
      setTesting(false);
    }
  }, [dirty, save]);

  return { config, loading, saving, testing, error, testResult, dirty, update, save, test };
}
