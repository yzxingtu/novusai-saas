<script lang="ts" setup>
/**
 * 通知偏好设置组件
 *
 * 5 类 × 3 渠道的 Switch 矩阵，保存到后端。
 */
defineOptions({ name: 'NotificationSettings' });

import { onMounted, ref } from 'vue';

import { Button, Drawer, Spin, Switch, message } from 'ant-design-vue';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

const props = defineProps<{
  /** API 前缀: '/admin' 或 '/tenant' */
  apiPrefix?: string;
}>();

const visible = ref(false);
const loading = ref(false);
const saving = ref(false);

const CATEGORIES = ['system', 'ai', 'task', 'biz', 'audit'];

interface PrefRow {
  category: string;
  channel_ws: boolean;
  channel_email: boolean;
  channel_inbox: boolean;
}

const preferences = ref<PrefRow[]>([]);

function getApiBase(): string {
  return props.apiPrefix || '/admin';
}

/** 打开设置面板 */
async function open() {
  visible.value = true;
  await loadPreferences();
}

/** 加载偏好数据 */
async function loadPreferences() {
  loading.value = true;
  try {
    const data = await requestClient.get<PrefRow[]>(
      `${getApiBase()}/notification-preferences`,
    );
    if (Array.isArray(data)) {
      preferences.value = data;
    } else {
      // 如果 API 未实现，初始化默认值
      preferences.value = CATEGORIES.map((cat) => ({
        category: cat,
        channel_ws: true,
        channel_email: false,
        channel_inbox: true,
      }));
    }
  } catch {
    // API 不存在时使用默认值
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

/** 确保所有分类都有行 */
function ensureAllCategories() {
  for (const cat of CATEGORIES) {
    if (!preferences.value.find((p) => p.category === cat)) {
      preferences.value.push({
        category: cat,
        channel_ws: true,
        channel_email: false,
        channel_inbox: true,
      });
    }
  }
}

/** 保存偏好 */
async function handleSave() {
  saving.value = true;
  try {
    await requestClient.put(
      `${getApiBase()}/notification-preferences`,
      preferences.value,
    );
    message.success($t('common.saveSuccess'));
    visible.value = false;
  } catch {
    message.error($t('common.requestFailed'));
  } finally {
    saving.value = false;
  }
}

/** 获取分类对应的偏好行 */
function getPref(category: string): PrefRow {
  return (
    preferences.value.find((p) => p.category === category) || {
      category,
      channel_ws: true,
      channel_email: false,
      channel_inbox: true,
    }
  );
}

onMounted(() => {
  ensureAllCategories();
});

defineExpose({ open });
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="$t('common.notification.settingsTitle')"
    :width="480"
    destroy-on-close
  >
    <Spin :spinning="loading">
      <table class="w-full">
        <thead>
          <tr class="border-b border-border text-left text-xs text-muted-foreground">
            <th class="pb-2 pr-4">{{ $t('common.notification.categoryLabel') }}</th>
            <th class="pb-2 text-center">{{ $t('common.notification.channelWs') }}</th>
            <th class="pb-2 text-center">{{ $t('common.notification.channelInbox') }}</th>
            <th class="pb-2 text-center">{{ $t('common.notification.channelEmail') }}</th>
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
              <Switch
                v-model:checked="getPref(cat).channel_ws"
                size="small"
              />
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
          </tr>
        </tbody>
      </table>
    </Spin>
    <template #footer>
      <div class="flex justify-end gap-2">
        <Button @click="visible = false">{{ $t('shared.common.cancel') }}</Button>
        <Button type="primary" :loading="saving" @click="handleSave">
          {{ $t('shared.common.save') }}
        </Button>
      </div>
    </template>
  </Drawer>
</template>
