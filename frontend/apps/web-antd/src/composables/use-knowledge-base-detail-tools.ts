import type { Ref } from 'vue';

import { ref } from 'vue';

import { $t } from '#/locales';

export interface KnowledgeBaseDocProgressInfo {
  processed_chunks: number;
  progress: number;
  stage: string;
  total_chunks: number;
}

export function getKnowledgeBaseFileIcon(fileType: string): string {
  const type = (fileType || '').toLowerCase();
  if (type === 'pdf') return 'lucide:file-text';
  if (['doc', 'docx'].includes(type)) return 'lucide:file-type';
  if (['csv', 'xls', 'xlsx'].includes(type)) return 'lucide:sheet';
  if (['md', 'txt'].includes(type)) return 'lucide:file-code';
  if (type === 'url') return 'lucide:globe';
  if (type === 'qa') return 'lucide:message-circle-question';
  return 'lucide:file';
}

export function getKnowledgeBaseFileIconBg(fileType: string): string {
  const type = (fileType || '').toLowerCase();
  if (type === 'pdf') return 'bg-red-500/10';
  if (['doc', 'docx'].includes(type)) return 'bg-blue-500/10';
  if (['csv', 'xls', 'xlsx'].includes(type)) return 'bg-green-500/10';
  if (['md', 'txt'].includes(type)) return 'bg-amber-500/10';
  if (type === 'url') return 'bg-purple-500/10';
  if (type === 'qa') return 'bg-cyan-500/10';
  return 'bg-muted';
}

export function getKnowledgeBaseFileIconColor(fileType: string): string {
  const type = (fileType || '').toLowerCase();
  if (type === 'pdf') return 'text-red-500';
  if (['doc', 'docx'].includes(type)) return 'text-blue-500';
  if (['csv', 'xls', 'xlsx'].includes(type)) return 'text-green-500';
  if (['md', 'txt'].includes(type)) return 'text-amber-500';
  if (type === 'url') return 'text-purple-500';
  if (type === 'qa') return 'text-cyan-500';
  return 'text-muted-foreground';
}

export function getKnowledgeBaseDocStatusText(
  i18nPrefix: string,
  status: string | undefined,
): string {
  if (!status) return '-';
  return $t(`${i18nPrefix}.document.status.${status}`);
}

export function getKnowledgeBaseDocStatusColor(
  status: string | undefined,
): string {
  switch (status) {
    case 'chunking':
    case 'embedding':
    case 'parsing': {
      return 'processing';
    }
    case 'completed': {
      return 'success';
    }
    case 'error': {
      return 'error';
    }
    case 'pending': {
      return 'default';
    }
    default: {
      return 'default';
    }
  }
}

export async function fetchKnowledgeBaseDocumentProgress<
  TDoc extends { id: number; status: string },
>(
  docs: TDoc[],
  opts: {
    getProgress: (
      kbId: number,
      docId: number,
    ) => Promise<KnowledgeBaseDocProgressInfo>;
    kbId: number;
    progressMap: Ref<Record<number, KnowledgeBaseDocProgressInfo>>;
  },
) {
  const processingDocs = docs.filter(
    (doc) => !['completed', 'error', 'pending'].includes(doc.status),
  );
  for (const doc of processingDocs) {
    try {
      const progress = await opts.getProgress(opts.kbId, doc.id);
      opts.progressMap.value[doc.id] = progress;
      if (progress.stage && progress.stage !== doc.status) {
        doc.status = progress.stage;
      }
    } catch {
      // ignore / 忽略单条进度拉取失败
    }
  }
}

export function useKnowledgeBaseChunkPreview<
  TDoc extends { id: number },
  TChunk extends { id: number },
>(opts: {
  getChunks: (
    kbId: number,
    docId: number,
    params: { page: number; page_size: number },
  ) => Promise<{ chunks: TChunk[]; total: number }>;
  kbId: Ref<number>;
}) {
  const chunkPreviewVisible = ref(false);
  const chunkPreviewDoc = ref<null | TDoc>(null);
  const chunkList = ref<TChunk[]>([]);
  const chunkLoading = ref(false);
  const chunkPage = ref(1);
  const chunkTotal = ref(0);

  async function loadChunks() {
    if (!chunkPreviewDoc.value) return;
    chunkLoading.value = true;
    try {
      const response = await opts.getChunks(
        opts.kbId.value,
        chunkPreviewDoc.value.id,
        { page: chunkPage.value, page_size: 10 },
      );
      chunkList.value = response.chunks;
      chunkTotal.value = response.total;
    } catch {
      chunkList.value = [];
    } finally {
      chunkLoading.value = false;
    }
  }

  async function openChunkPreview(doc: TDoc) {
    chunkPreviewDoc.value = doc;
    chunkPage.value = 1;
    chunkPreviewVisible.value = true;
    await loadChunks();
  }

  return {
    chunkList,
    chunkLoading,
    chunkPage,
    chunkPreviewDoc,
    chunkPreviewVisible,
    chunkTotal,
    loadChunks,
    openChunkPreview,
  };
}

export function useKnowledgeBaseSearch<TResult>(opts: {
  defaultSearchMode?: string;
  kbId: Ref<number>;
  search: (
    kbId: number,
    payload: {
      query: string;
      score_threshold: number;
      search_mode: string;
      top_k: number;
    },
  ) => Promise<TResult[]>;
}) {
  const searchLoading = ref(false);
  const searchMode = ref(opts.defaultSearchMode ?? 'hybrid');
  const searchQuery = ref('');
  const searchResults = ref<TResult[]>([]);
  const searchScoreThreshold = ref(0.5);
  const searchTopK = ref(5);

  async function handleSearch() {
    if (!searchQuery.value.trim()) return;
    searchLoading.value = true;
    try {
      searchResults.value = await opts.search(opts.kbId.value, {
        query: searchQuery.value.trim(),
        top_k: searchTopK.value,
        score_threshold: searchScoreThreshold.value,
        search_mode: searchMode.value,
      });
    } catch {
      // handled by request interceptor / 错误由请求拦截器处理
    } finally {
      searchLoading.value = false;
    }
  }

  return {
    handleSearch,
    searchLoading,
    searchMode,
    searchQuery,
    searchResults,
    searchScoreThreshold,
    searchTopK,
  };
}
