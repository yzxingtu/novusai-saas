/**
 * API error code definitions
 * API 错误码定义
 *
 * Kept in sync with backend for business error type determination.
 * Backend file: app/core/exceptions.py
 * 与后端保持一致，用于判断业务错误类型。
 * 后端文件: app/core/exceptions.py
 *
 * 错误码编码规则：
 * - 40xx: 通用验证错误
 * - 401x: 认证错误
 * - 403x: 授权错误
 * - 404x: 资源不存在
 * - 409x: 资源冲突
 * - 41xx: 角色/权限相关
 * - 42xx: 租户/域名相关
 * - 43xx: 管理员相关
 * - 5xxx: 服务端错误
 *
 * @module utils/request/error-codes
 */

/**
 * 业务错误码枚举
 * Business error code enumeration
 */
export enum ErrorCode {
  /** 邮箱已被使用 */
  /** Email already in use */
  ADMIN_EMAIL_EXISTS = 4302,
  /** 手机号已被使用 */
  /** Phone number already in use */
  ADMIN_PHONE_EXISTS = 4303,
  // ============================================================
  // ---- Administrator related / 管理员相关 ---- (43xx)
  // ============================================================
  /** 用户名已存在 */
  /** Username already exists */
  ADMIN_USERNAME_EXISTS = 4301,
  /** 资源冲突 */
  /** Resource conflict */
  CONFLICT = 4090,

  /** 域名已被使用 */
  /** Domain already in use */
  DOMAIN_ALREADY_EXISTS = 4203,
  // ============================================================
  // ---- Tenant & domain related / 租户、域名相关 ---- (42xx)
  // ============================================================
  /** 自定义域名功能未启用 */
  /** Custom domain feature not enabled */
  DOMAIN_CUSTOM_DISABLED = 4201,
  /** 域名数量已达上限 */
  /** Domain quota exceeded */
  DOMAIN_QUOTA_EXCEEDED = 4202,
  /** 数据已存在 */
  /** Data already exists */
  DUPLICATE_ENTRY = 4002,
  /** External service error / 外部服务错误 */
  EXTERNAL_SERVICE_ERROR = 5020,
  /** 禁止访问 */
  /** Forbidden */
  FORBIDDEN = 4030,
  /** 无效的参数 */
  /** Invalid parameter */
  INVALID_PARAMETER = 4003,

  /** 资源不存在 */
  /** Resource not found */
  NOT_FOUND = 4040,
  /** 原密码不正确 */
  /** Original password incorrect */
  OLD_PASSWORD_INCORRECT = 4004,
  /** 权限不足 */
  /** Permission denied */
  PERMISSION_DENIED = 4031,
  /** 该节点不允许添加成员 */
  /** Node does not allow adding members */
  ROLE_CANNOT_ADD_MEMBER = 4110,
  // ============================================================
  // ---- Role related / 角色相关 ---- (41xx)
  // ============================================================
  /** 不能将自己设为父节点 */
  /** Cannot set self as parent node */
  ROLE_CANNOT_SET_SELF_AS_PARENT = 4101,
  /** 检测到循环引用 */
  /** Circular reference detected */
  ROLE_CIRCULAR_REFERENCE = 4102,
  /** 该节点下有子节点，无法删除 */
  /** Node has child nodes, cannot delete */
  ROLE_HAS_CHILDREN = 4106,
  /** 该角色下有用户，无法删除 */
  /** Role has users, cannot delete */
  ROLE_HAS_USERS = 4107,
  /** 不允许的子节点类型 */
  /** Disallowed child node type */
  ROLE_INVALID_CHILD_TYPE = 4108,
  /** 超过最大层级深度限制 */
  /** Exceeded maximum depth limit */
  ROLE_MAX_DEPTH_EXCEEDED = 4103,
  /** 该成员已在此节点 */
  /** Member already exists in this node */
  ROLE_MEMBER_EXISTS = 4111,
  /** 该成员不在此节点 */
  /** Member does not exist in this node */
  ROLE_MEMBER_NOT_IN_NODE = 4112,

  /** 只有部门类型可以设置负责人 */
  /** Only department type can set leader */
  ROLE_ONLY_DEPARTMENT_CAN_SET_LEADER = 4109,
  /** 系统角色不能修改父级 */
  /** System role cannot change parent */
  ROLE_SYSTEM_CANNOT_CHANGE_PARENT = 4104,
  /** 系统角色不能删除 */
  /** System role cannot delete */
  ROLE_SYSTEM_CANNOT_DELETE = 4105,

  // ============================================================
  // ---- Server errors / 服务器错误 ---- (5xxx)
  // ============================================================
  /** 服务器内部错误 */
  /** Server internal error */
  SERVER_ERROR = 5000,
  /** 服务暂不可用 */
  /** Service unavailable */
  SERVICE_UNAVAILABLE = 5030,
  /** 令牌已过期 */
  /** Token expired */
  TOKEN_EXPIRED = 4011,

  /** 无效的令牌 */
  /** Invalid token */
  TOKEN_INVALID = 4012,
  // ============================================================
  // ---- Authentication/Authorization errors / 认证/授权错误 ---- (401x/403x/404x/409x)
  // ============================================================
  /** 未认证 */
  /** Unauthorized */
  UNAUTHORIZED = 4010,
  // ============================================================
  // ---- Common errors / 通用错误 ---- (40xx)
  // ============================================================
  /** 数据验证失败 */
  /** Data validation failed */
  VALIDATION_ERROR = 4001,
}

/**
 * 需要跳转登录的错误码
 * Error codes that require re-login
 */
export const AUTH_ERROR_CODES = [
  ErrorCode.UNAUTHORIZED,
  ErrorCode.TOKEN_EXPIRED,
  ErrorCode.TOKEN_INVALID,
];

/**
 * 是否为认证类错误（需要重新登录）
 * Whether it's an authentication error (requires re-login)
 */
export function isAuthError(code: number): boolean {
  return AUTH_ERROR_CODES.includes(code);
}

/**
 * 是否为客户端错误 (4xxx)
 * Whether it's a client error (4xxx)
 */
export function isClientError(code: number): boolean {
  return code >= 4000 && code < 5000;
}

/**
 * 是否为服务端错误 (5xxx)
 * Whether it's a server error (5xxx)
 */
export function isServerError(code: number): boolean {
  return code >= 5000 && code < 6000;
}
