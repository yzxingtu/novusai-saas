// Test type: behavioral
// 中文: 测试类型 behavioral，覆盖通知模板 API canonical snake_case 转换与更新载荷。
// EN: Test type behavioral, covering notification template API canonical snake_case transforms and update payloads.
// 中文: Mock 请求传输层，真实运行 API 适配映射。
// EN: Mock request transport while running the real API adapter mapping.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getNotificationTemplateListApi,
  restoreNotificationTemplateDefaultApi,
  updateNotificationTemplateApi,
} from '../notification-templates';

const { requestGetMock, requestPostMock, requestPutMock } = vi.hoisted(() => ({
  requestGetMock: vi.fn(),
  requestPostMock: vi.fn(),
  requestPutMock: vi.fn(),
}));

vi.mock('#/utils/request', () => ({
  requestClient: {
    get: requestGetMock,
    post: requestPostMock,
    put: requestPutMock,
  },
}));

describe('notification template api', () => {
  beforeEach(() => {
    requestGetMock.mockReset();
    requestPostMock.mockReset();
    requestPutMock.mockReset();
  });

  it('normalizes scope, source, override and effective preview fields', async () => {
    requestGetMock.mockResolvedValue({
      items: [
        {
          id: 9,
          code: 'task.failed',
          category: 'task',
          title_template: 'Task failed',
          body_template: null,
          channels: ['inbox'],
          priority: 'high',
          is_system: true,
          scope: 'tenant',
          tenant_id: 22,
          tenant_name: 'Tenant A',
          plugin_name: 'scheduler',
          source: 'plugin',
          override_of: 4,
          is_override: true,
          locked_fields: ['title_template', 'body_template'],
          is_enabled: false,
          effective_preview: {
            title_template: 'Effective title',
            body_template: 'Effective body',
            channels: ['email'],
            priority: 'urgent',
          },
          created_at: '2026-05-01T00:00:00Z',
          updated_at: '2026-05-02T00:00:00Z',
        },
      ],
      page: 1,
      page_size: 20,
      total: 1,
    });

    const result = await getNotificationTemplateListApi({
      'filter[scope][eq]': 'tenant',
    });

    expect(requestGetMock).toHaveBeenCalledWith(
      '/admin/notification-templates',
      { params: { 'filter[scope][eq]': 'tenant' } },
    );
    expect(result.items[0]).toMatchObject({
      id: 9,
      code: 'task.failed',
      titleTemplate: 'Task failed',
      bodyTemplate: null,
      scope: 'tenant',
      tenantId: 22,
      tenantName: 'Tenant A',
      pluginName: 'scheduler',
      source: 'plugin',
      overrideOf: 4,
      isOverride: true,
      lockedFields: ['title_template', 'body_template'],
      enabled: false,
      effectivePreview: {
        titleTemplate: 'Effective title',
        bodyTemplate: 'Effective body',
        channels: ['email'],
        priority: 'urgent',
      },
    });
  });

  it('ignores camelCase raw response aliases when normalizing template fields', async () => {
    requestGetMock.mockResolvedValue({
      items: [
        {
          id: 10,
          code: 'legacy.camel',
          titleTemplate: 'Legacy title',
          bodyTemplate: 'Legacy body',
          isSystem: true,
          tenantId: 33,
          tenantName: 'Legacy Tenant',
          pluginName: 'legacy-plugin',
          overrideOf: 2,
          isOverride: true,
          lockedFields: ['channels'],
          effectivePreview: {
            titleTemplate: 'Legacy effective title',
            bodyTemplate: 'Legacy effective body',
          },
          createdAt: '2026-05-03T00:00:00Z',
          updatedAt: '2026-05-04T00:00:00Z',
        },
      ],
      page: 1,
      page_size: 20,
      total: 1,
    });

    const result = await getNotificationTemplateListApi();

    expect(result.items[0]).toMatchObject({
      id: 10,
      code: 'legacy.camel',
      titleTemplate: '',
      bodyTemplate: null,
      isSystem: false,
      tenantId: null,
      tenantName: null,
      pluginName: null,
      overrideOf: null,
      isOverride: false,
      lockedFields: [],
      effectivePreview: {
        titleTemplate: '',
        bodyTemplate: null,
        channels: [],
        priority: 'normal',
      },
      createdAt: null,
      updatedAt: null,
    });
  });

  it('maps camelCase update params to backend payload fields', async () => {
    requestPutMock.mockResolvedValue(undefined);

    await updateNotificationTemplateApi(9, {
      titleTemplate: 'Updated title',
      bodyTemplate: null,
      channels: ['inbox', 'email'],
      priority: 'normal',
      enabled: true,
    });

    expect(requestPutMock).toHaveBeenCalledWith(
      '/admin/notification-templates/9',
      {
        title_template: 'Updated title',
        body_template: null,
        channels: ['inbox', 'email'],
        priority: 'normal',
        is_enabled: true,
      },
      undefined,
    );
  });

  it('calls restore default endpoint and normalizes returned template', async () => {
    requestPostMock.mockResolvedValue({
      id: 9,
      code: 'task.failed',
      title_template: 'Default title',
      is_override: false,
    });

    const result = await restoreNotificationTemplateDefaultApi(9);

    expect(requestPostMock).toHaveBeenCalledWith(
      '/admin/notification-templates/9/restore-default',
      {},
      undefined,
    );
    expect(result).toMatchObject({
      code: 'task.failed',
      titleTemplate: 'Default title',
      isOverride: false,
      enabled: true,
    });
  });
});
