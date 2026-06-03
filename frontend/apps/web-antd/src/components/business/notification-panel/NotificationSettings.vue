<script lang="ts" setup>
/**
 * Notification Preferences Component
 * 通知偏好设置组件
 *
 * Supports two modes:
 * - 'personal' (default): Drawer with individual overrides, "reset to global" button,
 *   and per-row "following global / customized" indicators.
 * - 'global': Inline switch matrix for embedding in global preference pages.
 */
import { ref, watch } from 'vue';

import {
  Alert,
  Button,
  Drawer,
  message,
  Modal,
  Spin,
  Switch,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { showRequestError } from '#/utils/error-helpers';
import { requestClient } from '#/utils/request';

defineOptions({ name: 'NotificationSettings' });

const props = withDefaults(
  defineProps<{
    /** API prefix: '/admin' or '/tenant' / API 前缀 */
    apiPrefix?: string;
    /** 'personal' = Drawer with global fallback; 'global' = inline form / personal=抽屉+全局回退，global=内联表单 */
    mode?: 'global' | 'personal';
  }>(),
  {
    apiPrefix: undefined,
    mode: 'personal',
  },
);

const emit = defineEmits<{
  (e: 'saved'): void;
}>();

const visible = ref(false);
const loading = ref(false);
const saving = ref(false);
const resetting = ref(false);

const CATEGORIES = ['system', 'ai', 'task', 'biz', 'audit'];
const CHANNEL_ITEMS = [
  { key: 'channel_ws', labelKey: 'common.notification.channelWs' },
  { key: 'channel_inbox', labelKey: 'common.notification.channelInbox' },
  { key: 'channel_email', labelKey: 'common.notification.channelEmail' },
] as const;

type ChannelKey = (typeof CHANNEL_ITEMS)[number]['key'];

interface PrefRow {
  category: string;
  channel_ws: boolean;
  channel_email: boolean;
  channel_inbox: boolean;
  is_custom?: boolean;
}

const preferences = ref<PrefRow[]>([]);

function getApiBase(): string {
  if (props.apiPrefix) return props.apiPrefix;
  return window.location.pathname.startsWith('/tenant') ? '/tenant' : '/admin';
}

function getUrl(): string {
  const base = getApiBase();
  return props.mode === 'global'
    ? `${base}/notification-preferences/global`
    : `${base}/notification-preferences`;
}

async function loadPreferences() {
  loading.value = true;
  try {
    const data = await requestClient.get<PrefRow[]>(getUrl());
    preferences.value = Array.isArray(data)
      ? data
      : CATEGORIES.map((cat) => ({
          category: cat,
          channel_ws: true,
          channel_email: false,
          channel_inbox: true,
        }));
  } catch {
    preferences.value = CATEGORIES.map((cat) => ({
      category: cat,
      channel_ws: true,
      channel_email: false,
      channel_inbox: true,
    }));
  } finally {
    loading.value = false;
  }
}

async function handleSave() {
  saving.value = true;
  try {
    await requestClient.put(getUrl(), preferences.value);
    const msgKey =
      props.mode === 'global'
        ? 'common.notification.saveGlobalSuccess'
        : 'common.notification.savePersonalSuccess';
    message.success($t(msgKey));
    if (props.mode === 'personal') {
      visible.value = false;
    }
    emit('saved');
  } catch (error) {
    showRequestError(error, 'common.requestFailed');
  } finally {
    saving.value = false;
  }
}

async function handleReset() {
  Modal.confirm({
    title: $t('common.notification.resetToGlobal'),
    content: $t('common.notification.resetToGlobalConfirm'),
    okType: 'danger',
    async onOk() {
      resetting.value = true;
      try {
        await requestClient.delete(`${getApiBase()}/notification-preferences`);
        message.success($t('common.notification.resetSuccess'));
        await loadPreferences();
      } catch (error) {
        showRequestError(error, 'common.requestFailed');
      } finally {
        resetting.value = false;
      }
    },
  });
}

function getPref(category: string): PrefRow {
  let row = preferences.value.find((p) => p.category === category);
  if (!row) {
    row = {
      category,
      channel_ws: true,
      channel_email: false,
      channel_inbox: true,
    };
    preferences.value.push(row);
  }
  return row;
}

function setChannelValue(category: string, key: ChannelKey, value: boolean) {
  getPref(category)[key] = value;
}

/** Open settings drawer (personal mode only) / 打开设置抽屉（仅 personal 模式） */
async function open() {
  visible.value = true;
  await loadPreferences();
}

/** Load data externally (global mode) / 外部加载数据（global 模式） */
async function load() {
  await loadPreferences();
}

watch(
  () => props.mode,
  () => {
    if (props.mode === 'global') {
      loadPreferences();
    }
  },
  { immediate: true },
);

defineExpose({ open, load, save: handleSave });
</script>

<template>
  <!-- Global mode: inline content -->
  <template v-if="mode === 'global'">
    <Spin :spinning="loading">
      <Alert
        :message="$t('common.notification.globalDesc')"
        type="info"
        show-icon
        class="mb-4 !rounded-xl !border !border-primary/15 !bg-primary/5"
      />

      <div class="grid gap-3 md:grid-cols-2">
        <div
          v-for="cat in CATEGORIES"
          :key="cat"
          class="rounded-[22px] border border-border/70 bg-background/80 p-4 shadow-sm"
        >
          <div class="mb-4">
            <div class="text-sm font-semibold text-foreground">
              {{ $t(`common.notification.category.${cat}`) }}
            </div>
            <div class="mt-1 text-xs text-muted-foreground">
              {{ $t('common.notification.categoryLabel') }}
            </div>
          </div>

          <div class="space-y-2">
            <div
              v-for="channel in CHANNEL_ITEMS"
              :key="channel.key"
              class="flex items-center justify-between rounded-2xl border border-border/60 bg-card px-3 py-2.5"
            >
              <span class="text-sm text-foreground">
                {{ $t(channel.labelKey) }}
              </span>
              <Switch
                :checked="getPref(cat)[channel.key]"
                size="small"
                @update:checked="setChannelValue(cat, channel.key, !!$event)"
              />
            </div>
          </div>
        </div>
      </div>
    </Spin>
  </template>

  <!-- Personal mode: Drawer -->
  <Drawer
    v-else
    v-model:open="visible"
    :title="$t('common.notification.settingsTitle')"
    :width="520"
    destroy-on-close
  >
    <Spin :spinning="loading">
      <table class="w-full">
        <thead>
          <tr
            class="border-b border-border text-left text-xs text-muted-foreground"
          >
            <th class="pb-2 pr-4">
              {{ $t('common.notification.categoryLabel') }}
            </th>
            <th class="pb-2 text-center">
              {{ $t('common.notification.channelWs') }}
            </th>
            <th class="pb-2 text-center">
              {{ $t('common.notification.channelInbox') }}
            </th>
            <th class="pb-2 text-center">
              {{ $t('common.notification.channelEmail') }}
            </th>
            <th class="pb-2 text-center" style="width: 80px">
              {{ $t('common.status') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="cat in CATEGORIES"
            :key="cat"
            class="border-b border-border/30"
          >
            <td class="py-3 pr-4 text-sm font-medium text-foreground">
              {{ $t(`common.notification.category.${cat}`) }}
            </td>
            <td class="py-3 text-center">
              <Switch v-model:checked="getPref(cat).channel_ws" size="small" />
            </td>
            <td class="py-3 text-center">
              <Switch
                v-model:checked="getPref(cat).channel_inbox"
                size="small"
              />
            </td>
            <td class="py-3 text-center">
              <Switch
                v-model:checked="getPref(cat).channel_email"
                size="small"
              />
            </td>
            <td class="py-3 text-center">
              <Tag v-if="getPref(cat).is_custom" color="blue">
                {{ $t('common.notification.customized') }}
              </Tag>
              <Tag v-else color="default">
                {{ $t('common.notification.followGlobal') }}
              </Tag>
            </td>
          </tr>
        </tbody>
      </table>
    </Spin>
    <template #footer>
      <div class="flex justify-between">
        <Button danger :loading="resetting" @click="handleReset">
          {{ $t('common.notification.resetToGlobal') }}
        </Button>
        <div class="flex gap-2">
          <Button @click="visible = false">
            {{ $t('shared.common.cancel') }}
          </Button>
          <Button type="primary" :loading="saving" @click="handleSave">
            {{ $t('shared.common.save') }}
          </Button>
        </div>
      </div>
    </template>
  </Drawer>
</template>
