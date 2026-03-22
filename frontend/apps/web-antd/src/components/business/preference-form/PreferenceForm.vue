<script setup lang="ts">
import type { WritableComputedRef } from 'vue';

/**
 * Global preference form with compact section cards.
 * 使用更细颗粒卡片分区的全局偏好表单。
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

import { IconifyIcon } from '@vben/icons';
import {
  Animation,
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
  Widget,
} from '@vben/layouts/preference-blocks';
import { usePreferences } from '@vben/preferences';

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

const form = reactive<PreferencesData>({});
const PREFERENCE_FORM_SECTIONS = [
  { anchor: 'preference-section-appearance', id: 'appearance' },
  { anchor: 'preference-section-layout', id: 'layout' },
  { anchor: 'preference-section-shortcut', id: 'shortcut' },
  { anchor: 'preference-section-general', id: 'general' },
] as const;

const panelClass =
  'rounded-[24px] border border-border/70 bg-card p-4 shadow-sm sm:p-5';
const subPanelClass =
  'rounded-2xl border border-border/60 bg-background/80 p-3.5';

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      Object.assign(form, val);
    }
  },
  { deep: true, immediate: true },
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

const showBreadcrumbConfig = computed(() => {
  return !isFullContent.value && !isMixedNav.value && !isHeaderNav.value;
});

type PreferencePrimitive = PreferencesData[string];

function bridge<T extends PreferencePrimitive>(
  key: string,
): WritableComputedRef<T> {
  return computed({
    get: () => form[key] as T,
    set: (value: T) => {
      form[key] = value as PreferencePrimitive;
      onFieldChange();
    },
  }) as WritableComputedRef<T>;
}

function getSectionAnchor(sectionId: string) {
  return (
    PREFERENCE_FORM_SECTIONS.find((section) => section.id === sectionId)
      ?.anchor ?? sectionId
  );
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
const sidebarCollapsedShowTitle = bridge<boolean>(
  'sidebar_collapsed_show_title',
);
const sidebarAutoActivateChild = bridge<boolean>('sidebar_auto_activate_child');
const sidebarExpandOnHover = bridge<boolean>('sidebar_expand_on_hover');
const sidebarCollapsedButton = bridge<boolean>('sidebar_collapsed_button');
const sidebarFixedButton = bridge<boolean>('sidebar_fixed_button');
const headerEnable = bridge<boolean>('header_enable');
const headerMode = bridge<LayoutHeaderModeType>('header_mode');
const headerMenuAlign = bridge<LayoutHeaderMenuAlignType>('header_menu_align');
const navigationStyleType = bridge<NavigationStyleType>(
  'navigation_style_type',
);
const navigationSplit = bridge<boolean>('navigation_split');
const navigationAccordion = bridge<boolean>('navigation_accordion');
const breadcrumbEnable = bridge<boolean>('breadcrumb_enable');
const breadcrumbShowIcon = bridge<boolean>('breadcrumb_show_icon');
const breadcrumbShowHome = bridge<boolean>('breadcrumb_show_home');
const breadcrumbStyleType = bridge<BreadcrumbStyleType>(
  'breadcrumb_style_type',
);
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
const tabbarMiddleClickToClose = bridge<boolean>(
  'tabbar_middle_click_to_close',
);
const widgetGlobalSearch = bridge<boolean>('widget_global_search');
const widgetFullscreen = bridge<boolean>('widget_fullscreen');
const widgetLanguageToggle = bridge<boolean>('widget_language_toggle');
const widgetNotification = bridge<boolean>('widget_notification');
const widgetThemeToggle = bridge<boolean>('widget_theme_toggle');
const widgetSidebarToggle = bridge<boolean>('widget_sidebar_toggle');
const widgetLockScreen = bridge<boolean>('widget_lock_screen');
const widgetRefresh = bridge<boolean>('widget_refresh');
const widgetPreferencesButtonPosition = bridge<PreferencesButtonPositionType>(
  'widget_preferences_button_position',
);
const footerEnable = bridge<boolean>('footer_enable');
const footerFixed = bridge<boolean>('footer_fixed');

const appLocale = bridge<string>('locale');
const dynamicTitle = bridge<boolean>('dynamic_title');
const shortcutKeysEnable = bridge<boolean>('shortcut_keys_enable');
const shortcutKeysGlobalSearch = bridge<boolean>('shortcut_keys_global_search');
const shortcutKeysGlobalLogout = bridge<boolean>('shortcut_keys_global_logout');
const shortcutKeysGlobalLockScreen = bridge<boolean>(
  'shortcut_keys_global_lock_screen',
);
const transitionEnable = bridge<boolean>('transition_enable');
const transitionLoading = bridge<boolean>('transition_loading');
const transitionProgress = bridge<boolean>('transition_progress');
const transitionName = bridge<string>('transition_name');

const watermarkEnable = bridge<boolean>('watermark_enable');
const watermarkContent = bridge<string>('watermark_content');

const watermarkInputRef = ref<InstanceType<typeof Input>>();

const WATERMARK_VARS = [
  {
    key: '{tenant_name}',
    label: () => $t('common.preference.watermarkVar.tenantName'),
  },
  {
    key: '{real_name}',
    label: () => $t('common.preference.watermarkVar.realName'),
  },
  {
    key: '{username}',
    label: () => $t('common.preference.watermarkVar.username'),
  },
  {
    key: '{user_id}',
    label: () => $t('common.preference.watermarkVar.userId'),
  },
] as const;

function insertWatermarkVar(varKey: string) {
  const inputElement = watermarkInputRef.value?.$el?.querySelector?.(
    'input',
  ) as HTMLInputElement | undefined;
  if (!inputElement) {
    watermarkContent.value = `${watermarkContent.value || ''}${varKey}`;
    return;
  }

  const start = inputElement.selectionStart ?? inputElement.value.length;
  const end = inputElement.selectionEnd ?? start;
  const before = inputElement.value.slice(0, start);
  const after = inputElement.value.slice(end);

  watermarkContent.value = `${before}${varKey}${after}`;

  nextTick(() => {
    const position = start + varKey.length;
    inputElement.focus();
    inputElement.setSelectionRange(position, position);
  });
}
</script>

<template>
  <div
    :class="{ 'pointer-events-none opacity-60': readonly }"
    class="space-y-8"
  >
    <section
      :id="getSectionAnchor('appearance')"
      class="scroll-mt-24 space-y-4"
    >
      <div class="flex items-center gap-3">
        <div
          class="flex size-10 items-center justify-center rounded-2xl bg-primary/10 text-primary"
        >
          <IconifyIcon icon="lucide:palette" class="size-5" />
        </div>
        <div>
          <p class="text-xs uppercase tracking-[0.18em] text-muted-foreground">
            {{ $t('common.preference.tab.appearance') }}
          </p>
          <h2 class="text-lg font-semibold text-foreground">
            {{ $t('common.preference.category.appearance') }}
          </h2>
        </div>
      </div>

      <div class="grid gap-4 xl:grid-cols-2">
        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:sparkles" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.category.theme') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('common.preference.field.themeMode') }}
              </div>
            </div>
          </div>
          <Theme
            v-model="themeMode"
            v-model:theme-semi-dark-header="themeSemiDarkHeader"
            v-model:theme-semi-dark-sidebar="themeSemiDarkSidebar"
          />
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:settings-2" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.field.builtinType') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('common.preference.field.colorPrimary') }}
              </div>
            </div>
          </div>
          <BuiltinTheme
            v-model="themeBuiltinType"
            v-model:theme-color-primary="themeColorPrimary"
            :is-dark="isDark"
          />
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:panel-left" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('preferences.theme.radius') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('preferences.theme.fontSize') }}
              </div>
            </div>
          </div>

          <div class="space-y-3">
            <div :class="subPanelClass">
              <div class="mb-3 text-xs font-medium text-muted-foreground">
                {{ $t('preferences.theme.radius') }}
              </div>
              <Radius v-model="themeRadius" />
            </div>
            <div :class="subPanelClass">
              <div class="mb-3 text-xs font-medium text-muted-foreground">
                {{ $t('preferences.theme.fontSize') }}
              </div>
              <FontSize v-model="themeFontSize" />
            </div>
          </div>
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:sliders-horizontal" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('preferences.other') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('preferences.theme.grayMode') }}
              </div>
            </div>
          </div>
          <ColorMode
            v-model:app-color-gray-mode="appColorGrayMode"
            v-model:app-color-weak-mode="appColorWeakMode"
          />
        </div>
      </div>
    </section>

    <section :id="getSectionAnchor('layout')" class="scroll-mt-24 space-y-4">
      <div class="flex items-center gap-3">
        <div
          class="flex size-10 items-center justify-center rounded-2xl bg-primary/10 text-primary"
        >
          <IconifyIcon icon="lucide:panel-left-close" class="size-5" />
        </div>
        <div>
          <p class="text-xs uppercase tracking-[0.18em] text-muted-foreground">
            {{ $t('common.preference.tab.layout') }}
          </p>
          <h2 class="text-lg font-semibold text-foreground">
            {{ $t('common.preference.category.layout') }}
          </h2>
        </div>
      </div>

      <div class="grid gap-4 xl:grid-cols-2">
        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:panel-left" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.field.layoutMode') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('preferences.layout') }}
              </div>
            </div>
          </div>
          <Layout v-model="appLayout" />
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:panel-left" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.field.contentCompact') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('preferences.content') }}
              </div>
            </div>
          </div>
          <Content v-model="appContentCompact" />
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:panel-left-open" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.category.sidebar') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('common.preference.field.sidebarWidth') }}
              </div>
            </div>
          </div>
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
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:settings-2" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.category.header') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('common.preference.field.headerMode') }}
              </div>
            </div>
          </div>
          <Header
            v-model:header-enable="headerEnable"
            v-model:header-menu-align="headerMenuAlign"
            v-model:header-mode="headerMode"
            :disabled="isFullContent"
          />
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:settings-2" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.category.navigation') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('common.preference.field.navigationStyleType') }}
              </div>
            </div>
          </div>
          <Navigation
            v-model:navigation-accordion="navigationAccordion"
            v-model:navigation-split="navigationSplit"
            v-model:navigation-style-type="navigationStyleType"
            :disabled="isFullContent"
            :disabled-navigation-split="!isMixedNav"
          />
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:panel-left" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.category.breadcrumb') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('common.preference.field.breadcrumbStyleType') }}
              </div>
            </div>
          </div>
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
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:panel-left" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.category.tabbar') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('common.preference.field.tabbarStyleType') }}
              </div>
            </div>
          </div>
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
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:sparkles" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.category.widget') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('preferences.position.title') }}
              </div>
            </div>
          </div>
          <Widget
            v-model:app-preferences-button-position="
              widgetPreferencesButtonPosition
            "
            v-model:widget-fullscreen="widgetFullscreen"
            v-model:widget-global-search="widgetGlobalSearch"
            v-model:widget-language-toggle="widgetLanguageToggle"
            v-model:widget-lock-screen="widgetLockScreen"
            v-model:widget-notification="widgetNotification"
            v-model:widget-refresh="widgetRefresh"
            v-model:widget-sidebar-toggle="widgetSidebarToggle"
            v-model:widget-theme-toggle="widgetThemeToggle"
          />
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:panel-left" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.category.footer') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('common.preference.field.footerFixed') }}
              </div>
            </div>
          </div>
          <Footer
            v-model:footer-enable="footerEnable"
            v-model:footer-fixed="footerFixed"
          />
        </div>
      </div>
    </section>

    <section :id="getSectionAnchor('shortcut')" class="scroll-mt-24 space-y-4">
      <div class="flex items-center gap-3">
        <div
          class="flex size-10 items-center justify-center rounded-2xl bg-primary/10 text-primary"
        >
          <IconifyIcon icon="lucide:keyboard" class="size-5" />
        </div>
        <div>
          <p class="text-xs uppercase tracking-[0.18em] text-muted-foreground">
            {{ $t('preferences.shortcutKeys.title') }}
          </p>
          <h2 class="text-lg font-semibold text-foreground">
            {{ $t('preferences.shortcutKeys.global') }}
          </h2>
        </div>
      </div>

      <div :class="panelClass">
        <div class="mb-4 flex items-center gap-2">
          <div
            class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
          >
            <IconifyIcon icon="lucide:keyboard" class="size-4" />
          </div>
          <div>
            <div class="text-sm font-semibold text-foreground">
              {{ $t('preferences.shortcutKeys.title') }}
            </div>
            <div class="text-xs text-muted-foreground">
              {{ $t('preferences.shortcutKeys.search') }}
            </div>
          </div>
        </div>
        <GlobalShortcutKeys
          v-model:shortcut-keys-enable="shortcutKeysEnable"
          v-model:shortcut-keys-global-search="shortcutKeysGlobalSearch"
          v-model:shortcut-keys-lock-screen="shortcutKeysGlobalLockScreen"
          v-model:shortcut-keys-logout="shortcutKeysGlobalLogout"
        />
      </div>
    </section>

    <section :id="getSectionAnchor('general')" class="scroll-mt-24 space-y-4">
      <div class="flex items-center gap-3">
        <div
          class="flex size-10 items-center justify-center rounded-2xl bg-primary/10 text-primary"
        >
          <IconifyIcon icon="lucide:sliders-horizontal" class="size-5" />
        </div>
        <div>
          <p class="text-xs uppercase tracking-[0.18em] text-muted-foreground">
            {{ $t('preferences.general') }}
          </p>
          <h2 class="text-lg font-semibold text-foreground">
            {{ $t('common.preference.category.language') }}
          </h2>
        </div>
      </div>

      <div class="grid gap-4 xl:grid-cols-2">
        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:languages" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.field.locale') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('preferences.dynamicTitle') }}
              </div>
            </div>
          </div>

          <div :class="subPanelClass">
            <div class="mb-2 text-xs font-medium text-muted-foreground">
              {{ $t('common.preference.field.locale') }}
            </div>
            <select
              :value="appLocale"
              class="h-10 w-full rounded-xl border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-primary/40"
              @change="appLocale = ($event.target as HTMLSelectElement).value"
            >
              <option value="zh-CN">
                {{ $t('common.preference.option.zhCN') }}
              </option>
              <option value="en">
                {{ $t('common.preference.option.en') }}
              </option>
            </select>
          </div>

          <div class="mt-3" :class="subPanelClass">
            <SwitchItem v-model="dynamicTitle">
              {{ $t('preferences.dynamicTitle') }}
            </SwitchItem>
          </div>
        </div>

        <div :class="panelClass">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:sparkles" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.category.animation') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('common.preference.field.transitionName') }}
              </div>
            </div>
          </div>
          <Animation
            v-model:transition-enable="transitionEnable"
            v-model:transition-loading="transitionLoading"
            v-model:transition-name="transitionName"
            v-model:transition-progress="transitionProgress"
          />
        </div>

        <div :class="`${panelClass} xl:col-span-2`">
          <div class="mb-4 flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:settings-2" class="size-4" />
            </div>
            <div>
              <div class="text-sm font-semibold text-foreground">
                {{ $t('common.preference.category.watermark') }}
              </div>
              <div class="text-xs text-muted-foreground">
                {{ $t('common.preference.field.watermarkContent') }}
              </div>
            </div>
          </div>

          <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
            <div class="space-y-3">
              <div :class="subPanelClass">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <div class="text-sm font-medium text-foreground">
                      {{ $t('common.preference.field.watermarkEnable') }}
                    </div>
                    <div class="text-xs text-muted-foreground">
                      {{ $t('common.preference.help.watermarkGlobalOnly') }}
                    </div>
                  </div>
                  <Switch
                    :checked="watermarkEnable"
                    size="small"
                    @update:checked="watermarkEnable = !!$event"
                  />
                </div>
              </div>

              <div v-if="watermarkEnable" :class="subPanelClass">
                <div class="mb-2 text-xs font-medium text-muted-foreground">
                  {{ $t('common.preference.field.watermarkContent') }}
                </div>
                <Input
                  ref="watermarkInputRef"
                  :value="watermarkContent"
                  size="small"
                  @update:value="watermarkContent = String($event ?? '')"
                />
                <div class="mt-3 flex flex-wrap items-center gap-1.5">
                  <span class="text-xs text-muted-foreground">
                    {{ $t('common.preference.watermarkVar.insert') }}
                  </span>
                  <button
                    v-for="variable in WATERMARK_VARS"
                    :key="variable.key"
                    type="button"
                    class="rounded-full border border-border/60 bg-background px-2.5 py-1 font-mono text-xs text-foreground transition hover:border-primary/30 hover:bg-primary/5 hover:text-primary"
                    @click="insertWatermarkVar(variable.key)"
                  >
                    {{ variable.label() }}
                  </button>
                </div>
              </div>
            </div>

            <Alert
              type="info"
              show-icon
              :message="$t('common.preference.help.watermarkVars')"
              class="!rounded-2xl !border !border-primary/15 !bg-primary/5"
            />
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
