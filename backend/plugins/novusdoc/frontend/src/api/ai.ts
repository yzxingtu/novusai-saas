/**
 * NovusDoc AI API — SSE 流式调用
 *
 * 通过 fetch + ReadableStream 处理 SSE，不走 requestClient（它不支持 SSE）
 */

import { requestClient } from '@novus/plugin-shared';

const API_PATH = '/tenant/plugins/novusdoc/api';

export interface AIRequestBody {
  selected_text?: string;
  before_text?: string;
  after_text?: string;
  doc_title?: string;
  instruction?: string;
  target_lang?: string;
  history?: Array<{ role: string; content: string }>;
}

export type AIFeature =
  | 'continue'
  | 'optimize'
  | 'proofread'
  | 'translate'
  | 'summarize'
  | 'expand'
  | 'rewrite'
  | 'image'
  | 'custom'
  | 'chat';

/**
 * 获取 requestClient 的 baseURL（从 axios 实例配置中提取）
 */
function getBaseUrl(): string {
  try {
    const axiosInstance = (requestClient as unknown as Record<string, unknown>).instance as
      | { defaults?: { baseURL?: string } }
      | undefined;
    return axiosInstance?.defaults?.baseURL || '';
  } catch {
    return '';
  }
}

/**
 * 从 localStorage 获取租户 token（兼容不同 key 前缀）
 */
function getTenantToken(): string {
  const keys = Object.keys(localStorage);
  const tokenKey = keys.find(k => k.includes('tenant_admin_token') && !k.includes('refresh'));
  return tokenKey ? (localStorage.getItem(tokenKey) || '') : '';
}

/**
 * Stream AI feature via SSE.
 *
 * Yields text deltas. Throws on error events.
 */
export async function* streamAIFeature(
  docId: number,
  feature: AIFeature,
  body: AIRequestBody,
  signal?: AbortSignal,
): AsyncGenerator<string, void, undefined> {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl}${API_PATH}/docs/${docId}/ai/${feature}`;
  const token = getTenantToken();

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`AI request failed: ${response.status} ${text}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('ReadableStream not supported');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);

        if (data === '[DONE]') return;
        if (data.startsWith(':')) continue; // heartbeat comment

        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            throw new Error(parsed.message || 'AI error');
          }
          if (parsed.delta) {
            yield parsed.delta;
          }
        } catch (e) {
          // Non-JSON data line — yield as raw text
          if (data && !data.startsWith('{')) {
            yield data;
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
