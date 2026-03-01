/**
 * NovusDoc Pro 功能检测 composable
 *
 * 检测 novusdoc-pro 插件是否已加载，若是则暴露 Pro 功能 API。
 * 基础版编辑器通过此 composable 有条件地显示 Pro 功能按钮。
 *
 * 检测方式：window.NovusPlugin_novusdoc_pro（由 plugin-loader 暴露）
 */

import { ref, computed } from 'vue';
import type { VersionItem, CommentItem } from '../api/pro';
import {
  listVersionsApi,
  createVersionApi,
  restoreVersionApi,
  listCommentsApi,
  createCommentApi,
  resolveCommentApi,
  createShareApi,
  exportWordApi,
  exportPdfApi,
} from '../api/pro';

function isProLoaded(): boolean {
  const w = window as unknown as Record<string, unknown>;
  const proMod = w.NovusPlugin_novusdoc_pro as Record<string, unknown> | undefined;
  return !!proMod?.CollabClient;
}

export interface UseProFeaturesReturn {
  /** Pro 插件是否可用 */
  proAvailable: ReturnType<typeof computed<boolean>>;
  /** 版本历史列表 */
  versions: ReturnType<typeof ref<VersionItem[]>>;
  /** 评论列表 */
  comments: ReturnType<typeof ref<CommentItem[]>>;
  /** 加载状态 */
  loading: ReturnType<typeof ref<boolean>>;

  /** 加载版本历史 */
  loadVersions: (docId: number) => Promise<void>;
  /** 创建版本快照 */
  createVersion: (docId: number, data: Record<string, unknown>) => Promise<void>;
  /** 恢复版本 */
  restoreVersion: (docId: number, versionId: number) => Promise<boolean>;
  /** 加载评论 */
  loadComments: (docId: number) => Promise<void>;
  /** 创建评论 */
  addComment: (docId: number, data: Record<string, unknown>) => Promise<void>;
  /** 标记评论已解决 */
  resolveComment: (docId: number, commentId: number) => Promise<void>;
  /** 创建分享链接 */
  createShare: (docId: number, permission?: string) => Promise<string | null>;
  /** 导出 Word */
  exportWord: (docId: number, title: string) => Promise<void>;
  /** 导出 PDF */
  exportPdf: (docId: number, title: string) => Promise<void>;
}

export function useProFeatures(): UseProFeaturesReturn {
  const proAvailable = computed(() => isProLoaded());
  const versions = ref<VersionItem[]>([]);
  const comments = ref<CommentItem[]>([]);
  const loading = ref(false);

  async function loadVersions(docId: number) {
    if (!proAvailable.value) return;
    loading.value = true;
    try {
      const resp = await listVersionsApi(docId);
      versions.value = resp?.items ?? [];
    } catch {
      versions.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function createVersion(docId: number, data: Record<string, unknown>) {
    if (!proAvailable.value) return;
    await createVersionApi(docId, data);
  }

  async function restoreVersion(docId: number, versionId: number): Promise<boolean> {
    if (!proAvailable.value) return false;
    try {
      await restoreVersionApi(docId, versionId);
      return true;
    } catch {
      return false;
    }
  }

  async function loadComments(docId: number) {
    if (!proAvailable.value) return;
    loading.value = true;
    try {
      const resp = await listCommentsApi(docId);
      comments.value = resp?.items ?? [];
    } catch {
      comments.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function addComment(docId: number, data: Record<string, unknown>) {
    if (!proAvailable.value) return;
    await createCommentApi(docId, data);
  }

  async function resolveComment(docId: number, commentId: number) {
    if (!proAvailable.value) return;
    await resolveCommentApi(docId, commentId);
  }

  async function createShare(docId: number, permission = 'viewer', expiresInHours = 72): Promise<string | null> {
    if (!proAvailable.value) return null;
    try {
      const resp = await createShareApi(docId, { permission, expires_in_hours: expiresInHours });
      return resp?.token ?? null;
    } catch {
      return null;
    }
  }

  async function exportWord(docId: number, title: string) {
    if (!proAvailable.value) return;
    try {
      const blob = await exportWordApi(docId) as unknown as Blob;
      _downloadBlob(blob, `${title || 'document'}.docx`);
    } catch {
      // handled by global interceptor
    }
  }

  async function exportPdf(docId: number, title: string) {
    if (!proAvailable.value) return;
    try {
      const blob = await exportPdfApi(docId) as unknown as Blob;
      _downloadBlob(blob, `${title || 'document'}.pdf`);
    } catch {
      // handled by global interceptor
    }
  }

  return {
    proAvailable,
    versions,
    comments,
    loading,
    loadVersions,
    createVersion,
    restoreVersion,
    loadComments,
    addComment,
    resolveComment,
    createShare,
    exportWord,
    exportPdf,
  };
}

function _downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
