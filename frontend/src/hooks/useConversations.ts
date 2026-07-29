import { useCallback, useEffect, useState } from "react";
import {
  createConversation,
  deleteConversation,
  getConversations,
  updateConversation,
} from "../api/client";
import type { ConversationOut } from "../types/api";

const STORAGE_KEY = "chatmaster:conversation";

function storageKey(identityId: string) {
  return `${STORAGE_KEY}:${identityId}`;
}

export function readStoredConversationId(identityId: string): string | null {
  try {
    return localStorage.getItem(storageKey(identityId));
  } catch {
    return null;
  }
}

export function writeStoredConversationId(identityId: string, conversationId: string | null) {
  try {
    if (conversationId) {
      localStorage.setItem(storageKey(identityId), conversationId);
    } else {
      localStorage.removeItem(storageKey(identityId));
    }
  } catch {
    // ignore quota / private mode errors
  }
}

export function useConversations(identityId: string | null) {
  const [conversations, setConversations] = useState<ConversationOut[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!identityId) {
      setConversations([]);
      setActiveId(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const items = await getConversations(identityId);
      setConversations(items);
      const stored = readStoredConversationId(identityId);
      const next =
        (stored && items.some((item) => item.id === stored) && stored) ||
        items[0]?.id ||
        null;
      setActiveId(next);
      if (next) {
        writeStoredConversationId(identityId, next);
      }
    } catch (e) {
      setError(String(e));
      setConversations([]);
      setActiveId(null);
    } finally {
      setLoading(false);
    }
  }, [identityId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectConversation = useCallback(
    (conversationId: string) => {
      if (!identityId) return;
      setActiveId(conversationId);
      writeStoredConversationId(identityId, conversationId);
    },
    [identityId]
  );

  const startConversation = useCallback(
    async (title?: string) => {
      if (!identityId) return null;
      const created = await createConversation(identityId, title);
      setConversations((items) => [created, ...items]);
      setActiveId(created.id);
      writeStoredConversationId(identityId, created.id);
      return created;
    },
    [identityId]
  );

  const removeConversation = useCallback(
    async (conversationId: string) => {
      if (!identityId) return;
      setError(null);
      try {
        await deleteConversation(conversationId);
        setConversations((items) => {
          const remaining = items.filter((item) => item.id !== conversationId);
          if (activeId === conversationId) {
            const next = remaining[0]?.id ?? null;
            setActiveId(next);
            writeStoredConversationId(identityId, next);
          }
          return remaining;
        });
      } catch (e) {
        setError(String(e));
      }
    },
    [activeId, identityId]
  );

  const deleteActiveConversation = useCallback(async () => {
    if (!activeId) return;
    await removeConversation(activeId);
  }, [activeId, removeConversation]);

  const renameConversation = useCallback(async (conversationId: string, title: string) => {
    setError(null);
    try {
      const updated = await updateConversation(conversationId, title);
      setConversations((items) =>
        items.map((item) => (item.id === updated.id ? updated : item))
      );
    } catch (e) {
      setError(String(e));
      throw e;
    }
  }, []);

  return {
    conversations,
    activeId,
    loading,
    error,
    refresh,
    selectConversation,
    startConversation,
    removeConversation,
    deleteActiveConversation,
    renameConversation,
    setActiveId,
  };
}
