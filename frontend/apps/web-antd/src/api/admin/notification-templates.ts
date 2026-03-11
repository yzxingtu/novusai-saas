/**
 * Admin notification template management API / 管理端通知模板管理 API
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

const PREFIX = '/admin/notification-templates';

/** Notification template info / 通知模板信息 */
export interface NotificationTemplateInfo {
  id: number;
  code: string;
  category: string;
  title_template: string;
  body_template: null | string;
  channels: string[];
  priority: string;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

/** Update notification template params / 通知模板更新参数 */
export interface UpdateNotificationTemplateParams {
  channels?: string[];
  priority?: string;
  title_template?: string;
  body_template?: string;
}

/** Paginated response / 分页响应 */
interface PageResponse {
  items: NotificationTemplateInfo[];
  page: number;
  page_size: number;
  total: number;
}

/** Get notification template list / 获取通知模板列表 */
export async function getNotificationTemplateListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse> {
  return requestClient.get<PageResponse>(PREFIX, { params, ...options });
}

/** Update notification template / 更新通知模板 */
export async function updateNotificationTemplateApi(
  id: number,
  data: UpdateNotificationTemplateParams,
  options?: ApiRequestOptions,
) {
  return requestClient.put(`${PREFIX}/${id}`, data, options);
}

/** Test notification template / 测试通知模板 */
export async function testNotificationTemplateApi(
  id: number,
  options?: ApiRequestOptions,
) {
  return requestClient.post(`${PREFIX}/${id}/test`, {}, options);
}
