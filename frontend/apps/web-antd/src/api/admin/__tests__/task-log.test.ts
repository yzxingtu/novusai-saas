// Test type: behavioral
// 中文: 测试类型 behavioral，覆盖任务日志 API 当前 snake_case 运行键与详情合同。
// EN: Test type behavioral, covering the current snake_case task-log run-key and detail contracts.
// 中文: Mock 请求传输层，真实运行 API 适配映射。
// EN: Mock request transport while running the real API adapter mapping.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getTaskLogDetailApi,
  getTaskLogListApi,
  retryTaskApi,
} from '../task-log';

const { requestGetMock, requestPostMock } = vi.hoisted(() => ({
  requestGetMock: vi.fn(),
  requestPostMock: vi.fn(),
}));

vi.mock('#/utils/request', () => ({
  requestClient: {
    get: requestGetMock,
    post: requestPostMock,
  },
}));

describe('task log api', () => {
  beforeEach(() => {
    requestGetMock.mockReset();
    requestPostMock.mockReset();
  });

  it('normalizes list rows from the current task-run contract', async () => {
    requestGetMock.mockResolvedValue({
      items: [
        {
          id: 41,
          task_id: 'celery-41',
          run_key: 'ai-health:gpt-5.4:20260510T1200Z',
          task_name: 'AI Provider Health Check',
          handler_path: 'app.tasks.scheduled.ai_provider_health_check',
          task_definition_id: 8,
          binding_id: 12,
          task_definition_name: 'AI provider health',
          task_scope: 'all_tenants',
          owner_tenant_id: null,
          owner_tenant_name: null,
          effective_tenant_id: 3,
          effective_tenant_name: 'Acme',
          queue: 'scheduled',
          status: 'success',
          args: [],
          kwargs: { provider_id: 7 },
          result: { healthy: true },
          error_message: null,
          trigger_source: 'scheduler',
          run_kind: 'tenant_binding',
          trace_id: 'trace-41',
          started_at: '2026-05-10T12:00:01Z',
          finished_at: '2026-05-10T12:00:02Z',
          duration_ms: 1000,
          retry_count: 0,
          created_at: '2026-05-10T12:00:00Z',
        },
      ],
      page: 1,
      page_size: 20,
      total: 1,
    });

    const result = await getTaskLogListApi({
      'filter[run_key][ilike]': 'ai-health',
      view: 'execution',
    });

    expect(requestGetMock).toHaveBeenCalledWith('/admin/tasks', {
      params: {
        'filter[run_key][ilike]': 'ai-health',
        view: 'execution',
      },
    });
    expect(result.items[0]).toEqual(
      expect.objectContaining({
        id: 41,
        taskId: 'celery-41',
        runKey: 'ai-health:gpt-5.4:20260510T1200Z',
        taskName: 'AI Provider Health Check',
        handlerPath: 'app.tasks.scheduled.ai_provider_health_check',
        bindingId: 12,
        effectiveTenantId: 3,
        effectiveTenantName: 'Acme',
        result: { healthy: true },
        traceId: 'trace-41',
      }),
    );
  });

  it('normalizes detail traceback without legacy task-log aliases', async () => {
    requestGetMock.mockResolvedValue({
      id: 42,
      task_id: 'celery-42',
      run_key: null,
      task_name: 'Cleanup',
      handler_path: 'app.tasks.cleanup',
      task_definition_id: null,
      binding_id: null,
      task_definition_name: null,
      task_scope: null,
      owner_tenant_id: null,
      owner_tenant_name: null,
      effective_tenant_id: null,
      effective_tenant_name: null,
      queue: 'scheduled',
      status: 'failed',
      args: null,
      kwargs: null,
      result: null,
      error_message: 'boom',
      trigger_source: 'scheduler',
      run_kind: 'platform',
      trace_id: null,
      started_at: null,
      finished_at: null,
      duration_ms: null,
      retry_count: 2,
      created_at: '2026-05-10T13:00:00Z',
      traceback: 'Traceback...',
    });

    const result = await getTaskLogDetailApi(42);

    expect(requestGetMock).toHaveBeenCalledWith('/admin/tasks/42', undefined);
    expect(result).toMatchObject({
      taskId: 'celery-42',
      runKey: null,
      taskName: 'Cleanup',
      errorMessage: 'boom',
      traceback: 'Traceback...',
    });
  });

  it('serializes retry queue through the current endpoint payload', async () => {
    requestPostMock.mockResolvedValue({ new_task_id: 'retry-42' });

    const result = await retryTaskApi(42, 'scheduled');

    expect(requestPostMock).toHaveBeenCalledWith(
      '/admin/tasks/42/retry',
      { queue: 'scheduled' },
      undefined,
    );
    expect(result).toEqual({ newTaskId: 'retry-42' });
  });
});
