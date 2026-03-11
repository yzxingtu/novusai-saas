/**
 * Access permission directive
 * Extends @vben/access v-access directive with super admin '*' wildcard support
 * 权限指令
 * 扩展 @vben/access 的 v-access 指令，支持超级管理员 '*' 通配符
 *
 * Usage / 使用方式：
 * - v-access:code="['permission:code']" - Permission code based control / 基于权限码控制
 * - v-access:role="['role_name']" - Role based control / 基于角色控制
 *
 * Super admins (permission codes include '*') have all permissions
 * 超级管理员（权限码包含 '*'）拥有所有权限
 */
import type { App, Directive, DirectiveBinding } from 'vue';

import { preferences } from '@vben/preferences';
import { useAccessStore, useUserStore } from '@vben/stores';

import { checkPermission } from '#/utils/access';

/**
 * Check if access is permitted
 * Returns true for permitted, false for denied
 * 检查是否有访问权限
 * 返回 true 表示有权限，false 表示无权限
 */
function checkAccess(binding: DirectiveBinding<string | string[]>): boolean {
  const accessStore = useAccessStore();
  const userStore = useUserStore();

  const value = binding.value;

  // No permission code specified, default to permitted / 没有指定权限码，默认有权限
  if (!value) return true;

  // Role mode check / 角色模式检查
  if (preferences.app.accessMode === 'frontend' && binding.arg === 'role') {
    const values = Array.isArray(value) ? value : [value];
    const userRoleSet = new Set(userStore.userRoles);
    return values.some((item) => userRoleSet.has(item));
  }

  // Permission code mode: use shared checkPermission function / 权限码模式：使用共享的 checkPermission 函数
  return checkPermission(value, accessStore.accessCodes);
}

/**
 * Update element visibility
 * Uses display: none instead of remove() to support re-checking after permission changes
 * 更新元素的显示状态
 * 使用 display: none 而不是 remove()，以支持权限变化后的重新检查
 */
function updateElementVisibility(
  el: HTMLElement,
  binding: DirectiveBinding<string | string[]>,
) {
  const hasAccess = checkAccess(binding);

  if (hasAccess) {
    // Permitted, restore display / 有权限，恢复显示
    if (el.style.display === 'none') {
      el.style.display = '';
    }
  } else {
    // Not permitted, hide element / 无权限，隐藏元素
    el.style.display = 'none';
  }
}

const accessDirective: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding<string | string[]>) {
    updateElementVisibility(el, binding);
  },
  updated(el: HTMLElement, binding: DirectiveBinding<string | string[]>) {
    updateElementVisibility(el, binding);
  },
};

/**
 * Register custom access directive
 * Replaces @vben/access registerAccessDirective
 * 注册自定义权限指令
 * 替代 @vben/access 的 registerAccessDirective
 */
export function registerCustomAccessDirective(app: App) {
  app.directive('access', accessDirective);
}

export { accessDirective };
