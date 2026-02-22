/**
 * 富文本编辑器 API composable
 *
 * 封装文档 CRUD、版本管理、协作者管理、自动保存等 API 调用
 */
import { requestClient } from '#/utils/request';

const BASE = '/tenant/plugins/rich-editor';

export function useRichEditorApi() {
  /** 获取插件配置 */
  async function getConfig() {
    return requestClient.get(`${BASE}/config`);
  }

  /** 文档列表 */
  async function listDocuments(params?: Record<string, string>) {
    return requestClient.get(`${BASE}/documents`, { params });
  }

  /** 创建文档 */
  async function createDocument(data: Record<string, unknown>) {
    return requestClient.post(`${BASE}/documents`, data);
  }

  /** 获取文档详情 */
  async function getDocument(id: number) {
    return requestClient.get(`${BASE}/documents/${id}`);
  }

  /** 更新文档 */
  async function updateDocument(id: number, data: Record<string, unknown>) {
    return requestClient.put(`${BASE}/documents/${id}`, data);
  }

  /** 自动保存 */
  async function autoSave(
    id: number,
    data: {
      content_html: string;
      content_json?: Record<string, unknown> | null;
      word_count: number;
      character_count: number;
      version: number;
    },
  ) {
    return requestClient.post(`${BASE}/documents/${id}/auto-save`, data);
  }

  /** 删除文档 */
  async function deleteDocument(id: number) {
    return requestClient.delete(`${BASE}/documents/${id}`);
  }

  /** 获取版本历史 */
  async function listVersions(id: number) {
    return requestClient.get(`${BASE}/documents/${id}/versions`);
  }

  /** 创建版本快照 */
  async function createVersion(
    id: number,
    data?: { change_summary?: string },
  ) {
    return requestClient.post(`${BASE}/documents/${id}/versions`, data || {});
  }

  /** 恢复版本 */
  async function restoreVersion(documentId: number, versionId: number) {
    return requestClient.post(
      `${BASE}/documents/${documentId}/restore/${versionId}`,
    );
  }

  /** 获取协作者列表 */
  async function listCollaborators(id: number) {
    return requestClient.get(`${BASE}/documents/${id}/collaborators`);
  }

  /** 添加协作者 */
  async function addCollaborator(
    id: number,
    data: { user_id: number; user_type?: string; role?: string },
  ) {
    return requestClient.post(`${BASE}/documents/${id}/collaborators`, data);
  }

  /** 移除协作者 */
  async function removeCollaborator(documentId: number, userId: number) {
    return requestClient.delete(
      `${BASE}/documents/${documentId}/collaborators/${userId}`,
    );
  }

  /** 复制文档 */
  async function duplicateDocument(id: number) {
    return requestClient.post(`${BASE}/documents/${id}/duplicate`);
  }

  /** 移动文档到文件夹 */
  async function moveDocument(
    id: number,
    data: { folder_id: number | null },
  ) {
    return requestClient.post(`${BASE}/documents/${id}/move`, data);
  }

  return {
    getConfig,
    listDocuments,
    createDocument,
    getDocument,
    updateDocument,
    autoSave,
    deleteDocument,
    listVersions,
    createVersion,
    restoreVersion,
    listCollaborators,
    addCollaborator,
    removeCollaborator,
    duplicateDocument,
    moveDocument,
  };
}
