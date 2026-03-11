/**
 * Unified export of utility functions
 * 工具函数统一导出
 */

// Access control utilities / 权限检查工具
export { checkPermission, useAccess } from './access';

// Common utility functions / 通用工具函数
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

// Console filter / 控制台过滤
export { setupConsoleFilter } from './console-filter';

// Endpoint utilities / 端点工具
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

// Image processing utilities / 图片处理工具
export * from './image';

// HTTP request client / HTTP 请求客户端
export { type ApiRequestOptions, requestClient } from './request';
