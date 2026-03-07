import { defineOverridesPreferences } from '@vben/preferences';

/**
 * @description 项目配置文件
 * 只需要覆盖项目中的一部分配置，不需要的配置不用覆盖，会自动使用默认配置
 * !!! 更改配置后请清空缓存，否则可能不生效
 */
export const overridesPreferences = defineOverridesPreferences({
  app: {
    accessMode: 'backend',
    name: import.meta.env.VITE_APP_TITLE,
    enableRefreshToken: true,
    loginExpiredMode: 'page',
    defaultHomePath: '/',
    layout: 'sidebar-nav',
    locale: 'zh-CN',
    dynamicTitle: true,
    watermark: false,
    enableCheckUpdates: false,
    contentCompact: 'wide',
  },
  breadcrumb: {
    enable: true,
    showIcon: true,
    styleType: 'normal',
  },
  copyright: {
    companyName: 'NovusAI',
    date: '2025',
    enable: true,
    settingShow: true,
  },
  footer: {
    enable: false,
  },
  header: {
    enable: true,
    mode: 'fixed',
  },
  logo: {
    enable: true,
  },
  navigation: {
    accordion: true,
    split: true,
    styleType: 'rounded',
  },
  sidebar: {
    collapsed: false,
    collapsedButton: true,
    expandOnHover: true,
    width: 224,
  },
  tabbar: {
    enable: true,
    persist: true,
    showIcon: true,
    styleType: 'chrome',
    maxCount: 30,
    draggable: true,
    keepAlive: true,
  },
  theme: {
    builtinType: 'sky-blue',
    colorPrimary: 'hsl(231 98% 65%)',
    colorSuccess: 'hsl(144 57% 58%)',
    colorWarning: 'hsl(42 84% 61%)',
    colorDestructive: 'hsl(348 100% 61%)',
    mode: 'dark',
    radius: '0.5',
    fontSize: 16,
  },
  transition: {
    enable: true,
    loading: true,
    name: 'fade-slide',
    progress: true,
  },
  widget: {
    fullscreen: true,
    globalSearch: true,
    languageToggle: true,
    lockScreen: false,
    notification: true,
    themeToggle: true,
  },
});
