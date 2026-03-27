/**
 * AI model management API / AI 模型管理 API
 * Backend: /admin/ai/models
 */
import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions - AI models / 类型定义 - AI 模型
// ============================================================

/** Model type / 模型类型 */
export type ModelType = 'chat' | 'embedding' | 'image';

/** AI model info / AI 模型信息 */
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
  supports_audio: boolean;
  supports_video: boolean;
  supports_streaming: boolean;
  max_image_count: null | number;
  max_image_size_mb: null | number;
  is_active: boolean;
  config: null | Record<string, unknown>;
  fallback_model_id: null | number;
  fallback_model_name: null | string;
  tier: null | string;
  provider_name: null | string;
  provider_icon?: null | string;
  created_at: string;
  updated_at: string;
}

/** Create model request / 创建模型请求 */
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
  supports_audio?: boolean;
  supports_video?: boolean;
  supports_streaming?: boolean;
  max_image_count?: null | number;
  max_image_size_mb?: null | number;
  is_active?: boolean;
  config?: null | Record<string, unknown>;
  fallback_model_id?: null | number;
  tier?: null | string;
}

/** Update model request / 更新模型请求 */
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
  supports_audio?: boolean | null;
  supports_video?: boolean | null;
  supports_streaming?: boolean | null;
  max_image_count?: null | number;
  max_image_size_mb?: null | number;
  is_active?: boolean | null;
  config?: null | Record<string, unknown>;
  fallback_model_id?: null | number;
  tier?: null | string;
}

/** Remote model capabilities from LiteLLM registry / 远程模型能力（来自 LiteLLM 注册表） */
export interface RemoteModelCapabilities {
  context_window?: null | number;
  input_price_per_1k?: null | number;
  max_output_tokens?: null | number;
  model_type?: null | string;
  output_price_per_1k?: null | number;
  rpm_limit?: null | number;
  tpm_limit?: null | number;
  supports_function_calling?: boolean | null;
  supports_audio?: boolean | null;
  supports_video?: boolean | null;
  supports_streaming?: boolean | null;
  supports_vision?: boolean | null;
}

/** Remote model info (fetched from provider API) / 远程模型信息 */
export interface RemoteModelInfo {
  capabilities?: null | RemoteModelCapabilities;
  id: string;
  owned_by: null | string;
}

// ============================================================
// Generic paginated response / 通用分页响应
// ============================================================

interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

// ============================================================
// API - AI models / API 接口 - AI 模型
// ============================================================

const MODEL_PREFIX = '/admin/ai/models';

/** Get model select options / 获取模型下拉选项 */
export async function getAIModelSelectApi(params?: Record<string, unknown>) {
  return requestClient.get(`${MODEL_PREFIX}/select`, { params });
}

/** Get model list / 获取模型列表 */
export async function getAIModelListApi(
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<AIModelInfo>> {
  return requestClient.get<PageResponse<AIModelInfo>>(MODEL_PREFIX, {
    params,
    ...options,
  });
}

/** Get models by provider / 获取供应商的模型列表 */
export async function getAIModelsByProviderApi(
  providerId: number,
  options?: ApiRequestOptions,
): Promise<AIModelInfo[]> {
  return requestClient.get<AIModelInfo[]>(
    `${MODEL_PREFIX}/provider/${providerId}`,
    options,
  );
}

/** Fetch available models remotely from provider / 从供应商远程拉取可用模型列表 */
export async function fetchRemoteModelsApi(
  providerId: number,
  options?: ApiRequestOptions,
): Promise<RemoteModelInfo[]> {
  return requestClient.get<RemoteModelInfo[]>(
    `${MODEL_PREFIX}/fetch-remote/${providerId}`,
    options,
  );
}

/** Get model detail / 获取模型详情 */
export async function getAIModelDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.get<AIModelInfo>(`${MODEL_PREFIX}/${id}`, options);
}

/** Create model / 创建模型 */
export async function createAIModelApi(
  data: AIModelCreateRequest,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.post<AIModelInfo>(MODEL_PREFIX, data, options);
}

/** Update model / 更新模型 */
export async function updateAIModelApi(
  id: number,
  data: AIModelUpdateRequest,
  options?: ApiRequestOptions,
): Promise<AIModelInfo> {
  return requestClient.put<AIModelInfo>(`${MODEL_PREFIX}/${id}`, data, options);
}

/** Delete model / 删除模型 */
export async function deleteAIModelApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<void> {
  await requestClient.delete(`${MODEL_PREFIX}/${id}`, options);
}

/** Toggle model status / 切换模型状态 */
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
