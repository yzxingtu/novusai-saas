/**
 * N15b: useFileUpload composable
 * - 小文件 (< CHUNK_SIZE) → 整文件上传
 * - 大文件 (≥ CHUNK_SIZE) → 分片上传，并发 3 片
 * - 断点续传：先查 /upload/status/{id} 跳过已上传分片
 * - 上传队列：pending → uploading → paused | done | error
 */

import { ref } from 'vue';
import type { UploadTask } from './useNetDiskStore';
import {
  getUploadStatusApi,
  initUploadApi,
  uploadPartApi,
  completeUploadApi,
} from '../api/netdisk';

const _t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

/** 小于此大小走整文件上传，否则分片 */
const CHUNK_SIZE = 5 * 1024 * 1024;    // 5 MB
const MAX_CONCURRENCY = 3;             // 分片并发数
const MAX_QUEUE_SIZE  = 5;             // 最大并发文件数

export function useFileUpload(
  currentParentId: { value: number | null },
  onComplete: (parentId: number | null) => void,
) {
  const queue = ref<UploadTask[]>([]);

  const getClient = () => {
    const shared = (window as unknown as { NovusPluginShared?: { requestClient?: unknown } }).NovusPluginShared;
    return shared?.requestClient as {
      post: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
      get:  <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    };
  };

  // ── 检查配额 ──────────────────────────────────────────────
  async function checkQuota(size: number): Promise<boolean> {
    try {
      const r = await getClient().get<{ data: { freeBytes: number } }>(
        '/tenant/plugins/netdisk/api/quota'
      );
      return r.data.freeBytes >= size;
    } catch { return true; }  // 检查失败时允许上传，后端二次校验
  }

  // ── 添加文件到队列 ────────────────────────────────────────
  async function addFiles(files: File[]) {
    for (const file of files) {
      const task: UploadTask = {
        id:        crypto.randomUUID?.() ?? String(Date.now() + Math.random()),
        filename:  file.name,
        sizeBytes: file.size,
        progress:  0,
        speed:     0,
        status:    'pending',
      };
      queue.value.push(task);
    }
    drainQueue(files);
  }

  // ── 队列调度 ──────────────────────────────────────────────
  function drainQueue(files: File[]) {
    const active = queue.value.filter(t => t.status === 'uploading').length;
    const slots  = MAX_QUEUE_SIZE - active;
    if (slots <= 0) return;

    const pending = queue.value.filter(t => t.status === 'pending').slice(0, slots);
    for (const task of pending) {
      const file = files.find(f => f.name === task.filename);
      if (file) startUpload(task, file);
    }
  }

  // ── 单文件上传入口 ────────────────────────────────────────
  async function startUpload(task: UploadTask, file: File) {
    task.status = 'uploading';

    // 配额检查
    const hasQuota = await checkQuota(file.size);
    if (!hasQuota) {
      task.status  = 'error';
      task.errorMsg = _t('plugin.netdisk.error.quota_insufficient');
      return;
    }

    try {
      if (file.size < CHUNK_SIZE) {
        await uploadWhole(task, file);
      } else {
        await uploadMultipart(task, file);
      }
      task.status   = 'done';
      task.progress = 100;
      onComplete(currentParentId.value);
    } catch (e) {
      task.status   = 'error';
      task.errorMsg = e instanceof Error ? e.message : _t('plugin.netdisk.error.upload_failed');
    }
  }

  // ── 整文件上传 ────────────────────────────────────────────
  async function uploadWhole(task: UploadTask, file: File) {
    const form = new FormData();
    form.append('file', file);
    if (currentParentId.value !== null) {
      form.append('parent_id', String(currentParentId.value));
    }

    const startTime = Date.now();
    const xhr = new XMLHttpRequest();

    await new Promise<void>((resolve, reject) => {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          task.progress = Math.round(e.loaded / e.total * 100);
          const elapsed = (Date.now() - startTime) / 1000;
          task.speed    = elapsed > 0 ? Math.round(e.loaded / elapsed) : 0;
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve();
        else reject(new Error(`HTTP ${xhr.status}`));
      };
      xhr.onerror = () => reject(new Error(_t('plugin.netdisk.error.network_error')));

      xhr.open('POST', '/tenant/plugins/netdisk/api/upload');
      xhr.withCredentials = true;
      xhr.send(form);
    });
  }

  // ── 分片上传 ──────────────────────────────────────────────
  async function uploadMultipart(task: UploadTask, file: File) {
    const totalParts = Math.ceil(file.size / CHUNK_SIZE);

    // 1. 初始化（或断点续传）
    let uploadId: string;
    let completedParts = new Set<number>();

    const initResp = await initUploadApi({
      filename: file.name,
      size:     file.size,
      parent_id: currentParentId.value,
    });
    uploadId = initResp.data.uploadId;

    // 2. 断点续传：查询已上传分片
    try {
      const statusResp = await getUploadStatusApi(uploadId);
      completedParts = new Set(statusResp.data.uploaded_parts ?? []);
    } catch { /* 没有已上传分片，从 0 开始 */ }

    // 3. 分片并发上传
    const partQueue: number[] = [];
    for (let i = 0; i < totalParts; i++) {
      if (!completedParts.has(i)) partQueue.push(i);
    }

    const startTime  = Date.now();
    let uploadedBytes = completedParts.size * CHUNK_SIZE;
    let runningCount  = 0;
    let idx           = 0;

    await new Promise<void>((resolve, reject) => {
      function launchNext() {
        while (runningCount < MAX_CONCURRENCY && idx < partQueue.length) {
          if (task.status === 'paused') return;
          const partNo = partQueue[idx++];
          runningCount++;

          const start = partNo * CHUNK_SIZE;
          const end   = Math.min(start + CHUNK_SIZE, file.size);
          const blob  = file.slice(start, end);

          uploadPartApi(uploadId, partNo, blob)
            .then(() => {
              uploadedBytes += (end - start);
              task.progress = Math.round(
                (completedParts.size * CHUNK_SIZE + uploadedBytes) / file.size * 100
              );
              const elapsed = (Date.now() - startTime) / 1000;
              task.speed    = elapsed > 0 ? Math.round(uploadedBytes / elapsed) : 0;
              runningCount--;
              if (idx < partQueue.length) launchNext();
              else if (runningCount === 0) resolve();
            })
            .catch(reject);
        }
      }
      launchNext();
      if (partQueue.length === 0) resolve();
    });

    // 4. 合并分片
    await completeUploadApi(uploadId);
  }

  // ── 控制函数 ──────────────────────────────────────────────
  function pauseTask(taskId: string) {
    const task = queue.value.find(t => t.id === taskId);
    if (task?.status === 'uploading') task.status = 'paused';
  }

  function resumeTask(taskId: string, file: File) {
    const task = queue.value.find(t => t.id === taskId);
    if (task?.status === 'paused') startUpload(task, file);
  }

  function cancelTask(taskId: string) {
    queue.value = queue.value.filter(t => t.id !== taskId);
  }

  function clearCompleted() {
    queue.value = queue.value.filter(t => t.status !== 'done');
  }

  return {
    queue,
    addFiles,
    pauseTask,
    resumeTask,
    cancelTask,
    clearCompleted,
  };
}
