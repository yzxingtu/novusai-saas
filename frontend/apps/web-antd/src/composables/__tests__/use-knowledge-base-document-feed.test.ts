import { ref } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import { useKnowledgeBaseDocumentFeed } from '../use-knowledge-base-document-feed';

describe('use-knowledge-base-document-feed', () => {
  it('loads documents, tracks progress, and refreshes on terminal ws status', async () => {
    const registerHandler = vi.fn();
    const unregisterHandler = vi.fn();
    const onTerminalStatus = vi.fn();
    const listDocuments = vi.fn().mockResolvedValue({
      items: [{ id: 1, status: 'chunking' }],
      total: 1,
    });
    const getDocumentProgress = vi.fn().mockResolvedValue({
      stage: 'embedding',
      progress: 60,
      total_chunks: 3,
      processed_chunks: 2,
    });

    const feed = useKnowledgeBaseDocumentFeed({
      kbId: ref(9),
      listDocuments,
      getDocumentProgress,
      onTerminalStatus,
      socketStore: {
        registerHandler,
        unregisterHandler,
      },
    });

    await feed.loadDocuments();

    expect(listDocuments).toHaveBeenCalledWith(9, {
      'page[number]': 1,
      'page[size]': 20,
      sort: '-created_at',
    });
    expect(feed.documents.value[0]?.status).toBe('embedding');
    expect(registerHandler).toHaveBeenCalled();

    feed.handleWsNotification({
      type: 'ai.kb_doc_progress',
      data: {
        document_id: 1,
        kb_id: 9,
        stage: 'completed',
        progress: 100,
        total_chunks: 3,
        processed_chunks: 3,
      },
    });

    await Promise.resolve();
    expect(onTerminalStatus).toHaveBeenCalled();
  });
});
