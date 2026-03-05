<script setup lang="ts">
/**
 * 智能体版本历史抽屉（管理端）
 *
 * 功能：版本列表、回滚
 */
import type { AIAgentVersionItem } from '#/api/admin/ai';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  message,
  Modal,
  Spin,
  Tag,
  Timeline,
  TimelineItem,
} from 'ant-design-vue';

import { getAIAgentVersionsApi, rollbackAIAgentApi } from '#/api/admin/ai';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

defineOptions({ name: 'AdminAgentVersionHistory' });

const emits = defineEmits<{ success: [] }>();

const loading = ref(false);
const versions = ref<AIAgentVersionItem[]>([]);
const agentId = ref<number>(0);
const publishedVersion = ref<null | number>(null);

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange: async (isOpen) => {
    if (isOpen) {
      const data = drawerApi.getData<{
        id: number;
        publishedVersion: null | number;
      }>();
      if (data?.id) {
        agentId.value = data.id;
        publishedVersion.value = data.publishedVersion ?? null;
        await loadVersions();
      }
    } else {
      versions.value = [];
    }
  },
});

const title = computed(() => $t('admin.ai.agent.versionHistory'));

async function loadVersions() {
  loading.value = true;
  try {
    versions.value = await getAIAgentVersionsApi(agentId.value);
  } catch {
    // error handled by global interceptor
  } finally {
    loading.value = false;
  }
}

async function onRollback(version: number) {
  Modal.confirm({
    title: $t('admin.ai.agent.messages.rollbackConfirm'),
    okType: 'danger',
    onOk: async () => {
      try {
        await rollbackAIAgentApi(agentId.value, version);
        message.success($t('admin.ai.agent.messages.rollbackSuccess'));
        emits('success');
        drawerApi.close();
      } catch {
        // error handled by global interceptor
      }
    },
  });
}
</script>

<template>
  <Drawer :title="title" class="w-[520px]">
    <Spin :spinning="loading">
      <Empty
        v-if="!loading && versions.length === 0"
        :description="$t('admin.ai.agent.messages.noVersions')"
      />

      <Timeline v-else>
        <TimelineItem
          v-for="ver in versions"
          :key="ver.id"
          :color="ver.version === publishedVersion ? 'green' : 'blue'"
        >
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center gap-2">
                <span class="font-medium">v{{ ver.version }}</span>
                <Tag
                  v-if="ver.version === publishedVersion"
                  color="success"
                  class="text-xs"
                >
                  {{ $t('admin.ai.agent.status_options.published') }}
                </Tag>
              </div>
              <div
                v-if="ver.change_log"
                class="mt-1 text-sm text-muted-foreground"
              >
                {{ ver.change_log }}
              </div>
              <div class="mt-1 text-xs text-muted-foreground">
                {{ formatDate(ver.created_at) }}
              </div>
            </div>
            <Button
              v-if="ver.version !== publishedVersion"
              size="small"
              danger
              @click="onRollback(ver.version)"
            >
              <template #icon>
                <IconifyIcon icon="lucide:undo-2" />
              </template>
              {{ $t('admin.ai.agent.messages.rollback') }}
            </Button>
          </div>
        </TimelineItem>
      </Timeline>
    </Spin>
  </Drawer>
</template>
