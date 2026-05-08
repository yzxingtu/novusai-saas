// 中文: 测试类型 behavioral，覆盖回收站清理 API 参数映射。
// EN: Test type behavioral, covering recycle-bin cleanup API parameter mapping.
// 中文: Mock 请求传输层，真实运行 API 适配映射。
// EN: Mock request transport while running the real API adapter mapping.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { triggerRecycleBinCleanupApi } from '../recycle-bin';

const { requestDeleteMock } = vi.hoisted(() => ({
  requestDeleteMock: vi.fn(),
}));

vi.mock('#/utils/request', () => ({
  requestClient: {
    delete: requestDeleteMock,
  },
}));

describe('recycle bin api', () => {
  beforeEach(() => {
    requestDeleteMock.mockReset();
  });

  it('serializes cleanup retention as explicit stage parameters', async () => {
    requestDeleteMock.mockResolvedValue({ task_id: 'cleanup-task' });

    await triggerRecycleBinCleanupApi({
      moduleRetentionDays: 15,
      globalRetentionDays: 45,
    });

    expect(requestDeleteMock).toHaveBeenCalledWith('/admin/recycle-bin/cleanup', {
      params: {
        module_retention_days: 15,
        global_retention_days: 45,
      },
    });
  });

  it('does not send retired retention_days parameter', async () => {
    requestDeleteMock.mockResolvedValue({ task_id: 'cleanup-task' });

    await triggerRecycleBinCleanupApi();

    expect(requestDeleteMock).toHaveBeenCalledWith('/admin/recycle-bin/cleanup', {
      params: {},
    });
    expect(
      JSON.stringify(requestDeleteMock.mock.calls[0]?.[1] ?? {}),
    ).not.toContain('retention_days');
  });
});
