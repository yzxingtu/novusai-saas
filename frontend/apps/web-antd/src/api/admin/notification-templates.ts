/**
 * Admin notification template management API / 管理端通知模板管理 API
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

const PREFIX = '/admin/notification-templates';

export interface NotificationTemplateEffectivePreview {
  bodyTemplate: null | string;
  channels: string[];
  priority: string;
  titleTemplate: string;
}

export interface NotificationTemplateEffectivePreviewRaw {
  body_template?: null | string;
  channels?: string[];
  priority?: string;
  title_template?: string;
}

/** Notification template info / 通知模板信息 */
export interface NotificationTemplateInfo {
  id: number;
  code: string;
  category: string;
  titleTemplate: string;
  bodyTemplate: null | string;
  channels: string[];
  priority: string;
  isSystem: boolean;
  scope: null | string;
  tenantId: null | number;
  tenantName: null | string;
  pluginName: null | string;
  source: null | string;
  overrideOf: null | number;
  isOverride: boolean;
  enabled: boolean;
  effectivePreview: NotificationTemplateEffectivePreview;
  createdAt: null | string;
  updatedAt: null | string;
}

export interface NotificationTemplateInfoRaw {
  id: number;
  code: string;
  category?: string;
  title_template?: string;
  body_template?: null | string;
  channels?: string[];
  priority?: string;
  is_system?: boolean;
  scope?: null | string;
  tenant_id?: null | number;
  tenant_name?: null | string;
  plugin_name?: null | string;
  source?: null | string;
  override_of?: null | number;
  is_override?: boolean;
  is_enabled?: boolean;
  effective_preview?: NotificationTemplateEffectivePreviewRaw;
  created_at?: null | string;
  updated_at?: null | string;
}

/** Update notification template params / 通知模板更新参数 */
export interface UpdateNotificationTemplateParams {
  bodyTemplate?: null | string;
  channels?: string[];
  enabled?: boolean;
  priority?: string;
  titleTemplate?: string;
}

/** Paginated response / 分页响应 */
interface PageResponse {
  items: NotificationTemplateInfo[];
  page: number;
  page_size: number;
  total: number;
}

interface PageResponseRaw {
  items: NotificationTemplateInfoRaw[];
  page: number;
  page_size: number;
  total: number;
}

function transformEffectivePreview(
  raw: NotificationTemplateEffectivePreviewRaw | null | undefined,
  fallback: Pick<
    NotificationTemplateInfoRaw,
    'body_template' | 'channels' | 'priority' | 'title_template'
  >,
): NotificationTemplateEffectivePreview {
  return {
    titleTemplate: raw?.title_template ?? fallback.title_template ?? '',
    bodyTemplate: raw?.body_template ?? fallback.body_template ?? null,
    channels: raw?.channels ?? fallback.channels ?? [],
    priority: raw?.priority ?? fallback.priority ?? 'normal',
  };
}

function transformNotificationTemplateInfo(
  raw: NotificationTemplateInfoRaw,
): NotificationTemplateInfo {
  return {
    id: raw.id,
    code: raw.code,
    category: raw.category ?? 'system',
    titleTemplate: raw.title_template ?? '',
    bodyTemplate: raw.body_template ?? null,
    channels: raw.channels ?? [],
    priority: raw.priority ?? 'normal',
    isSystem: raw.is_system ?? false,
    scope: raw.scope ?? null,
    tenantId: raw.tenant_id ?? null,
    tenantName: raw.tenant_name ?? null,
    pluginName: raw.plugin_name ?? null,
    source: raw.source ?? null,
    overrideOf: raw.override_of ?? null,
    isOverride: raw.is_override ?? false,
    enabled: raw.is_enabled ?? true,
    effectivePreview: transformEffectivePreview(raw.effective_preview, raw),
    createdAt: raw.created_at ?? null,
    updatedAt: raw.updated_at ?? null,
  };
}

function toUpdatePayload(data: UpdateNotificationTemplateParams) {
  return Object.fromEntries(
    Object.entries({
      channels: data.channels,
      priority: data.priority,
      title_template: data.titleTemplate,
      body_template: data.bodyTemplate,
      is_enabled: data.enabled,
    }).filter(([, value]) => value !== undefined),
  );
}

/** Get notification template list / 获取通知模板列表 */
export async function getNotificationTemplateListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse> {
  const response = await requestClient.get<PageResponseRaw>(PREFIX, {
    params,
    ...options,
  });
  return {
    ...response,
    items: response.items.map((item) =>
      transformNotificationTemplateInfo(item),
    ),
  };
}

/** Update notification template / 更新通知模板 */
export async function updateNotificationTemplateApi(
  id: number,
  data: UpdateNotificationTemplateParams,
  options?: ApiRequestOptions,
): Promise<NotificationTemplateInfo | undefined> {
  const response = await requestClient.put<
    NotificationTemplateInfoRaw | undefined
  >(`${PREFIX}/${id}`, toUpdatePayload(data), options);
  return response ? transformNotificationTemplateInfo(response) : undefined;
}

/** Test notification template / 测试通知模板 */
export async function testNotificationTemplateApi(
  id: number,
  options?: ApiRequestOptions,
) {
  return requestClient.post(`${PREFIX}/${id}/test`, {}, options);
}

/** Get effective preview / 获取生效预览 */
export async function getNotificationTemplatePreviewApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<NotificationTemplateEffectivePreview> {
  const raw = await requestClient.get<NotificationTemplateEffectivePreviewRaw>(
    `${PREFIX}/${id}/effective-preview`,
    options,
  );
  return transformEffectivePreview(raw, {});
}

/** Restore default template / 恢复默认模板 */
export async function restoreNotificationTemplateDefaultApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<NotificationTemplateInfo | undefined> {
  const response = await requestClient.post<
    NotificationTemplateInfoRaw | undefined
  >(`${PREFIX}/${id}/restore-default`, {}, options);
  return response ? transformNotificationTemplateInfo(response) : undefined;
}
