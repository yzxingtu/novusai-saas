<script setup lang="ts">
import { computed, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Spin } from 'ant-design-vue';

import NotificationSettings from '#/components/business/notification-panel/NotificationSettings.vue';
import { PreferenceForm } from '#/components/business/preference-form';
import { useGlobalPreferencePage } from '#/composables/use-global-preference-page';
import { $t } from '#/locales';

const props = defineProps<{
  apiPrefix: '/admin' | '/tenant';
  side: 'admin' | 'tenant';
}>();

const NOTIFICATION_SECTION_ANCHOR = 'preference-section-notification';
const PREFERENCE_FORM_SECTIONS = [
  {
    anchor: 'preference-section-appearance',
    icon: 'lucide:palette',
    labelKey: 'common.preference.tab.appearance',
  },
  {
    anchor: 'preference-section-layout',
    icon: 'lucide:panel-left-close',
    labelKey: 'common.preference.tab.layout',
  },
  {
    anchor: 'preference-section-shortcut',
    icon: 'lucide:keyboard',
    labelKey: 'preferences.shortcutKeys.title',
  },
  {
    anchor: 'preference-section-general',
    icon: 'lucide:sliders-horizontal',
    labelKey: 'preferences.general',
  },
] as const;

const { formData, isDirty, loading, saving, onSave } = useGlobalPreferencePage(
  props.side,
);

const notifSettingsRef = ref<InstanceType<typeof NotificationSettings>>();
const notifSaving = ref(false);

const themeModeLabelMap: Record<string, string> = {
  auto: 'preferences.followSystem',
  dark: 'preferences.theme.dark',
  light: 'preferences.theme.light',
};
const SECTION_SCROLL_OFFSET = 24;

const layoutModeLabelMap: Record<string, string> = {
  'full-content': 'preferences.fullContent',
  'header-mixed-nav': 'preferences.headerTwoColumn',
  'header-nav': 'preferences.horizontal',
  'header-sidebar-nav': 'preferences.headerSidebarNav',
  'mixed-nav': 'preferences.mixedMenu',
  'sidebar-mixed-nav': 'preferences.twoColumn',
  'sidebar-nav': 'preferences.vertical',
};

const localeLabelMap: Record<string, string> = {
  en: 'common.preference.option.en',
  'zh-CN': 'common.preference.option.zhCN',
};

function resolveMappedLabel(
  currentValue: string,
  mapping: Record<string, string>,
) {
  const labelKey = mapping[currentValue];
  return labelKey ? $t(labelKey) : $t('common.notSet');
}

const summaryItems = computed(() => {
  const themeMode = String(formData.value.theme_mode ?? '');
  const layoutMode = String(formData.value.layout_mode ?? '');
  const locale = String(formData.value.locale ?? '');

  return [
    {
      icon: 'lucide:palette',
      label: $t('common.preference.field.themeMode'),
      value: resolveMappedLabel(themeMode, themeModeLabelMap),
    },
    {
      icon: 'lucide:panel-left',
      label: $t('common.preference.field.layoutMode'),
      value: resolveMappedLabel(layoutMode, layoutModeLabelMap),
    },
    {
      icon: 'lucide:languages',
      label: $t('common.preference.field.locale'),
      value: resolveMappedLabel(locale, localeLabelMap),
    },
    {
      icon: 'lucide:settings-2',
      label: $t('common.preference.field.watermarkEnable'),
      value: formData.value.watermark_enable
        ? $t('common.enabled')
        : $t('common.disabled'),
    },
  ];
});

const quickLinks = computed(() => {
  return [
    ...PREFERENCE_FORM_SECTIONS.map((section) => ({
      anchor: section.anchor,
      icon: section.icon,
      label: $t(section.labelKey),
    })),
    {
      anchor: NOTIFICATION_SECTION_ANCHOR,
      icon: 'lucide:bell',
      label: $t('common.notification.globalTitle'),
    },
  ];
});

const endpointLabel = computed(() => {
  return props.side === 'admin'
    ? $t('common.endpoint.admin')
    : $t('common.endpoint.tenant');
});

function scrollToSection(anchor: string) {
  const target = document.querySelector<HTMLElement>(`#${anchor}`);
  if (!target) {
    return;
  }

  const scrollContainer = document.querySelector<HTMLElement>(
    '[data-preference-scroll-container]',
  );
  if (!scrollContainer) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }

  const containerRect = scrollContainer.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  const top =
    scrollContainer.scrollTop +
    targetRect.top -
    containerRect.top -
    SECTION_SCROLL_OFFSET;

  scrollContainer.scrollTo({
    behavior: 'smooth',
    top: Math.max(top, 0),
  });
}

async function onSaveNotif() {
  notifSaving.value = true;
  try {
    await notifSettingsRef.value?.save();
  } finally {
    notifSaving.value = false;
  }
}
</script>

<template>
  <Page auto-content-height>
    <div data-preference-scroll-container class="flex h-full flex-col gap-6 overflow-auto pb-4">
      <section
        class="relative overflow-hidden rounded-[28px] border border-border/70 bg-card shadow-sm"
      >
        <div
          class="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent"
        ></div>

        <div class="relative z-10 p-5 sm:p-6">
          <div class="space-y-5">
            <div class="space-y-3">
              <div
                class="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary"
              >
                <IconifyIcon icon="lucide:settings-2" class="size-3.5" />
                <span>{{ endpointLabel }}</span>
              </div>

              <div class="flex items-start gap-4">
                <div
                  class="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-sm"
                >
                  <IconifyIcon icon="lucide:settings-2" class="size-6" />
                </div>

                <div class="min-w-0">
                  <h1 class="text-xl font-semibold text-foreground sm:text-2xl">
                    {{ $t('common.preference.globalTitle') }}
                  </h1>
                  <p
                    class="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground"
                  >
                    {{ $t('common.preference.globalDesc') }}
                  </p>
                </div>
              </div>
            </div>

            <div class="flex flex-wrap gap-2">
              <div
                class="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/80 px-3 py-1 text-xs text-foreground"
              >
                <span
                  class="inline-block size-2 rounded-full bg-primary"
                ></span>
                <span>{{ $t('common.preview') }}</span>
                <span class="text-muted-foreground">/</span>
                <span>{{ $t('common.enabled') }}</span>
              </div>
              <div
                class="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/80 px-3 py-1 text-xs text-muted-foreground"
              >
                <IconifyIcon icon="lucide:sparkles" class="size-3.5" />
                <span>{{ $t('common.preference.globalSaveHint') }}</span>
              </div>
            </div>

            <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div
                v-for="item in summaryItems"
                :key="item.label"
                class="rounded-[22px] border border-border/60 bg-background/85 px-4 py-3"
              >
                <div class="mb-2 flex items-center gap-2 text-muted-foreground">
                  <IconifyIcon :icon="item.icon" class="size-4" />
                  <span class="text-xs font-medium uppercase tracking-[0.14em]">
                    {{ item.label }}
                  </span>
                </div>
                <div class="text-sm font-semibold text-foreground">
                  {{ item.value }}
                </div>
              </div>
              </div>
            </div>
          </div>
      </section>

      <section class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px] 2xl:grid-cols-[minmax(0,1fr)_380px]">
        <div class="min-w-0">
          <Spin :spinning="loading">
            <PreferenceForm v-model="formData" />
          </Spin>
        </div>

        <aside class="space-y-4 xl:sticky xl:top-4 xl:self-start">
          <section
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <div class="space-y-4">
              <div class="flex items-start gap-3">
                <div
                  class="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
                >
                  <IconifyIcon icon="lucide:save" class="size-5" />
                </div>
                <div class="min-w-0">
                  <div class="text-lg font-semibold text-foreground">
                    {{
                      isDirty
                        ? $t('shared.config.page.unsaved_title')
                        : $t('common.save')
                    }}
                  </div>
                  <p class="mt-1 text-sm leading-6 text-muted-foreground">
                    {{ $t('common.preference.globalSaveHint') }}
                  </p>
                </div>
              </div>

              <Button type="primary" block :loading="saving" @click="onSave">
                <template #icon>
                  <IconifyIcon icon="lucide:save" />
                </template>
                {{ $t('common.save') }}
              </Button>

              <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
                <button
                  v-for="link in quickLinks"
                  :key="link.anchor"
                  type="button"
                  class="flex items-center gap-2 rounded-2xl border border-border/60 bg-background/80 px-3 py-2 text-left text-sm text-foreground transition hover:border-primary/30 hover:bg-primary/5 hover:text-primary"
                  @click="scrollToSection(link.anchor)"
                >
                  <IconifyIcon :icon="link.icon" class="size-4" />
                  <span class="truncate">{{ link.label }}</span>
                </button>
              </div>
            </div>
          </section>

          <section
            :id="NOTIFICATION_SECTION_ANCHOR"
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <div class="mb-5 flex items-start justify-between gap-3">
              <div class="flex items-start gap-3">
                <div
                  class="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
                >
                  <IconifyIcon icon="lucide:bell" class="size-5" />
                </div>
                <div>
                  <div class="text-lg font-semibold text-foreground">
                    {{ $t('common.notification.globalTitle') }}
                  </div>
                  <p class="mt-1 text-sm leading-6 text-muted-foreground">
                    {{ $t('common.notification.globalDesc') }}
                  </p>
                </div>
              </div>

              <Button
                type="primary"
                :loading="notifSaving"
                @click="onSaveNotif"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:save" />
                </template>
                {{ $t('common.save') }}
              </Button>
            </div>

            <NotificationSettings
              ref="notifSettingsRef"
              mode="global"
              :api-prefix="apiPrefix"
            />
          </section>
        </aside>
      </section>
    </div>
  </Page>
</template>
