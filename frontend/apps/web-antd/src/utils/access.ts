/**
 * 权限控制工具
 * 扩展 @vben/access 的权限检查逻辑，支持超级管理员通配符
 */
import { computed } from 'vue';

import { useAccess as useVbenAccess } from '@vben/access';
import { useAccessStore } from '@vben/stores';

/**
 * 检查是否有权限（共享工具函数）
 * 支持超级管理员 '*' 通配符
 * @param codes 需要检查的权限码列表，传 undefined 表示不需要权限
 * @param userCodes 用户拥有的权限码列表
 * @returns true 表示有权限
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
 * 增强版权限检查 Hook
 * 支持超级管理员 '*' 通配符
 */
export function useAccess() {
  const vbenAccess = useVbenAccess();
  const accessStore = useAccessStore();

  /**
   * 检查是否为超级管理员（拥有 '*' 权限）
   */
  const isSuperAdmin = computed(() => {
    return accessStore.accessCodes.includes('*');
  });

  /**
   * 基于权限码判断是否有权限
   * 支持超级管理员 '*' 通配符
   * @param codes 需要检查的权限码列表
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
