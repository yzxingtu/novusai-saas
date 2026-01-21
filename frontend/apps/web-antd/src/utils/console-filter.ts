/**
 * 控制台消息过滤器
 * 过滤掉框架产生的特定错误消息，避免干扰开发体验
 */

// 保存原始的 console.error 方法
const originalConsoleError = console.error;

/**
 * 修复 Ant Design Tabs 的 aria-hidden 警告
 *
 * 问题：ant-tabs-nav-more 按钮在展开下拉时同时设置了 aria-hidden="true"
 * 和 aria-expanded="true"，导致浏览器警告焦点元素被隐藏
 *
 * 解决：使用 MutationObserver 监听，当按钮展开时移除 aria-hidden 属性
 */
export function setupAriaHiddenFix(): void {
  if (typeof window === 'undefined' || typeof MutationObserver === 'undefined') {
    return;
  }

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type !== 'attributes' || mutation.attributeName !== 'aria-expanded') {
        continue;
      }

      const target = mutation.target as HTMLElement;
      // 检查是否是 Tabs 的 more 按钮
      if (!target.classList?.contains('ant-tabs-nav-more')) {
        continue;
      }

      // 当按钮展开时，移除 aria-hidden 属性
      if (target.getAttribute('aria-expanded') === 'true') {
        target.removeAttribute('aria-hidden');
      }
    }
  });

  // 延迟启动观察，等待 DOM 准备好
  setTimeout(() => {
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['aria-expanded'],
      subtree: true,
    });
  }, 0);
}

/**
 * 需要过滤的错误消息模式
 * 这些错误会被转换为更友好的提示，或直接忽略
 */
const FILTERED_ERROR_PATTERNS = [
  // 框架的路由组件无效错误 - 已在 menu-transformer 中输出友好提示
  /route component is invalid:/i,
];

/**
 * 设置控制台过滤器
 * 过滤掉框架产生的组件错误消息，因为我们已经在 menu-transformer 中输出了更友好的提示
 */
export function setupConsoleFilter(): void {
  console.error = (...args: any[]) => {
    // 检查第一个参数是否匹配需要过滤的模式
    const firstArg = args[0];
    if (typeof firstArg === 'string') {
      for (const pattern of FILTERED_ERROR_PATTERNS) {
        if (pattern.test(firstArg)) {
          // 跳过这条错误消息，因为已在 menu-transformer 中输出友好提示
          return;
        }
      }
    }

    // 其他错误正常输出
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
