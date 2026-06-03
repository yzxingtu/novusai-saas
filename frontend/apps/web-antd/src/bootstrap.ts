import { createApp } from 'vue';

import { registerLoadingDirective } from '@vben/common-ui/es/loading';
import {
  disableOnlineIconifyRequests,
  ensureLucideIconSubsetRegistered,
} from '@vben/icons';
import { preferences } from '@vben/preferences';
import { initStores, useTabbarStore } from '@vben/stores';
import '@vben/styles';
import '@vben/styles/antd';

import AntDesignVue from 'ant-design-vue';

import { initComponentAdapter } from '#/adapter/component';
import { initSetupVbenForm } from '#/adapter/form';
import { setupVxeTable } from '#/adapter/vxe-table';
import { $t, $te, setupI18n } from '#/locales';
import { resolveRuntimeLocale } from '#/locales/runtime-locale';

import App from './app.vue';
import { registerCustomAccessDirective } from './directives/access';
import { setupDocumentTitleSync } from './layouts/document-title-sync';
import { router } from './router';
import { TokenStorage } from './store/shared/token-storage';
import { setupAriaHiddenFix, setupConsoleFilter } from './utils/console-filter';

import './styles/vxe-table-modern.css';

async function bootstrap(namespace: string) {
  disableOnlineIconifyRequests();
  ensureLucideIconSubsetRegistered();

  // 初始化 TokenStorage（多端 Token 分离存储）
  TokenStorage.init(namespace);

  // 设置控制台过滤器，过滤框架的组件错误输出 / filter noisy framework console errors
  setupConsoleFilter();

  // 修复 Ant Design Tabs 的 aria-hidden 警告 / Fix Ant Design Tabs aria-hidden warning
  setupAriaHiddenFix();

  // 初始化组件适配器 / Init component adapter
  await initComponentAdapter();

  // 初始化表单组件 / init form setup
  await initSetupVbenForm();

  // 初始化声明式表格 / init VXE table adapter
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

  app.config.errorHandler = (err, _instance, info) => {
    console.warn(`[Vue Error] ${info}:`, err);
  };

  // 注册v-loading指令
  registerLoadingDirective(app, {
    loading: 'loading', // 在这里可以自定义指令名称，也可以明确提供false表示不注册这个指令
    spinning: 'spinning',
  });

  // 国际化 i18n 配置 / setup i18n
  await setupI18n(app);

  // 配置 pinia-tore
  await initStores(app, { namespace });

  // 安装自定义权限指令（支持超级管理员 '*' 通配符）/ v-access + '*' wildcard
  registerCustomAccessDirective(app);

  const tabbarStore = useTabbarStore();

  // 初始化 tippy
  const { initTippy } = await import('@vben/common-ui/es/tippy');
  initTippy(app);

  // 全局注册 Ant Design Vue 组件（插件 Vue SFC 中使用 <a-button> 等模板标签需要）
  app.use(AntDesignVue);

  // 暴露插件共享依赖到 window（供插件 UMD 包引用）
  const { exposePluginShared } = await import('#/utils/plugin-shared');
  exposePluginShared();

  // 配置路由及路由守卫 / router + navigation guards
  app.use(router);

  // 配置Motion插件
  const { MotionPlugin } = await import('@vben/plugins/motion');
  app.use(MotionPlugin);

  // 动态更新标题 / document title from route meta
  setupDocumentTitleSync({
    appName: () => preferences.app.name,
    dynamicTitle: () => preferences.app.dynamicTitle,
    hasLocaleKey: $te,
    locale: () => resolveRuntimeLocale(),
    refreshSignal: () => tabbarStore.updateTime ?? 0,
    router,
    translate: $t,
  });

  app.mount('#app');
}

export { bootstrap };
