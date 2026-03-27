import type { Preferences } from '@vben/preferences';
/**
 * User preference store / 用户偏好 Store
 *
 * 管理用户偏好设置的加载、同步与更新。
 * 登录后从后端拉取生效偏好，与 @vben/preferences 双向同步。
 * Manages preference loading, syncing, and updates.
 * Loads effective preferences from backend after login, syncs with @vben/preferences.
 */
import type { DeepPartial } from '@vben/types';

import type { PreferencesData } from '#/api/shared/types';

import {
  updatePreferences,
  preferences as vbenPreferences,
} from '@vben/preferences';

import { defineStore } from 'pinia';

import {
  getAdminGlobalPreferencesApi,
  getAdminMyPreferencesApi,
  resetAdminMyPreferencesApi,
  updateAdminGlobalPreferencesApi,
  updateAdminMyPreferencesApi,
} from '#/api/admin/preferences';
import {
  getTenantGlobalPreferencesApi,
  getTenantMyPreferencesApi,
  resetTenantMyPreferencesApi,
  updateTenantGlobalPreferencesApi,
  updateTenantMyPreferencesApi,
} from '#/api/tenant/preferences';

type EndpointSide = 'admin' | 'tenant';

interface UserPreferenceState {
  /** 当前生效偏好 / Current effective preferences */
  preferences: null | PreferencesData;
  /** 全局偏好 / Global preferences */
  globalPreferences: null | PreferencesData;
  /** 是否已加载 / Whether loaded */
  loaded: boolean;
  /** 加载中 / Loading */
  loading: boolean;
  /** 当前端 / Current endpoint side */
  side: EndpointSide | null;
  /** 全局偏好页面正在实时预览中，阻止个人偏好同步 / Global preference page is live-previewing, block personal sync */
  globalPreviewActive: boolean;
}

/**
 * 全局专属 key（水印等），不参与个人偏好同步
 * Global-only keys (watermark, etc.), excluded from personal preference sync
 */
const GLOBAL_ONLY_KEYS = new Set(['watermark_content', 'watermark_enable']);

/**
 * 后端 flat key -> Vben 嵌套路径映射表
 * Backend flat key -> Vben nested path mapping
 */
const FLAT_TO_VBEN_MAP: Record<string, [string, string]> = {
  // Appearance / 外观
  theme_mode: ['theme', 'mode'],
  builtin_type: ['theme', 'builtinType'],
  color_primary: ['theme', 'colorPrimary'],
  radius: ['theme', 'radius'],
  font_size: ['theme', 'fontSize'],
  semi_dark_sidebar: ['theme', 'semiDarkSidebar'],
  semi_dark_header: ['theme', 'semiDarkHeader'],
  color_weak_mode: ['app', 'colorWeakMode'],
  color_gray_mode: ['app', 'colorGrayMode'],
  // Layout / 布局
  layout_mode: ['app', 'layout'],
  content_compact: ['app', 'contentCompact'],
  locale: ['app', 'locale'],
  // General / 通用
  dynamic_title: ['app', 'dynamicTitle'],
  // Sidebar / 侧栏
  sidebar_enable: ['sidebar', 'enable'],
  sidebar_collapsed: ['sidebar', 'collapsed'],
  sidebar_expand_on_hover: ['sidebar', 'expandOnHover'],
  sidebar_collapsed_show_title: ['sidebar', 'collapsedShowTitle'],
  sidebar_auto_activate_child: ['sidebar', 'autoActivateChild'],
  sidebar_width: ['sidebar', 'width'],
  sidebar_collapsed_button: ['sidebar', 'collapsedButton'],
  sidebar_fixed_button: ['sidebar', 'fixedButton'],
  // Header / 顶栏
  header_enable: ['header', 'enable'],
  header_mode: ['header', 'mode'],
  header_menu_align: ['header', 'menuAlign'],
  // Navigation / 导航
  navigation_style_type: ['navigation', 'styleType'],
  navigation_split: ['navigation', 'split'],
  navigation_accordion: ['navigation', 'accordion'],
  // Breadcrumb / 面包屑
  breadcrumb_enable: ['breadcrumb', 'enable'],
  breadcrumb_hide_only_one: ['breadcrumb', 'hideOnlyOne'],
  breadcrumb_show_icon: ['breadcrumb', 'showIcon'],
  breadcrumb_show_home: ['breadcrumb', 'showHome'],
  breadcrumb_style_type: ['breadcrumb', 'styleType'],
  // Tabbar / 标签栏
  tabbar_enable: ['tabbar', 'enable'],
  tabbar_persist: ['tabbar', 'persist'],
  tabbar_max_count: ['tabbar', 'maxCount'],
  tabbar_draggable: ['tabbar', 'draggable'],
  tabbar_wheelable: ['tabbar', 'wheelable'],
  tabbar_middle_click_to_close: ['tabbar', 'middleClickToClose'],
  tabbar_show_icon: ['tabbar', 'showIcon'],
  tabbar_show_more: ['tabbar', 'showMore'],
  tabbar_show_maximize: ['tabbar', 'showMaximize'],
  tabbar_style_type: ['tabbar', 'styleType'],
  // Widget / 小部件
  widget_global_search: ['widget', 'globalSearch'],
  widget_theme_toggle: ['widget', 'themeToggle'],
  widget_language_toggle: ['widget', 'languageToggle'],
  widget_fullscreen: ['widget', 'fullscreen'],
  widget_notification: ['widget', 'notification'],
  widget_lock_screen: ['widget', 'lockScreen'],
  widget_sidebar_toggle: ['widget', 'sidebarToggle'],
  widget_refresh: ['widget', 'refresh'],
  widget_preferences_button_position: ['widget', 'preferencesButtonPosition'],
  // Footer / 页脚
  footer_enable: ['footer', 'enable'],
  footer_fixed: ['footer', 'fixed'],
  // Shortcut Keys / 快捷键
  shortcut_keys_enable: ['shortcutKeys', 'enable'],
  shortcut_keys_global_search: ['shortcutKeys', 'globalSearch'],
  shortcut_keys_global_logout: ['shortcutKeys', 'globalLogout'],
  shortcut_keys_global_lock_screen: ['shortcutKeys', 'globalLockScreen'],
  // Transition / 动画
  transition_enable: ['transition', 'enable'],
  transition_loading: ['transition', 'loading'],
  transition_progress: ['transition', 'progress'],
  transition_name: ['transition', 'name'],
};

/**
 * Vben 嵌套路径 -> 后端 flat key 反向映射表（自动构建）
 * Vben nested path -> Backend flat key reverse mapping (auto-built)
 */
const VBEN_TO_FLAT_MAP: Record<string, Record<string, string>> = {};
for (const [flatKey, [group, subKey]] of Object.entries(FLAT_TO_VBEN_MAP)) {
  const groupMap = (VBEN_TO_FLAT_MAP[group] ??= {});
  groupMap[subKey] = flatKey;
}

/**
 * 后端 flat 偏好 -> Vben DeepPartial<Preferences>
 * Backend flat preferences -> Vben DeepPartial<Preferences>
 */
export function mapToVbenPreferences(
  prefs: PreferencesData,
): DeepPartial<Preferences> {
  const mapped: Record<string, Record<string, unknown>> = {};

  for (const [flatKey, value] of Object.entries(prefs)) {
    const path = FLAT_TO_VBEN_MAP[flatKey];
    if (!path) continue;
    const [group, subKey] = path;
    const groupMap = (mapped[group] ??= {});
    groupMap[subKey] = value;
  }

  return mapped as DeepPartial<Preferences>;
}

/**
 * Vben preferences -> 后端 flat 偏好（仅提取有映射的 key，排除全局专属 key）
 * Vben preferences -> backend flat preferences (only mapped keys, excluding global-only keys)
 */
export function mapFromVbenPreferences(
  vben: Readonly<Preferences>,
): PreferencesData {
  const result: PreferencesData = {};

  for (const [group, subMap] of Object.entries(VBEN_TO_FLAT_MAP)) {
    const groupObj = vben[group as keyof Preferences];
    if (!groupObj || typeof groupObj !== 'object') continue;

    for (const [subKey, flatKey] of Object.entries(subMap)) {
      if (GLOBAL_ONLY_KEYS.has(flatKey)) continue;
      const value = (groupObj as unknown as Record<string, unknown>)[subKey];
      if (value !== undefined) {
        result[flatKey] = value as boolean | number | string;
      }
    }
  }

  return result;
}

/**
 * 获取当前 Vben preferences 快照（仅管理的 key）
 * Get current Vben preferences snapshot (only managed keys)
 */
export function getVbenSnapshot(): PreferencesData {
  return mapFromVbenPreferences(
    vbenPreferences as unknown as Readonly<Preferences>,
  );
}

export const useUserPreferenceStore = defineStore('userPreference', {
  state: (): UserPreferenceState => ({
    preferences: null,
    globalPreferences: null,
    loaded: false,
    loading: false,
    side: null,
    globalPreviewActive: false,
  }),

  getters: {
    /** 获取指定偏好值 / Get specific preference value */
    getPref:
      (state) =>
      (key: string): boolean | number | string | undefined => {
        return state.preferences?.[key];
      },
  },

  actions: {
    /**
     * 登录后加载偏好并同步到框架
     * Load preferences after login and sync to framework
     */
    async loadPreferences(side: EndpointSide): Promise<null | PreferencesData> {
      if (this.loading) return this.preferences;

      this.loading = true;
      this.side = side;

      try {
        const getMyApi =
          side === 'admin'
            ? getAdminMyPreferencesApi
            : getTenantMyPreferencesApi;

        const prefs = await getMyApi();
        this.preferences = prefs;
        this.loaded = true;

        this._applyToVben(prefs);

        return prefs;
      } catch (error) {
        console.error('[UserPreference] Failed to load preferences:', error);
        return null;
      } finally {
        this.loading = false;
      }
    },

    /**
     * 加载全局偏好（管理全局偏好页面用）
     * Load global preferences (for global preference settings page)
     */
    async loadGlobalPreferences(
      side: EndpointSide,
    ): Promise<null | PreferencesData> {
      try {
        const getGlobalApi =
          side === 'admin'
            ? getAdminGlobalPreferencesApi
            : getTenantGlobalPreferencesApi;

        const prefs = await getGlobalApi();
        this.globalPreferences = prefs;
        return prefs;
      } catch (error) {
        console.error(
          '[UserPreference] Failed to load global preferences:',
          error,
        );
        return null;
      }
    },

    /**
     * 更新全局偏好并立即应用到本地 UI
     * Update global preferences and immediately apply to local UI
     *
     * 保存后同时更新 this.preferences + Vben 状态，确保操作者自身
     * 立即看到变更（水印、主题等），无需等待 WS 事件到达。
     * WS 事件在 ~ms 级到达后会设置 skipNextSync，阻止防抖回调
     * 将这些值误写为个人偏好。
     */
    async updateGlobalPreferences(
      side: EndpointSide,
      data: PreferencesData,
    ): Promise<null | PreferencesData> {
      try {
        const updateGlobalApi =
          side === 'admin'
            ? updateAdminGlobalPreferencesApi
            : updateTenantGlobalPreferencesApi;

        const prefs = await updateGlobalApi(data);
        this.globalPreferences = prefs;

        if (this.preferences) {
          this.preferences = { ...this.preferences, ...prefs };
        }
        this._applyToVben(prefs);

        return prefs;
      } catch (error) {
        console.error(
          '[UserPreference] Failed to update global preferences:',
          error,
        );
        return null;
      }
    },

    /**
     * 更新个人偏好并同步到框架
     * Update individual preferences and sync to framework
     */
    async updateMyPreferences(
      data: PreferencesData,
    ): Promise<null | PreferencesData> {
      const side = this.side;
      if (!side) return null;

      try {
        const updateMyApi =
          side === 'admin'
            ? updateAdminMyPreferencesApi
            : updateTenantMyPreferencesApi;

        const prefs = await updateMyApi(data);
        this.preferences = prefs;
        return prefs;
      } catch (error) {
        console.error('[UserPreference] Failed to update preferences:', error);
        return null;
      }
    },

    /**
     * 重置个人偏好（恢复全局默认）
     * Reset individual preferences (restore to global defaults)
     */
    async resetMyPreferences(): Promise<null | PreferencesData> {
      const side = this.side;
      if (!side) return null;

      try {
        const resetApi =
          side === 'admin'
            ? resetAdminMyPreferencesApi
            : resetTenantMyPreferencesApi;

        const prefs = await resetApi();
        this.preferences = prefs;
        this._applyToVben(prefs);
        return prefs;
      } catch (error) {
        console.error('[UserPreference] Failed to reset preferences:', error);
        return null;
      }
    },

    /**
     * 清空本地缓存（登出时调用）
     * Clear local cache (called on logout)
     */
    clearPreferences() {
      this.preferences = null;
      this.globalPreferences = null;
      this.loaded = false;
      this.side = null;
    },

    /**
     * 将偏好同步到 @vben/preferences
     * Sync preferences to @vben/preferences
     */
    _applyToVben(prefs: PreferencesData) {
      const mapped = mapToVbenPreferences(prefs);
      if (Object.keys(mapped).length > 0) {
        updatePreferences(mapped as Parameters<typeof updatePreferences>[0]);
      }
    },
  },
});
