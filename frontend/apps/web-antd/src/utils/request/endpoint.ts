import type { ApiEndpoint } from './types';

import { resolveEndpointByPath } from '#/constants/endpoints';

/**
 * Determine endpoint type from request URL.
 * 根据请求 URL 判断端类型。
 */
export function getEndpointByUrl(url: string): ApiEndpoint {
  if (url.startsWith('/plugins/')) {
    if (/^\/plugins\/[^/]+\/admin(?:\/|$)/.test(url)) return 'admin';
    if (/^\/plugins\/[^/]+\/tenant(?:\/|$)/.test(url)) return 'tenant';
  }
  return resolveEndpointByPath(url) as ApiEndpoint;
}
