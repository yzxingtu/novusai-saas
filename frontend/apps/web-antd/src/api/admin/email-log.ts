/**
 * 邮件日志 API
 * 对接后端 /admin/email-logs/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

const API_PREFIX = '/admin/email-logs';

/** 邮件日志信息（后端原始 snake_case） */
interface EmailLogInfoRaw {
  id: number;
  to_address: string;
  cc: string | null;
  bcc: string | null;
  subject: string;
  status: string;
  triggered_by: string;
  error_message: string | null;
  sent_at: string | null;
  tenant_id: number | null;
  created_at: string;
}

/** 邮件日志信息（前端 camelCase） */
export interface EmailLogInfo {
  id: number;
  toAddress: string;
  cc: string | null;
  bcc: string | null;
  subject: string;
  status: string;
  triggeredBy: string;
  errorMessage: string | null;
  sentAt: string | null;
  tenantId: number | null;
  createdAt: string;
}

/** 手动发送邮件请求 */
export interface EmailSendRequest {
  to: string[];
  subject: string;
  html_body?: string | null;
  text_body?: string | null;
  cc?: string[] | null;
  bcc?: string[] | null;
}

/** 测试邮件请求 */
export interface EmailTestRequest {
  to: string;
}

/** 发送结果 */
export interface EmailSendResult {
  success: boolean;
  message: string;
  error: string | null;
}

/** 邮件日志详情（含 body） */
export interface EmailLogDetail {
  id: number;
  toAddress: string;
  cc: string | null;
  bcc: string | null;
  subject: string;
  status: string;
  triggeredBy: string;
  htmlBody: string | null;
  textBody: string | null;
  errorMessage: string | null;
  sentAt: string | null;
  tenantId: number | null;
  createdAt: string | null;
}

/** 分页响应 */
export interface EmailLogListResponse {
  items: EmailLogInfo[];
  total: number;
  page: number;
  page_size: number;
}

function transformEmailLogInfo(raw: EmailLogInfoRaw): EmailLogInfo {
  return {
    id: raw.id,
    toAddress: raw.to_address,
    cc: raw.cc,
    bcc: raw.bcc,
    subject: raw.subject,
    status: raw.status,
    triggeredBy: raw.triggered_by,
    errorMessage: raw.error_message,
    sentAt: raw.sent_at,
    tenantId: raw.tenant_id,
    createdAt: raw.created_at,
  };
}

/**
 * 获取邮件日志列表
 */
export async function getEmailLogListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<EmailLogListResponse> {
  const response = await requestClient.get<{
    items: EmailLogInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map(transformEmailLogInfo),
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}

/**
 * 获取邮件日志详情（含 body）
 */
export async function getEmailLogDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<EmailLogDetail> {
  const raw = await requestClient.get<Record<string, unknown>>(
    `${API_PREFIX}/${id}`,
    options,
  );
  return {
    id: raw.id as number,
    toAddress: raw.to_address as string,
    cc: raw.cc as string | null,
    bcc: raw.bcc as string | null,
    subject: raw.subject as string,
    status: raw.status as string,
    triggeredBy: raw.triggered_by as string,
    htmlBody: raw.html_body as string | null,
    textBody: raw.text_body as string | null,
    errorMessage: raw.error_message as string | null,
    sentAt: raw.sent_at as string | null,
    tenantId: raw.tenant_id as number | null,
    createdAt: raw.created_at as string | null,
  };
}

/**
 * 手动发送邮件
 */
export async function sendEmailApi(
  data: EmailSendRequest,
  options?: ApiRequestOptions,
): Promise<EmailSendResult> {
  return requestClient.post<EmailSendResult>(
    `${API_PREFIX}/send`,
    data,
    options,
  );
}

/**
 * 发送测试邮件
 */
export async function sendTestEmailApi(
  data: EmailTestRequest,
  options?: ApiRequestOptions,
): Promise<EmailSendResult> {
  return requestClient.post<EmailSendResult>(
    `${API_PREFIX}/test`,
    data,
    options,
  );
}
