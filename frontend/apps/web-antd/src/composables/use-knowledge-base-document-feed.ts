import type { Ref } from 'vue';

import { ref } from 'vue';

import { fetchKnowledgeBaseDocumentProgress } from './use-knowledge-base-detail-tools';

export interface KnowledgeBaseDocumentFeedProgress {
  processed_chunks: number;
  progress: number;
  stage: string;
  total_chunks: number;
}

interface KnowledgeBaseDocumentFeedOptions<
  TDoc extends { id: number; status: string },
> {
  getDocumentProgress: (
    kbId: number,
    docId: number,
  ) => Promise<KnowledgeBaseDocumentFeedProgress>;
  kbId: Ref<number>;
  listDocuments: (
    kbId: number,
    params: Record<string, number | string>,
  ) => Promise<{ items: TDoc[]; total: number }>;
  onTerminalStatus?: () => void;
  socketStore: {
    registerHandler: (
      event: string,
      handler: (payload: unknown) => void,
    ) => void;
    unregisterHandler: (
      event: string,
      handler: (payload: unknown) => void,
    ) => void;
  };
}

export function useKnowledgeBaseDocumentFeed<
  TDoc extends { id: number; status: string },
>(options: KnowledgeBaseDocumentFeedOptions<TDoc>) {
  const documents = ref<TDoc[]>([]);
  const docPage = ref(1);
  const docProgress = ref<Record<number, KnowledgeBaseDocumentFeedProgress>>(
    {},
  );
  const docTotal = ref(0);
  const loading = ref(false);

  function handleWsNotification(payload: unknown) {
    const msg = payload as Record<string, unknown>;
    if (msg?.type !== 'ai.kb_doc_progress') return;

    const data = msg.data as Record<string, unknown>;
    if (!data?.document_id) return;

    const docId = data.document_id as number;
    const kbIdFromWs = data.kb_id as number;

    if (kbIdFromWs && kbIdFromWs !== options.kbId.value) return;

    const progress: KnowledgeBaseDocumentFeedProgress = {
      stage: (data.stage as string) || 'pending',
      progress: (data.progress as number) || 0,
      total_chunks: (data.total_chunks as number) || 0,
      processed_chunks: (data.processed_chunks as number) || 0,
    };

    docProgress.value[docId] = progress;

    const found = documents.value.find((doc) => doc.id === docId);
    if (found && progress.stage && progress.stage !== found.status) {
      found.status = progress.stage;
    }

    if (['completed', 'error'].includes(progress.stage)) {
      void loadDocuments();
      options.onTerminalStatus?.();
    }
  }

  async function fetchInitialProgress() {
    await fetchKnowledgeBaseDocumentProgress(documents.value, {
      kbId: options.kbId.value,
      getProgress: options.getDocumentProgress,
      progressMap: docProgress,
    });
  }

  async function loadDocuments() {
    loading.value = true;
    try {
      const response = await options.listDocuments(options.kbId.value, {
        'page[number]': docPage.value,
        'page[size]': 20,
        sort: '-created_at',
      });
      documents.value = response.items;
      docTotal.value = response.total;
      startWsListener();
      await fetchInitialProgress();
    } finally {
      loading.value = false;
    }
  }

  function startWsListener() {
    options.socketStore.unregisterHandler('notification', handleWsNotification);
    options.socketStore.registerHandler('notification', handleWsNotification);
  }

  function stopWsListener() {
    options.socketStore.unregisterHandler('notification', handleWsNotification);
  }

  return {
    docPage,
    docProgress,
    docTotal,
    documents,
    fetchInitialProgress,
    handleWsNotification,
    loadDocuments,
    loading,
    startWsListener,
    stopWsListener,
  };
}
