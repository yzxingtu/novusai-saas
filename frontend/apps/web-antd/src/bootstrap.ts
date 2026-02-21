import { createApp, watchEffect } from 'vue';

import { registerLoadingDirective } from '@vben/common-ui/es/loading';
import { preferences } from '@vben/preferences';
import { initStores } from '@vben/stores';
import '@vben/styles';
import '@vben/styles/antd';
import './styles/vxe-table-modern.css';

import { useTitle } from '@vueuse/core';

import { initComponentAdapter } from '#/adapter/component';
import { initSetupVbenForm } from '#/adapter/form';
import { setupVxeTable } from '#/adapter/vxe-table';
import { $t, setupI18n } from '#/locales';

import App from './app.vue';
import { registerCustomAccessDirective } from './directives/access';
import { router } from './router';
import { TokenStorage } from './store/shared/token-storage';
import { setupAriaHiddenFix, setupConsoleFilter } from './utils/console-filter';

async function bootstrap(namespace: string) {
  // 初始化 TokenStorage（多端 Token 分离存储）
  TokenStorage.init(namespace);

  // 设置控制台过滤器，过滤框架的组件错误输出
  setupConsoleFilter();

  // 修复 Ant Design Tabs 的 aria-hidden 警告
  setupAriaHiddenFix();

  // 初始化组件适配器
  await initComponentAdapter();

  // 初始化表单组件
  await initSetupVbenForm();

  // 初始化声明式表格
  setupVxeTable();

  // // 设置弹窗的默认配置
  // setDefaultModalProps({
  //   fullscreenButton: false,
  // });
  // // 设置抽屉的默认配置
  // setDefaultDrawerProps({
  //   zIndex: 1020,
  // });

  const app = createApp(App);

  // 注册v-loading指令
  registerLoadingDirective(app, {
    loading: 'loading', // 在这里可以自定义指令名称，也可以明确提供false表示不注册这个指令
    spinning: 'spinning',
  });

  // 国际化 i18n 配置
  await setupI18n(app);

  // 配置 pinia-tore
  await initStores(app, { namespace });

  // 安装自定义权限指令（支持超级管理员 '*' 通配符）
  registerCustomAccessDirective(app);

  // 初始化 tippy
  const { initTippy } = await import('@vben/common-ui/es/tippy');
  initTippy(app);

  // 配置路由及路由守卫
  app.use(router);

  // 配置Motion插件
  const { MotionPlugin } = await import('@vben/plugins/motion');
  app.use(MotionPlugin);

  // 动态更新标题
  watchEffect(() => {
    if (preferences.app.dynamicTitle) {
      const routeTitle = router.currentRoute.value.meta?.title;
      const pageTitle =
        (routeTitle ? `${$t(routeTitle)} - ` : '') + preferences.app.name;
      useTitle(pageTitle);
    }
  });

  app.mount('#app');
}

export { bootstrap };
