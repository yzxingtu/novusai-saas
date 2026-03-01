/**
 * 天气插件前端入口
 *
 * UMD 构建后挂载到 window.NovusPlugin_weather_widget
 * 宿主通过 plugin-loader.ts 加载此包。
 */
import type { NovusPluginSharedAPI } from './types';

import WeatherHeaderWidget from './WeatherHeaderWidget.vue';
import { zhCN, enUS } from './locales';
import { WX_STYLES } from './styles';

/**
 * 插件 setup —— 宿主加载后自动调用
 *
 * 注册 i18n 翻译到宿主全局
 */
export function setup(): void {
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as NovusPluginSharedAPI | undefined;

  if (shared?.registerLocale) {
    shared.registerLocale('zh-CN', 'plugin.weather-widget', zhCN);
    shared.registerLocale('zh', 'plugin.weather-widget', zhCN);
    shared.registerLocale('en-US', 'plugin.weather-widget', enUS);
    shared.registerLocale('en', 'plugin.weather-widget', enUS);
  }

  // 注入全部插件样式（scoped CSS 在 Popover portal 中不生效，改为 JS 注入）
  if (!document.getElementById('wx-plugin-styles')) {
    const style = document.createElement('style');
    style.id = 'wx-plugin-styles';
    style.textContent = WX_STYLES;
    document.head.appendChild(style);
  }
}

export { WeatherHeaderWidget };
