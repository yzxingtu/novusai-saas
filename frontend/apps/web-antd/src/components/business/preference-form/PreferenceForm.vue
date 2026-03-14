<script setup lang="ts">
/**
 * Global preference form using Vben's built-in preference blocks.
 * 使用 Vben 内置偏好块组件的全局偏好表单。
 */
import type {
  BreadcrumbStyleType,
  BuiltinThemeType,
  ContentCompactType,
  LayoutHeaderMenuAlignType,
  LayoutHeaderModeType,
  LayoutType,
  NavigationStyleType,
  PreferencesButtonPositionType,
  ThemeModeType,
} from '@vben/types';

import type { PreferencesData } from '#/api/shared/types';

import { computed, nextTick, reactive, ref, watch } from 'vue';

import type { SegmentedItem } from '@vben/layouts/preference-blocks';

import { usePreferences } from '@vben/preferences';

import {
  Animation,
  Block,
  Breadcrumb,
  BuiltinTheme,
  ColorMode,
  Content,
  FontSize,
  Footer,
  GlobalShortcutKeys,
  Header,
  Layout,
  Navigation,
  Radius,
  Sidebar,
  SwitchItem,
  Tabbar,
  Theme,
  VbenSegmented,
  Widget,
} from '@vben/layouts/preference-blocks';

import { Alert, Input, Switch } from 'ant-design-vue';

import { $t } from '#/locales';

interface Props {
  modelValue: PreferencesData;
  readonly?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false,
});

const emit = defineEmits<{
  'update:modelValue': [value: PreferencesData];
}>();

const form = reactive<Record<string, any>>({});

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      Object.assign(form, val);
    }
  },
  { immediate: true, deep: true },
);

function onFieldChange() {
  emit('update:modelValue', { ...form });
}

const {
  isDark,
  isFullContent,
  isHeaderNav,
  isHeaderSidebarNav,
  isMixedNav,
  isSideMixedNav,
  isSideMode,
  isSideNav,
} = usePreferences();

const activeTab = ref('appearance');

const tabs = computed((): SegmentedItem[] => [
  { label: $t('preferences.appearance'), value: 'appearance' },
  { label: $t('preferences.layout'), value: 'layout' },
  { label: $t('preferences.shortcutKeys.title'), value: 'shortcutKey' },
  { label: $t('preferences.general'), value: 'general' },
]);

const showBreadcrumbConfig = computed(() => {
  return (
    !isFullContent.value &&
    !isMixedNav.value &&
    !isHeaderNav.value
  );
});

// ── Computed bridge: flat snake_case form ↔ camelCase defineModel ──

function bridge<T>(key: string) {
  return computed<T>({
    get: () => form[key] as T,
    set: (v: T) => {
      form[key] = v;
      onFieldChange();
    },
  });
}

const themeMode = bridge<ThemeModeType>('theme_mode');
const themeSemiDarkSidebar = bridge<boolean>('semi_dark_sidebar');
const themeSemiDarkHeader = bridge<boolean>('semi_dark_header');
const themeBuiltinType = bridge<BuiltinThemeType>('builtin_type');
const themeColorPrimary = bridge<string>('color_primary');
const themeRadius = bridge<string>('radius');
const themeFontSize = bridge<number>('font_size');
const appColorWeakMode = bridge<boolean>('color_weak_mode');
const appColorGrayMode = bridge<boolean>('color_gray_mode');

const appLayout = bridge<LayoutType>('layout_mode');
const appContentCompact = bridge<ContentCompactType>('content_compact');
const sidebarEnable = bridge<boolean>('sidebar_enable');
const sidebarWidth = bridge<number>('sidebar_width');
const sidebarCollapsed = bridge<boolean>('sidebar_collapsed');
const sidebarCollapsedShowTitle = bridge<boolean>('sidebar_collapsed_show_title');
const sidebarAutoActivateChild = bridge<boolean>('sidebar_auto_activate_child');
const sidebarExpandOnHover = bridge<boolean>('sidebar_expand_on_hover');
const sidebarCollapsedButton = bridge<boolean>('sidebar_collapsed_button');
const sidebarFixedButton = bridge<boolean>('sidebar_fixed_button');
const headerEnable = bridge<boolean>('header_enable');
const headerMode = bridge<LayoutHeaderModeType>('header_mode');
const headerMenuAlign = bridge<LayoutHeaderMenuAlignType>('header_menu_align');
const navigationStyleType = bridge<NavigationStyleType>('navigation_style_type');
const navigationSplit = bridge<boolean>('navigation_split');
const navigationAccordion = bridge<boolean>('navigation_accordion');
const breadcrumbEnable = bridge<boolean>('breadcrumb_enable');
const breadcrumbShowIcon = bridge<boolean>('breadcrumb_show_icon');
const breadcrumbShowHome = bridge<boolean>('breadcrumb_show_home');
const breadcrumbStyleType = bridge<BreadcrumbStyleType>('breadcrumb_style_type');
const breadcrumbHideOnlyOne = bridge<boolean>('breadcrumb_hide_only_one');
const tabbarEnable = bridge<boolean>('tabbar_enable');
const tabbarShowIcon = bridge<boolean>('tabbar_show_icon');
const tabbarPersist = bridge<boolean>('tabbar_persist');
const tabbarDraggable = bridge<boolean>('tabbar_draggable');
const tabbarWheelable = bridge<boolean>('tabbar_wheelable');
const tabbarStyleType = bridge<string>('tabbar_style_type');
const tabbarShowMore = bridge<boolean>('tabbar_show_more');
const tabbarShowMaximize = bridge<boolean>('tabbar_show_maximize');
const tabbarMaxCount = bridge<number>('tabbar_max_count');
const tabbarMiddleClickToClose = bridge<boolean>('tabbar_middle_click_to_close');
const widgetGlobalSearch = bridge<boolean>('widget_global_search');
const widgetFullscreen = bridge<boolean>('widget_fullscreen');
const widgetLanguageToggle = bridge<boolean>('widget_language_toggle');
const widgetNotification = bridge<boolean>('widget_notification');
const widgetThemeToggle = bridge<boolean>('widget_theme_toggle');
const widgetSidebarToggle = bridge<boolean>('widget_sidebar_toggle');
const widgetLockScreen = bridge<boolean>('widget_lock_screen');
const widgetRefresh = bridge<boolean>('widget_refresh');
const widgetPreferencesButtonPosition = bridge<PreferencesButtonPositionType>('widget_preferences_button_position');
const footerEnable = bridge<boolean>('footer_enable');
const footerFixed = bridge<boolean>('footer_fixed');

const appLocale = bridge<string>('locale');
const dynamicTitle = bridge<boolean>('dynamic_title');
const shortcutKeysEnable = bridge<boolean>('shortcut_keys_enable');
const shortcutKeysGlobalSearch = bridge<boolean>('shortcut_keys_global_search');
const shortcutKeysGlobalLogout = bridge<boolean>('shortcut_keys_global_logout');
const shortcutKeysGlobalLockScreen = bridge<boolean>('shortcut_keys_global_lock_screen');
const transitionEnable = bridge<boolean>('transition_enable');
const transitionLoading = bridge<boolean>('transition_loading');
const transitionProgress = bridge<boolean>('transition_progress');
const transitionName = bridge<string>('transition_name');

const watermarkEnable = bridge<boolean>('watermark_enable');
const watermarkContent = bridge<string>('watermark_content');

const watermarkInputRef = ref<InstanceType<typeof Input>>();

const WATERMARK_VARS = [
  { key: '{tenant_name}', label: () => $t('common.preference.watermarkVar.tenantName') },
  { key: '{real_name}', label: () => $t('common.preference.watermarkVar.realName') },
  { key: '{username}', label: () => $t('common.preference.watermarkVar.username') },
  { key: '{user_id}', label: () => $t('common.preference.watermarkVar.userId') },
];

function insertWatermarkVar(varKey: string) {
  const el = watermarkInputRef.value?.$el?.querySelector?.('input') as
    | HTMLInputElement
    | undefined;
  if (!el) {
    watermarkContent.value = (watermarkContent.value || '') + varKey;
    return;
  }
  const start = el.selectionStart ?? el.value.length;
  const end = el.selectionEnd ?? start;
  const before = el.value.slice(0, start);
  const after = el.value.slice(end);
  watermarkContent.value = before + varKey + after;
  nextTick(() => {
    const pos = start + varKey.length;
    el.focus();
    el.setSelectionRange(pos, pos);
  });
}
</script>

<template>
  <div :class="{ 'pointer-events-none opacity-60': readonly }">
    <VbenSegmented v-model="activeTab" :tabs="tabs">
      <!-- ===== Appearance ===== -->
      <template #appearance>
        <Block :title="$t('preferences.theme.title')">
          <Theme
            v-model="themeMode"
            v-model:theme-semi-dark-sidebar="themeSemiDarkSidebar"
            v-model:theme-semi-dark-header="themeSemiDarkHeader"
          />
        </Block>
        <Block :title="$t('preferences.theme.builtin.title')">
          <BuiltinTheme
            v-model="themeBuiltinType"
            v-model:theme-color-primary="themeColorPrimary"
            :is-dark="isDark"
          />
        </Block>
        <Block :title="$t('preferences.theme.radius')">
          <Radius v-model:theme-radius="themeRadius" />
        </Block>
        <Block :title="$t('preferences.theme.fontSize')">
          <FontSize v-model="themeFontSize" />
        </Block>
        <Block :title="$t('preferences.other')">
          <ColorMode
            v-model:app-color-gray-mode="appColorGrayMode"
            v-model:app-color-weak-mode="appColorWeakMode"
          />
        </Block>
      </template>

      <!-- ===== Layout ===== -->
      <template #layout>
        <Block :title="$t('preferences.layout')">
          <Layout v-model="appLayout" />
        </Block>
        <Block :title="$t('preferences.content')">
          <Content v-model="appContentCompact" />
        </Block>
        <Block :title="$t('preferences.sidebar.title')">
          <Sidebar
            v-model:sidebar-auto-activate-child="sidebarAutoActivateChild"
            v-model:sidebar-collapsed="sidebarCollapsed"
            v-model:sidebar-collapsed-show-title="sidebarCollapsedShowTitle"
            v-model:sidebar-enable="sidebarEnable"
            v-model:sidebar-expand-on-hover="sidebarExpandOnHover"
            v-model:sidebar-width="sidebarWidth"
            v-model:sidebar-collapsed-button="sidebarCollapsedButton"
            v-model:sidebar-fixed-button="sidebarFixedButton"
            :current-layout="appLayout"
            :disabled="!isSideMode"
          />
        </Block>
        <Block :title="$t('preferences.header.title')">
          <Header
            v-model:header-enable="headerEnable"
            v-model:header-menu-align="headerMenuAlign"
            v-model:header-mode="headerMode"
            :disabled="isFullContent"
          />
        </Block>
        <Block :title="$t('preferences.navigationMenu.title')">
          <Navigation
            v-model:navigation-accordion="navigationAccordion"
            v-model:navigation-split="navigationSplit"
            v-model:navigation-style-type="navigationStyleType"
            :disabled="isFullContent"
            :disabled-navigation-split="!isMixedNav"
          />
        </Block>
        <Block :title="$t('preferences.breadcrumb.title')">
          <Breadcrumb
            v-model:breadcrumb-enable="breadcrumbEnable"
            v-model:breadcrumb-hide-only-one="breadcrumbHideOnlyOne"
            v-model:breadcrumb-show-home="breadcrumbShowHome"
            v-model:breadcrumb-show-icon="breadcrumbShowIcon"
            v-model:breadcrumb-style-type="breadcrumbStyleType"
            :disabled="
              !showBreadcrumbConfig ||
              !(isSideNav || isSideMixedNav || isHeaderSidebarNav)
            "
          />
        </Block>
        <Block :title="$t('preferences.tabbar.title')">
          <Tabbar
            v-model:tabbar-draggable="tabbarDraggable"
            v-model:tabbar-enable="tabbarEnable"
            v-model:tabbar-max-count="tabbarMaxCount"
            v-model:tabbar-middle-click-to-close="tabbarMiddleClickToClose"
            v-model:tabbar-persist="tabbarPersist"
            v-model:tabbar-show-icon="tabbarShowIcon"
            v-model:tabbar-show-maximize="tabbarShowMaximize"
            v-model:tabbar-show-more="tabbarShowMore"
            v-model:tabbar-style-type="tabbarStyleType"
            v-model:tabbar-wheelable="tabbarWheelable"
          />
        </Block>
        <Block :title="$t('preferences.widget.title')">
          <Widget
            v-model:app-preferences-button-position="widgetPreferencesButtonPosition"
            v-model:widget-fullscreen="widgetFullscreen"
            v-model:widget-global-search="widgetGlobalSearch"
            v-model:widget-language-toggle="widgetLanguageToggle"
            v-model:widget-lock-screen="widgetLockScreen"
            v-model:widget-notification="widgetNotification"
            v-model:widget-refresh="widgetRefresh"
            v-model:widget-sidebar-toggle="widgetSidebarToggle"
            v-model:widget-theme-toggle="widgetThemeToggle"
          />
        </Block>
        <Block :title="$t('preferences.footer.title')">
          <Footer
            v-model:footer-enable="footerEnable"
            v-model:footer-fixed="footerFixed"
          />
        </Block>
      </template>

      <!-- ===== Shortcut Keys ===== -->
      <template #shortcutKey>
        <Block :title="$t('preferences.shortcutKeys.global')">
          <GlobalShortcutKeys
            v-model:shortcut-keys-enable="shortcutKeysEnable"
            v-model:shortcut-keys-global-search="shortcutKeysGlobalSearch"
            v-model:shortcut-keys-lock-screen="shortcutKeysGlobalLockScreen"
            v-model:shortcut-keys-logout="shortcutKeysGlobalLogout"
          />
        </Block>
      </template>

      <!-- ===== General ===== -->
      <template #general>
        <Block :title="$t('preferences.general')">
          <div class="flex flex-col gap-2">
            <div
              class="text-muted-foreground flex items-center justify-between py-2 text-sm"
            >
              <span>{{ $t('preferences.language') }}</span>
              <select
                :value="appLocale"
                class="border-input bg-background h-8 rounded-md border px-2 text-sm"
                @change="
                  appLocale = ($event.target as HTMLSelectElement).value
                "
              >
                <option value="zh-CN">简体中文</option>
                <option value="en">English</option>
              </select>
            </div>
            <SwitchItem v-model="dynamicTitle">
              {{ $t('preferences.dynamicTitle') }}
            </SwitchItem>
          </div>
        </Block>
        <Block :title="$t('preferences.animation.title')">
          <Animation
            v-model:transition-enable="transitionEnable"
            v-model:transition-loading="transitionLoading"
            v-model:transition-name="transitionName"
            v-model:transition-progress="transitionProgress"
          />
        </Block>

        <Block :title="$t('common.preference.category.watermark')">
          <div class="flex flex-col gap-4">
            <div class="flex items-center justify-between">
              <span class="text-sm">{{
                $t('common.preference.field.watermarkEnable')
              }}</span>
              <Switch
                :checked="watermarkEnable"
                size="small"
                @update:checked="watermarkEnable = !!$event"
              />
            </div>
            <div v-if="watermarkEnable" class="flex flex-col gap-2">
              <span class="text-sm">{{
                $t('common.preference.field.watermarkContent')
              }}</span>
              <Input
                ref="watermarkInputRef"
                :value="watermarkContent"
                :placeholder="'{tenant_name} - {real_name}'"
                size="small"
                @update:value="watermarkContent = $event"
              />
              <div class="flex flex-wrap items-center gap-1.5">
                <span class="text-muted-foreground text-xs">{{
                  $t('common.preference.watermarkVar.insert')
                }}</span>
                <button
                  v-for="v in WATERMARK_VARS"
                  :key="v.key"
                  type="button"
                  class="bg-accent hover:bg-primary/10 hover:text-primary rounded px-1.5 py-0.5 font-mono text-xs transition"
                  @click="insertWatermarkVar(v.key)"
                >
                  {{ v.label() }}
                </button>
              </div>
            </div>
            <Alert
              type="info"
              show-icon
              :message="$t('common.preference.help.watermarkGlobalOnly')"
              class="!py-1 !text-xs"
            />
          </div>
        </Block>
      </template>
    </VbenSegmented>
  </div>
</template>
