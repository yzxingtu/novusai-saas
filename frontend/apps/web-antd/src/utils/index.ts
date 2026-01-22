/**
 * 工具函数统一导出
 */

// 权限检查工具
export { checkPermission, useAccess } from './access';

// 通用工具函数
export {
  buildTree,
  type BuildTreeOptions,
  confirmDelete,
  type ConfirmDeleteOptions,
  copyToClipboard,
  debounce,
  formatDate,
  formatDateOnly,
  type FormatDateOptions,
  formatRelativeTime,
  formatTimeOnly,
  generateCode,
  type GenerateCodeOptions,
  generateUUID,
  getLevelColor,
  type LevelColor,
  throttle,
  type TreeExpandReturn,
  type TreeNodeBase,
  useTreeExpand,
} from './common';

// 控制台过滤
export { setupConsoleFilter } from './console-filter';

// 端点工具
export {
  ALL_ENDPOINTS,
  type ApiEndpoint,
  convertPath,
  type EndpointConfig,
  EndpointType,
  forEachEndpoint,
  getApiEndpoint,
  getEndpointConfig,
  getEndpointFromPath,
  getHomePath,
  getLoginPath,
  getRelativePath,
  isAdminPath,
  isPathOfEndpoint,
  isTenantPath,
  isUserPath,
  isValidEndpoint,
  mapEndpoints,
} from './endpoint';

// HTTP 请求客户端
export { type ApiRequestOptions, requestClient } from './request';
