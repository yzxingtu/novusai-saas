/**
 * API 业务错误码定义
 *
 * 基于后端 API 错误码规范（文档 ID 204）
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
 */
export enum ErrorCode {
  /** 邮箱已被使用 */
  ADMIN_EMAIL_EXISTS = 4302,
  /** 手机号已被使用 */
  ADMIN_PHONE_EXISTS = 4303,
  // ============================================================
  // 管理员相关错误 (43xx)
  // ============================================================
  /** 用户名已存在 */
  ADMIN_USERNAME_EXISTS = 4301,
  /** 资源冲突 */
  CONFLICT = 4090,

  /** 域名已被使用 */
  DOMAIN_ALREADY_EXISTS = 4203,
  // ============================================================
  // 租户/域名相关错误 (42xx)
  // ============================================================
  /** 自定义域名功能未启用 */
  DOMAIN_CUSTOM_DISABLED = 4201,
  /** 域名数量已达上限 */
  DOMAIN_QUOTA_EXCEEDED = 4202,
  /** 数据已存在 */
  DUPLICATE_ENTRY = 4002,
  /** 外部服务错误 */
  EXTERNAL_SERVICE_ERROR = 5020,
  /** 禁止访问 */
  FORBIDDEN = 4030,
  /** 无效的参数 */
  INVALID_PARAMETER = 4003,

  /** 资源不存在 */
  NOT_FOUND = 4040,
  /** 原密码不正确 */
  OLD_PASSWORD_INCORRECT = 4004,
  /** 权限不足 */
  PERMISSION_DENIED = 4031,
  /** 该节点不允许添加成员 */
  ROLE_CANNOT_ADD_MEMBER = 4110,
  // ============================================================
  // 角色相关错误 (41xx)
  // ============================================================
  /** 不能将自己设为父节点 */
  ROLE_CANNOT_SET_SELF_AS_PARENT = 4101,
  /** 检测到循环引用 */
  ROLE_CIRCULAR_REFERENCE = 4102,
  /** 该节点下有子节点，无法删除 */
  ROLE_HAS_CHILDREN = 4106,
  /** 该角色下有用户，无法删除 */
  ROLE_HAS_USERS = 4107,
  /** 不允许的子节点类型 */
  ROLE_INVALID_CHILD_TYPE = 4108,
  /** 超过最大层级深度限制 */
  ROLE_MAX_DEPTH_EXCEEDED = 4103,
  /** 该成员已在此节点 */
  ROLE_MEMBER_EXISTS = 4111,
  /** 该成员不在此节点 */
  ROLE_MEMBER_NOT_IN_NODE = 4112,

  /** 只有部门类型可以设置负责人 */
  ROLE_ONLY_DEPARTMENT_CAN_SET_LEADER = 4109,
  /** 系统角色不能修改父级 */
  ROLE_SYSTEM_CANNOT_CHANGE_PARENT = 4104,
  /** 系统角色不能删除 */
  ROLE_SYSTEM_CANNOT_DELETE = 4105,

  // ============================================================
  // 服务端错误 (5xxx)
  // ============================================================
  /** 服务器内部错误 */
  SERVER_ERROR = 5000,
  /** 服务暂不可用 */
  SERVICE_UNAVAILABLE = 5030,
  /** 令牌已过期 */
  TOKEN_EXPIRED = 4011,

  /** 无效的令牌 */
  TOKEN_INVALID = 4012,
  // ============================================================
  // 认证授权错误 (401x/403x/404x/409x)
  // ============================================================
  /** 未认证 */
  UNAUTHORIZED = 4010,
  // ============================================================
  // 通用错误 (40xx)
  // ============================================================
  /** 数据验证失败 */
  VALIDATION_ERROR = 4001,
}

/**
 * 需要跳转登录的错误码
 */
export const AUTH_ERROR_CODES = [
  ErrorCode.UNAUTHORIZED,
  ErrorCode.TOKEN_EXPIRED,
  ErrorCode.TOKEN_INVALID,
];

/**
 * 判断是否为认证错误
 */
export function isAuthError(code: number): boolean {
  return AUTH_ERROR_CODES.includes(code);
}

/**
 * 判断是否为客户端错误（4xxx）
 */
export function isClientError(code: number): boolean {
  return code >= 4000 && code < 5000;
}

/**
 * 判断是否为服务端错误（5xxx）
 */
export function isServerError(code: number): boolean {
  return code >= 5000 && code < 6000;
}
