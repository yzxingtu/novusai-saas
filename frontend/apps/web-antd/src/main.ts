import { initPreferences } from '@vben/preferences';
import { unmountGlobalLoading } from '@vben/utils';

import { overridesPreferences } from './preferences';
import { sanitizePersistedTabbarStorage } from './utils/tabbar-storage';

/**
 * 应用初始化完成之后再进行页面加载渲染
 */
async function initApplication() {
  // name用于指定项目唯一标识 / name: project unique ID for preferences, storage key prefix, data isolation
  const env = import.meta.env.PROD ? 'prod' : 'dev';
  const appVersion = import.meta.env.VITE_APP_VERSION;
  const namespace = `${import.meta.env.VITE_APP_NAMESPACE}-${appVersion}-${env}`;

  // 先修复同标签页遗留的异常 tabbar 持久化状态，避免 F5 后继续卡顿 / Fix stale tabbar state before F5
  sanitizePersistedTabbarStorage(namespace);

  // app偏好设置初始化 / Init app preferences
  await initPreferences({
    namespace,
    overrides: overridesPreferences,
  });

  // 启动应用并挂载 / Start app and mount Vue
  const { bootstrap } = await import('./bootstrap');
  await bootstrap(namespace);

  // 移除并销毁loading / Remove and destroy loading
  unmountGlobalLoading();
}

initApplication();
