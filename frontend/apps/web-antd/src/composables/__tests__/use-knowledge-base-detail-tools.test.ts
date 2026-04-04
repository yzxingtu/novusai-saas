import { ref } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import {
  fetchKnowledgeBaseDocumentProgress,
  getKnowledgeBaseFileIcon,
  getKnowledgeBaseFileIconBg,
  getKnowledgeBaseFileIconColor,
  useKnowledgeBaseChunkPreview,
  useKnowledgeBaseSearch,
} from '../use-knowledge-base-detail-tools';

describe('use-knowledge-base-detail-tools', () => {
  it('maps file icon helpers by file type', () => {
    expect(getKnowledgeBaseFileIcon('pdf')).toBe('lucide:file-text');
    expect(getKnowledgeBaseFileIconBg('qa')).toBe('bg-cyan-500/10');
    expect(getKnowledgeBaseFileIconColor('xlsx')).toBe('text-green-500');
  });

  it('loads progress only for processing documents', async () => {
    const docs = [
      { id: 1, status: 'chunking' },
      { id: 2, status: 'completed' },
    ];
    const progressMap = ref({});
    const getProgress = vi.fn().mockResolvedValue({
      stage: 'embedding',
      progress: 60,
      total_chunks: 3,
      processed_chunks: 2,
    });

    await fetchKnowledgeBaseDocumentProgress(docs, {
      kbId: 9,
      getProgress,
      progressMap,
    });

    expect(getProgress).toHaveBeenCalledOnce();
    expect(progressMap.value).toEqual({
      1: {
        stage: 'embedding',
        progress: 60,
        total_chunks: 3,
        processed_chunks: 2,
      },
    });
    expect(docs[0]?.status).toBe('embedding');
  });

  it('manages search and chunk preview state with injected APIs', async () => {
    const kbId = ref(12);
    const search = vi.fn().mockResolvedValue([{ chunk_id: 3 }]);
    const getChunks = vi.fn().mockResolvedValue({
      chunks: [{ id: 7 }],
      total: 1,
    });

    const searchState = useKnowledgeBaseSearch({
      kbId,
      search,
    });
    searchState.searchQuery.value = 'hello';
    await searchState.handleSearch();

    expect(search).toHaveBeenCalledWith(12, {
      query: 'hello',
      top_k: 5,
      score_threshold: 0.5,
      search_mode: 'hybrid',
    });
    expect(searchState.searchResults.value).toEqual([{ chunk_id: 3 }]);

    const chunkState = useKnowledgeBaseChunkPreview({
      kbId,
      getChunks,
    });
    await chunkState.openChunkPreview({ id: 7 });

    expect(getChunks).toHaveBeenCalledWith(12, 7, {
      page: 1,
      page_size: 10,
    });
    expect(chunkState.chunkList.value).toEqual([{ id: 7 }]);
    expect(chunkState.chunkTotal.value).toBe(1);
  });
});
