<script lang="ts" setup>
/**
 * 租户端 API Key 管理页面
 */
import type { TenantAIApiKeyInfo } from '#/api/tenant/ai';

import { onMounted, ref } from 'vue';

import { IconifyIcon, Plus } from '@vben/icons';

import {
  Button,
  Card,
  Empty,
  message,
  Modal,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  createTenantAIKeyApi,
  deleteTenantAIKeyApi,
  getTenantAIKeysApi,
} from '#/api/tenant/ai';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import ApiKeyForm from './modules/ApiKeyForm.vue';

defineOptions({ name: 'TenantAIApiKeyList' });

const loading = ref(false);
const keys = ref<TenantAIApiKeyInfo[]>([]);
const showCreateForm = ref(false);

async function loadKeys() {
  loading.value = true;
  try {
    keys.value = await getTenantAIKeysApi();
  } catch {
    // Error handled by request interceptor
  } finally {
    loading.value = false;
  }
}

async function handleCreate(values: Record<string, unknown>) {
  try {
    await createTenantAIKeyApi({
      provider_id: values.provider_id as number,
      name: values.name as string,
      api_key: values.api_key as string,
    });
    message.success($t('tenant.ai.apiKey.messages.createSuccess'));
    showCreateForm.value = false;
    await loadKeys();
  } catch {
    // Error handled by request interceptor
  }
}

async function handleDelete(key: TenantAIApiKeyInfo) {
  Modal.confirm({
    title: $t('tenant.ai.apiKey.confirmDelete'),
    onOk: async () => {
      try {
        await deleteTenantAIKeyApi(key.id);
        message.success($t('tenant.ai.apiKey.messages.deleteSuccess'));
        await loadKeys();
      } catch {
        // Error handled by request interceptor
      }
    },
  });
}

onMounted(loadKeys);
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- 创建表单弹窗 -->
    <ApiKeyForm v-model:open="showCreateForm" @submit="handleCreate" />

    <!-- 顶部操作栏 -->
    <Card :body-style="{ padding: '12px 16px' }">
      <div class="flex items-center justify-between">
        <span class="text-sm text-muted-foreground">
          {{ keys.length }} {{ $t('tenant.ai.apiKey.title') }}
        </span>
        <Button
          v-access:code="['ai_config:create_key']"
          type="primary"
          @click="showCreateForm = true"
        >
          <template #icon><Plus class="size-4" /></template>
          {{ $t('tenant.ai.apiKey.create') }}
        </Button>
      </div>
    </Card>

    <!-- Key 列表 -->
    <Spin :spinning="loading">
      <div v-if="keys.length > 0" class="flex flex-col gap-3">
        <Card
          v-for="key in keys"
          :key="key.id"
          class="transition-shadow duration-200 hover:shadow-md"
          :body-style="{ padding: '16px' }"
        >
          <div class="flex items-center justify-between">
            <!-- 左侧：Key 信息 -->
            <div class="flex items-center gap-3">
              <div
                class="flex size-10 items-center justify-center rounded-lg"
                :class="key.is_available ? 'bg-success/10' : 'bg-muted'"
              >
                <IconifyIcon
                  icon="lucide:key"
                  class="size-5"
                  :class="
                    key.is_available ? 'text-success' : 'text-muted-foreground'
                  "
                />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-medium text-foreground">{{
                    key.name
                  }}</span>
                  <Tag color="blue">{{ key.provider_name }}</Tag>
                </div>
                <div
                  class="mt-0.5 flex items-center gap-3 text-xs text-muted-foreground"
                >
                  <code
                    v-if="key.key_preview"
                    class="rounded bg-accent px-1 py-0.5"
                  >
                    {{ key.key_preview }}
                  </code>
                  <span
                    >{{ $t('tenant.ai.apiKey.usageCount') }}:
                    {{ key.usage_count }}</span
                  >
                  <Tooltip
                    v-if="key.last_used_at"
                    :title="formatDate(key.last_used_at)"
                  >
                    <span
                      >{{ $t('tenant.ai.apiKey.lastUsedAt') }}:
                      {{ formatRelativeTime(key.last_used_at) }}</span
                    >
                  </Tooltip>
                </div>
              </div>
            </div>

            <!-- 右侧：状态 + 操作 -->
            <div class="flex items-center gap-3">
              <Tag :color="key.is_available ? 'success' : 'error'">
                {{
                  key.is_available
                    ? $t('tenant.ai.apiKey.isAvailable')
                    : $t('tenant.ai.apiKey.unavailable')
                }}
              </Tag>
              <Button
                v-access:code="['ai_config:delete_key']"
                type="text"
                danger
                size="small"
                @click="handleDelete(key)"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:trash-2" class="size-4" />
                </template>
              </Button>
            </div>
          </div>
        </Card>
      </div>
      <Empty v-else :description="$t('common.noData')" class="py-16" />
    </Spin>
  </div>
</template>
