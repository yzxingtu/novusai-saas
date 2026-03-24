/**
 * Console message filter utilities
 * 控制台消息过滤工具
 *
 * Used to filter and fix specific warnings and error messages in the console.
 * 用于过滤和修复控制台中的特定警告和错误消息。
 *
 * Avoids interfering with the development experience.
 * 避免干扰开发体验
 */

// Save the original console.error method / 保留原始 console.error
const originalConsoleError = console.error;

/**
 * Fix Ant Design Tabs aria-hidden warning
 * 修复 Ant Design Tabs 的 aria-hidden 警告
 *
 * When using Ant Design Tabs, it sets aria-hidden="true" on focusable elements
 * that also have aria-expanded="true", causing accessibility warnings.
 * This function uses MutationObserver to monitor and remove conflicting aria-hidden attributes.
 * 当使用 Ant Design 的 Tabs 组件时，它会在具有 aria-expanded="true" 的可聚焦元素上
 * 同时设置 aria-hidden="true"，导致无障碍警告。
 * 此函数通过 MutationObserver 监视并自动移除这些冲突的 aria-hidden 属性。
 */
export function setupAriaHiddenFix(): void {
  if (
    typeof window === 'undefined' ||
    typeof MutationObserver === 'undefined'
  ) {
    return;
  }

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (
        mutation.type !== 'attributes' ||
        mutation.attributeName !== 'aria-expanded'
      ) {
        continue;
      }

      const target = mutation.target as HTMLElement;
      // Check if it's the Tabs' more button / 是否为 Tabs「更多」按钮
      if (!target.classList?.contains('ant-tabs-nav-more')) {
        continue;
      }

      // Remove aria-hidden attribute when the button is expanded / 展开时移除 aria-hidden
      if (target.getAttribute('aria-expanded') === 'true') {
        target.removeAttribute('aria-hidden');
      }
    }
  });

  // Delay starting the observer to wait for the DOM to be ready
  // Global lifetime observer, intentionally no disconnect() — active for entire app lifecycle
  // 全局生命周期 observer，无需 disconnect，应用存活期间持续生效
  setTimeout(() => {
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['aria-expanded'],
      subtree: true,
    });
  }, 0);
}

/**
 * Filter console error messages
 * 过滤控制台错误消息
 *
 * Some framework errors are already handled more gracefully elsewhere;
 * this suppresses them in the console to avoid developer confusion.
 * 某些框架错误在其他地方已用更友好的方式处理，此处将其在控制台中抑制，
 * 避免给开发者造成困扰。
 */
const FILTERED_ERROR_PATTERNS = [
  // Framework's route component invalid error - already handled in menu-transformer / 路由无效错误已由 menu-transformer 处理
  /route component is invalid:/i,
];

/**
 * Set up the console filter
 * 设置控制台过滤器
 *
 * Filters out framework-generated component error messages, as we've already
 * output more user-friendly hints in menu-transformer.
 * 过滤掉框架产生的组件错误消息，因为我们已经在 menu-transformer 中输出了更友好的提示
 */
export function setupConsoleFilter(): void {
  console.error = (...args: any[]) => {
    // Check if the first argument matches a filtered pattern / 首参是否命中过滤规则
    const firstArg = args[0];
    if (typeof firstArg === 'string') {
      for (const pattern of FILTERED_ERROR_PATTERNS) {
        if (pattern.test(firstArg)) {
          // 跳过这条错误消息，因为已在 menu-transformer 中输出友好提示
          return;
        }
      }
    }

    // 其他错误正常输出 / passthrough other errors
    originalConsoleError.apply(console, args);
  };
}

/**
 * 恢复原始的 console.error
 * 用于测试或需要查看完整错误信息的场景
 */
export function restoreConsoleError(): void {
  console.error = originalConsoleError;
}
