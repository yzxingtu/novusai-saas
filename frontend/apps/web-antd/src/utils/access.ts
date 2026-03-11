/**
 * Access control utilities
 * 权限控制工具
 *
 * Extends @vben/access permission check logic with super admin wildcard support
 * 扩展 @vben/access 的权限检查逻辑，支持超级管理员通配符
 */
import { computed } from 'vue';

import { useAccess as useVbenAccess } from '@vben/access';
import { useAccessStore } from '@vben/stores';

/**
 * General permission check
 * 通用权限检查
 *
 * Extends @vben/access hasAccessByCodes with super admin wildcard support.
 * When userCodes contains '*', access is granted directly (super admin).
 * 扩展 @vben/access 的 hasAccessByCodes，增加超级管理员通配符支持。
 * 当 userCodes 包含 '*' 时直接放行（超级管理员）。
 *
 * @param codes - Permission codes to check / 需要检查的权限码
 * @param userCodes - Current user's permission codes / 当前用户拥有的权限码
 * @returns Whether the user has permission / 是否有权限
 */
export function checkPermission(
  codes: string | string[] | undefined,
  userCodes: string[],
): boolean {
  // 无权限码要求（undefined 或空数组），默认有权限
  if (!codes || (Array.isArray(codes) && codes.length === 0)) return true;
  // 超级管理员拥有所有权限
  if (userCodes.includes('*')) return true;
  // 正常权限检查
  const codeList = Array.isArray(codes) ? codes : [codes];
  return codeList.some((code) => userCodes.includes(code));
}

/**
 * Permission check hook
 * 权限检查 Hook
 *
 * @returns Permission check utilities / 权限检查工具集
 */
export function useAccess() {
  const vbenAccess = useVbenAccess();
  const accessStore = useAccessStore();

  /**
   * Whether the user is a super admin (permission codes include '*') / 是否为超级管理员（权限码包含 '*'）
   */
  const isSuperAdmin = computed(() => {
    return accessStore.accessCodes.includes('*');
  });

  /**
   * 基于权限码判断是否有权限
   * Check by permission codes (with super admin wildcard)
   * 按权限码检查（已加入超管通配符）
   * @param codes Permission codes to check / 要检查的权限码
   * @returns Whether the user has the specified permissions / 是否拥有指定权限
   */
  function hasAccessByCodes(codes: string[]): boolean {
    // 超级管理员拥有所有权限
    if (isSuperAdmin.value) {
      return true;
    }
    return vbenAccess.hasAccessByCodes(codes);
  }

  /**
   * 基于角色判断是否有权限
   */
  function hasAccessByRoles(roles: string[]): boolean {
    return vbenAccess.hasAccessByRoles(roles);
  }

  return {
    ...vbenAccess,
    hasAccessByCodes,
    hasAccessByRoles,
    isSuperAdmin,
  };
}
