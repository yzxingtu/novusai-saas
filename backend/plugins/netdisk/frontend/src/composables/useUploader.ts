/**
 * 分片上传管理器 — 支持暂停/继续/取消
 * 每个文件独立上传通道：init → uploadPart → complete
 */

import { useNetDiskStore } from './useNetDiskStore';
import type { UploadTask } from './useNetDiskStore';
import {
  initUploadApi,
  uploadPartApi,
  completeUploadApi,
  getUploadStatusApi,
} from '../api/netdisk';

const pausedIds    = new Set<string>();
const cancelledIds = new Set<string>();

export function useUploader() {
  const {
    addUploadTask,
    updateUploadTask,
    removeUploadTask,
    uploadQueue,
    refreshDir,
  } = useNetDiskStore();

  async function uploadFile(file: File, parentId: number | null): Promise<void> {
    const taskId = `upload-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    const task: UploadTask = {
      id: taskId,
      filename: file.name,
      sizeBytes: file.size,
      progress: 0,
      speed: 0,
      status: 'pending',
    };
    addUploadTask(task);

    try {
      // 1. 初始化上传会话
      const initRes = await initUploadApi({
        filename: file.name,
        size: file.size,
        parent_id: parentId,
      });
      const { uploadId, chunkSize } = (initRes as { data: { uploadId: string; chunkSize: number; totalSize: number } }).data ?? {};
      if (!uploadId) throw new Error('uploadId missing from server response');

      updateUploadTask(taskId, { status: 'uploading' });

      // 2. 获取已上传分片（断点续传）
      let uploadedParts: number[] = [];
      try {
        const statusRes = await getUploadStatusApi(uploadId);
        uploadedParts = (statusRes as { data: { uploaded_parts: number[] } }).data?.uploaded_parts ?? [];
      } catch {
        // 忽略 — 从第 1 片开始
      }

      const totalChunks = Math.ceil(file.size / chunkSize);
      let uploadedBytes = uploadedParts.reduce((acc, p) => {
        const start = (p - 1) * chunkSize;
        return acc + Math.min(chunkSize, file.size - start);
      }, 0);
      let lastTs = Date.now();

      // 3. 逐片上传
      for (let partNo = 1; partNo <= totalChunks; partNo++) {
        if (cancelledIds.has(taskId)) {
          cancelledIds.delete(taskId);
          updateUploadTask(taskId, { status: 'error', errorMsg: 'Cancelled' });
          return;
        }

        if (uploadedParts.includes(partNo)) {
          const partBytes = Math.min(chunkSize, file.size - (partNo - 1) * chunkSize);
          uploadedBytes += partBytes;
          updateUploadTask(taskId, {
            progress: Math.round((uploadedBytes / file.size) * 100),
          });
          continue;
        }

        // 暂停等待
        while (pausedIds.has(taskId)) {
          updateUploadTask(taskId, { status: 'paused', speed: 0 });
          await new Promise<void>(r => setTimeout(r, 400));
          if (cancelledIds.has(taskId)) {
            cancelledIds.delete(taskId);
            pausedIds.delete(taskId);
            updateUploadTask(taskId, { status: 'error', errorMsg: 'Cancelled' });
            return;
          }
        }
        updateUploadTask(taskId, { status: 'uploading' });

        const start = (partNo - 1) * chunkSize;
        const chunk = file.slice(start, start + chunkSize);

        await uploadPartApi(uploadId, partNo, chunk);

        const partBytes = chunk.size;
        uploadedBytes += partBytes;
        const now = Date.now();
        const elapsed = Math.max((now - lastTs) / 1000, 0.01);
        const speed   = partBytes / elapsed;
        lastTs = now;

        updateUploadTask(taskId, {
          progress: Math.round((uploadedBytes / file.size) * 100),
          speed,
        });
      }

      // 4. 合并分片
      await completeUploadApi(uploadId);
      updateUploadTask(taskId, { status: 'done', progress: 100, speed: 0 });
      await refreshDir();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      updateUploadTask(taskId, { status: 'error', errorMsg: msg });
    }
  }

  function addFiles(files: FileList | File[], parentId: number | null): void {
    Array.from(files).forEach(f => { void uploadFile(f, parentId); });
  }

  function pause(id: string): void  { pausedIds.add(id); }
  function resume(id: string): void { pausedIds.delete(id); }
  function cancel(id: string): void { cancelledIds.add(id); pausedIds.delete(id); }

  function clearDone(): void {
    const done = uploadQueue.value
      .filter(t => t.status === 'done' || t.status === 'error')
      .map(t => t.id);
    done.forEach(id => removeUploadTask(id));
  }

  return { addFiles, pause, resume, cancel, clearDone };
}
