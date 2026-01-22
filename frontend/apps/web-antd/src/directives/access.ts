/**
 * 权限指令
 * 扩展 @vben/access 的 v-access 指令，支持超级管理员 '*' 通配符
 *
 * 使用方式：
 * - v-access:code="['permission:code']" - 基于权限码控制
 * - v-access:role="['role_name']" - 基于角色控制
 *
 * 超级管理员（权限码包含 '*'）拥有所有权限
 */
import type { App, Directive, DirectiveBinding } from 'vue';

import { preferences } from '@vben/preferences';
import { useAccessStore, useUserStore } from '@vben/stores';

import { checkPermission } from '#/utils/access';

/**
 * 检查是否有访问权限
 * 返回 true 表示有权限，false 表示无权限
 */
function checkAccess(binding: DirectiveBinding<string | string[]>): boolean {
  const accessStore = useAccessStore();
  const userStore = useUserStore();

  const value = binding.value;

  // 没有指定权限码，默认有权限
  if (!value) return true;

  // 角色模式检查
  if (preferences.app.accessMode === 'frontend' && binding.arg === 'role') {
    const values = Array.isArray(value) ? value : [value];
    const userRoleSet = new Set(userStore.userRoles);
    return values.some((item) => userRoleSet.has(item));
  }

  // 权限码模式：使用共享的 checkPermission 函数
  return checkPermission(value, accessStore.accessCodes);
}

/**
 * 更新元素的显示状态
 * 使用 display: none 而不是 remove()，以支持权限变化后的重新检查
 */
function updateElementVisibility(
  el: HTMLElement,
  binding: DirectiveBinding<string | string[]>,
) {
  const hasAccess = checkAccess(binding);

  if (hasAccess) {
    // 有权限，恢复显示
    if (el.style.display === 'none') {
      el.style.display = '';
    }
  } else {
    // 无权限，隐藏元素
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
 * 注册自定义权限指令
 * 替代 @vben/access 的 registerAccessDirective
 */
export function registerCustomAccessDirective(app: App) {
  app.directive('access', accessDirective);
}

export { accessDirective };
