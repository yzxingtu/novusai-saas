/**
 * AI 模型管理 API
 * 对接后端 /admin/ai/models 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// 类型定义 - AI 模型
// ============================================================

/** 模型类型 */
export type ModelType = 'chat' | 'embedding' | 'image';

/** AI 模型信息 */
export interface AIModelInfo {
  id: number;
  provider_id: number;
  name: string;
  code: string;
  type: ModelType;
  context_window: null | number;
  max_output_tokens: null | number;
  input_price_per_1k: null | number;
  output_price_per_1k: null | number;
  rpm_limit: null | number;
  tpm_limit: null | number;
  supports_function_calling: boolean;
  supports_vision: boolean;
  supports_streaming: boolean;
  is_active: boolean;
  config: null | Record<string, unknown>;
  provider_name: null | string;
  created_at: string;
  updated_at: string;
}

/** 创建模型请求 */
export interface AIModelCreateRequest {
  provider_id: number;
  name: string;
  code: string;
  type: ModelType;
  context_window?: null | number;
  max_output_tokens?: null | number;
  input_price_per_1k?: null | number;
  output_price_per_1k?: null | number;
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  supports_function_calling?: boolean;
  supports_vision?: boolean;
  supports_streaming?: boolean;
  is_active?: boolean;
  config?: null | Record<string, unknown>;
}

/** 更新模型请求 */
export interface AIModelUpdateRequest {
  provider_id?: null | number;
  name?: null | string;
  code?: null | string;
  type?: null | string;
  context_window?: null | number;
  max_output_tokens?: null | number;
  input_price_per_1k?: null | number;
  output_price_per_1k?: null | number;
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  supports_function_calling?: boolean | null;
  supports_vision?: boolean | null;
  supports_streaming?: boolean | null;
  is_active?: boolean | null;
  config?: null | Record<string, unknown>;
}

/** 远程模型信息（从供应商 API 拉取） */
export interface RemoteModelInfo {
  id: string;
  owned_by: null | string;
}

// ============================================================
// 通用分页响应
// ============================================================

interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API 接口 - AI 模型
// ============================================================

const MODEL_PREFIX = '/admin/ai/models';

/** 获取模型列表 */
export async function getAIModelListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIModelInfo>> {
  return requestClient.get<PageResponse<AIModelInfo>>(
    MODEL_PREFIX,
    { params, ...options },
  );
}

/** 获取供应商的模型列表 */
export async function getAIModelsByProviderApi(
  providerId: number,
  options?: ApiRequestOptions,
): Promise<AIModelInfo[]> {
  return requestClient.get<AIModelInfo[]>(
    `${MODEL_PREFIX}/provider/${providerId}`,
    options,
  );
}

/** 从供应商远程拉取可用模型列表 */
export async function fetchRemoteModelsApi(
  providerId: number,
  options?: ApiRequestOptions,
): Promise<RemoteModelInfo[]> {
  return requestClient.get<RemoteModelInfo[]>(
    `${MODEL_PREFIX}/fetch-remote/${providerId}`,
    options,
  );
}

/** 获取模型详情 */
export async function getAIModelDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.get<AIModelInfo>(
    `${MODEL_PREFIX}/${id}`,
    options,
  );
}

/** 创建模型 */
export async function createAIModelApi(
  data: AIModelCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.post<AIModelInfo>(
    MODEL_PREFIX,
    data,
    options,
  );
}

/** 更新模型 */
export async function updateAIModelApi(
  id: number,
  data: AIModelUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.put<AIModelInfo>(
    `${MODEL_PREFIX}/${id}`,
    data,
    options,
  );
}

/** 删除模型 */
export async function deleteAIModelApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${MODEL_PREFIX}/${id}`, options);
}

/** 切换模型状态 */
export async function toggleAIModelStatusApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.put<AIModelInfo>(
    `${MODEL_PREFIX}/${id}/status`,
    {},
    options,
  );
}
