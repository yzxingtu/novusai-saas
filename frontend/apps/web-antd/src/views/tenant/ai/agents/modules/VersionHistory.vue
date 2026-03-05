<script setup lang="ts">
/**
 * 智能体版本历史抽屉
 *
 * 功能：版本列表、回滚、版本对比
 */
import type {
  AgentVersionDiff,
  AgentVersionListItem,
} from '#/api/tenant/agents';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Descriptions,
  DescriptionsItem,
  Empty,
  message,
  Modal,
  Select,
  SelectOption,
  Spin,
  Tag,
  Timeline,
  TimelineItem,
} from 'ant-design-vue';

import {
  diffAgentVersionsApi,
  getAgentVersionsApi,
  rollbackAgentApi,
} from '#/api/tenant/agents';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

defineOptions({ name: 'AgentVersionHistory' });

const emits = defineEmits<{ success: [] }>();

const loading = ref(false);
const versions = ref<AgentVersionListItem[]>([]);
const agentId = ref<number>(0);
const publishedVersion = ref<null | number>(null);

// 版本对比状态
const diffLoading = ref(false);
const diffResult = ref<AgentVersionDiff | null>(null);
const diffV1 = ref<number | undefined>(undefined);
const diffV2 = ref<number | undefined>(undefined);

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
      // 关闭时重置
      versions.value = [];
      diffResult.value = null;
      diffV1.value = undefined;
      diffV2.value = undefined;
    }
  },
});

const title = computed(() => $t('tenant.ai.agent.version.title'));

async function loadVersions() {
  loading.value = true;
  try {
    versions.value = await getAgentVersionsApi(agentId.value);
  } catch {
    // error handled by global interceptor
  } finally {
    loading.value = false;
  }
}

async function onRollback(version: number) {
  Modal.confirm({
    title: $t('tenant.ai.agent.version.rollback'),
    content: $t('tenant.ai.agent.messages.rollbackConfirm', { version }),
    okType: 'danger',
    onOk: async () => {
      try {
        await rollbackAgentApi(agentId.value, { version });
        message.success(
          $t('tenant.ai.agent.messages.rollbackSuccess', { version }),
        );
        emits('success');
        drawerApi.close();
      } catch {
        // error handled by global interceptor
      }
    },
  });
}

async function onDiff() {
  if (!diffV1.value || !diffV2.value) return;
  diffLoading.value = true;
  try {
    diffResult.value = await diffAgentVersionsApi(
      agentId.value,
      diffV1.value,
      diffV2.value,
    );
  } catch {
    // error handled by global interceptor
  } finally {
    diffLoading.value = false;
  }
}

function formatFieldValue(val: unknown): string {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'object') return JSON.stringify(val, null, 2);
  return String(val);
}

/** 版本下拉选项 */
const versionOptions = computed(() =>
  versions.value.map((v) => ({
    label: `v${v.version}`,
    value: v.version,
  })),
);

const diffChanges = computed(() => {
  if (!diffResult.value?.changes) return [];
  return Object.entries(diffResult.value.changes).map(([field, vals]) => ({
    field,
    v1: vals.v1,
    v2: vals.v2,
  }));
});
</script>

<template>
  <Drawer :title="title" class="w-[640px]">
    <Spin :spinning="loading">
      <!-- 版本对比区 -->
      <div
        v-if="versions.length >= 2"
        class="mb-4 rounded-lg border border-border bg-accent/30 p-4"
      >
        <div class="mb-2 text-sm font-medium">
          <IconifyIcon
            icon="lucide:git-compare"
            class="mr-1 inline-block size-4"
          />
          {{ $t('tenant.ai.agent.version.diff') }}
        </div>
        <div class="flex items-center gap-2">
          <Select
            v-model:value="diffV1"
            :placeholder="$t('tenant.ai.agent.version.selectVersion')"
            class="w-32"
            size="small"
          >
            <SelectOption
              v-for="opt in versionOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </SelectOption>
          </Select>
          <span class="text-muted-foreground">↔</span>
          <Select
            v-model:value="diffV2"
            :placeholder="$t('tenant.ai.agent.version.selectVersion')"
            class="w-32"
            size="small"
          >
            <SelectOption
              v-for="opt in versionOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </SelectOption>
          </Select>
          <Button
            type="primary"
            size="small"
            :disabled="!diffV1 || !diffV2 || diffV1 === diffV2"
            :loading="diffLoading"
            @click="onDiff"
          >
            {{ $t('tenant.ai.agent.version.diff') }}
          </Button>
        </div>

        <!-- 对比结果 -->
        <div v-if="diffResult" class="mt-3">
          <div
            v-if="diffChanges.length === 0"
            class="text-sm text-muted-foreground"
          >
            {{ $t('tenant.ai.agent.version.noDiff') }}
          </div>
          <Descriptions
            v-else
            :title="
              $t('tenant.ai.agent.version.diffTitle', {
                v1: diffResult.v1,
                v2: diffResult.v2,
              })
            "
            :column="1"
            bordered
            size="small"
          >
            <DescriptionsItem
              v-for="item in diffChanges"
              :key="item.field"
              :label="item.field"
            >
              <div class="flex flex-col gap-1">
                <div>
                  <Tag color="red" class="mr-1"> v{{ diffResult.v1 }} </Tag>
                  <code class="break-all text-xs">
                    {{ formatFieldValue(item.v1) }}
                  </code>
                </div>
                <div>
                  <Tag color="green" class="mr-1"> v{{ diffResult.v2 }} </Tag>
                  <code class="break-all text-xs">
                    {{ formatFieldValue(item.v2) }}
                  </code>
                </div>
              </div>
            </DescriptionsItem>
          </Descriptions>
        </div>
      </div>

      <!-- 版本时间线 -->
      <Empty
        v-if="!loading && versions.length === 0"
        :description="$t('tenant.ai.agent.version.noVersions')"
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
                <span class="font-medium"> v{{ ver.version }} </span>
                <Tag
                  v-if="ver.version === publishedVersion"
                  color="success"
                  class="text-xs"
                >
                  {{ $t('tenant.ai.agent.version.current') }}
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
              {{ $t('tenant.ai.agent.version.rollback') }}
            </Button>
          </div>
        </TimelineItem>
      </Timeline>
    </Spin>
  </Drawer>
</template>
